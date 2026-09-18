"""简历解析服务"""
from typing import Optional
from loguru import logger

from app.llm.client import get_llm_client
from app.llm.prompts import PromptTemplates
from app.models.resume import ResumeData, Education, WorkExperience, Project, Skill


class ResumeParserService:
    """简历解析服务"""
    
    def __init__(self):
        self.llm_client = get_llm_client()
    
    def parse(self, resume_text: str) -> ResumeData:
        """解析简历文本为结构化数据"""
        logger.info("开始解析简历...")
        
        # 构建prompt
        prompt = PromptTemplates.format_template("PARSE_RESUME", resume_text=resume_text)
        messages = [{"role": "user", "content": prompt}]
        
        # 调用LLM（完整简历的结构化 JSON 输出体积大，max_tokens 放宽防截断；
        # 长生成耗时超过全局 llm_timeout，单次 timeout 同步放宽）
        try:
            result = self.llm_client.chat_json_sync(messages, temperature=0.3,
                                                    max_tokens=8000, timeout=120)
            logger.info(f"LLM解析完成，结果: {list(result.keys())}")
        except Exception as e:
            logger.error(f"LLM解析失败: {e}")
            # 返回空数据
            return ResumeData(raw_text=resume_text)
        
        # 转换为ResumeData
        return self._convert_to_resume_data(result, resume_text)
    
    def _convert_to_resume_data(self, data: dict, raw_text: str) -> ResumeData:
        """将LLM返回转换为ResumeData"""
        try:
            # 解析教育经历
            educations = []
            for edu in data.get("educations", []):
                educations.append(Education(
                    school=edu.get("school", ""),
                    degree=edu.get("degree", ""),
                    major=edu.get("major", ""),
                    start_date=edu.get("start_date", ""),
                    end_date=edu.get("end_date", ""),
                    gpa=edu.get("gpa")
                ))
            
            # 解析工作经历
            work_experiences = []
            for work in data.get("work_experiences", []):
                work_experiences.append(WorkExperience(
                    company=work.get("company", ""),
                    position=work.get("position", ""),
                    start_date=work.get("start_date", ""),
                    end_date=work.get("end_date", ""),
                    description=work.get("description", ""),
                    achievements=work.get("achievements", [])
                ))
            
            # 解析项目经历
            projects = []
            for proj in data.get("projects", []):
                projects.append(Project(
                    name=proj.get("name", ""),
                    role=proj.get("role", ""),
                    description=proj.get("description", ""),
                    technologies=proj.get("technologies", []),
                    achievements=proj.get("achievements", [])
                ))
            
            # 解析技能
            skills = []
            for skill in data.get("skills", []):
                skills.append(Skill(
                    name=skill.get("name", ""),
                    level=skill.get("level", "熟悉"),
                    category=skill.get("category", "")
                ))
            
            # 构建ResumeData（使用 or 防止 LLM 返回 None）
            resume_data = ResumeData(
                name=data.get("name") or "",
                phone=data.get("phone") or "",
                email=data.get("email") or "",
                location=data.get("location") or "",
                years_of_experience=data.get("years_of_experience") or 0,
                educations=educations,
                work_experiences=work_experiences,
                projects=projects,
                skills=skills,
                summary=data.get("summary") or "",
                raw_text=raw_text
            )
            
            logger.info(f"简历解析完成: {resume_data.name}, 技能数: {len(skills)}")
            return resume_data
            
        except Exception as e:
            logger.error(f"转换简历数据失败: {e}")
            return ResumeData(raw_text=raw_text)
    
    def parse_from_file(self, file_path: str, file_type: str = "text") -> ResumeData:
        """从文件解析简历"""
        if file_type == "pdf":
            text = self._extract_pdf(file_path)
        elif file_type == "docx":
            text = self._extract_docx(file_path)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        
        return self.parse(text)
    
    def _extract_pdf(self, file_path: str) -> str:
        """从PDF提取文本"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            logger.error(f"PDF解析失败: {e}")
            return ""
    
    def _extract_docx(self, file_path: str) -> str:
        """从DOCX提取文本"""
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f"DOCX解析失败: {e}")
            return ""
