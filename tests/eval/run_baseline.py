"""运行全量评测，生成基线报告"""
import sys
import os

job_agent_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, job_agent_root)

from tests.eval.eval_cases import get_all_cases
from tests.eval.eval_runner import EvalRunner

print("=" * 60)
print("  求职Agent全面评测 — 基线报告")
print("=" * 60)

runner = EvalRunner()
cases = get_all_cases()
print(f"\n加载用例: {len(cases)} 条")

report = runner.run_cases(cases, run_id="baseline_v2_full")

print(f"\n{'=' * 60}")
print(f"  评测完成")
print(f"  总用例: {report.total_cases}")
print(f"  通过: {report.passed}  失败: {report.failed}  错误: {report.error}")
print(f"  通过率: {report.pass_rate:.1%}")
print(f"  质量门禁: {'通过' if report.gate_passed else '未通过'}")
print(f"{'=' * 60}")
