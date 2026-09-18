"""数据模型单元测试"""
import pytest
from app.models.resume import ResumeData, Education, WorkExperience, Project, Skill
from app.models.job import JobData, JobRequirement, JobBenefit
from app.models.score import ScoreResult, ScoreDetail, SkillMatch


class TestResumeData:
    """简历数据模型测试"""
    
    def test_create_resume_data(self, sample_resume_data):
        """测试创建简历数据"""
        resume = ResumeData(**sample_resume_data)
        
        assert resume.name == "张三"
        assert resume.phone == "13800138000"
        assert resume.years_of_experience == 5
        assert len(resume.skills) == 3
        assert len(resume.work_experiences) == 1
    
    def test_get_all_skills(self, sample_resume_data):
        """测试获取所有技能"""
        resume = ResumeData(**sample_resume_data)
        skills = resume.get_all_skills()
        
        assert "Python" in skills
        assert "Django" in skills
        assert "MySQL" in skills
    
    def test_get_all_keywords(self, sample_resume_data):
        """测试获取所有关键词"""
        resume = ResumeData(**sample_resume_data)
        keywords = resume.get_all_keywords()
        
        assert len(keywords) > 0
    
    def test_to_text(self, sample_resume_data):
        """测试转换为文本"""
        resume = ResumeData(**sample_resume_data)
        text = resume.to_text()
        
        assert "张三" in text
        assert "Python" in text
        assert "阿里巴巴" in text


class TestJobData:
    """岗位数据模型测试"""
    
    def test_create_job_data(self, sample_job_data):
        """测试创建岗位数据"""
        job = JobData(**sample_job_data)
        
        assert job.title == "高级Python工程师"
        assert job.company == "某科技公司"
        assert job.location == "杭州"
        assert len(job.requirements) == 3
    
    def test_get_required_skills(self, sample_job_data):
        """测试获取必须技能"""
        job = JobData(**sample_job_data)
        required = job.get_required_skills()
        
        assert "Python" in required
        assert "Django" in required
    
    def test_get_all_skills(self, sample_job_data):
        """测试获取所有技能"""
        job = JobData(**sample_job_data)
        skills = job.get_all_skills()
        
        assert len(skills) == 3


class TestScoreResult:
    """评分结果模型测试"""
    
    def test_calculate_total(self):
        """测试计算总分"""
        detail = ScoreDetail(
            skill_score=80,
            experience_score=70,
            salary_score=60,
            stability_score=90,
            growth_score=100
        )
        
        result = ScoreResult(
            resume_id=1,
            job_id=1,
            detail=detail
        )
        
        total = result.calculate_total()
        
        # 80*0.30 + 70*0.20 + 60*0.15 + 90*0.25 + 100*0.10 = 24 + 14 + 9 + 22.5 + 10 = 79.5
        assert total == 79.5
        assert result.score_level == "B"
    
    def test_get_score_level(self):
        """测试评分等级"""
        result = ScoreResult(resume_id=1, job_id=1)
        
        result.total_score = 90
        assert result.get_score_level() == "A"
        
        result.total_score = 75
        assert result.get_score_level() == "B"
        
        result.total_score = 60
        assert result.get_score_level() == "C"
        
        result.total_score = 40
        assert result.get_score_level() == "D"
