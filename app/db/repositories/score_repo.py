"""评分数据访问"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models import ScoreRecord
from app.models.score import ScoreResult, ScoreDetail


class ScoreRepository:
    """评分数据仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, score_result: ScoreResult) -> ScoreRecord:
        """创建评分记录"""
        record = ScoreRecord(
            resume_id=score_result.resume_id,
            job_id=score_result.job_id,
            total_score=score_result.total_score,
            score_level=score_result.score_level,
            detail_json=score_result.detail.model_dump(mode='json'),
            ai_advice=score_result.ai_advice,
            strengths=score_result.strengths,
            weaknesses=score_result.weaknesses,
            suggestions=score_result.suggestions
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_by_id(self, score_id: int) -> Optional[ScoreRecord]:
        """根据ID获取评分"""
        return self.db.query(ScoreRecord).filter(ScoreRecord.id == score_id).first()
    
    def get_by_resume_and_job(self, resume_id: int, job_id: int) -> Optional[ScoreRecord]:
        """根据简历ID和岗位ID获取评分"""
        return self.db.query(ScoreRecord).filter(
            ScoreRecord.resume_id == resume_id,
            ScoreRecord.job_id == job_id
        ).first()
    
    def get_by_resume(self, resume_id: int, limit: int = 10) -> List[ScoreRecord]:
        """获取简历的所有评分"""
        return self.db.query(ScoreRecord).filter(
            ScoreRecord.resume_id == resume_id
        ).order_by(ScoreRecord.created_at.desc()).limit(limit).all()
    
    def get_by_job(self, job_id: int, limit: int = 10) -> List[ScoreRecord]:
        """获取岗位的所有评分"""
        return self.db.query(ScoreRecord).filter(
            ScoreRecord.job_id == job_id
        ).order_by(ScoreRecord.created_at.desc()).limit(limit).all()
    
    def get_all(self, limit: int = 100) -> List[ScoreRecord]:
        """获取所有评分"""
        return self.db.query(ScoreRecord).order_by(
            ScoreRecord.created_at.desc()
        ).limit(limit).all()
    
    def delete(self, score_id: int) -> bool:
        """删除评分"""
        record = self.get_by_id(score_id)
        if not record:
            return False
        
        self.db.delete(record)
        self.db.commit()
        return True
    
    def get_score_result(self, score_id: int) -> Optional[ScoreResult]:
        """获取评分结果"""
        record = self.get_by_id(score_id)
        if not record:
            return None
        return ScoreResult(
            resume_id=record.resume_id,
            job_id=record.job_id,
            total_score=record.total_score,
            score_level=record.score_level,
            detail=ScoreDetail(**record.detail_json),
            ai_advice=record.ai_advice,
            strengths=record.strengths or [],
            weaknesses=record.weaknesses or [],
            suggestions=record.suggestions or [],
            created_at=record.created_at
        )
