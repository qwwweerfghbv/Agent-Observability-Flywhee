"""投递管理API - SDD"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from loguru import logger

from app.models.application import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    ApplicationStats, DailyProgress
)
from app.services.application_service import ApplicationService

router = APIRouter(prefix="/api/application", tags=["投递管理"])

application_service = ApplicationService()


@router.post("", response_model=ApplicationResponse)
async def create_application(data: ApplicationCreate):
    """创建投递记录"""
    try:
        return application_service.create(data)
    except Exception as e:
        logger.error(f"创建投递记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ApplicationResponse])
async def list_applications(
    status: Optional[str] = Query(None, description="状态筛选"),
    limit: int = Query(50, description="返回数量")
):
    """获取投递列表"""
    try:
        return application_service.list(status, limit)
    except Exception as e:
        logger.error(f"获取投递列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ApplicationStats)
async def get_stats():
    """获取投递统计（必须定义在 /{application_id} 之前，否则 'stats' 被路径参数路由捕获致 422）"""
    try:
        return application_service.get_stats()
    except Exception as e:
        logger.error(f"获取投递统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(application_id: int):
    """获取投递记录"""
    try:
        result = application_service.get(application_id)
        if not result:
            raise HTTPException(status_code=404, detail="投递记录不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取投递记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(application_id: int, data: ApplicationUpdate):
    """更新投递记录"""
    try:
        result = application_service.update(application_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="投递记录不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新投递记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{application_id}")
async def delete_application(application_id: int):
    """删除投递记录"""
    try:
        success = application_service.delete(application_id)
        if not success:
            raise HTTPException(status_code=404, detail="投递记录不存在")
        return {"message": "投递记录删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除投递记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/today/progress", response_model=DailyProgress)
async def get_daily_progress():
    """获取今日投递进度"""
    try:
        return application_service.get_daily_progress()
    except Exception as e:
        logger.error(f"获取今日进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
