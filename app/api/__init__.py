"""API路由模块 - 按SDD文档设计"""
from app.api.resume import router as resume_router
from app.api.job import router as job_router
from app.api.interview import router as interview_router
from app.api.chat import router as chat_router
from app.api.application import router as application_router
from app.api.settings import router as settings_router
from app.api.upload import router as upload_router
from app.api.observability import router as observability_router

__all__ = [
    "resume_router",
    "job_router",
    "interview_router",
    "chat_router",
    "application_router",
    "settings_router",
    "upload_router",
    "observability_router",
]
