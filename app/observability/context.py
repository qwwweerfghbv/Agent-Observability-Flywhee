"""观测上下文（SDD §3.2）：ContextVar + trace_id + 就地填充 + 版本快照

线上域走 ObservabilityContext（中间件 begin_context）；
评测域另设 eval_context（M5，SpanRecorder 显式埋点），共用本模块的 fill/版本快照。
所有函数静默降级：埋点失败绝不影响主链路。
"""
import contextvars
import hashlib
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_obs_ctx: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "obs_ctx", default=None
)

# 启动后只算一次的版本快照缓存
_VERSION_SNAPSHOT: Optional[Dict[str, str]] = None

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def new_trace_id(prefix: str = "req") -> str:
    return f"{prefix}-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"


def get_version_snapshot() -> Dict[str, str]:
    """版本快照（SDD §3.3 version 字段）：任何历史记录可复现当时环境"""
    global _VERSION_SNAPSHOT
    if _VERSION_SNAPSHOT is None:
        snap = {"agent_version": "0.3.0", "git_hash": "", "prompt_hash": "", "model": ""}
        try:
            snap["git_hash"] = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=3,
            ).stdout.strip()
        except Exception:
            pass  # git 不可用时留空，静默降级
        try:
            from app.core.config import settings
            snap["model"] = settings.qwen_model or ""
        except Exception:
            pass
        try:
            tpl = Path(__file__).resolve().parents[1] / "prompts" / "templates.py"
            snap["prompt_hash"] = "ph-" + hashlib.md5(tpl.read_bytes()).hexdigest()[:6]
        except Exception:
            pass
        _VERSION_SNAPSHOT = snap
    return _VERSION_SNAPSHOT


def begin_context(source: str = "production", **seed) -> Dict[str, Any]:
    """请求/用例开始时建立上下文；source=production|eval（流量隔离，SDD D6）"""
    ctx = {
        "trace_id": new_trace_id("eval" if source == "eval" else "req"),
        "source": source,
        "start_ts": time.time(),
        "version": get_version_snapshot(),
        **seed,
    }
    _obs_ctx.set(ctx)
    return ctx


def get_context() -> Optional[Dict[str, Any]]:
    return _obs_ctx.get()


def fill(**fields) -> None:
    """各层就地填充字段（静默：无上下文时 no-op；dict 原地变更跨线程/任务可见）"""
    try:
        ctx = _obs_ctx.get()
        if ctx is not None:
            ctx.update(fields)
    except Exception:
        pass


def add_llm_metrics(tokens: Optional[Dict[str, int]] = None,
                    duration_ms: Optional[float] = None,
                    count_call: bool = True) -> None:
    """LLM 调用指标累加：同一请求多次调用时 tokens/耗时累加、次数计数（SDD §4.3）

    count_call=False 用于“只补 tokens 不重复计次”（流式末尾 usage chunk 回填）。
    """
    try:
        ctx = _obs_ctx.get()
        if ctx is None:
            return
        if tokens:
            cur = ctx.get("tokens") or {"prompt": 0, "completion": 0, "total": 0}
            ctx["tokens"] = {k: (cur.get(k) or 0) + (tokens.get(k) or 0)
                             for k in ("prompt", "completion", "total")}
        if duration_ms is not None:
            ctx["llm_duration_ms"] = round((ctx.get("llm_duration_ms") or 0) + duration_ms, 1)
        if count_call:
            ctx["llm_calls"] = (ctx.get("llm_calls") or 0) + 1
    except Exception:
        pass


def add_span(name: str, **attrs) -> None:
    """L4 决策链 span（SDD §4.5 P1）：planner/tool_pipeline 向当前上下文追加一个 span。

    与 harness/trajectory.py 的事件格式对齐（plan/tool），静默降级：无上下文时 no-op。
    """
    try:
        ctx = _obs_ctx.get()
        if ctx is None:
            return
        span = {"span": name, "ts": round(time.time(), 3)}
        span.update(attrs)
        ctx.setdefault("spans", []).append(span)
    except Exception:
        pass


def setup_trace_logging(level: str = "INFO") -> None:
    """trace_id 贯穿 loguru（横切 Logs 关联，SDD §4.8）

    patcher 给每条日志记录注入当前上下文的 trace_id；无上下文时为 '-'。
    """
    from loguru import logger

    def _patcher(record):
        ctx = _obs_ctx.get()
        record["extra"]["trace_id"] = (ctx or {}).get("trace_id", "-")

    logger.configure(patcher=_patcher)
    logger.remove()
    logger.add(
        sys.stdout, level=level,
        format=("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[trace_id]} | "
                "{name}:{function}:{line} - {message}"),
    )
