"""简历API路由"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger

from app.db.database import get_db
from app.db.repositories import ResumeRepository
from app.services.resume_parser import ResumeParserService
from app.models.resume import ResumeCreate, ResumeResponse, ResumeData

router = APIRouter(prefix="/api/resume", tags=["简历管理"])


def _ensure_parsed(resume_data: ResumeData) -> None:
    """LLM 结构化结果为空即判解析失败，显式报错。

    治理静默降级：解析失败不再落库空简历并返回“成功”，
    避免简历中心出现“未识别姓名/0年经验”的脏数据。
    """
    if not any([
        resume_data.name, resume_data.summary, resume_data.skills,
        resume_data.work_experiences, resume_data.projects, resume_data.educations,
    ]):
        raise HTTPException(
            status_code=502,
            detail="简历解析失败：LLM 未返回有效结构化内容，请重试或改用文本粘贴"
        )


@router.post("/parse", response_model=ResumeResponse)
async def parse_resume(
    request: ResumeCreate,
    db: Session = Depends(get_db)
):
    """解析简历文本"""
    logger.info("收到简历解析请求")
    
    # 解析简历（LLM 长生成可达分钟级，放入工作线程避免阻塞事件循环）
    parser = ResumeParserService()
    resume_data = await asyncio.to_thread(parser.parse, request.raw_text)
    _ensure_parsed(resume_data)
    
    # 保存到数据库
    repo = ResumeRepository(db)
    record = repo.create(resume_data, request.raw_text)
    
    return ResumeResponse(
        id=record.id,
        data=resume_data,
        created_at=record.created_at
    )


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传简历文件（PDF/DOCX）"""
    logger.info(f"收到简历上传: {file.filename}")
    
    # 检查文件类型
    if not file.filename.endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(status_code=400, detail="仅支持PDF、DOCX和TXT格式")
    
    # 读取文件内容
    content = await file.read()
    
    # 保存到临时文件
    import tempfile
    import os
    
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # 解析简历
        parser = ResumeParserService()
        file_type = suffix[1:] if suffix else "text"
        resume_data = await asyncio.to_thread(parser.parse_from_file, tmp_path, file_type)
        _ensure_parsed(resume_data)
        
        # 保存到数据库
        repo = ResumeRepository(db)
        record = repo.create(resume_data)
        
        return {
            "id": record.id,
            "name": resume_data.name,
            "skills_count": len(resume_data.skills),
            "message": "简历上传并解析成功"
        }
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    db: Session = Depends(get_db)
):
    """获取简历详情"""
    repo = ResumeRepository(db)
    record = repo.get_by_id(resume_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    return ResumeResponse(
        id=record.id,
        data=ResumeData(**record.data_json),
        created_at=record.created_at
    )


@router.get("/")
async def list_resumes(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取简历列表"""
    repo = ResumeRepository(db)
    records = repo.get_all(limit=limit)
    
    return {
        "total": len(records),
        "resumes": [
            {
                "id": r.id,
                "name": r.name,
                "location": r.location,
                "years_of_experience": r.years_of_experience,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
    }


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db)
):
    """删除简历"""
    repo = ResumeRepository(db)
    success = repo.delete(resume_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    return {"message": "删除成功"}
