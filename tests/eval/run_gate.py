"""质量门禁入口 — 全量/ P0 评测 + 门禁判定，进程退出码承载门禁结果。

用法:
    python tests/eval/run_gate.py                     # 全量 + 真实LLM，run_id 自动带时间戳
    python tests/eval/run_gate.py --run-id xxx        # 指定运行ID（结果落 results/{run_id}.json）
    python tests/eval/run_gate.py --p0-only           # 只跑 P0（提交前快速门禁）
    python tests/eval/run_gate.py --no-llm            # 不接真实LLM（规则基线，离线可跑）

退出码: 0=门禁通过  1=门禁未通过  2=运行错误（LLM不通等）
可直接接入 pre-commit / CI: 非零即拦截。
"""
import argparse
import sys
import os
from datetime import datetime

job_agent_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, job_agent_root)

from tests.eval.eval_cases import get_all_cases
from tests.eval.eval_runner import EvalRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="求职Agent质量门禁")
    parser.add_argument("--run-id", default="gate_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--p0-only", action="store_true", help="只跑P0用例（快速门禁）")
    parser.add_argument("--no-llm", action="store_true", help="不接真实LLM（规则基线）")
    args = parser.parse_args()

    if not args.no_llm:
        from app.core.config import settings
        from app.llm.client import QwenClient, set_llm_client
        qwen_client = QwenClient(api_key=settings.qwen_api_key, model=settings.qwen_model)
        try:
            qwen_client.chat_json_sync(
                [{"role": "user", "content": "回复一个json格式的结果，包含status字段"}],
                temperature=0.1,
            )
        except Exception as e:
            print(f"[gate] LLM连通失败，终止: {e}")
            return 2
        set_llm_client(qwen_client)
        print("[gate] 真实LLM已接入")
    else:
        print("[gate] 规则基线模式（不接LLM）")

    cases = get_all_cases()
    if args.p0_only:
        cases = [c for c in cases if c.priority == "P0"]
    print(f"[gate] 用例数: {len(cases)}  run_id: {args.run_id}")

    runner = EvalRunner()
    report = runner.run_cases(cases, run_id=args.run_id)

    print(f"[gate] 通过率: {report.pass_rate:.1%}  门禁: {'PASS' if report.gate_passed else 'FAIL'}")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    sys.exit(main())
