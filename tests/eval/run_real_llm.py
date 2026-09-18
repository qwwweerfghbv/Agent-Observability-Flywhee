"""用真实通义千问LLM运行评测"""
import sys
import os

job_agent_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, job_agent_root)

from tests.eval.eval_cases import get_all_cases
from tests.eval.eval_runner import EvalRunner
from app.core.config import settings
from app.llm.client import QwenClient, set_llm_client

print("=" * 60)
print("  求职Agent全面评测 — 真实LLM评测")
print("=" * 60)

# 设置真实LLM客户端（Key/模型从.env配置读取，避免硬编码过期）
print("\n[1] 初始化通义千问客户端...")
qwen_client = QwenClient(api_key=settings.qwen_api_key, model=settings.qwen_model)
set_llm_client(qwen_client)
print("    ✅ 通义千问客户端已设置")

# 先测试LLM连通性
print("\n[2] 测试LLM连通性...")
try:
    test_result = qwen_client.chat_json_sync(
        [{"role": "user", "content": "回复一个json格式的结果，包含status字段"}],
        temperature=0.1
    )
    print(f"    ✅ LLM连通成功: {test_result}")
except Exception as e:
    print(f"    ❌ LLM连通失败: {e}")
    sys.exit(1)

# 运行评测
print("\n[3] 加载评测用例...")
runner = EvalRunner()
cases = get_all_cases()
print(f"    加载用例: {len(cases)} 条")

print("\n[4] 开始评测（使用真实LLM，预计耗时较长）...")
print("-" * 60)
report = runner.run_cases(cases, run_id="real_llm_eval")

print(f"\n{'=' * 60}")
print(f"  评测完成")
print(f"  总用例: {report.total_cases}")
print(f"  通过: {report.passed}  失败: {report.failed}  错误: {report.error}")
print(f"  通过率: {report.pass_rate:.1%}")
print(f"  质量门禁: {'✅ 通过' if report.gate_passed else '❌ 未通过'}")
print(f"{'=' * 60}")
