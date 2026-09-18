# syntax=docker/dockerfile:1
# ============================================================
# 多阶段构建：Stage 1 编译 React 前端 → Stage 2 运行 FastAPI 后端并单端口托管前端
# 默认 Mock 模式，零 API Key 即可起全栈；接入真实模型见 README「Docker 一键部署」
# ============================================================

# ---------- Stage 1: 构建 React 前端（Vite 8 / React 19 需 Node 20+，用 22 LTS + glibc 保证原生模块可用）----------
FROM node:22-slim AS web-build
WORKDIR /web
# 先装依赖，充分利用层缓存
COPY web/package.json web/package-lock.json ./
RUN npm ci
# 再拷贝源码构建（产出 /web/dist）
COPY web/ ./
RUN npm run build

# ---------- Stage 2: 运行后端（单端口托管前端构建产物） ----------
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LLM_PROVIDER=mock

# 先装 Python 依赖（所有依赖均有 cp311 manylinux 轮子，无需编译器）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝后端源码与示例
COPY app/ ./app/
COPY examples/ ./examples/

# 拷贝前端构建产物到 main.py 期望的位置（<repo>/web/dist）
COPY --from=web-build /web/dist ./web/dist

# 预建运行时数据目录（可被 compose 卷覆盖）
RUN mkdir -p data/trajectories data/sessions data/resumes data/exports \
             data/observability data/memory data/uploads/files data/uploads/images

EXPOSE 8000

# 健康检查：命中 /health 即视为就绪
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
