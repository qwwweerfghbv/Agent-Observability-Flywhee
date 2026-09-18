"""可观测性模块（SDD §3.2 / §4.1 / §5.1，M1）

设计原则：
- ContextVar 传递观测上下文，各层就地 fill()，不改业务函数签名
- 全链路静默降级：任何埋点/落盘失败仅 loguru.warning，绝不影响主链路
- 字段命名对齐 OTel 语义约定（trace_id/duration_ms/status）
"""
