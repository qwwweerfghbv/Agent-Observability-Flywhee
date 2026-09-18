"""示例 02 · 可观测：一次调用的完整 Trace 是如何被采集的

这是本项目最核心的差异化能力——「七层可观测」的最小内核：
  ① begin_context 建立请求上下文（线上由中间件自动完成）；
  ② 业务执行过程中，各层「就地填充」埋点（fill / add_span / add_llm_metrics）；
  ③ get_context 读回一条结构化 Trace，可落盘、可回放、可聚合、可告警。

运行：
    python examples/02_observability_trace.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import build_job, build_resume  # noqa: E402
from app.llm.client import MockClient, set_llm_client  # noqa: E402
from app.observability.context import (  # noqa: E402
    add_span,
    begin_context,
    fill,
    get_context,
)
from app.services.job_scorer import JobScorerService  # noqa: E402


def main() -> None:
    set_llm_client(MockClient())

    # ① 请求开始：建立上下文，拿到贯穿全链路的 trace_id 与版本快照
    begin_context(source="production", intent="evaluate_job")

    # ② 业务执行：过程中各层就地追加埋点
    t0 = time.time()
    add_span("planner.route", intent="evaluate_job", router="rules")
    result = JobScorerService().score(build_resume(), build_job())
    add_span("tool.score_job", total_score=result.total_score, level=result.score_level)
    fill(duration_ms=round((time.time() - t0) * 1000, 1))

    # ③ 请求结束：读回这条结构化 Trace
    ctx = get_context() or {}
    tokens = ctx.get("tokens")

    print("=" * 60)
    print("一次请求采集到的 Trace（七层可观测的最小内核）")
    print("-" * 60)
    print(f"trace_id : {ctx.get('trace_id')}")
    print(f"intent   : {ctx.get('intent')}")
    print(f"duration : {ctx.get('duration_ms')} ms")
    print(f"tokens   : {tokens if tokens else '（Mock 模式不产生真实 token；接入 qwen/openai 后自动回填）'}")
    print(f"version  : {ctx.get('version')}")
    print("spans    :")
    for s in ctx.get("spans", []):
        attrs = {k: v for k, v in s.items() if k not in ("span", "ts")}
        print(f"  - {s['span']:<18} {attrs}")
    print("=" * 60)


if __name__ == "__main__":
    main()
