"""求职Agent - FastAPI入口 (按SDD文档重构)"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import sys

from app.core.config import settings
from app.db.database import init_db
from app.observability.context import begin_context, fill, get_context, setup_trace_logging
from app.observability.writers import write_request
from app.api import (
    resume_router, job_router, interview_router,
    chat_router, application_router, settings_router,
    upload_router, observability_router
)

# 配置日志（trace_id 贯穿，SDD §4.8）
setup_trace_logging(settings.log_level)

# 创建FastAPI应用
app = FastAPI(
    title="求职Agent",
    description="智能求职助手 - 对话式交互、简历解析、岗位评分、简历优化、面试模拟",
    version="0.3.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 观测中间件（SDD §5.1，M1）：请求级埋点 + 非流式落盘
# 流式响应（text/event-stream）由 event_gen 的 finally 落盘，此处豁免
# ============================================================
@app.middleware("http")
async def observability_middleware(request, call_next):
    try:
        begin_context(source="production", path=request.url.path, method=request.method)
    except Exception as e:  # 静默降级：埋点失败不影响请求
        logger.warning(f"观测上下文初始化失败(降级): {e}")
    response = None
    try:
        response = await call_next(request)
        fill(status_code=response.status_code)
        ctx = get_context()
        if ctx and response is not None:
            response.headers["X-Trace-Id"] = ctx.get("trace_id", "")  # 日志/落盘关联入口
        return response
    except Exception as e:
        fill(status="error", error=f"{type(e).__name__}: {e}")
        raise
    finally:
        # BaseHTTPMiddleware 把响应包成 _StreamingResponse，其 .media_type 恒为 None
        # （content-type 只存在于 headers），故必须查 header 才能正确豁免 SSE。
        ctype = ""
        if response is not None:
            try:
                ctype = response.headers.get("content-type", "") or ""
            except Exception:
                ctype = ""
        if response is None or not ctype.startswith("text/event-stream"):
            write_request(get_context())

# ============================================================
# 初始化数据库
# ============================================================
logger.info("初始化数据库...")
init_db()
logger.info("数据库初始化完成")

# ============================================================
# 注册API路由
# ============================================================
# SDD新增路由
app.include_router(chat_router)           # 对话API
app.include_router(application_router)    # 投递管理API
app.include_router(settings_router)       # 设置API
app.include_router(observability_router)  # 可观测平台API（M3: bad case 评审）

# 原有业务路由
app.include_router(resume_router)
app.include_router(job_router)
app.include_router(interview_router)

# 上传路由
app.include_router(upload_router)

logger.info("API路由注册完成")


# ============================================================
# 基础路由
# ============================================================

# React 生产构建产物（web/dist）：存在则单端口托管 SPA，不存在则保留 JSON 根路由（dev 模式走 vite :5173）
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
SPA_ENABLED = (WEB_DIST / "index.html").exists()
# index.html 禁缓存：它引用带 content-hash 的资源，HTML 本身必须每次重新拉取，
# 否则前端重新 build 后浏览器普通刷新仍用旧 HTML（指向旧 hash 的 js/css）。
_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
if SPA_ENABLED:
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="spa-assets")
    logger.info(f"React 生产构建已挂载: {WEB_DIST}")


@app.get("/")
async def root():
    """根路径：SPA 存在时返回前端首页，否则返回 API 信息"""
    if SPA_ENABLED:
        return FileResponse(WEB_DIST / "index.html", headers=_NO_CACHE)
    return {
        "message": "求职Agent - 智能求职助手",
        "version": "0.3.0",
        "status": "running",
        "docs": "/docs",
        "features": [
            "💬 对话式交互（核心）",
            "📄 简历解析（PDF/Word/文本）",
            "💼 岗位评估（5维度评分+稳定性分析）",
            "📝 简历优化（逐条确认修改）",
            "🎯 面试模拟（技术面+行为面+HR面）",
            "📊 投递追踪（进度统计）",
            "🔥 信念区（每日启示录）",
            "⏱️ 计时区（求职天数）"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "version": "0.3.0"
    }


# SPA 前端路由 fallback（BrowserRouter 直接访问 /jobs 等路径时返回 index.html）。
# 必须注册在所有 API 路由之后；白名单外的未知路径仍返 404 JSON。
_SPA_ROUTES = {"dashboard", "jobs", "resumes", "applications", "settings", "observability"}


@app.get("/{spa_path:path}", include_in_schema=False)
async def spa_fallback(spa_path: str):
    if SPA_ENABLED and spa_path.split("/")[0] in _SPA_ROUTES:
        return FileResponse(WEB_DIST / "index.html", headers=_NO_CACHE)
    return JSONResponse({"detail": "Not Found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
