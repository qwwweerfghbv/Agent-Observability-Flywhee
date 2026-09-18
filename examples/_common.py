"""examples 共享的最小样例数据（全部虚构，不含任何真实 PII）。

单独抽出以避免各示例重复；示例脚本会把仓库根加入 import 路径后再引用本模块。
"""
from __future__ import annotations

from app.models.job import JobData, JobRequirement
from app.models.resume import Project, ResumeData, Skill, WorkExperience


def build_resume() -> ResumeData:
    """构造一份「测试开发」背景的样例简历。"""
    return ResumeData(
        name="张三",
        location="杭州",
        years_of_experience=5,
        skills=[
            Skill(name="Python", level="精通", category="编程语言"),
            Skill(name="pytest", level="精通", category="测试框架"),
            Skill(name="Selenium", level="熟练", category="测试工具"),
            Skill(name="CI/CD", level="熟练", category="工程实践"),
        ],
        work_experiences=[
            WorkExperience(
                company="杭州某互联网公司",
                position="高级测试开发工程师",
                start_date="2021.07",
                description="负责自动化测试框架设计与 AI 模型测试方案落地",
                achievements=["搭建 CI/CD 测试流水线", "主导 AI 模型测试方案"],
            )
        ],
        projects=[
            Project(
                name="AI 模型自动化测试平台",
                role="技术负责人",
                technologies=["Python", "pytest", "FastAPI", "Docker"],
                achievements=["支持准确率/召回率/F1 指标自动化计算"],
            )
        ],
        summary="5 年测试开发经验，专注自动化测试与 AI 模型测试",
    )


def build_job() -> JobData:
    """构造一个「AI 测试开发工程师」样例岗位。"""
    return JobData(
        title="AI 测试开发工程师",
        company="某科技公司",
        location="杭州",
        salary_min=30,
        salary_max=50,
        years_required=3,
        education_required="本科",
        requirements=[
            JobRequirement(skill="Python", required=True, level="熟练"),
            JobRequirement(skill="pytest", required=True, level="熟练"),
            JobRequirement(skill="AI模型测试", required=True, level="了解"),
            JobRequirement(skill="CI/CD", required=False, level="熟悉"),
        ],
        responsibilities=["负责 AI 模型测试方案设计与实施", "搭建和维护自动化测试框架"],
    )
