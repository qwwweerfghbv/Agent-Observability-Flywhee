"""数据访问层"""
from app.db.repositories.resume_repo import ResumeRepository
from app.db.repositories.job_repo import JobRepository
from app.db.repositories.score_repo import ScoreRepository

__all__ = ["ResumeRepository", "JobRepository", "ScoreRepository"]
