"""质量哨兵（SDD §4.6 / §5.7，M4）

职责：请求完成后对回复做质量校验并落 quality.jsonl，供 M3 flywheel 回流消费。
- 卡片完整性：card_count / empty_card / missing_fields
- 空/截断回复：empty_reply / truncated
- 安全扫描：注入样式（输入）+ 敏感信息（输出）→ red_line_hit
- 抽样在线评分：命中 sampling_rate 的请求投递后台任务，复用 tests/eval/scorers/，
  judge token 走独立账本（source=eval 上下文），不阻塞响应、不污染线上统计。

落盘 schema 对齐 SDD §3.5；flywheel._load_records 按 trace_id last-wins 合并，
故抽样评分完成后追加的 scored 记录会覆盖同 trace 的基础记录。
所有函数静默降级：任何异常仅 loguru.warning，绝不影响主链路。
"""
import asyncio
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.observability.writers import OBS_DIR, _append_jsonl, rotate_if_needed
from app.observability.context import get_context, fill, begin_context
from app.observability import security

QUALITY_PATH = OBS_DIR / "quality.jsonl"
_SLO_CONFIG = Path(__file__).resolve().parents[2] / "tests" / "eval" / "slo_config.json"
_DEFAULT_SAMPLE_RATE = 0.10

# 后台任务强引用，防止被 GC 提前回收
_pending_tasks: set = set()

# 关键卡片类型的必填字段（缺失即视为质量问题）
_REQUIRED_CARD_FIELDS = {
    "score_card": ["total_score", "dimensions"],
    "diff_card": ["items"],
    "question_card": ["questions"],
    "recommend_card": ["jobs"],
    "progress_card": ["applied_today"],
}


def _now_ts() -> str:
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)) + f".{int(t % 1 * 1000):03d}"


def get_sample_rate() -> float:
    """抽样率：优先读 slo_config.json 的 sampling_rate，否则默认 10%"""
    try:
        cfg = json.loads(_SLO_CONFIG.read_text(encoding="utf-8"))
        rate = float(cfg.get("sampling_rate", _DEFAULT_SAMPLE_RATE))
        return max(0.0, min(1.0, rate))
    except Exception:
        return _DEFAULT_SAMPLE_RATE


def check_cards(cards: Optional[List[Dict]]) -> Dict[str, Any]:
    """卡片完整性校验 → {card_count, empty_card, missing_fields}"""
    cards = cards or []
    empty_card = False
    missing: List[str] = []
    for c in cards:
        if not isinstance(c, dict):
            empty_card = True
            continue
        ctype = c.get("type")
        data = c.get("data")
        if not ctype or data in (None, "", [], {}):
            empty_card = True
            continue
        for f in _REQUIRED_CARD_FIELDS.get(ctype, []):
            if not isinstance(data, dict) or data.get(f) in (None, "", [], {}):
                missing.append(f"{ctype}.{f}")
    return {"card_count": len(cards), "empty_card": empty_card, "missing_fields": missing}


def check_completion(text: Optional[str]) -> Dict[str, bool]:
    """空/截断回复校验 → {empty_reply, truncated}"""
    t = (text or "").strip()
    if not t:
        return {"empty_reply": True, "truncated": False}
    # 截断启发式：以省略号或悬挂标点结尾（生成被截断的常见特征）
    truncated = t.endswith(("...", "…", "、", "，", ",", "：", ":")) and len(t) > 1
    return {"empty_reply": False, "truncated": truncated}


def build_record(trace_id: str, source: str, user_message: str,
                 reply_text: str, cards: Optional[List[Dict]]) -> Dict[str, Any]:
    """组装 quality.jsonl 基础记录（廉价同步校验 + 安全扫描）"""
    card = check_cards(cards)
    comp = check_completion(reply_text)
    sec_in = security.scan_input(user_message)
    sec_out = security.scan_output(reply_text)
    red_line_hit = bool(sec_out["sensitive_hit"] or sec_in["injection_hit"])
    return {
        "ts": _now_ts(),
        "trace_id": trace_id,
        "source": source,
        "sampled": False,
        "card_count": card["card_count"],
        "empty_card": card["empty_card"],
        "missing_fields": card["missing_fields"],
        "empty_reply": comp["empty_reply"],
        "truncated": comp["truncated"],
        "scores": None,
        "injection_hit": sec_in["injection_hit"],
        "injection_patterns": sec_in["patterns"],
        "sensitive_types": sec_out["types"],
        "red_line_hit": red_line_hit,
    }


def write_quality(rec: Dict[str, Any]) -> None:
    """追加写 quality.jsonl（静默降级）"""
    try:
        rotate_if_needed(QUALITY_PATH)
        _append_jsonl(QUALITY_PATH, rec)
    except Exception as e:
        logger.warning(f"质量记录落盘失败(静默降级): {e}")


def _quality_flags(rec: Dict[str, Any]) -> List[str]:
    flags = []
    if rec.get("empty_reply"):
        flags.append("empty_reply")
    if rec.get("empty_card"):
        flags.append("empty_card")
    if rec.get("missing_fields"):
        flags.append("missing_card_fields")
    if rec.get("truncated"):
        flags.append("truncated")
    if rec.get("injection_hit"):
        flags.append("injection")
    if rec.get("sensitive_types"):
        flags.append("sensitive_output")
    return flags


def observe_reply(user_message: str, reply_text: str,
                  cards: Optional[List[Dict]] = None) -> Optional[Dict[str, Any]]:
    """请求完成后调用（chat_engine 内）：同步做廉价校验并落盘 + 回填请求上下文；
    命中抽样则调度后台异步评分。返回基础记录（无上下文时返回 None）。
    """
    try:
        ctx = get_context()
        if not ctx:
            return None
        trace_id = ctx.get("trace_id", "")
        source = ctx.get("source", "production")
        rec = build_record(trace_id, source, user_message, reply_text, cards)
        write_quality(rec)
        # 回填请求上下文摘要（进 requests.jsonl 供 trace 详情；判定仍以 quality.jsonl 为准）
        fill(card_count=rec["card_count"], empty_reply=rec["empty_reply"],
             security_hit=rec["red_line_hit"], quality_flags=_quality_flags(rec))
        # 抽样异步评分（不阻塞响应）
        if random.random() < get_sample_rate():
            _schedule_scoring(rec, user_message, reply_text)
        return rec
    except Exception as e:
        logger.warning(f"质量哨兵执行失败(静默降级): {e}")
        return None


def _schedule_scoring(base_rec: Dict[str, Any], user_message: str, reply_text: str) -> None:
    """投递后台评分任务（fire-and-forget，强引用防 GC）"""
    try:
        loop = asyncio.get_event_loop()
        task = loop.create_task(_score_and_append(base_rec, user_message, reply_text))
        _pending_tasks.add(task)
        task.add_done_callback(_pending_tasks.discard)
    except Exception as e:
        logger.warning(f"抽样评分任务调度失败(静默降级): {e}")


async def _run_judge(user_message: str, reply_text: str) -> Dict[str, Any]:
    """调用 LLM judge（独立入口，便于测试替换）"""
    from tests.eval.scorers.llm_judge_scorer import LLMJudgeScorer
    scorer = LLMJudgeScorer()
    return await scorer.judge_response_quality(user_message, reply_text)


async def _run_truthfulness(reply_text: str) -> Dict[str, Any]:
    """幻觉维度 judge：以库内基础简历为地面真相查回复是否编造（指南 2.4/4.3 幻觉率在线化）

    无库存简历时返回 {}（不评幻觉分，不误判）；judge 失败静默降级。
    """
    try:
        from app.db.database import SessionLocal
        from app.db.repositories import ResumeRepository
        db = SessionLocal()
        try:
            # is_base 列历史遗留默认全 True，统一经 get_base() 取最新存档（与简历中心 UI 一致）
            base = ResumeRepository(db).get_base()
            resume_text = (base.raw_text if base else "") or ""
            if base and len(resume_text.strip()) < 100:
                # raw_text 为提取失败残桩时退化用结构化数据作地面真相，避免以残桩误判幻觉
                import json as _json
                resume_text = _json.dumps(base.data_json or {}, ensure_ascii=False)
        finally:
            db.close()
        if not resume_text:
            return {}
        from tests.eval.scorers.llm_judge_scorer import LLMJudgeScorer
        scorer = LLMJudgeScorer()
        return await scorer.judge_truthfulness(resume_text, reply_text, "") or {}
    except Exception as e:
        logger.warning(f"真实性 judge 失败(静默降级): {e}")
        return {}


async def _score_and_append(base_rec: Dict[str, Any], user_message: str, reply_text: str) -> None:
    """后台抽样评分：切 eval 上下文（judge token 独立账本）→ 追加 scored 记录"""
    try:
        # 独立账本：本任务内新建 eval 上下文，judge 的 LLM 调用不污染线上请求记录
        begin_context(source="eval")
    except Exception:
        pass
    try:
        res = await _run_judge(user_message, reply_text) or {}
        truth = await _run_truthfulness(reply_text)
        judge_ctx = get_context() or {}
        scores = {
            "relevance": res.get("intent_understanding"),
            "quality": res.get("response_quality"),
            "red_line": res.get("safety_score"),
            "overall": res.get("overall"),
            "truthfulness": truth.get("score"),
        }
        scores = {k: v for k, v in scores.items() if isinstance(v, (int, float))}
        # judge 侧红线：安全分过低/显式违规/查出编造
        judge_red_line = bool(res.get("red_line_violation")) or (
            isinstance(res.get("safety_score"), (int, float)) and res["safety_score"] < 60)
        judge_red_line = judge_red_line or bool(truth.get("has_fabrication")) \
            or bool(truth.get("red_line_violation"))
        reason = str(res.get("reason", ""))[:200]
        fabrication = truth.get("fabrication_details") or []
        if fabrication:
            reason += " | 编造: " + "; ".join(str(x) for x in fabrication[:3])[:150]
        scored = dict(base_rec)
        scored.update({
            "ts": _now_ts(),
            "sampled": True,
            "scores": scores or None,
            "red_line_hit": bool(base_rec.get("red_line_hit") or judge_red_line),
            "judge_reason": security.mask_pii(reason),
            "judge_model": judge_ctx.get("model"),
            "judge_tokens": (judge_ctx.get("tokens") or {}).get("total"),
        })
        write_quality(scored)
    except Exception as e:
        logger.warning(f"抽样评分失败(静默降级): {e}")
