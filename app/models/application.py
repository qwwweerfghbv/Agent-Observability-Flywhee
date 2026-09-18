"""投递记录数据模型 - SDD"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date
from enum import Enum


class ApplicationStatus(str, Enum):
    """投递状态"""
    PENDING = "pending"                    # 待投递
    APPLIED = "applied"                    # 已投递
    SCREENING = "screening"                # 简历筛选中
    INTERVIEW = "interview"                # 面试中
    OFFER = "offer"                        # 收到offer
    REJECTED = "rejected"                  # 被拒
    INAPPROPRIATE = "inappropriate"        # 不合适


class ApplicationCreate(BaseModel):
    """创建投递记录"""
    job_id: int = Field(..., description="岗位ID")
    resume_id: Optional[int] = Field(None, description="简历ID")
    apply_date: Optional[date] = Field(None, description="投递日期")
    platform: str = Field(default="", description="投递平台: Boss/猎聘/拉勾")
    status: ApplicationStatus = Field(default=ApplicationStatus.PENDING, description="状态")
    notes: str = Field(default="", description="备注")


class ApplicationUpdate(BaseModel):
    """更新投递记录"""
    status: Optional[ApplicationStatus] = Field(None, description="状态")
    notes: Optional[str] = Field(None, description="备注")


class ApplicationResponse(BaseModel):
    """投递记录响应"""
    id: int
    job_id: int
    resume_id: Optional[int] = None
    apply_date: Optional[date] = None
    platform: str
    status: ApplicationStatus
    notes: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ApplicationStats(BaseModel):
    """投递统计"""
    today_count: int = Field(default=0, description="今日投递数")
    week_count: int = Field(default=0, description="本周投递数")
    interview_count: int = Field(default=0, description="面试邀请数")
    offer_count: int = Field(default=0, description="offer数")
    pass_rate: float = Field(default=0, description="通过率")
    total_applied: int = Field(default=0, description="累计投递数")


class DailyProgress(BaseModel):
    """今日投递进度"""
    daily_target: int = Field(..., description="每日目标")
    applied_today: int = Field(..., description="今日已投递")
    valid_applied: int = Field(..., description="今日有效投递（评分>=70）")
    remaining: int = Field(..., description="还需投递")
    encouragement: str = Field(default="", description="鼓励语")
