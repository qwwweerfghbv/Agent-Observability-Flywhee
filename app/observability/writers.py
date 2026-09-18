"""JSONL 落盘（SDD §5.2）：追加写 / 轮转 / 静默降级

- 采集端只负责"就地填充 + 追加写"，聚合/判定全在消费端离线做
- 任一环节失败仅 loguru.warning，绝不抛出影响主链路
"""
import gzip
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

OBS_DIR = Path(__file__).resolve().parents[2] / "data" / "observability"
REQUESTS_PATH = OBS_DIR / "requests.jsonl"
RUM_PATH = OBS_DIR / "rum.jsonl"
_ROTATE_MB = 50


def _append_jsonl(path: Path, rec: Dict[str, Any]) -> None:
    """通用追加写：失败仅告警，永不抛出"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.warning(f"观测数据写入失败(静默降级，不影响主链路): {path.name}: {e}")


def rotate_if_needed(path: Path, mb: int = _ROTATE_MB) -> None:
    """超阈值轮转 → gzip 归档（压缩比 ~10:1）"""
    try:
        if path.exists() and path.stat().st_size > mb * 1024 * 1024:
            archived = path.with_name(
                f"{path.stem}.{time.strftime('%Y%m%d%H%M%S')}.jsonl.gz")
            with open(path, "rb") as src, gzip.open(archived, "wb") as dst:
                shutil.copyfileobj(src, dst)
            path.unlink()
    except Exception as e:
        logger.warning(f"观测数据轮转失败(静默降级): {e}")


def stream_metrics(delta_times: List[float]) -> Optional[Dict[str, float]]:
    """delta 时间戳列表 → {delta_count, gap_median_ms, total_span_ms}

    gap_median < 5ms 且 delta_count > 5 即流式退化（B2 判据，M3 规则引擎消费）。
    """
    n = len(delta_times)
    if n == 0:
        return None
    gaps = sorted(
        round((delta_times[i + 1] - delta_times[i]) * 1000, 1) for i in range(n - 1)
    )
    median = gaps[len(gaps) // 2] if gaps else 0.0
    return {
        "delta_count": n,
        "gap_median_ms": median,
        "total_span_ms": round((delta_times[-1] - delta_times[0]) * 1000, 1),
    }


def write_request(ctx: Optional[Dict[str, Any]]) -> None:
    """ObservabilityContext → RequestObservation → 追加 requests.jsonl

    - 仅落盘 /api/* 请求（静态资源/SPA 页面不落，避免噪音）
    - 非流式：中间件响应后调用；流式：event_gen 的 finally 调用
    - degraded 派生：LLM 出错但请求最终成功 = 服务层 fallback 兜底（静默降级显性化）
    """
    if not ctx:
        return
    try:
        from app.observability.models import RequestObservation

        path = ctx.get("path", "")
        if not path.startswith("/api"):
            return
        start_ts = ctx.get("start_ts") or time.time()
        duration_ms = round((time.time() - start_ts) * 1000, 1)
        degraded = bool(ctx.get("llm_error")) and ctx.get("status", "ok") == "ok"
        obs = RequestObservation(
            trace_id=ctx.get("trace_id", ""),
            source=ctx.get("source", "production"),
            ts=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_ts))
               + f".{int(start_ts % 1 * 1000):03d}",
            path=path,
            method=ctx.get("method", ""),
            status=ctx.get("status", "ok"),
            status_code=ctx.get("status_code", 200),
            duration_ms=duration_ms,
            ttft_ms=ctx.get("ttft_ms"),
            stream=ctx.get("stream"),
            tokens=ctx.get("tokens"),
            model=ctx.get("model"),
            intent=ctx.get("intent"),
            intent_confidence=ctx.get("intent_confidence"),
            intent_router=ctx.get("intent_router"),
            ambiguous=bool(ctx.get("ambiguous", False)),
            clarified=bool(ctx.get("clarified", False)),
            conversation_id=ctx.get("conversation_id"),
            msg_persisted=ctx.get("msg_persisted"),
            llm_calls=ctx.get("llm_calls"),
            llm_duration_ms=ctx.get("llm_duration_ms"),
            llm_first_delta_ms=ctx.get("llm_first_delta_ms"),
            llm_error=ctx.get("llm_error"),
            degraded=bool(ctx.get("degraded", degraded)),
            user_interrupted=bool(ctx.get("user_interrupted", False)),
            waited_ms=ctx.get("waited_ms"),
            card_count=ctx.get("card_count"),
            empty_reply=bool(ctx.get("empty_reply", False)),
            security_hit=bool(ctx.get("security_hit", False)),
            quality_flags=ctx.get("quality_flags"),
            memory_flags=ctx.get("memory_flags"),
            spans=ctx.get("spans"),
            message_preview=(ctx.get("message_preview") or "")[:100],
            error=ctx.get("error"),
            version=ctx.get("version"),
        )
        rotate_if_needed(REQUESTS_PATH)
        _append_jsonl(REQUESTS_PATH, obs.model_dump(exclude_none=True))
    except Exception as e:
        logger.warning(f"请求观测落盘失败(静默降级): {e}")


def write_rum(event: Optional[Dict[str, Any]]) -> None:
    """L6 RUM 事件落盘（SDD §4.7/§6.1，M6）：js_error/card_render_fail/feedback。

    自动补 ts/source；隐私约束（不含 DOM/消息全文）由前端上报侧保证。
    feedback 事件带 trace_id 时，回流采集器按 trace_id 合并出 rating 触发 explicit_negative。
    静默降级：失败仅告警。
    """
    if not event:
        return
    try:
        rec = dict(event)
        rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        rec.setdefault("source", "production")
        rotate_if_needed(RUM_PATH)
        _append_jsonl(RUM_PATH, rec)
    except Exception as e:
        logger.warning(f"RUM 事件写入失败(静默降级): {e}")
