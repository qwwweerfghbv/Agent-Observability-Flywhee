"""性能专项评测入口：系统级指标(K-001实测) + 体验层延迟(K-003全链路)

说明：
- K-001 延迟场景真实调用服务链路（真实LLM环境下测得真实LLM延迟）
- K-003 经HTTP全链路实测，需后端已在 http://127.0.0.1:8000 启动，
  未启动时用例自动跳过（skipped），不计入通过率
- LLM使用.env配置（默认qwen真实Key），会产生少量真实调用（约5-6次）
"""
import sys
import os

job_agent_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, job_agent_root)

from tests.eval.eval_cases_v2 import get_system_metric_cases, get_experience_layer_cases
from tests.eval.eval_runner import EvalRunner

print("=" * 60)
print("  求职Agent性能专项评测（K-001实测 + K-003全链路）")
print("=" * 60)

cases = get_system_metric_cases() + get_experience_layer_cases()
print(f"\n加载性能用例: {len(cases)} 条")

runner = EvalRunner()
report = runner.run_cases(cases, run_id="perf_eval")

print(f"\n{'=' * 60}")
print(f"  性能专项评测完成")
print(f"  总用例: {report.total_cases}  跳过: {report.skipped}")
print(f"  通过: {report.passed}  失败: {report.failed}  错误: {report.error}")
print(f"  通过率: {report.pass_rate:.1%}")
print(f"  P50延迟: {report.p50_latency_ms:.0f}ms  P95延迟: {report.p95_latency_ms:.0f}ms")
print(f"  累计Token: {report.total_tokens}  平均Token/任务: {report.avg_token_per_task:.0f}")
print(f"{'=' * 60}")
