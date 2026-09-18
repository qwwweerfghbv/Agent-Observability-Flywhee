"""测试配置"""
import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import ResumeRecord, JobRecord, ScoreRecord


@pytest.fixture(scope="function")
def db_session():
    """创建测试数据库会话"""
    # 使用内存SQLite
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


@pytest.fixture
def sample_resume_data():
    """示例简历数据"""
    return {
        "name": "张三",
        "phone": "13800138000",
        "email": "zhangsan@example.com",
        "location": "杭州",
        "years_of_experience": 5,
        "educations": [
            {"school": "浙江大学", "degree": "硕士", "major": "计算机科学"}
        ],
        "work_experiences": [
            {
                "company": "阿里巴巴",
                "position": "高级工程师",
                "start_date": "2020-01",
                "end_date": "至今",
                "description": "负责后端开发",
                "achievements": ["优化系统性能30%"]
            }
        ],
        "projects": [
            {
                "name": "电商平台",
                "role": "技术负责人",
                "technologies": ["Python", "Django", "Redis", "MySQL"],
                "achievements": ["日活100万"]
            }
        ],
        "skills": [
            {"name": "Python", "level": "精通", "category": "编程语言"},
            {"name": "Django", "level": "掌握", "category": "框架"},
            {"name": "MySQL", "level": "掌握", "category": "数据库"}
        ],
        "summary": "5年后端开发经验"
    }


@pytest.fixture
def sample_job_data():
    """示例岗位数据"""
    return {
        "title": "高级Python工程师",
        "company": "某科技公司",
        "location": "杭州",
        "salary_min": 30,
        "salary_max": 50,
        "years_required": 3,
        "education_required": "本科",
        "requirements": [
            {"skill": "Python", "required": True, "level": "精通"},
            {"skill": "Django", "required": True, "level": "掌握"},
            {"skill": "Redis", "required": False, "level": "了解"}
        ],
        "responsibilities": [
            "负责后端系统开发",
            "优化系统性能"
        ]
    }
