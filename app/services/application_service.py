"""投递管理服务 - SDD"""
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
from loguru import logger

from app.db.database import SessionLocal
from app.db.models import ApplicationRecord, JobRecord, ScoreRecord
from app.models.application import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    ApplicationStats, DailyProgress, ApplicationStatus
)


class ApplicationService:
    """投递管理服务"""
    
    def create(self, data: ApplicationCreate) -> ApplicationResponse:
        """创建投递记录"""
        db = SessionLocal()
        try:
            record = ApplicationRecord(
                job_id=data.job_id,
                resume_id=data.resume_id,
                apply_date=data.apply_date or date.today(),
                platform=data.platform,
                status=data.status.value if isinstance(data.status, ApplicationStatus) else data.status,
                notes=data.notes,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_response(record)
        finally:
            db.close()
    
    def get(self, application_id: int) -> Optional[ApplicationResponse]:
        """获取投递记录"""
        db = SessionLocal()
        try:
            record = db.query(ApplicationRecord).filter_by(id=application_id).first()
            return self._to_response(record) if record else None
        finally:
            db.close()
    
    def list(self, status: Optional[str] = None, limit: int = 50) -> List[ApplicationResponse]:
        """获取投递列表"""
        db = SessionLocal()
        try:
            query = db.query(ApplicationRecord)
            if status:
                query = query.filter(ApplicationRecord.status == status)
            records = query.order_by(ApplicationRecord.created_at.desc()).limit(limit).all()
            return [self._to_response(r) for r in records]
        finally:
            db.close()
    
    def update(self, application_id: int, data: ApplicationUpdate) -> Optional[ApplicationResponse]:
        """更新投递记录"""
        db = SessionLocal()
        try:
            record = db.query(ApplicationRecord).filter_by(id=application_id).first()
            if not record:
                return None
            
            if data.status is not None:
                record.status = data.status.value if isinstance(data.status, ApplicationStatus) else data.status
            if data.notes is not None:
                record.notes = data.notes
            record.updated_at = datetime.now()
            
            db.commit()
            db.refresh(record)
            return self._to_response(record)
        finally:
            db.close()
    
    def delete(self, application_id: int) -> bool:
        """删除投递记录"""
        db = SessionLocal()
        try:
            record = db.query(ApplicationRecord).filter_by(id=application_id).first()
            if record:
                db.delete(record)
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    def get_stats(self) -> ApplicationStats:
        """获取投递统计"""
        db = SessionLocal()
        try:
            today = date.today()
            week_start = today - timedelta(days=today.timetuple().tm_wday)  # 本周一
            
            today_count = db.query(ApplicationRecord).filter(
                ApplicationRecord.apply_date == today,
                ApplicationRecord.status == "applied"
            ).count()
            
            week_count = db.query(ApplicationRecord).filter(
                ApplicationRecord.apply_date >= week_start,
                ApplicationRecord.status == "applied"
            ).count()
            
            interview_count = db.query(ApplicationRecord).filter(
                ApplicationRecord.status == "interview"
            ).count()
            
            offer_count = db.query(ApplicationRecord).filter(
                ApplicationRecord.status == "offer"
            ).count()
            
            total_applied = db.query(ApplicationRecord).filter(
                ApplicationRecord.status == "applied"
            ).count()
            
            pass_rate = (interview_count / total_applied * 100) if total_applied > 0 else 0
            
            return ApplicationStats(
                today_count=today_count,
                week_count=week_count,
                interview_count=interview_count,
                offer_count=offer_count,
                pass_rate=round(pass_rate, 1),
                total_applied=total_applied
            )
        finally:
            db.close()
    
    def get_daily_progress(self, daily_target: int = 12) -> DailyProgress:
        """获取今日投递进度"""
        db = SessionLocal()
        try:
            today = date.today()
            
            applied_today = db.query(ApplicationRecord).filter(
                ApplicationRecord.apply_date == today,
                ApplicationRecord.status == "applied"
            ).count()
            
            # 有效投递（评分>=70）
            valid_applied = 0
            today_apps = db.query(ApplicationRecord).filter(
                ApplicationRecord.apply_date == today,
                ApplicationRecord.status == "applied"
            ).all()
            
            for app in today_apps:
                score = db.query(ScoreRecord).filter_by(job_id=app.job_id).first()
                if score and score.total_score >= 70:
                    valid_applied += 1
            
            remaining = max(0, daily_target - valid_applied)
            
            if remaining == 0:
                encouragement = "今天目标已完成！继续保持！"
            elif remaining <= 3:
                encouragement = "快完成了，加油！"
            else:
                encouragement = "继续努力，还差几个！"
            
            return DailyProgress(
                daily_target=daily_target,
                applied_today=applied_today,
                valid_applied=valid_applied,
                remaining=remaining,
                encouragement=encouragement
            )
        finally:
            db.close()
    
    def _to_response(self, record: ApplicationRecord) -> ApplicationResponse:
        """转换为响应模型"""
        return ApplicationResponse(
            id=record.id,
            job_id=record.job_id,
            resume_id=record.resume_id,
            apply_date=record.apply_date,
            platform=record.platform,
            status=record.status,
            notes=record.notes,
            created_at=record.created_at,
            updated_at=record.updated_at
        )
