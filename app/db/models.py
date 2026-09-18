"""数据库ORM模型 - 按SDD文档设计"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, Boolean, Date, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime

from app.db.database import Base


class ResumeRecord(Base):
    """简历记录表"""
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 基本信息
    name = Column(String(100), default="")
    phone = Column(String(20), default="")
    email = Column(String(100), default="")
    location = Column(String(50), default="")
    years_of_experience = Column(Integer, default=0)
    
    # 结构化数据（JSON）
    data_json = Column(JSON, nullable=False)
    
    # 原始文本
    raw_text = Column(Text, default="")
    
    # 简历类型
    is_base = Column(Boolean, default=True)  # 是否为基础简历
    base_resume_id = Column(Integer, nullable=True)  # 关联的基础简历ID（定制版）
    target_job_id = Column(Integer, nullable=True)  # 针对的岗位ID（定制版）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class JobRecord(Base):
    """岗位记录表"""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 基本信息
    title = Column(String(200), nullable=False)
    company = Column(String(100), default="")
    location = Column(String(50), default="")
    salary_min = Column(Integer, default=0)
    salary_max = Column(Integer, default=0)
    
    # 结构化数据（JSON）
    data_json = Column(JSON, nullable=False)
    
    # 原始文本
    raw_text = Column(Text, default="")
    
    # 来源
    source_url = Column(String(500), default="")
    source_platform = Column(String(50), default="")
    
    # 稳定性信号（SDD新增）
    stability_signals = Column(JSON, default=dict)  # 稳定性评估信号
    ai_replacement_risk = Column(Integer, default=50)  # AI替代风险(0-100)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)


class ScoreRecord(Base):
    """评分记录表"""
    __tablename__ = "scores"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联ID
    resume_id = Column(Integer, nullable=False)
    job_id = Column(Integer, nullable=False)
    
    # 评分结果
    total_score = Column(Float, default=0)
    score_level = Column(String(10), default="")
    
    # 详细评分（JSON）
    detail_json = Column(JSON, nullable=False)
    
    # AI建议
    ai_advice = Column(Text, default="")
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    suggestions = Column(JSON, default=list)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)


class ConversationRecord(Base):
    """对话记录表 - SDD新增"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 对话标题（自动提取第一条消息前20字）
    title = Column(String(200), default="")
    
    # 消息列表（JSON）
    messages = Column(JSON, default=list)
    
    # 上下文关联
    context_job_id = Column(Integer, nullable=True)  # 当前关联的岗位
    context_resume_id = Column(Integer, nullable=True)  # 当前关联的简历
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ApplicationRecord(Base):
    """投递记录表 - SDD新增"""
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联
    job_id = Column(Integer, nullable=False)
    resume_id = Column(Integer, nullable=True)
    
    # 投递信息
    apply_date = Column(Date, nullable=True)
    platform = Column(String(50), default="")  # Boss/猎聘/拉勾
    
    # 状态: pending/applied/screening/interview/offer/rejected/inappropriate
    status = Column(String(20), default="pending")
    
    # 备注
    notes = Column(Text, default="")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class InterviewRecord(Base):
    """面试记录表 - SDD新增"""
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联岗位
    job_id = Column(Integer, nullable=False)
    
    # 面试类型: technical/behavioral/hr
    interview_type = Column(String(20), default="")
    
    # 面试题、回答、反馈（JSON）
    questions = Column(JSON, default=list)
    answers = Column(JSON, default=list)
    feedback = Column(JSON, default=list)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)


class UserPreferenceRecord(Base):
    """用户偏好表 - SDD新增"""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True)
    
    # 求职偏好
    target_city = Column(String(50), default="杭州")
    expected_salary_min = Column(Integer, default=27)  # 万/年
    target_positions = Column(JSON, default=list)  # ["AI测试开发", "AI Agent评测"]
    excluded_keywords = Column(JSON, default=list)  # ["外包"]
    daily_apply_target = Column(Integer, default=12)
    job_start_date = Column(Date, nullable=True)  # 求职开始日期
    
    # LLM配置
    llm_provider = Column(String(20), default="qwen")
    llm_model = Column(String(50), default="qwen-plus")
    
    # 时间戳
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DailyBeliefRecord(Base):
    """信念启示录表 - SDD新增"""
    __tablename__ = "daily_beliefs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 信念内容
    content = Column(Text, nullable=False)
    category = Column(String(20), default="")  # persist/confidence/growth/expression
    
    # 最近展示日期
    shown_date = Column(Date, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
