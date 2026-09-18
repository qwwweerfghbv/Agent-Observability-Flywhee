"""数据库配置和会话管理"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator

from app.core.config import settings

# 创建数据库引擎
# SQLite使用相对路径，确保在job-agent目录下创建数据库文件
engine = create_engine(
    settings.database_url.replace("+aiosqlite", ""),  # 同步模式
    connect_args={"check_same_thread": False},  # SQLite需要
    echo=settings.app_env == "development"
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db() -> Generator:
    """获取数据库会话依赖项"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，创建所有表"""
    # 导入所有模型以确保它们被注册
    from app.db.models import (
        ResumeRecord, JobRecord, ScoreRecord,
        ConversationRecord, ApplicationRecord, InterviewRecord,
        UserPreferenceRecord, DailyBeliefRecord
    )
    
    Base.metadata.create_all(bind=engine)
    
    # 迁移：为已有表添加缺失列
    _migrate_schema()
    
    # 初始化默认用户偏好和信念启示录
    _init_defaults()


def reset_db():
    """重置数据库，删除所有数据（谨慎使用）"""
    Base.metadata.drop_all(bind=engine)
    init_db()


def _migrate_schema():
    """为已有表添加缺失列（SQLite不支持DROP COLUMN，仅支持ADD COLUMN）"""
    from loguru import logger
    from sqlalchemy import text
    with engine.connect() as conn:
        # 检查jobs表是否缺少stability_signals和ai_replacement_risk列
        try:
            conn.execute(text("SELECT stability_signals FROM jobs LIMIT 0"))
        except Exception:
            logger.info("迁移: 为jobs表添加stability_signals列")
            conn.execute(text("ALTER TABLE jobs ADD COLUMN stability_signals JSON DEFAULT '{}'")
            )
            conn.commit()
        
        try:
            conn.execute(text("SELECT ai_replacement_risk FROM jobs LIMIT 0"))
        except Exception:
            logger.info("迁移: 为jobs表添加ai_replacement_risk列")
            conn.execute(text("ALTER TABLE jobs ADD COLUMN ai_replacement_risk INTEGER DEFAULT 50"))
            conn.commit()


def _init_defaults():
    """初始化默认数据"""
    from app.db.models import UserPreferenceRecord, DailyBeliefRecord
    
    session = SessionLocal()
    try:
        # 初始化默认用户偏好（如果不存在）
        pref = session.query(UserPreferenceRecord).filter_by(id=1).first()
        if not pref:
            pref = UserPreferenceRecord(
                id=1,
                target_city="杭州",
                expected_salary_min=27,
                target_positions=["AI测试开发", "AI Agent评测"],
                excluded_keywords=["外包"],
                daily_apply_target=12,
                llm_provider="qwen",
                llm_model="qwen-plus"
            )
            session.add(pref)
        
        # 初始化信念启示录（如果不存在）
        belief_count = session.query(DailyBeliefRecord).count()
        if belief_count == 0:
            beliefs = [
                # 坚持类
                ("每一天的积累，都在缩短你与理想offer的距离", "persist"),
                ("坚持不是胜利，而是通往胜利的路", "persist"),
                ("求职是一场马拉松，不是短跑，保持节奏比速度更重要", "persist"),
                ("今天的努力，是明天从容的底气", "persist"),
                ("每一次投递，都是向目标靠近一步", "persist"),
                # 自信类
                ("你的每一行代码经验，都是谈判的底气", "confidence"),
                ("面试不是被挑选，而是双向选择", "confidence"),
                ("你的价值不由面试官定义，而由你的能力定义", "confidence"),
                ("被拒绝不代表你不够好，只是还没遇到对的机会", "confidence"),
                ("相信自己的判断，你比想象中更优秀", "confidence"),
                # 成长类
                ("面试是最好的学习，每次面试都让你更强", "growth"),
                ("失败不是终点，而是成长的起点", "growth"),
                ("每一次复盘，都是一次自我升级", "growth"),
                ("不要害怕暴露不足，那是进步的开始", "growth"),
                ("学无止境，每天进步一点点就够了", "growth"),
                # 表达类
                ("清晰的表达 = 清晰的思维，练表达就是练思维", "expression"),
                ("好的回答不是背出来的，是想清楚的", "expression"),
                ("STAR法则不是套路，而是让故事更有力的结构", "expression"),
                ("用数据说话，让成果自己发声", "expression"),
                ("简洁有力的表达，胜过冗长的叙述", "expression"),
            ]
            for content, category in beliefs:
                session.add(DailyBeliefRecord(content=content, category=category))
        
        session.commit()
    except Exception as e:
        session.rollback()
        from loguru import logger
        logger.warning(f"初始化默认数据失败: {e}")
    finally:
        session.close()
