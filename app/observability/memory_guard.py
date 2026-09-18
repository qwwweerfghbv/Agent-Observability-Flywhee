"""记忆观测守卫（指南 1.2 Memory Span / 5.3 异常规则落地）

三类记忆埋点的统一收口点，"记忆是否出错"由此抛出：
- 短期记忆（会话上下文窗口）：trim 裁剪 span + 「压缩频繁」异常 flag
- 中期记忆（session 多轮持久化）：read/inject/write span +
  「上下文未注入」「会话持久化失败」「会话不存在」flag
- 长期记忆（跨会话 JSON 持久化）：load/save span + 「加载损坏」「保存失败」flag

产出两路：
1. memory span → ctx["spans"] → requests.jsonl → 链路详情关联 span 可见
2. memory_flags → ctx["memory_flags"] → requests.jsonl → monitor 聚合 /
   SLO 判定（memory_error_rate/memory_warn_rate）/ 总览告警清单

flag 分级：CRITICAL_MEMORY_FLAGS 命中即 critical（及时告警），其余 warning。
静默降级：本模块所有函数失败仅 loguru 记录，绝不影响主链路。
"""
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.observability.context import add_span, fill, get_context

# 长期记忆存储目录（与 LongTermMemory 默认路径一致）
LONG_TERM_DIR = Path(__file__).resolve().parents[2] / "data" / "memory"
_LONG_TERM_FILES = ("user_profile.json", "user_preferences.json", "operation_history.json")

# 短期记忆「压缩频繁」阈值：单实例累计裁剪消息数达到即抛 warning flag（指南 5.3）
TRIM_FREQUENT_THRESHOLD = 3

# critical 级 flag：命中即告警（中期写失败 / 长期 I/O 损坏）
CRITICAL_MEMORY_FLAGS = {
    "session_persist_failed",
    "long_term_load_corrupt",
    "long_term_save_failed",
}


def record_memory_span(op: str, memory_type: str, success: bool = True, **attrs) -> None:
    """记一个 memory span（short_term/session/long_term 的 read/inject/trim/write/load/save）。

    success=False 时同步 logger.error，保证"出错即有日志现场"。静默降级。
    """
    try:
        if not success:
            logger.error(f"记忆异常: type={memory_type} op={op} "
                         f"error={attrs.get('error', '')}")
        add_span("memory", memory_type=memory_type, op=op, success=success, **attrs)
    except Exception as e:  # 观测自身失败绝不影响主链路
        logger.warning(f"memory span 记录失败(静默降级): {e}")


def flag_memory(flag: str, detail: str = "") -> None:
    """抛记忆异常 flag：去重追加到 ctx["memory_flags"] 并立即打日志（及时抛出）。

    无观测上下文时仅落日志（如 harness 离线路径），不丢信号。
    """
    level = "critical" if flag in CRITICAL_MEMORY_FLAGS else "warning"
    msg = f"记忆异常flag[{level}]: {flag}" + (f" | {detail}" if detail else "")
    if level == "critical":
        logger.error(msg)
    else:
        logger.warning(msg)
    try:
        ctx = get_context()
        if ctx is None:
            return
        flags: List[str] = ctx.setdefault("memory_flags", [])
        if flag not in flags:
            flags.append(flag)
            fill(memory_flags=flags)
    except Exception as e:
        logger.warning(f"memory flag 回填失败(静默降级): {e}")


def check_session_read(msg_count: int) -> None:
    """中期记忆读取埋点：会话历史消息数"""
    record_memory_span("read", "session", msg_count=msg_count)


def check_session_inject(history_count: int, injected: int) -> None:
    """中期记忆注入埋点：历史是否真的进了 prompt。

    有历史但注入 0 条 = 上下文丢失缺陷复发 → 抛 context_not_injected。
    """
    record_memory_span("inject", "session",
                       history_count=history_count, injected=injected)
    if history_count > 0 and injected == 0:
        flag_memory("context_not_injected",
                    detail=f"会话有 {history_count} 条历史但 prompt 未注入")


def check_session_write(msg_count: int, error: Optional[str] = None) -> None:
    """中期记忆持久化埋点：commit 成功/失败；失败抛 critical flag"""
    if error is None:
        record_memory_span("write", "session", msg_count=msg_count)
    else:
        record_memory_span("write", "session", success=False,
                           msg_count=msg_count, error=error)
        flag_memory("session_persist_failed", detail=error)


def check_session_missing(conversation_id: object) -> None:
    """中期记忆读取失败：会话不存在"""
    record_memory_span("read", "session", success=False,
                       conversation_id=str(conversation_id), error="conversation not found")
    flag_memory("session_not_found", detail=f"conversation_id={conversation_id}")


def probe_long_term_storage(storage_dir: Optional[Path] = None) -> Dict:
    """长期记忆存储探针（/summary 记忆灯数据源）：三个 JSON 文件可解析 + 目录可写。

    返回 {status: green|critical, errors: [...]}；探针自身失败判 critical。
    """
    errors: List[str] = []
    import json
    d = storage_dir or LONG_TERM_DIR
    try:
        if d.exists():
            for name in _LONG_TERM_FILES:
                fp = d / name
                if not fp.exists():
                    continue
                try:
                    json.loads(fp.read_text(encoding="utf-8"))
                except Exception as e:
                    errors.append(f"{name} 解析失败: {e}")
        # 可写性探针：写临时文件再删除
        d.mkdir(parents=True, exist_ok=True)
        probe_fp = d / ".obs_probe"
        probe_fp.write_text("ok", encoding="utf-8")
        probe_fp.unlink()
    except Exception as e:
        errors.append(f"存储目录不可写: {e}")
    return {"status": "critical" if errors else "green", "errors": errors}


def memory_status(flags: Optional[List[str]], probe: Optional[Dict] = None) -> str:
    """flag 列表 + 存储探针 → 灯色：critical > warning > green"""
    flags = flags or []
    if any(f in CRITICAL_MEMORY_FLAGS for f in flags):
        return "critical"
    if (probe or {}).get("status") == "critical":
        return "critical"
    if flags:
        return "warning"
    return "green"
