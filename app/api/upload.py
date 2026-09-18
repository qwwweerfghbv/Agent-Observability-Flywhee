"""文件/图片上传API"""
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List
from loguru import logger

router = APIRouter(prefix="/api/upload", tags=["上传"])

# 上传目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
IMAGE_DIR = BASE_DIR / "images"
FILE_DIR = BASE_DIR / "files"

# 允许的图片格式
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
# 允许的文件格式
ALLOWED_FILE_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILE_SIZE = 20 * 1024 * 1024   # 20MB
MAX_IMAGES = 10


def _ensure_dirs():
    """确保上传目录存在"""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    FILE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/images")
async def upload_images(files: List[UploadFile] = File(...)):
    """上传图片（最多10张）"""
    _ensure_dirs()
    
    if len(files) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"最多上传{MAX_IMAGES}张图片")
    
    saved = []
    for f in files:
        if f.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的图片格式: {f.content_type}，支持: {', '.join(ALLOWED_IMAGE_TYPES)}"
            )
        
        content = await f.read()
        if len(content) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail=f"图片 {f.filename} 超过10MB限制")
        
        ext = Path(f.filename).suffix or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = IMAGE_DIR / filename
        
        with open(filepath, "wb") as out:
            out.write(content)
        
        saved.append({
            "filename": f.filename,
            "saved_name": filename,
            "url": f"/api/upload/images/{filename}",
            "size": len(content),
        })
        logger.info(f"图片上传成功: {filename}")
    
    return {"images": saved, "count": len(saved)}


@router.post("/files")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传文件（简历等）"""
    _ensure_dirs()
    
    saved = []
    for f in files:
        if f.content_type not in ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {f.content_type}，支持: PDF, Word, TXT, Markdown"
            )
        
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件 {f.filename} 超过20MB限制")
        
        ext = Path(f.filename).suffix or ""
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = FILE_DIR / filename
        
        with open(filepath, "wb") as out:
            out.write(content)
        
        saved.append({
            "filename": f.filename,
            "saved_name": filename,
            "url": f"/api/upload/files/{filename}",
            "size": len(content),
            "content_type": f.content_type,
        })
        logger.info(f"文件上传成功: {filename}")
    
    return {"files": saved, "count": len(saved)}


@router.get("/images/{filename}")
async def get_image(filename: str):
    """获取已上传的图片"""
    filepath = IMAGE_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(filepath)


@router.get("/files/{filename}")
async def get_file(filename: str):
    """获取已上传的文件"""
    filepath = FILE_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(filepath, filename=filename)
