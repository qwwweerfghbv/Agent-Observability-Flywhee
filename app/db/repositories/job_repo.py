"""岗位数据访问"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models import JobRecord
from app.models.job import JobData


class JobRepository:
    """岗位数据仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, job_data: JobData, raw_text: str = "") -> JobRecord:
        """创建岗位记录"""
        data_dict = job_data.model_dump(mode='json')
        
        record = JobRecord(
            title=job_data.title,
            company=job_data.company,
            location=job_data.location,
            salary_min=job_data.salary_min,
            salary_max=job_data.salary_max,
            data_json=data_dict,
            raw_text=raw_text or job_data.raw_text
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_by_id(self, job_id: int) -> Optional[JobRecord]:
        """根据ID获取岗位"""
        return self.db.query(JobRecord).filter(JobRecord.id == job_id).first()
    
    def get_all(self, limit: int = 100) -> List[JobRecord]:
        """获取所有岗位"""
        return self.db.query(JobRecord).order_by(
            JobRecord.created_at.desc()
        ).limit(limit).all()
    
    def update(self, job_id: int, job_data: JobData) -> Optional[JobRecord]:
        """更新岗位"""
        record = self.get_by_id(job_id)
        if not record:
            return None
        
        record.title = job_data.title
        record.company = job_data.company
        record.location = job_data.location
        record.salary_min = job_data.salary_min
        record.salary_max = job_data.salary_max
        record.data_json = job_data.model_dump(mode='json')
        
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def delete(self, job_id: int) -> bool:
        """删除岗位"""
        record = self.get_by_id(job_id)
        if not record:
            return False
        
        self.db.delete(record)
        self.db.commit()
        return True
    
    def get_job_data(self, job_id: int) -> Optional[JobData]:
        """获取岗位结构化数据"""
        record = self.get_by_id(job_id)
        if not record:
            return None
        return JobData(**record.data_json)
