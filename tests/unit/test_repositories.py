"""数据库层单元测试"""
import pytest
from app.db.repositories import ResumeRepository, JobRepository, ScoreRepository
from app.models.resume import ResumeData
from app.models.job import JobData
from app.models.score import ScoreResult, ScoreDetail


class TestResumeRepository:
    """简历仓库测试"""
    
    def test_create_resume(self, db_session, sample_resume_data):
        """测试创建简历"""
        repo = ResumeRepository(db_session)
        resume_data = ResumeData(**sample_resume_data)
        
        record = repo.create(resume_data, "原始简历文本")
        
        assert record.id is not None
        assert record.name == "张三"
        assert record.location == "杭州"
    
    def test_get_resume_by_id(self, db_session, sample_resume_data):
        """测试根据ID获取简历"""
        repo = ResumeRepository(db_session)
        resume_data = ResumeData(**sample_resume_data)
        
        created = repo.create(resume_data)
        fetched = repo.get_by_id(created.id)
        
        assert fetched is not None
        assert fetched.name == "张三"
    
    def test_get_all_resumes(self, db_session, sample_resume_data):
        """测试获取所有简历"""
        repo = ResumeRepository(db_session)
        resume_data = ResumeData(**sample_resume_data)
        
        repo.create(resume_data)
        repo.create(resume_data)
        
        all_resumes = repo.get_all()
        assert len(all_resumes) == 2
    
    def test_delete_resume(self, db_session, sample_resume_data):
        """测试删除简历"""
        repo = ResumeRepository(db_session)
        resume_data = ResumeData(**sample_resume_data)
        
        record = repo.create(resume_data)
        assert repo.delete(record.id) is True
        assert repo.get_by_id(record.id) is None


class TestJobRepository:
    """岗位仓库测试"""
    
    def test_create_job(self, db_session, sample_job_data):
        """测试创建岗位"""
        repo = JobRepository(db_session)
        job_data = JobData(**sample_job_data)
        
        record = repo.create(job_data, "原始JD文本")
        
        assert record.id is not None
        assert record.title == "高级Python工程师"
    
    def test_get_job_by_id(self, db_session, sample_job_data):
        """测试根据ID获取岗位"""
        repo = JobRepository(db_session)
        job_data = JobData(**sample_job_data)
        
        created = repo.create(job_data)
        fetched = repo.get_by_id(created.id)
        
        assert fetched is not None
        assert fetched.title == "高级Python工程师"


class TestScoreRepository:
    """评分仓库测试"""
    
    def test_create_score(self, db_session):
        """测试创建评分"""
        repo = ScoreRepository(db_session)
        
        score_result = ScoreResult(
            resume_id=1,
            job_id=1,
            total_score=75.5,
            score_level="B",
            detail=ScoreDetail(
                skill_score=80,
                experience_score=70,
                salary_score=60,
                stability_score=90,
                growth_score=100
            ),
            ai_advice="建议加强Redis学习"
        )
        
        record = repo.create(score_result)
        
        assert record.id is not None
        assert record.total_score == 75.5
        assert record.score_level == "B"
    
    def test_get_scores_by_resume(self, db_session):
        """测试获取简历的所有评分"""
        repo = ScoreRepository(db_session)
        
        for i in range(3):
            score_result = ScoreResult(
                resume_id=1,
                job_id=i+1,
                total_score=70 + i*5,
                score_level="B",
                detail=ScoreDetail()
            )
            repo.create(score_result)
        
        scores = repo.get_by_resume(1)
        assert len(scores) == 3
