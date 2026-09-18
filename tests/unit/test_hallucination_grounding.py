"""幻觉防线单元测试（时间接地 + 简历接地解析回归）

历史缺陷回归：
- 系统Prompt未注入当前日期 → 问年份答训练截止年份；
- "帮我解析简历"落 general_chat 且无简历原文 → 模型凭空编造他人经历。
"""
import asyncio
from datetime import datetime

from app.llm.prompts import PromptTemplates
from app.models.resume import ResumeData, WorkExperience
from app.services.chat_engine import ChatEngineService


class TestTimeGrounding:
    """时间幻觉防线：系统Prompt必须携带请求时刻日期"""

    def test_prompt_contains_current_year(self):
        prompt = PromptTemplates.build_system_prompt()
        assert str(datetime.now().year) in prompt

    def test_prompt_forbids_training_cutoff(self):
        assert "训练截止时间" in PromptTemplates.build_system_prompt()

    def test_no_resume_declares_not_uploaded(self):
        assert "尚未上传任何简历" in PromptTemplates.build_system_prompt(resume_summary="")

    def test_resume_summary_marked_sole_basis(self):
        prompt = PromptTemplates.build_system_prompt(resume_summary="姓名: 张三")
        assert "张三" in prompt
        assert "唯一事实依据" in prompt
        assert "不得编造" in prompt


class TestParseResumeRouting:
    """简历解析必须走接地意图，不得落 general_chat 凭空生成"""

    @staticmethod
    def _intent(message: str) -> str:
        engine = object.__new__(ChatEngineService)
        engine.llm_client = None  # 确定性规则路径（离线单测不触LLM）
        return asyncio.run(engine._recognize_intent(message, []))["intent"]

    def test_parse_resume_routes_to_grounded_intent(self):
        assert self._intent("帮我解析简历") == "parse_resume"

    def test_time_question_stays_general_chat(self):
        assert self._intent("今年是几几年?") == "general_chat"

    def test_optimize_intent_not_hijacked(self):
        assert self._intent("优化我的简历") == "optimize_resume"

    def test_evaluate_intent_not_hijacked(self):
        assert self._intent("帮我评估这个岗位怎么样") == "evaluate_job"


class TestRewriteResumeRouting:
    """重写系请求必须路由 optimize_resume，不得被长文本JD启发式劫持为 evaluate_job

    历史缺陷回归："粘贴JD+根据岗位职责重写我的简历"(>200字含岗位/职责)
    被长文本启发式前置命中为 evaluate_job，只回JD评分、不产出重写结果。
    """

    JD_LONG = (
        "岗位职责\n"
        "1、开发大模型应用：智能体（Agent）、RAG知识库、工作流编排、API/工具集成等，支撑业务场景落地。\n"
        "2、深度实践AI Coding工具按SDD开发范式交付，参与需求拆解、方案设计、代码生成、单测生成、联调验证与问题定位。\n"
        "3、参与AI平台/工具链建设，包括Prompt、Spec结构化设计、Skill能力沉淀、自动化开发工作流优化等。\n"
        "任职要求\n"
        "1、全日制本科及以上学历，计算机相关专业，3年以上软件开发经验；\n"
        "2、精通至少一门主流语言（Java/Python/TypeScript等），熟悉Git、CI/CD、TDD、单元测试。"
    )

    @staticmethod
    def _intent(message: str) -> str:
        engine = object.__new__(ChatEngineService)
        engine.llm_client = None  # 确定性规则路径（离线单测不触LLM）
        return asyncio.run(engine._recognize_intent(message, []))["intent"]

    def test_rewrite_with_pasted_jd_routes_to_optimize(self):
        message = "根据这个岗位职责重写我的简历\n" + self.JD_LONG
        assert len(message) > 200
        assert self._intent(message) == "optimize_resume"

    def test_rewrite_short_message_routes_to_optimize(self):
        assert self._intent("重写我的简历") == "optimize_resume"
        assert self._intent("帮我改写简历") == "optimize_resume"

    def test_pure_jd_paste_still_routes_to_evaluate(self):
        assert self._intent(self.JD_LONG + "\n" + self.JD_LONG) == "evaluate_job"


class TestResumeAdviceRouting:
    """咨询类问句路由回归："我的简历"所有格短语不得作解析动词劫持为 parse_resume

    历史缺陷回归："我的简历篇幅需要修改么"被规则关键词"我的简历"决定性
    命中 parse_resume，回存档简历解析结果而非回答咨询。
    """

    @staticmethod
    def _intent(message: str) -> str:
        engine = object.__new__(ChatEngineService)
        engine.llm_client = None  # 确定性规则路径（离线单测不触LLM）
        return asyncio.run(engine._recognize_intent(message, []))["intent"]

    def test_resume_length_question_routes_to_advice(self):
        assert self._intent("我的简历篇幅需要修改么") == "give_advice"

    def test_resume_opinion_question_routes_to_advice(self):
        assert self._intent("我的简历怎么样") == "give_advice"
        assert self._intent("简历有什么问题") == "give_advice"

    def test_explicit_parse_still_routes_to_parse(self):
        assert self._intent("帮我解析简历") == "parse_resume"
        assert self._intent("解析我的简历") == "parse_resume"

    def test_resume_match_question_still_routes_to_evaluate(self):
        assert self._intent("我的简历匹配这个岗位吗") == "evaluate_job"


class TestWeakVerbRouting:
    """泛义弱词路由回归："看看/怎么样"无领域锚点不得决定性劫持为评估岗位

    历史缺陷回归："我再问你个问题看看你是不是会出现幻觉？今年是几几年？"
    被泛义动词"看看"决定性命中 evaluate_job，回"请粘贴JD文本"。
    """

    @staticmethod
    def _intent(message: str) -> str:
        engine = object.__new__(ChatEngineService)
        engine.llm_client = None  # 确定性规则路径（离线单测不触LLM）
        return asyncio.run(engine._recognize_intent(message, []))["intent"]

    def test_hallucination_probe_question_stays_general_chat(self):
        assert self._intent(
            "那好，我再问你个问题看看你是不是会出现幻觉？今年是几几年？") == "general_chat"

    def test_weak_verb_with_job_anchor_routes_to_evaluate(self):
        assert self._intent("看看这个岗位怎么样") == "evaluate_job"
        assert self._intent("帮我看看这个JD行不行") == "evaluate_job"

    def test_weak_verb_without_anchor_not_hijacked(self):
        assert self._intent("帮我看看这段代码对不对") == "general_chat"

    def test_explicit_evaluate_verb_still_decisive(self):
        assert self._intent("帮我评估这个岗位") == "evaluate_job"


class TestClarificationGate:
    """低置信度澄清闸门：高成本工具意图置信度不足时反问而非硬执行

    参考分层漏斗架构的置信度兜底：普通查询阈值 0.7；
    显式规则（decisive）与长文本JD兜底（0.9）不触发澄清。"""

    def test_low_confidence_tool_intent_needs_clarification(self):
        assert ChatEngineService._needs_clarification(
            {"intent": "evaluate_job", "confidence": 0.6, "router": "llm"}) is True
        assert ChatEngineService._needs_clarification(
            {"intent": "optimize_resume", "confidence": 0.5, "router": "llm"}) is True

    def test_high_confidence_or_decisive_not_clarified(self):
        assert ChatEngineService._needs_clarification(
            {"intent": "evaluate_job", "confidence": 0.9, "router": "llm"}) is False
        assert ChatEngineService._needs_clarification(
            {"intent": "evaluate_job", "confidence": 0.7,
             "decisive": True, "router": "rules"}) is False

    def test_low_cost_intents_never_clarified(self):
        # general_chat/give_advice 直接回答比反问体验好，不走澄清
        assert ChatEngineService._needs_clarification(
            {"intent": "general_chat", "confidence": 0.3, "router": "llm"}) is False
        assert ChatEngineService._needs_clarification(
            {"intent": "give_advice", "confidence": 0.5, "router": "llm"}) is False

    def test_clarification_message_offers_confirm_branch(self):
        msg = ChatEngineService._clarification_message(
            {"intent": "evaluate_job", "confidence": 0.6, "router": "llm"})
        assert "确认" in msg.content and "评估" in msg.content and "JD" in msg.content
        assert msg.cards == []


class _StubLLMClient:
    """最小LLM客户端桩：仅提供 chat_json_sync，供语义路由单测"""

    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    def chat_json_sync(self, messages, **kwargs):
        if self.error:
            raise self.error
        return self.payload


def _engine_with_client(client) -> ChatEngineService:
    engine = object.__new__(ChatEngineService)
    engine.llm_client = client
    return engine


class TestLLMIntentRouter:
    """LLM 语义路由：理解规则未覆盖的同义改写；异常/越界静默降级规则"""

    @staticmethod
    def _result(engine, message):
        return asyncio.run(engine._recognize_intent(message, []))

    def test_llm_routes_uncovered_paraphrase(self):
        engine = _engine_with_client(_StubLLMClient(
            {"intent": "optimize_resume", "confidence": 0.85,
             "extracted_data": {"jd_text": ""}}))
        result = self._result(engine, "帮我按这个岗位的要求润色一下简历")
        assert result["intent"] == "optimize_resume"
        assert result["router"] == "llm"

    def test_llm_failure_falls_back_to_rules(self):
        engine = _engine_with_client(_StubLLMClient(error=RuntimeError("timeout")))
        result = self._result(engine, "你好")
        assert result["intent"] == "general_chat"
        assert result["router"] == "rules"

    def test_illegal_intent_falls_back_to_rules(self):
        engine = _engine_with_client(_StubLLMClient(
            {"intent": "hack_system", "confidence": 0.9}))
        result = self._result(engine, "你好")
        assert result["intent"] == "general_chat"

    def test_long_jd_context_merged_from_rules(self):
        engine = _engine_with_client(_StubLLMClient(
            {"intent": "evaluate_job", "confidence": 0.9, "extracted_data": {}}))
        jd = TestRewriteResumeRouting.JD_LONG
        result = self._result(engine, jd + "\n" + jd)
        assert result["intent"] == "evaluate_job"
        assert result.get("jd_text")

    def test_intent_prompt_template_renders(self):
        # 模板花括号转义正确：format 后占位符消失、JSON 示例为单花括号
        prompt = PromptTemplates.format_template(
            "INTENT_RECOGNITION", user_message="你好", context="无")
        assert "{user_message}" not in prompt and "你好" in prompt
        assert '"intent": "意图名称"' in prompt and "{{" not in prompt

    def test_decisive_rule_skips_llm(self):
        # 显式动词命中规则快路径：桩客户端不应被调用
        class _SpyClient(_StubLLMClient):
            called = False

            def chat_json_sync(self, messages, **kwargs):
                _SpyClient.called = True
                return super().chat_json_sync(messages, **kwargs)

        engine = _engine_with_client(_SpyClient({"intent": "general_chat"}))
        result = self._result(engine, "重写我的简历")
        assert result["intent"] == "optimize_resume"
        assert result["router"] == "rules"
        assert _SpyClient.called is False


class TestFormatResumeSourceLabel:
    """解析回复必须标注来源，便于用户核对防编造"""

    def test_source_label_and_company_present(self):
        data = ResumeData(
            name="张三",
            years_of_experience=3,
            work_experiences=[WorkExperience(
                company="星辰科技", position="测试开发",
                start_date="2023.01", end_date="至今", description="负责平台测试"
            )],
        )
        text = ChatEngineService._format_resume(data, "你在对话中粘贴的简历文本")
        assert "已基于你在对话中粘贴的简历文本解析" in text
        assert "星辰科技" in text
