"""简历数据访问"""
from typing import List, Optional
from sqlalchemy.orm import Session
import json

from app.db.models import ResumeRecord
from app.models.resume import ResumeData


class ResumeRepository:
    """简历数据仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, resume_data: ResumeData, raw_text: str = "") -> ResumeRecord:
        """创建简历记录"""
        # 转换为dict并处理datetime
        data_dict = resume_data.model_dump(mode='json')
        
        record = ResumeRecord(
            name=resume_data.name,
            phone=resume_data.phone,
            email=resume_data.email,
            location=resume_data.location,
            years_of_experience=resume_data.years_of_experience,
            data_json=data_dict,
            raw_text=raw_text or resume_data.raw_text
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_by_id(self, resume_id: int) -> Optional[ResumeRecord]:
        """根据ID获取简历"""
        return self.db.query(ResumeRecord).filter(ResumeRecord.id == resume_id).first()
    
    def get_all(self, limit: int = 100) -> List[ResumeRecord]:
        """获取所有简历"""
        return self.db.query(ResumeRecord).order_by(
            ResumeRecord.created_at.desc()
        ).limit(limit).all()
    
    def get_base(self) -> Optional[ResumeRecord]:
        """基础简历：与简历中心 UI 一致取最新一条。

        is_base 列历史遗留默认全为 True，filter_by(is_base).first() 会拿到
        最旧记录，与 UI「第一条为基础简历」矛盾，故统一以创建时间倒序为准。
        """
        return self.db.query(ResumeRecord).order_by(
            ResumeRecord.created_at.desc()
        ).first()
    
    def update(self, resume_id: int, resume_data: ResumeData) -> Optional[ResumeRecord]:
        """更新简历"""
        record = self.get_by_id(resume_id)
        if not record:
            return None
        
        record.name = resume_data.name
        record.phone = resume_data.phone
        record.email = resume_data.email
        record.location = resume_data.location
        record.years_of_experience = resume_data.years_of_experience
        record.data_json = resume_data.model_dump(mode='json')
        
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def delete(self, resume_id: int) -> bool:
        """删除简历"""
        record = self.get_by_id(resume_id)
        if not record:
            return False
        
        self.db.delete(record)
        self.db.commit()
        return True
    
    def get_resume_data(self, resume_id: int) -> Optional[ResumeData]:
        """获取简历结构化数据"""
        record = self.get_by_id(resume_id)
        if not record:
            return None
        return ResumeData(**record.data_json)
