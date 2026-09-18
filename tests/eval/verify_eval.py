"""验证评测框架"""
import sys
import os
# 添加 job-agent/ 到路径
job_agent_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, job_agent_root)

print("=" * 50)
print("  评测框架验证")
print("=" * 50)

# 1. 验证模型
try:
    from tests.eval.eval_models import EvalCase, EvalReport, QualityGates, UserProfile
    print("✅ eval_models: OK")
except Exception as e:
    print(f"❌ eval_models: {e}")

# 2. 验证评分器
try:
    from tests.eval.scorers.rule_scorer import RuleScorer
    scorer = RuleScorer()
    print("✅ rule_scorer: OK")
except Exception as e:
    print(f"❌ rule_scorer: {e}")

# 3. 验证评测用例
try:
    from tests.eval.eval_cases import get_all_cases, get_p0_cases, get_cases_by_module
    all_cases = get_all_cases()
    p0_cases = get_p0_cases()
    
    modules = {}
    for c in all_cases:
        modules[c.module] = modules.get(c.module, 0) + 1
    
    print(f"✅ eval_cases: {len(all_cases)} 条用例")
    print(f"   P0用例: {len(p0_cases)} 条")
    for module, count in sorted(modules.items()):
        print(f"   - {module}: {count} 条")
except Exception as e:
    print(f"❌ eval_cases: {e}")

# 4. 验证运行器
try:
    from tests.eval.eval_runner import EvalRunner
    runner = EvalRunner()
    print("✅ eval_runner: OK")
except Exception as e:
    print(f"❌ eval_runner: {e}")

# 5. 验证飞轮
try:
    from tests.eval.flywheel import FlywheelOrchestrator, BadCaseCollector, VersionComparator
    flywheel = FlywheelOrchestrator()
    print("✅ flywheel: OK")
except Exception as e:
    print(f"❌ flywheel: {e}")

# 6. 试运行几条P0用例
print("\n" + "-" * 50)
print("  试运行P0用例...")
print("-" * 50)

try:
    test_cases = p0_cases[:5]  # 取前5条P0
    report = runner.run_cases(test_cases, run_id="verify_run")
    print(f"\n试运行完成: 通过 {report.passed}/{report.total_cases}")
except Exception as e:
    print(f"试运行出错: {e}")

print("\n" + "=" * 50)
print("  验证完成!")
print("=" * 50)
