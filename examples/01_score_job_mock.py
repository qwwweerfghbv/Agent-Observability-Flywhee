"""示例 01 · 零门槛跑通「岗位评分」（Mock 模式，无需任何 API Key）

演示：构造一份简历 + 一个岗位 → 调用 JobScorerService → 打印 5 维加权评分与建议。
MockClient 返回结构逼真的假数据，用于验证业务链路，不消耗任何 Token。

运行：
    python examples/01_score_job_mock.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 把仓库根目录加入 import 路径，使示例可从任意工作目录直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import build_job, build_resume  # noqa: E402
from app.llm.client import MockClient, set_llm_client  # noqa: E402
from app.services.job_scorer import JobScorerService  # noqa: E402


def main() -> None:
    # 关键一行：注入 Mock 客户端（等价于 LLM_PROVIDER=mock），全程无需 API Key
    set_llm_client(MockClient())

    result = JobScorerService().score(build_resume(), build_job())
    d = result.detail

    print("=" * 52)
    print(f"综合得分：{result.total_score}  （等级 {result.score_level}）")
    print("-" * 52)
    print(f"  技能匹配 : {d.skill_score}")
    print(f"  经验匹配 : {d.experience_score}")
    print(f"  薪资匹配 : {d.salary_score}")
    print(f"  岗位稳定 : {d.stability_score}")
    print(f"  发展前景 : {d.growth_score}")
    print("-" * 52)
    print(f"命中技能：{', '.join(d.matched_skills) or '无'}")
    print(f"缺失技能：{', '.join(d.missing_skills) or '无'}")
    if result.strengths:
        print(f"优势    ：{result.strengths[0]}")
    if result.ai_advice:
        print(f"AI 建议 ：{result.ai_advice}")
    print("=" * 52)


if __name__ == "__main__":
    main()
