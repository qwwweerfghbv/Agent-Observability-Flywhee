"""信念区服务 - SDD"""
from typing import Optional, Dict
from datetime import datetime, date
import random
from loguru import logger

from app.db.database import SessionLocal
from app.db.models import DailyBeliefRecord


class BeliefService:
    """信念区服务"""
    
    def get_today_belief(self) -> Dict:
        """获取今日信念"""
        db = SessionLocal()
        try:
            today = date.today()
            
            # 查找今天已展示的信念
            today_belief = db.query(DailyBeliefRecord).filter(
                DailyBeliefRecord.shown_date == today
            ).first()
            
            if today_belief:
                return {
                    "content": today_belief.content,
                    "category": today_belief.category
                }
            
            # 随机选择一条未展示过的信念
            all_beliefs = db.query(DailyBeliefRecord).all()
            if not all_beliefs:
                return {
                    "content": "每一天都是新的开始，加油！",
                    "category": "persist"
                }
            
            # 优先选择最近没展示过的
            shown_dates = {b.shown_date for b in all_beliefs if b.shown_date}
            not_shown_recently = [b for b in all_beliefs if b.shown_date not in shown_dates or b.shown_date is None]
            
            if not not_shown_recently:
                # 所有都展示过，随机选一条
                selected = random.choice(all_beliefs)
            else:
                selected = random.choice(not_shown_recently)
            
            # 更新展示日期
            selected.shown_date = today
            db.commit()
            
            return {
                "content": selected.content,
                "category": selected.category
            }
        finally:
            db.close()
    
    def get_job_seeking_days(self, start_date: Optional[date] = None) -> Dict:
        """获取求职天数"""
        # 防御：仅接受真实 date 实例。历史脏数据（如 job_start_date 被存成 int 年份）
        # 会让 today - start_date 抛 TypeError 导致接口 500，此处统一降级为“未配置”。
        if not isinstance(start_date, date):
            return {
                "days_count": 0,
                "message": "请在设置中配置求职开始日期"
            }
        
        today = date.today()
        days = (today - start_date).days + 1
        
        return {
            "days_count": max(1, days),
            "start_date": start_date.isoformat(),
            "message": f"今天是求职的第 {days} 天"
        }
