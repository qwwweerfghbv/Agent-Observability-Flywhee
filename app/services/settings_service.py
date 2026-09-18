"""设置服务 - SDD"""
from typing import Optional, Dict
from datetime import datetime, date
from loguru import logger

from app.db.database import SessionLocal
from app.db.models import UserPreferenceRecord
from app.models.settings import UserPreferences, SettingsUpdate


class SettingsService:
    """设置服务"""
    
    def get_preferences(self) -> UserPreferences:
        """获取用户偏好"""
        db = SessionLocal()
        try:
            pref = db.query(UserPreferenceRecord).filter_by(id=1).first()
            if not pref:
                return UserPreferences()
            
            return UserPreferences(
                target_city=pref.target_city,
                expected_salary_min=pref.expected_salary_min,
                target_positions=pref.target_positions or ["AI测试开发", "AI Agent评测"],
                excluded_keywords=pref.excluded_keywords or ["外包"],
                daily_apply_target=pref.daily_apply_target,
                job_start_date=pref.job_start_date,
                llm_provider=pref.llm_provider,
                llm_model=pref.llm_model
            )
        finally:
            db.close()
    
    def update_preferences(self, data: SettingsUpdate) -> UserPreferences:
        """更新用户偏好"""
        db = SessionLocal()
        try:
            pref = db.query(UserPreferenceRecord).filter_by(id=1).first()
            if not pref:
                pref = UserPreferenceRecord(id=1)
                db.add(pref)
            
            if data.target_city is not None:
                pref.target_city = data.target_city
            if data.expected_salary_min is not None:
                pref.expected_salary_min = data.expected_salary_min
            if data.target_positions is not None:
                pref.target_positions = data.target_positions
            if data.excluded_keywords is not None:
                pref.excluded_keywords = data.excluded_keywords
            if data.daily_apply_target is not None:
                pref.daily_apply_target = data.daily_apply_target
            if data.job_start_date is not None:
                pref.job_start_date = data.job_start_date
            if data.llm_provider is not None:
                pref.llm_provider = data.llm_provider
            if data.llm_model is not None:
                pref.llm_model = data.llm_model
            
            pref.updated_at = datetime.now()
            db.commit()
            db.refresh(pref)
            
            return UserPreferences(
                target_city=pref.target_city,
                expected_salary_min=pref.expected_salary_min,
                target_positions=pref.target_positions,
                excluded_keywords=pref.excluded_keywords,
                daily_apply_target=pref.daily_apply_target,
                job_start_date=pref.job_start_date,
                llm_provider=pref.llm_provider,
                llm_model=pref.llm_model
            )
        finally:
            db.close()
