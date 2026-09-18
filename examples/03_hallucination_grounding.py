"""示例 03 · 幻觉防线：以「库内简历」为唯一事实依据的接地机制

Agent 最典型的两类幻觉：
  1) 时间幻觉——问「今年几几年」，模型按训练截止年份作答；
  2) 简历编造——拿不到简历原文时，凭空「解析」出一段他人经历。

本示例展示 build_system_prompt 如何在系统提示里注入防线：
  - 始终写入「请求时刻的真实日期」，并禁用训练截止时间；
  - 有简历摘要时，标注为「唯一事实依据 / 不得编造」；
  - 无简历时，显式声明「尚未上传任何简历」，拒绝凭空生成。

运行：
    python examples/03_hallucination_grounding.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.prompts import PromptTemplates  # noqa: E402


def _check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


def main() -> None:
    year = str(datetime.now().year)

    print("=" * 60)
    print("场景 A：已上传简历 → 注入为「唯一事实依据」")
    print("-" * 60)
    grounded = PromptTemplates.build_system_prompt(
        resume_summary="姓名: 张三\n技能: Python, pytest"
    )
    _check(f"系统提示包含当前年份 {year}（抑制时间幻觉）", year in grounded)
    _check("标注「唯一事实依据」", "唯一事实依据" in grounded)
    _check("包含「不得编造」约束", "不得编造" in grounded)
    _check("简历摘要已接地（张三）", "张三" in grounded)

    print("=" * 60)
    print("场景 B：未上传简历 → 显式声明，拒绝凭空生成")
    print("-" * 60)
    empty = PromptTemplates.build_system_prompt(resume_summary="")
    _check("声明「尚未上传任何简历」", "尚未上传任何简历" in empty)
    _check("禁用「训练截止时间」作答", "训练截止时间" in empty)

    print("=" * 60)
    print("结论：接地信息随每次请求动态注入系统提示，从源头收敛幻觉。")
    print("=" * 60)


if __name__ == "__main__":
    main()
