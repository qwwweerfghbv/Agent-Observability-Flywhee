"""JD解析服务"""
from typing import Optional
from loguru import logger

from app.llm.client import get_llm_client
from app.llm.prompts import PromptTemplates
from app.models.job import JobData, JobRequirement, JobBenefit


class JobParserService:
    """JD解析服务"""
    
    def __init__(self):
        self.llm_client = get_llm_client()
    
    def parse(self, jd_text: str) -> JobData:
        """解析JD文本为结构化数据"""
        logger.info("开始解析JD...")
        
        # 构建prompt
        prompt = PromptTemplates.format_template("PARSE_JD", jd_text=jd_text)
        messages = [{"role": "user", "content": prompt}]
        
        # 调用LLM（含 stability_signals 的结构化输出，max_tokens 放宽防截断）
        try:
            result = self.llm_client.chat_json_sync(messages, temperature=0.3,
                                                    max_tokens=4096, timeout=60)
            logger.info(f"LLM解析完成，结果: {list(result.keys())}")
        except Exception as e:
            logger.error(f"LLM解析失败: {e}")
            # 返回空数据
            return JobData(title="未知岗位", raw_text=jd_text)
        
        # 转换为JobData
        return self._convert_to_job_data(result, jd_text)
    
    def _convert_to_job_data(self, data: dict, raw_text: str) -> JobData:
        """将LLM返回转换为JobData"""
        try:
            # 解析岗位要求
            requirements = []
            for req in data.get("requirements", []):
                requirements.append(JobRequirement(
                    skill=req.get("skill", ""),
                    required=req.get("required", True),
                    years=req.get("years"),
                    level=req.get("level", "")
                ))
            
            # 解析福利
            benefits = []
            for ben in data.get("benefits", []):
                benefits.append(JobBenefit(
                    category=ben.get("category", "其他"),
                    description=ben.get("description", "")
                ))
            
            # 构建JobData（使用 or 防止 LLM 返回 None）
            job_data = JobData(
                title=data.get("title") or "未知岗位",
                company=data.get("company") or "",
                location=data.get("location") or "",
                salary_min=data.get("salary_min") or 0,
                salary_max=data.get("salary_max") or 0,
                years_required=data.get("years_required") or 0,
                education_required=data.get("education_required") or "本科",
                requirements=requirements,
                responsibilities=data.get("responsibilities", []),
                benefits=benefits,
                company_size=data.get("company_size") or "",
                industry=data.get("industry") or "",
                stability_signals=data.get("stability_signals"),
                raw_text=raw_text
            )
            
            logger.info(f"JD解析完成: {job_data.title}, 要求技能数: {len(requirements)}")
            return job_data
            
        except Exception as e:
            logger.error(f"转换JD数据失败: {e}")
            return JobData(title="未知岗位", raw_text=raw_text)
