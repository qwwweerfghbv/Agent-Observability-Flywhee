"""设置API - SDD"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.settings import UserPreferences, SettingsUpdate, DailyBelief, JobSeekingStats
from app.services.settings_service import SettingsService
from app.services.belief_service import BeliefService
from app.services.application_service import ApplicationService

router = APIRouter(prefix="/api/settings", tags=["设置"])

settings_service = SettingsService()
belief_service = BeliefService()
application_service = ApplicationService()


@router.get("", response_model=UserPreferences)
async def get_preferences():
    """获取用户偏好"""
    try:
        return settings_service.get_preferences()
    except Exception as e:
        logger.error(f"获取用户偏好失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("", response_model=UserPreferences)
async def update_preferences(data: SettingsUpdate):
    """更新用户偏好"""
    try:
        return settings_service.update_preferences(data)
    except Exception as e:
        logger.error(f"更新用户偏好失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/belief/today", response_model=DailyBelief)
async def get_today_belief():
    """获取今日信念"""
    try:
        return belief_service.get_today_belief()
    except Exception as e:
        logger.error(f"获取今日信念失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job-seeking-stats", response_model=JobSeekingStats)
async def get_job_seeking_stats():
    """获取求职统计"""
    try:
        prefs = settings_service.get_preferences()
        belief_info = belief_service.get_job_seeking_days(prefs.job_start_date)
        stats = application_service.get_stats()
        
        return JobSeekingStats(
            days_count=belief_info.get("days_count", 0),
            total_applied=stats.total_applied,
            interview_count=stats.interview_count,
            offer_count=stats.offer_count
        )
    except Exception as e:
        logger.error(f"获取求职统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
