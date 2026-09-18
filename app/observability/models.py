"""观测数据模型（SDD §3.10）：请求观测记录 + 流式节奏 + 版本快照"""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class StreamMetrics(BaseModel):
    """SSE 流式节奏（B2 流式退化判定依据：gap_median < 5ms 即退化）"""
    delta_count: int = 0
    gap_median_ms: float = 0
    total_span_ms: float = 0


class VersionSnapshot(BaseModel):
    agent_version: str = ""
    git_hash: str = ""
    prompt_hash: str = ""
    model: str = ""


class RequestObservation(BaseModel):
    """requests.jsonl 一行（L2/L3/L4，线上域）；schema 演进只增不改"""
    model_config = ConfigDict(extra="ignore")

    trace_id: str
    source: str = "production"              # production | eval（流量隔离 D6）
    ts: str = ""
    path: str = ""
    method: str = ""
    status: str = "ok"                      # ok|error|interrupted|timeout
    status_code: int = 200
    duration_ms: float = 0
    ttft_ms: Optional[float] = None         # 请求进入 → 首个 text-delta
    stream: Optional[StreamMetrics] = None
    tokens: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    intent: Optional[str] = None            # M4 填充
    intent_confidence: Optional[float] = None
    intent_router: Optional[str] = None     # 路由来源：llm | rules（三级路由可观测）
    ambiguous: bool = False                 # M4：意图置信度 < 0.6
    clarified: bool = False                 # 低置信度澄清触发（高成本工具意图反问而非硬执行）
    conversation_id: Optional[int] = None
    msg_persisted: Optional[bool] = None    # M4：会话完整性（消息已入库）
    llm_calls: Optional[int] = None
    llm_duration_ms: Optional[float] = None
    llm_first_delta_ms: Optional[float] = None
    llm_error: Optional[str] = None         # 401/429/5xx/timeout 分类
    degraded: bool = False                  # LLM 出错但请求成功 = 服务层 fallback 兜底
    user_interrupted: bool = False          # SSE 生成器捕获 CancelledError
    waited_ms: Optional[float] = None       # 中断前等待时长
    card_count: Optional[int] = None        # M4：卡片产出数（L5）
    empty_reply: bool = False               # M4：空回复（L5）
    security_hit: bool = False              # M4：注入/敏感信息命中（横切）
    quality_flags: Optional[List[str]] = None  # M4：质量标记摘要
    memory_flags: Optional[List[str]] = None   # 记忆异常标记（短期trim/中期持久化/长期IO）
    spans: Optional[List[Dict]] = None      # M4（P1）：L4 决策链 plan/tool span
    message_preview: str = ""               # 截断 100 字符，脱敏
    error: Optional[str] = None
    version: Optional[VersionSnapshot] = None


class EvalSpan(BaseModel):
    """评测域 span（M5，四类 span 共用外层字段 + 各自 attrs）"""
    model_config = ConfigDict(extra="ignore")

    span: str                               # eval_run|case|judge_call|service_call
    run_id: str
    span_id: Optional[str] = None
    parent: Optional[str] = None
    start_ts: float = 0
    end_ts: float = 0
    attrs: Dict = {}
