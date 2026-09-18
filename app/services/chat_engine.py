"""对话引擎服务 - SDD核心"""
import asyncio
import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.orm.attributes import flag_modified

from app.db.database import SessionLocal
from app.db.models import ConversationRecord, JobRecord, ResumeRecord
from app.db.repositories import ResumeRepository
from app.models.conversation import (
    Message, CardType, ScoreCardData, ChatResponse
)
from app.llm.client import get_llm_client
from app.llm.prompts import PromptTemplates
from app.observability.context import fill as _obs_fill
from app.observability.quality import observe_reply as _observe_reply
from app.observability import memory_guard as _memory_guard
from app.services.job_parser import JobParserService
from app.services.job_scorer import JobScorerService
from app.services.resume_optimizer import ResumeOptimizerService
from app.services.interview_simulator import InterviewSimulatorService

# 工具意图（流式通道）状态前置话术：结构化报告无 token 级流，
# 先回一条状态消除 20-40s 静默，全文再分块渐进 cascading 输出
INTENT_PROGRESS_HINT = {
    "optimize_resume": "已收到重写简历请求：正在解析岗位JD、生成优化diff，预计需要20-40秒…",
    "evaluate_job": "已收到评估岗位请求：正在解析JD、评分匹配度，预计需要20-40秒…",
    "parse_resume": "已收到解析简历请求，预计需要10-30秒…",
    "generate_questions": "正在根据岗位生成针对性面试题，预计需要20-40秒…",
    "mock_interview": "正在准备模拟面试，预计需要20-40秒…",
}
_DEFAULT_PROGRESS_HINT = "已收到请求，正在处理，预计需要20-40秒…"

# 低置信度澄清（分层漏斗的置信度兜底）：高成本工具意图置信度不足时
# 反问确认而非硬执行，消除"答非所问还跑20-40秒工具链"的最差体感
CLARIFY_THRESHOLD = 0.7
HIGH_COST_INTENTS = {"evaluate_job", "optimize_resume", "parse_resume",
                     "generate_questions", "mock_interview"}
CLARIFY_QUESTION = {
    "evaluate_job": "您是想评估某个岗位吗？是的话请把JD文本粘贴给我；",
    "optimize_resume": "您是想优化/重写自己的简历吗？",
    "parse_resume": "您是想解析简历、查看结构化内容吗？",
    "generate_questions": "您是想生成面试题吗？",
    "mock_interview": "您是想开始模拟面试吗？",
}


def _progressive_chunks(text: str, size: int = 48):
    """全文按行切小块（结构化报告的渐进输出，形成 cascading 阅读体验）"""
    for line in (text or "").splitlines(keepends=True):
        while len(line) > size:
            yield line[:size]
            line = line[size:]
        if line:
            yield line


class ChatEngineService:
    """对话引擎服务"""

    # 中期记忆：general_chat prompt 注入的历史轮数上限（防 token 膨胀）
    HISTORY_INJECT_LIMIT = 10

    # 意图白名单：LLM 语义路由返回越界意图一律拒收降级规则
    ALLOWED_INTENTS = {
        "evaluate_job", "optimize_resume", "parse_resume", "generate_questions",
        "mock_interview", "view_recommendations", "view_progress", "give_advice",
        "general_chat",
    }
    
    def __init__(self):
        self.llm_client = get_llm_client()
        self.job_parser = JobParserService()
        self.job_scorer = JobScorerService()
        self.resume_optimizer = ResumeOptimizerService()
        self.interview_simulator = InterviewSimulatorService()
    
    def create_conversation(self, title: Optional[str] = None) -> int:
        """创建新对话"""
        db = SessionLocal()
        try:
            conv = ConversationRecord(
                title=title or "新对话",
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
            return conv.id
        finally:
            db.close()
    
    def get_conversation(self, conversation_id: int) -> Optional[Dict]:
        """获取对话详情"""
        db = SessionLocal()
        try:
            conv = db.query(ConversationRecord).filter_by(id=conversation_id).first()
            if not conv:
                return None
            return {
                "id": conv.id,
                "title": conv.title,
                "messages": conv.messages or [],
                "context_job_id": conv.context_job_id,
                "context_resume_id": conv.context_resume_id,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at
            }
        finally:
            db.close()
    
    def list_conversations(self, limit: int = 50) -> List[Dict]:
        """获取对话列表"""
        db = SessionLocal()
        try:
            convs = db.query(ConversationRecord).order_by(
                ConversationRecord.updated_at.desc()
            ).limit(limit).all()
            return [
                {
                    "id": c.id,
                    "title": c.title,
                    "message_count": len(c.messages or []),
                    "created_at": c.created_at,
                    "updated_at": c.updated_at
                }
                for c in convs
            ]
        finally:
            db.close()
    
    def delete_conversation(self, conversation_id: int) -> bool:
        """删除对话"""
        db = SessionLocal()
        try:
            conv = db.query(ConversationRecord).filter_by(id=conversation_id).first()
            if conv:
                db.delete(conv)
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    async def chat(self, conversation_id: Optional[int], user_message: str,
                   image_paths: Optional[List[str]] = None,
                   file_paths: Optional[List[str]] = None) -> ChatResponse:
        """处理对话消息"""
        db = SessionLocal()
        try:
            # 获取或创建对话
            if conversation_id:
                conv = db.query(ConversationRecord).filter_by(id=conversation_id).first()
                if not conv:
                    _memory_guard.check_session_missing(conversation_id)
                    raise ValueError(f"对话不存在: {conversation_id}")
            else:
                # 创建新对话
                title = user_message[:20] + "..." if len(user_message) > 20 else user_message
                conv = ConversationRecord(
                    title=title,
                    messages=[],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(conv)
                db.commit()
                db.refresh(conv)
                conversation_id = conv.id
            
            # 添加用户消息
            messages = conv.messages or []
            user_msg = {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            }
            messages.append(user_msg)
            
            # 中期记忆读取埋点（历史轮数，不含本轮新消息）
            _memory_guard.check_session_read(len(messages) - 1)
            
            # 识别意图并处理（高成本工具意图低置信度时先澄清，不硬执行）
            intent_result = await self._recognize_intent(user_message, messages)
            self._observe_intent(intent_result)
            if self._needs_clarification(intent_result):
                _obs_fill(clarified=True)
                reply = self._clarification_message(intent_result)
            else:
                reply = await self._handle_intent(intent_result, conv, user_message,
                                                  image_paths, file_paths)
            
            # 添加助手回复（附件卡片随消息落盘，历史回合与后续附件回溯可见）
            att_cards = self._attachment_cards(image_paths, file_paths)
            assistant_msg = {
                "role": "assistant",
                "content": reply.content,
                "cards": att_cards + [c for c in reply.cards],
                "timestamp": datetime.now().isoformat()
            }
            messages.append(assistant_msg)
            
            # 更新对话
            conv.messages = messages
            conv.updated_at = datetime.now()
            # JSON 列原地 mutate + 同对象赋值不会被 ORM 标记 dirty（commit 只写 updated_at，
            # 历史永远冻结在旧快照）→ 显式 flag_modified 保证多轮消息逐轮落盘
            flag_modified(conv, "messages")
            try:
                db.commit()
                _memory_guard.check_session_write(len(messages))
            except Exception as e:
                # 中期记忆写失败：抛 critical flag 后再上抛
                _memory_guard.check_session_write(len(messages), error=str(e))
                _obs_fill(msg_persisted=False)
                raise

            # L4 会话完整性 + L5 质量哨兵（静默降级，不阻塞响应）
            _obs_fill(conversation_id=conversation_id, msg_persisted=True)
            _observe_reply(user_message, reply.content, list(reply.cards))

            return ChatResponse(
                conversation_id=conversation_id,
                reply=reply,
                context_job_id=conv.context_job_id,
                context_resume_id=conv.context_resume_id
            )
        finally:
            db.close()
    
    async def stream_chat(self, conversation_id: Optional[int], user_message: str,
                          image_paths: Optional[List[str]] = None,
                          file_paths: Optional[List[str]] = None):
        """流式处理对话（异步生成器），逐段产出事件 dict：

        - {"conversation_id": int}  会话ID（首个事件）
        - {"delta": str}            文本增量
        - {"cards": [...]}          卡片（文本之后）
        - {"done": True}            结束
        - {"error": str}            异常

        general_chat 意图走 LLM token 级流式；其他意图（结构化报告无 token 级流）
        先前置一条状态消除长静默，再将全文按行切小块渐进输出（卡片仍走 cards 事件）。
        状态前置话术仅展示不落盘，落盘内容仍为 reply.content。
        """
        db = SessionLocal()
        try:
            # 获取或创建对话（与 chat() 一致）
            if conversation_id:
                conv = db.query(ConversationRecord).filter_by(id=conversation_id).first()
                if not conv:
                    _memory_guard.check_session_missing(conversation_id)
                    raise ValueError(f"对话不存在: {conversation_id}")
            else:
                title = user_message[:20] + "..." if len(user_message) > 20 else user_message
                conv = ConversationRecord(
                    title=title,
                    messages=[],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(conv)
                db.commit()
                db.refresh(conv)
                conversation_id = conv.id

            yield {"conversation_id": conversation_id}

            messages = conv.messages or []
            messages.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })

            # 中期记忆读取埋点（历史轮数，不含本轮新消息）
            _memory_guard.check_session_read(len(messages) - 1)

            intent_result = await self._recognize_intent(user_message, messages)
            self._observe_intent(intent_result)
            intent = intent_result.get("intent", "general_chat")

            cards = self._attachment_cards(image_paths, file_paths)
            if intent in ("general_chat", "give_advice"):
                # 流式分支：prompt 构建与 _handle_general_chat 保持一致（含中期记忆注入）；
                # give_advice 同属接地问答，复用 token 级流式避免整段蹦出

                history = messages[:-1]
                prompt, injected = self._build_general_prompt(
                    user_message, history, image_paths, file_paths,
                    anchor_text=self._session_anchors(conv, len(history)))
                _memory_guard.check_session_inject(len(history), injected)
                full_text = ""
                try:
                    # 异步桥接流式：每个 delta 间有 await 点，事件循环可及时 flush SSE 帧
                    async for delta in self.llm_client.chat_stream_async([{"role": "user", "content": prompt}]):
                        full_text += delta
                        yield {"delta": delta}
                except Exception as e:
                    logger.error(f"LLM流式调用失败: {e}")
                    if not full_text:
                        full_text = "抱歉，我暂时无法回答。请稍后再试。"
                        yield {"delta": full_text}
                reply_content = full_text
            elif self._needs_clarification(intent_result):
                # 低置信度澄清：不硬执行高成本工具意图，先反问确认（照常落盘）
                _obs_fill(clarified=True)
                reply_content = self._clarification_message(intent_result).content
                for chunk in _progressive_chunks(reply_content):
                    yield {"delta": chunk}
                    await asyncio.sleep(0.02)
            else:
                # 非普通对话意图：复用既有处理链路；先前置状态消除长静默，
                # 全文分块渐进输出（附件卡片同样落盘，否则上传在历史中不可回溯）
                yield {"delta": INTENT_PROGRESS_HINT.get(intent, _DEFAULT_PROGRESS_HINT) + "\n\n"}
                # 心跳：处理任务挂 task，每 10s 静默补一条进度，避免长等待期无任何输出
                task = asyncio.create_task(self._handle_intent(
                    intent_result, conv, user_message, image_paths, file_paths))
                try:
                    waited = 0
                    while True:
                        done, _ = await asyncio.wait({task}, timeout=10)
                        if done:
                            break
                        waited += 10
                        yield {"delta": f"…处理中（已{waited}s）\n"}
                except asyncio.CancelledError:
                    task.cancel()
                    raise
                reply = task.result()
                reply_content = reply.content
                cards = cards + list(reply.cards)
                for chunk in _progressive_chunks(reply_content):
                    yield {"delta": chunk}
                    await asyncio.sleep(0.02)

            # 保存助手回复
            messages.append({
                "role": "assistant",
                "content": reply_content,
                "cards": cards,
                "timestamp": datetime.now().isoformat()
            })
            conv.messages = messages
            conv.updated_at = datetime.now()
            # 同 chat()：JSON 列原地 mutate 需显式标记 dirty，否则多轮历史不落盘
            flag_modified(conv, "messages")
            try:
                db.commit()
                _memory_guard.check_session_write(len(messages))
            except Exception as e:
                # 中期记忆写失败：抛 critical flag 后再上抛
                _memory_guard.check_session_write(len(messages), error=str(e))
                _obs_fill(msg_persisted=False)
                raise

            # L4 会话完整性 + L5 质量哨兵（在 yield done 前，早于 event_gen.finally 落盘）
            _obs_fill(conversation_id=conversation_id, msg_persisted=True)
            _observe_reply(user_message, reply_content, cards)

            if cards:
                yield {"cards": cards}
            yield {"done": True}
        except Exception as e:
            logger.error(f"流式对话处理失败: {e}")
            yield {"error": str(e)}
        finally:
            db.close()
    
    def _build_general_prompt(self, user_message: str, history: List[Dict],
                              image_paths: Optional[List[str]] = None,
                              file_paths: Optional[List[str]] = None,
                              anchor_text: str = ""):
        """general_chat prompt：接地 SYSTEM + 会话锚点 + 最近 N 轮历史 + 本轮消息（中期记忆注入）。

        返回 (prompt, injected_count)；injected_count 供 context_not_injected 判定。
        anchor_text 为 _session_anchors 产出的长程锚点（首轮交换/关联岗位），补超窗口回忆。
        """
        parts = []
        for m in (history or [])[-self.HISTORY_INJECT_LIMIT:]:
            role = m.get("role", "")
            if role not in ("user", "assistant"):
                continue
            parts.append(f"{role}: {str(m.get('content', ''))[:500]}")  # 单轮截断防膨胀
        injected = len(parts)
        content_parts = [user_message]
        if image_paths:
            content_parts.append(f"\n\n[用户上传了{len(image_paths)}张图片]")
        if file_paths:
            content_parts.append(f"\n\n[用户上传了{len(file_paths)}个文件]")
        parts.append("用户: " + "\n".join(content_parts))
        blocks = [self._grounded_system_prompt()]
        if anchor_text:
            blocks.append(anchor_text)
        blocks.append("\n".join(parts))
        prompt = "\n\n".join(blocks)
        return prompt, injected

    def _session_anchors(self, conv, history_count: int) -> str:
        """长程记忆锚点（评测集 H-002）：会话首轮交换 + 关联岗位，补 10 轮窗口外的回忆。

        - 首轮锚点仅在历史超出注入窗口时加（窗口内已覆盖，避免重复）
        - 关联岗位取 conv.context_job_id（中期记忆结构化状态，不占窗口）
        - 静默降级：任一查询失败仅退化已生成部分，不影响主链路
        """
        lines = []
        try:
            msgs = conv.messages or []
            if history_count > self.HISTORY_INJECT_LIMIT and len(msgs) >= 2:
                first_u = next((m for m in msgs if m.get("role") == "user"), None)
                first_a = next((m for m in msgs if m.get("role") == "assistant"), None)
                seg = []
                if first_u:
                    seg.append(f"user: {str(first_u.get('content', ''))[:200]}")
                if first_a:
                    seg.append(f"assistant: {str(first_a.get('content', ''))[:200]}")
                if seg:
                    lines.append("会话起点(首轮交换): " + " | ".join(seg))
        except Exception as e:
            logger.warning(f"会话起点锚点构建失败(降级): {e}")
        try:
            job_id = getattr(conv, "context_job_id", None)
            if job_id:
                db = SessionLocal()
                try:
                    job = db.query(JobRecord).filter_by(id=job_id).first()
                    if job:
                        lines.append(
                            f"当前会话关联岗位: {job.title} @ {job.company or '未知公司'}"
                            + (f"（{job.location}）" if job.location else ""))
                finally:
                    db.close()
        except Exception as e:
            logger.warning(f"关联岗位锚点构建失败(降级): {e}")
        return "\n".join(f"[会话锚点] {l}" for l in lines)

    @staticmethod
    def _observe_intent(intent_result: Dict) -> None:
        """L4 意图观测（SDD §4.5）：回填 intent/confidence/路由来源，置信度 < 0.6 标 ambiguous。静默降级。"""
        try:
            conf = intent_result.get("confidence")
            _obs_fill(intent=intent_result.get("intent"), intent_confidence=conf,
                      ambiguous=(conf is not None and conf < 0.6),
                      intent_router=intent_result.get("router", "rules"))
        except Exception:
            pass

    def _grounded_system_prompt(self) -> str:
        """系统Prompt + 动态接地信息（当前时间/库内简历摘要），防时间幻觉与简历编造"""
        return PromptTemplates.build_system_prompt(resume_summary=self._resume_summary())

    @staticmethod
    def _resume_summary() -> str:
        """库内基础简历摘要（接地用）；无简历返回空串。静默降级。"""
        try:
            db = SessionLocal()
            try:
                base = ResumeRepository(db).get_base()
                if not base:
                    return ""
                data = base.data_json or {}
                head = [f"姓名: {data.get('name') or base.name or '未知'}"]
                if data.get("location"):
                    head.append(f"城市: {data['location']}")
                if data.get("years_of_experience"):
                    head.append(f"工作年限: {data['years_of_experience']}年")
                lines = [" | ".join(head)]
                for edu in data.get("educations") or []:
                    lines.append(f"教育: {edu.get('school', '')} {edu.get('degree', '')} {edu.get('major', '')}")
                for work in data.get("work_experiences") or []:
                    lines.append(f"工作: {work.get('company', '')} · {work.get('position', '')}"
                                 f"（{work.get('start_date', '')}~{work.get('end_date', '')}）")
                skills = [s.get("name") for s in (data.get("skills") or []) if s.get("name")]
                if skills:
                    lines.append("技能: " + ", ".join(skills[:20]))
                raw = (base.raw_text or "").strip()
                if raw:
                    lines.append(f"原文摘录: {raw[:800]}")
                return "\n".join(lines)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"简历摘要构建失败(降级为无接地): {e}")
            return ""

    async def _recognize_intent(self, message: str, context: List[Dict]) -> Dict:
        """识别用户意图：规则快路径（显式动词，零延迟/离线可复现）
        → LLM 语义路由（理解规则未覆盖的同义改写与新动词）→ LLM 异常静默降级规则"""
        rules_result = self._recognize_intent_rules(message)
        if rules_result.get("decisive"):
            return rules_result
        llm_result = await self._classify_intent_with_llm(message, context)
        if llm_result:
            # 长文本JD上下文由规则确定性检测，LLM 未回传时补齐，避免 evaluate 链丢 jd_text
            if not llm_result.get("jd_text") and rules_result.get("jd_text"):
                llm_result["jd_text"] = rules_result["jd_text"]
            return llm_result
        return rules_result

    async def _classify_intent_with_llm(self, message: str, context: List[Dict]) -> Optional[Dict]:
        """LLM 语义路由：语义读懂消息选意图，覆盖规则外的同义改写/新动词。

        静默降级：无客户端/调用失败/非法意图均返回 None，由调用方回退规则结果。
        """
        client = getattr(self, "llm_client", None)
        if client is None:
            return None
        history = [m for m in (context or [])[:-1]
                   if m.get("role") in ("user", "assistant")][-3:]
        ctx_text = "\n".join(
            f"{m.get('role')}: {str(m.get('content', ''))[:200]}" for m in history) or "无"
        prompt = PromptTemplates.format_template(
            "INTENT_RECOGNITION", user_message=message[:1500], context=ctx_text)
        try:
            data = await asyncio.to_thread(
                lambda: client.chat_json_sync(
                    [{"role": "user", "content": prompt}],
                    temperature=0.0, max_tokens=200, timeout=8)
            )
        except Exception as e:
            logger.warning(f"LLM意图路由失败，降级规则: {e}")
            return None
        intent = str((data or {}).get("intent", "")).strip()
        if intent not in self.ALLOWED_INTENTS:
            logger.warning(f"LLM意图路由返回越界意图 {intent!r}，降级规则")
            return None
        try:
            confidence = min(max(float(data.get("confidence", 0.7)), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.7
        result = {"intent": intent, "confidence": confidence, "router": "llm"}
        jd_text = str(((data.get("extracted_data") or {}).get("jd_text") or "")).strip()
        if jd_text:
            result["jd_text"] = jd_text
        return result

    @staticmethod
    def _recognize_intent_rules(message: str) -> Dict:
        """规则快路径与降级兜底：仅显式意图动词算确定性命中（decisive），
        长文本JD兜底与闲聊不决定性，优先交 LLM 语义路由裁决"""
        message_lower = message.lower()
        
        # 长文本JD检测：仅作上下文附着（jd_text），不再单独定意图，
        # 避免"粘贴JD并要求重写简历"这类显式请求被误判为评估岗位
        jd_text = message if (
            len(message) > 200 and any(kw in message for kw in ["岗位", "职责", "要求", "技能"])
        ) else ""
        
        # === 优化/重写简历 ===（强意图动词优先：含重写系动词，
        # 避免"重写我的简历"无规则命中或被长文本JD启发式劫持为 evaluate_job）
        if any(kw in message_lower for kw in ["优化简历", "优化我的简历", "改改简历", "改简历", 
                                                "帮我改", "改改", "优化一下",
                                                "重写简历", "改写简历", "重写我的简历"]) or (
                "简历" in message and any(kw in message for kw in ["重写", "改写"])):
            result = {"intent": "optimize_resume", "confidence": 0.9,
                      "decisive": True, "router": "rules"}
            if jd_text:
                result["jd_text"] = jd_text
            return result
        
        # === 解析简历 ===（接地解析：必须显式解析动词或"简历+解析"组合；
        # "我的简历"这类所有格短语不得作解析动词，否则咨询类问句（篇幅/怎么样/有问题么）被劫持为解析）
        if any(kw in message_lower for kw in ["解析简历", "简历解析", "分析简历", "识别简历",
                                                "读简历"]) or (
                "简历" in message and "解析" in message):
            return {"intent": "parse_resume", "confidence": 0.85,
                    "decisive": True, "router": "rules"}
        
        # === 简历咨询/建议 ===（咨询类问句：就自己简历征求意见/建议，
        # 如"我的简历篇幅需要修改么/我的简历怎么样/简历有什么问题"；
        # 含岗位/匹配/评估字眼时不在此抢，交 evaluate 链路）
        if "简历" in message and not any(
                kw in message for kw in ["匹配", "评估", "岗位", "JD", "jd"]) and any(
                q in message for q in ["么", "吗", "？", "?", "怎么样", "如何",
                                        "要不要", "建议", "问题"]):
            return {"intent": "give_advice", "confidence": 0.8,
                    "decisive": True, "router": "rules"}
        
        # === 长文本JD兜底 ===（无显式意图动词的纯JD粘贴）：不决定性，LLM 语义路由优先
        if jd_text:
            return {"intent": "evaluate_job", "confidence": 0.9, "jd_text": jd_text,
                    "decisive": False, "router": "rules"}
        
        # === 评估岗位 ===（显式评估动词才决定性；"看看/怎么样"等泛义弱词
        # 必须组合领域锚点（岗位/职位/JD/公司/offer）才 decisive，
        # 否则"问你个问题看看你是不是会出现幻觉"这类闲聊被劫持为评估岗位）
        if any(kw in message_lower for kw in ["评估", "匹配", "打分", "帮我评",
                                                "匹配度", "靠谱吗", "合适吗"]):
            return {"intent": "evaluate_job", "confidence": 0.7,
                    "decisive": True, "router": "rules"}
        if any(kw in message_lower for kw in ["岗位", "职位", "jd", "公司", "offer"]) and any(
                w in message_lower for w in ["看看", "怎么样", "行不行", "好不好", "如何"]):
            return {"intent": "evaluate_job", "confidence": 0.7,
                    "decisive": True, "router": "rules"}
        
        # === 生成面试题 ===
        if any(kw in message_lower for kw in ["面试题", "生成题", "出几道题", "出题", 
                                                "生成面试题", "面试题目"]):
            return {"intent": "generate_questions", "confidence": 0.9,
                    "decisive": True, "router": "rules"}
        
        # === 模拟面试 ===
        if any(kw in message_lower for kw in ["模拟面试", "面试练习", "模拟面试", "开始模拟", 
                                                "开始模拟面试", "练一下面试", "练习面试"]):
            return {"intent": "mock_interview", "confidence": 0.9,
                    "decisive": True, "router": "rules"}
        
        # === 查看推荐 ===
        if any(kw in message_lower for kw in ["推荐", "今天投什么", "哪些岗位", "有什么岗位"]):
            return {"intent": "view_recommendations", "confidence": 0.8,
                    "decisive": True, "router": "rules"}
        
        # === 查看进度 ===
        if any(kw in message_lower for kw in ["投了多少", "进度", "统计", "今天投", "今天投啥", 
                                                "投了啥", "投递进度"]):
            return {"intent": "view_progress", "confidence": 0.8,
                    "decisive": True, "router": "rules"}
        
        # === 投递建议 ===
        if any(kw in message_lower for kw in ["值不值得", "要不要投", "投递建议"]):
            return {"intent": "give_advice", "confidence": 0.8,
                    "decisive": True, "router": "rules"}
        
        return {"intent": "general_chat", "confidence": 0.5,
                "decisive": False, "router": "rules"}
    
    @staticmethod
    def _needs_clarification(intent_result: Dict) -> bool:
        """低置信度澄清闸门：高成本工具意图 + 非显式规则命中 + 置信度 < CLARIFY_THRESHOLD。

        显式动词（decisive）与长文本JD兜底（0.9）不触发；general_chat/give_advice
        本身是低成本兜底路径也不触发（直接回答比反问体验更好）。"""
        if intent_result.get("decisive"):
            return False
        intent = intent_result.get("intent", "general_chat")
        if intent not in HIGH_COST_INTENTS:
            return False
        try:
            conf = float(intent_result.get("confidence", 1.0))
        except (TypeError, ValueError):
            conf = 1.0
        return conf < CLARIFY_THRESHOLD

    @staticmethod
    def _clarification_message(intent_result: Dict) -> Message:
        """澄清反问：说明推断意图与置信度，给出确认/否认分支，不执行任何工具"""
        intent = intent_result.get("intent", "general_chat")
        conf = intent_result.get("confidence")
        guess = CLARIFY_QUESTION.get(intent, "您能再具体说下想做什么吗？")
        conf_text = f"{conf:.0%}" if isinstance(conf, (int, float)) else "偏低"
        content = (f"我不太确定您的意图（置信度{conf_text}），为避免跑偏先和您确认：\n\n"
                   f"{guess}\n\n"
                   f"如果是，请确认或补充细节；如果不是，直接告诉我您的需求即可，"
                   f"比如\"评估这个JD\"\"重写我的简历\"，或直接向我提问。")
        logger.info(f"低置信度澄清触发: intent={intent} conf={conf} router={intent_result.get('router')}")
        return Message(role="assistant", content=content, cards=[])

    async def _handle_intent(self, intent_result: Dict, conv: ConversationRecord,
                              user_message: str = "",
                              image_paths: Optional[List[str]] = None,
                              file_paths: Optional[List[str]] = None) -> Message:
        """处理意图并返回回复"""
        intent = intent_result.get("intent", "general_chat")
        db = SessionLocal()
        
        try:
            if intent == "evaluate_job":
                return await self._handle_evaluate_job(intent_result, conv, db)
            
            elif intent == "parse_resume":
                return await self._handle_parse_resume(conv, user_message, file_paths, db)
            
            elif intent == "optimize_resume":
                return await self._handle_optimize_resume(intent_result, conv, db)
            
            elif intent == "generate_questions":
                return await self._handle_generate_questions(intent_result, conv, db)
            
            elif intent == "view_recommendations":
                return await self._handle_view_recommendations(conv, db)
            
            elif intent == "view_progress":
                return await self._handle_view_progress(conv, db)
            
            else:
                return await self._handle_general_chat(intent_result, conv, user_message,
                                                        image_paths, file_paths)
        
        finally:
            db.close()
    
    async def _handle_parse_resume(self, conv: ConversationRecord, user_message: str,
                                   file_paths: Optional[List[str]], db) -> Message:
        """处理解析简历意图：只基于接地来源（粘贴文本/附件文件/库内基础简历）解析

        幻觉防线：无任何来源原文时不调LLM，直接引导用户提供，杜绝凭空编造。
        """
        from app.services.resume_parser import ResumeParserService

        resume_text, source = "", ""
        # 1) 消息中直接粘贴的简历文本（长文本视为粘贴简历）
        if len(user_message) > 100:
            resume_text, source = user_message, "你在对话中粘贴的简历文本"
        # 2) 本条消息携带的附件；无则回溯会话历史中最近一轮的简历附件
        #    （file_paths 为上传接口返回的 URL，需映射为磁盘路径再提取）
        candidates = list(file_paths or [])
        if not candidates:
            candidates = self._history_resume_attachments(conv)
        if not resume_text and candidates:
            parser = ResumeParserService()
            texts = []
            for fp in candidates:
                disk = self._resolve_upload_path(fp)
                ext = os.path.splitext(disk)[1].lower()
                if ext == ".pdf":
                    texts.append(parser._extract_pdf(disk))
                elif ext == ".docx":
                    texts.append(parser._extract_docx(disk))
                else:
                    try:
                        with open(disk, "r", encoding="utf-8") as f:
                            texts.append(f.read())
                    except Exception as e:
                        logger.warning(f"读取附件失败 {disk}: {e}")
            merged = "\n".join(t for t in texts if t)
            if merged:
                resume_text, source = merged, "你在对话中上传的文件"
        # 3) 库内已存档的基础简历（与 UI 一致取最新一条）；
        #    已有结构化解析结果直接复用，不再对 raw_text 残桩重解析
        if not resume_text:
            base = ResumeRepository(db).get_base()
            if base:
                archived = self._resume_data_from_record(base)
                if archived is not None:
                    return Message(
                        role="assistant",
                        content=self._format_resume(
                            archived,
                            f"简历中心已存档的简历（姓名: {base.name or '未知'}）"),
                        cards=[]
                    )
                if base.raw_text:
                    resume_text = base.raw_text
                    source = f"简历中心已存档的简历（姓名: {base.name or '未知'}）"
        if not resume_text:
            return Message(
                role="assistant",
                content="我还没有你的简历文本，不会在没有原文的情况下编造简历内容。\n"
                        "请任选一种方式提供：\n"
                        "1. 在简历中心上传简历（PDF/DOCX/TXT）；\n"
                        "2. 在本对话中直接附上简历文件；\n"
                        "3. 直接粘贴简历文本发送。\n"
                        "我会严格基于你提供的原文解析。",
                cards=[]
            )

        parser = ResumeParserService()
        data = await asyncio.to_thread(parser.parse, resume_text)
        return Message(role="assistant", content=self._format_resume(data, source), cards=[])

    @staticmethod
    def _format_resume(data, source: str) -> str:
        """ResumeData → 可读Markdown，显式标注来源便于用户核对"""
        lines = [f"已基于{source}解析，结果如下（如与原文有出入请指出）：", "",
                 f"**{data.name or '姓名未知'}** | {data.location or '城市未知'} | {data.years_of_experience or 0}年经验"]
        if data.educations:
            lines.append("\n**教育经历**")
            lines += [f"- {e.school} {e.degree} {e.major}（{e.start_date}~{e.end_date}）"
                      for e in data.educations]
        if data.work_experiences:
            lines.append("\n**工作经历**")
            for w in data.work_experiences:
                lines.append(f"- {w.company} · {w.position}（{w.start_date}~{w.end_date}）")
                if w.description:
                    lines.append(f"  {w.description}")
        if data.projects:
            lines.append("\n**项目经历**")
            lines += [f"- {p.name}（{p.role}）" for p in data.projects]
        if data.skills:
            lines.append("\n**技能**")
            lines.append("、".join(s.name for s in data.skills if s.name))
        if not any([data.educations, data.work_experiences, data.projects, data.skills]):
            lines.append("\n（未从原文中解析出结构化字段，请检查简历文本是否完整。）")
        return "\n".join(lines)

    @staticmethod
    def _attachment_cards(image_paths: Optional[List[str]],
                          file_paths: Optional[List[str]]) -> List[Dict]:
        """本条消息的附件卡片（展示 + 落盘，供历史回合附件回溯）"""
        cards = []
        if image_paths:
            cards += [{"type": "image_card", "data": {"url": p, "index": i}}
                      for i, p in enumerate(image_paths)]
        if file_paths:
            cards += [{"type": "file_card", "data": {"url": p, "index": i}}
                      for i, p in enumerate(file_paths)]
        return cards

    @staticmethod
    def _resolve_upload_path(path: str) -> str:
        """附件 URL（/api/upload/files|images/xxx）映射为磁盘路径；非 URL 原样返回"""
        from app.api.upload import FILE_DIR, IMAGE_DIR
        for prefix, dir_ in (("/api/upload/files/", FILE_DIR),
                             ("/api/upload/images/", IMAGE_DIR)):
            if path.startswith(prefix):
                return str(dir_ / path[len(prefix):])
        return path

    @staticmethod
    def _history_resume_attachments(conv: ConversationRecord) -> List[str]:
        """回溯会话历史中最近一轮的简历类附件（file_card），
        使「先上传附件、后续回合再要求解析」仍能接地到该文件"""
        exts = (".pdf", ".docx", ".doc", ".txt", ".md")
        for m in reversed(conv.messages or []):
            urls = [
                (c.get("data") or {}).get("url")
                for c in (m.get("cards") or [])
                if isinstance(c, dict) and c.get("type") == "file_card"
            ]
            urls = [u for u in urls if isinstance(u, str) and u.lower().endswith(exts)]
            if urls:
                return urls
        return []

    @staticmethod
    def _resume_data_from_record(record: ResumeRecord):
        """存档记录已有结构化解析结果则直接复用；为空返回 None 由调用方降级原文解析"""
        from app.models.resume import ResumeData
        try:
            data = ResumeData(**(record.data_json or {}))
        except Exception:
            return None
        if any([data.name, data.skills, data.work_experiences,
                data.projects, data.educations]):
            return data
        return None

    @staticmethod
    def _find_job_by_raw_text(db, jd_text: str):
        """按JD原文查岗位：同一段JD已解析入库则直接复用，省一次 LLM 解析调用"""
        if not jd_text:
            return None
        return db.query(JobRecord).filter_by(raw_text=jd_text).first()

    async def _handle_evaluate_job(self, intent_result: Dict, conv: ConversationRecord, db) -> Message:
        """处理评估岗位意图"""
        jd_text = intent_result.get("jd_text", "")
        
        if not jd_text:
            return Message(
                role="assistant",
                content="请粘贴JD文本，我来帮你评估这个岗位。",
                cards=[]
            )
        
        try:
            # 同文JD复用已入库解析结果（重复粘贴JD为高频场景），省一次 LLM 解析调用
            job = self._find_job_by_raw_text(db, jd_text)
            if job is not None:
                from app.models.job import JobData
                job_data = JobData(**job.data_json)
            else:
                # 解析JD（同步 LLM 调用，放线程池避免阻塞事件循环）
                job_data = await asyncio.to_thread(self.job_parser.parse, jd_text)

                # 保存岗位
                job = JobRecord(
                    title=job_data.title,
                    company=job_data.company,
                    location=job_data.location,
                    salary_min=job_data.salary_min or 0,
                    salary_max=job_data.salary_max or 0,
                    data_json=job_data.model_dump(mode='json'),
                    raw_text=jd_text
                )
                db.add(job)
                db.commit()
                db.refresh(job)
            
            # 更新对话上下文
            conv.context_job_id = job.id
            
            # 获取基础简历进行评分
            base_resume = ResumeRepository(db).get_base()
            if not base_resume:
                return Message(
                    role="assistant",
                    content="请先上传你的简历，我才能帮你评估岗位匹配度。",
                    cards=[]
                )
            
            # 评分
            from app.models.resume import ResumeData
            resume_data = ResumeData(**base_resume.data_json)
            score_result = await asyncio.to_thread(self.job_scorer.score, resume_data, job_data)
            
            # 构建评分卡片
            score_card = {
                "type": "score_card",
                "data": {
                    "total_score": score_result.total_score,
                    "score_level": score_result.score_level,
                    "dimensions": {
                        "skill": score_result.detail.skill_score,
                        "experience": score_result.detail.experience_score,
                        "salary": score_result.detail.salary_score,
                        "stability": score_result.detail.stability_score if hasattr(score_result.detail, 'stability_score') else 70,
                        "growth": score_result.detail.growth_score if hasattr(score_result.detail, 'growth_score') else 70
                    },
                    "strengths": score_result.strengths,
                    "weaknesses": score_result.weaknesses,
                    "suggestions": score_result.suggestions
                }
            }
            
            content = f"已解析JD「{job_data.title} - {job_data.company}」，评分结果如下："
            
            return Message(
                role="assistant",
                content=content,
                cards=[score_card]
            )
        
        except Exception as e:
            logger.error(f"评估岗位失败: {e}")
            return Message(
                role="assistant",
                content=f"评估岗位时出错：{str(e)}",
                cards=[]
            )
    
    async def _handle_optimize_resume(self, intent_result: Dict, conv: ConversationRecord, db) -> Message:
        """处理优化简历意图"""
        job_id = conv.context_job_id
        jd_text = intent_result.get("jd_text", "")
        if not job_id and jd_text:
            # 同消息附带目标JD：先按原文查已入库解析，未命中再就地解析入库并绑定当前会话，
            # 避免新会话"粘贴JD要求重写简历"被弹回"请先评估一个岗位"
            try:
                job = self._find_job_by_raw_text(db, jd_text)
                if job is None:
                    job_data = await asyncio.to_thread(self.job_parser.parse, jd_text)
                    job = JobRecord(
                        title=job_data.title,
                        company=job_data.company,
                        location=job_data.location,
                        salary_min=job_data.salary_min or 0,
                        salary_max=job_data.salary_max or 0,
                        data_json=job_data.model_dump(mode='json'),
                        raw_text=jd_text
                    )
                    db.add(job)
                    db.commit()
                    db.refresh(job)
                conv.context_job_id = job.id
                job_id = job.id
            except Exception as e:
                logger.error(f"解析消息内附带JD失败: {e}")
        if not job_id:
            return Message(
                role="assistant",
                content="请先评估一个岗位，或直接在消息中附上目标岗位JD，我再帮你针对该岗位优化简历。",
                cards=[]
            )
        
        job = db.query(JobRecord).filter_by(id=job_id).first()
        base_resume = db.query(ResumeRecord).filter_by(is_base=True).first()
        
        if not base_resume:
            return Message(
                role="assistant",
                content="请先上传你的简历。",
                cards=[]
            )
        
        try:
            from app.models.resume import ResumeData
            from app.models.job import JobData
            resume_data = ResumeData(**base_resume.data_json)
            job_data = JobData(**job.data_json)
            
            # 优化简历
            optimized = await asyncio.to_thread(self.resume_optimizer.optimize, resume_data, job_data)
            
            # 构建Diff卡片
            diff_items = [
                {
                    "section": change.get("section", ""),
                    "before": change.get("before", ""),
                    "after": change.get("after", ""),
                    "reason": change.get("reason", "")
                }
                for change in optimized.get("changes", [])
            ]
            
            diff_card = {
                "type": "diff_card",
                "data": {
                    "items": diff_items,
                    "total_changes": len(diff_items),
                    "confirmed_count": 0
                }
            }
            
            return Message(
                role="assistant",
                content=f"优化完成，共修改{len(diff_items)}处，请逐一确认：",
                cards=[diff_card]
            )
        
        except Exception as e:
            logger.error(f"优化简历失败: {e}")
            return Message(
                role="assistant",
                content=f"优化简历时出错：{str(e)}",
                cards=[]
            )
    
    async def _handle_generate_questions(self, intent_result: Dict, conv: ConversationRecord, db) -> Message:
        """处理生成面试题意图"""
        job_id = conv.context_job_id
        if not job_id:
            return Message(
                role="assistant",
                content="请先评估一个岗位，我再帮你生成针对性面试题。",
                cards=[]
            )
        
        job = db.query(JobRecord).filter_by(id=job_id).first()
        if not job:
            return Message(
                role="assistant",
                content="岗位信息不存在，请重新评估。",
                cards=[]
            )
        
        try:
            from app.models.job import JobData
            job_data = JobData(**job.data_json)
            
            # 注意：generate_questions 签名仅收 job_data，多传参数会 TypeError
            questions = await asyncio.to_thread(self.interview_simulator.generate_questions, job_data)
            
            # generate_questions 返回 {technical_questions, behavioral_questions}，
            # 前端 QuestionCardData.questions 期望题目数组 → 合并两类题目
            q_list = list(questions.get("technical_questions", [])) + \
                     list(questions.get("behavioral_questions", []))
            
            question_card = {
                "type": "question_card",
                "data": {
                    "interview_type": "technical",
                    "questions": q_list
                }
            }
            
            return Message(
                role="assistant",
                content=f"已为「{job.title}」生成{len(q_list)}道面试题：",
                cards=[question_card]
            )
        
        except Exception as e:
            logger.error(f"生成面试题失败: {e}")
            return Message(
                role="assistant",
                content=f"生成面试题时出错：{str(e)}",
                cards=[]
            )
    
    async def _handle_view_recommendations(self, conv: ConversationRecord, db) -> Message:
        """处理查看推荐岗位意图"""
        # 获取评分最高的岗位
        jobs = db.query(JobRecord).order_by(JobRecord.created_at.desc()).limit(10).all()
        
        if not jobs:
            return Message(
                role="assistant",
                content="还没有录入任何岗位，请先粘贴JD进行评估。",
                cards=[]
            )
        
        recommend_card = {
            "type": "recommend_card",
            "data": {
                "jobs": [
                    {
                        "id": j.id,
                        "title": j.title,
                        "company": j.company,
                        "salary": f"{j.salary_min}-{j.salary_max}万" if j.salary_max else "面议"
                    }
                    for j in jobs
                ]
            }
        }
        
        return Message(
            role="assistant",
            content=f"最近录入的{len(jobs)}个岗位：",
            cards=[recommend_card]
        )
    
    async def _handle_view_progress(self, conv: ConversationRecord, db) -> Message:
        """处理查看进度意图"""
        from app.db.models import ApplicationRecord
        from datetime import date
        
        today = date.today()
        today_count = db.query(ApplicationRecord).filter(
            ApplicationRecord.apply_date == today,
            ApplicationRecord.status == "applied"
        ).count()
        
        progress_card = {
            "type": "progress_card",
            "data": {
                "daily_target": 12,
                "applied_today": today_count,
                "remaining": max(0, 12 - today_count),
                "encouragement": "加油！" if today_count < 12 else "今天目标已完成！"
            }
        }
        
        return Message(
            role="assistant",
            content=f"今日投递进度：已投{today_count}个，目标12个",
            cards=[progress_card]
        )
    
    async def _handle_general_chat(self, intent_result: Dict, conv: ConversationRecord,
                                    user_message: str = "",
                                    image_paths: Optional[List[str]] = None,
                                    file_paths: Optional[List[str]] = None) -> Message:
        """处理普通对话"""
        try:
            cards = []
            if image_paths:
                for i, img_path in enumerate(image_paths):
                    cards.append({
                        "type": "image_card",
                        "data": {"url": img_path, "index": i}
                    })
            if file_paths:
                for i, file_path in enumerate(file_paths):
                    cards.append({
                        "type": "file_card",
                        "data": {"url": file_path, "index": i}
                    })

            # 中期记忆注入：最近 N 轮历史进 prompt（历史不含本轮新消息）
            history = (conv.messages or [])[:-1]
            prompt, injected = self._build_general_prompt(
                user_message, history, image_paths, file_paths,
                anchor_text=self._session_anchors(conv, len(history)))
            _memory_guard.check_session_inject(len(history), injected)

            response = await self.llm_client.chat([{"role": "user", "content": prompt}])
            
            return Message(
                role="assistant",
                content=response,
                cards=cards
            )
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return Message(
                role="assistant",
                content="抱歉，我暂时无法回答。请稍后再试。",
                cards=[]
            )
