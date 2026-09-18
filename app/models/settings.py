"""用户设置数据模型 - SDD"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class UserPreferences(BaseModel):
    """用户偏好"""
    target_city: str = Field(default="杭州", description="目标城市")
    expected_salary_min: int = Field(default=27, description="期望最低总包(万/年)")
    target_positions: List[str] = Field(
        default=["AI测试开发", "AI Agent评测"],
        description="目标岗位方向"
    )
    excluded_keywords: List[str] = Field(default=["外包"], description="排除关键词")
    daily_apply_target: int = Field(default=12, description="每日投递目标")
    job_start_date: Optional[date] = Field(None, description="求职开始日期")
    llm_provider: str = Field(default="qwen", description="LLM提供商")
    llm_model: str = Field(default="qwen-plus", description="LLM模型")


class SettingsUpdate(BaseModel):
    """更新设置请求"""
    target_city: Optional[str] = None
    expected_salary_min: Optional[int] = None
    target_positions: Optional[List[str]] = None
    excluded_keywords: Optional[List[str]] = None
    daily_apply_target: Optional[int] = None
    job_start_date: Optional[date] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class DailyBelief(BaseModel):
    """每日信念"""
    content: str = Field(..., description="信念内容")
    category: str = Field(default="", description="分类: persist/confidence/growth/expression")


class JobSeekingStats(BaseModel):
    """求职统计"""
    days_count: int = Field(..., description="求职天数")
    total_applied: int = Field(default=0, description="累计投递")
    interview_count: int = Field(default=0, description="面试次数")
    offer_count: int = Field(default=0, description="offer数量")
