"""评测框架独立运行脚本

使用方式:
    # 在项目根目录下运行
    cd job-agent
    python -m tests.eval.run_eval_script

    # 或者
    python tests/eval/run_eval_script.py

支持的命令:
    # 运行全部评测
    python tests/eval/run_eval_script.py --all

    # 仅运行P0门禁
    python tests/eval/run_eval_script.py --p0

    # 按模块运行
    python tests/eval/run_eval_script.py --module resume_parse
    python tests/eval/run_eval_script.py --module job_score
    python tests/eval/run_eval_script.py --module security

    # 版本对比
    python tests/eval/run_eval_script.py --compare run_20260904_100000 run_20260904_120000

    # 列出所有评测运行
    python tests/eval/run_eval_script.py --list-runs
"""
import sys
import os
import argparse

# 确保项目根目录在路径中 (tests/eval/ -> job-agent/)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tests.eval.eval_runner import EvalRunner
from tests.eval.eval_cases import (
    get_all_cases, get_p0_cases, get_cases_by_module
)
from tests.eval.flywheel import FlywheelOrchestrator, VersionComparator


def main():
    parser = argparse.ArgumentParser(description="求职Agent评测框架")
    parser.add_argument("--all", action="store_true", help="运行全部评测用例")
    parser.add_argument("--p0", action="store_true", help="仅运行P0门禁用例")
    parser.add_argument("--module", type=str, help="按模块运行评测")
    parser.add_argument("--compare", nargs=2, metavar=("OLD_RUN", "NEW_RUN"), help="版本对比")
    parser.add_argument("--list-runs", action="store_true", help="列出所有评测运行")
    parser.add_argument("--flywheel", action="store_true", help="运行评测并触发飞轮")
    parser.add_argument("--compare-with", type=str, help="与指定版本对比")
    
    args = parser.parse_args()
    
    runner = EvalRunner()
    
    if args.all:
        print("\n🚀 运行全部评测用例...")
        cases = get_all_cases()
        report = runner.run_cases(cases)
        
        if args.flywheel:
            flywheel = FlywheelOrchestrator()
            flywheel.run_eval_and_flywheel(report, compare_with=args.compare_with)
        
        return 0 if report.gate_passed else 1
    
    elif args.p0:
        print("\n🔒 运行P0质量门禁...")
        cases = get_p0_cases()
        report = runner.run_cases(cases, run_id="p0_gate")
        return 0 if report.gate_passed else 1
    
    elif args.module:
        print(f"\n📋 运行模块评测: {args.module}")
        cases = get_cases_by_module(args.module)
        if not cases:
            print(f"❌ 模块 '{args.module}' 没有评测用例")
            return 1
        report = runner.run_cases(cases, run_id=f"module_{args.module}")
        return 0 if report.pass_rate >= 0.70 else 1
    
    elif args.compare:
        old_run, new_run = args.compare
        comparator = VersionComparator()
        comparison = comparator.compare(old_run, new_run)
        comparator.print_comparison(comparison)
        return 1 if comparison.get("is_regression") else 0
    
    elif args.list_runs:
        flywheel = FlywheelOrchestrator()
        runs = flywheel.list_eval_runs()
        if not runs:
            print("暂无评测记录")
            return 0
        
        print(f"\n{'运行ID':<30} {'时间':<25} {'版本':<10} {'用例数':<8} {'通过率':<10} {'门禁'}")
        print("-" * 90)
        for run in runs:
            gate_icon = "✅" if run.get("gate_passed") else "❌"
            print(f"{run['run_id']:<30} {run['timestamp']:<25} {run.get('agent_version', ''):<10} "
                  f"{run.get('total_cases', 0):<8} {run.get('pass_rate', 0):.1%}     {gate_icon}")
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
