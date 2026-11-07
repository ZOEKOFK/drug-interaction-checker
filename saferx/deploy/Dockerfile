# ============================================================
# SafeRx 生产镜像：Node 构建前端 -> Python 运行 FastAPI 单服务
# 构建上下文 = saferx/（compose 已配置），构建后仅 8000 端口对外
#
# 设计要点：镜像内**自带已构建的 SQLite 数据库**（data/saferx.sqlite，约 45MB），
# 容器冷启动 < 5s 且无需联网——答辩/内网环境不会因为下载 DDInter CSV 失败而挂掉。
# 只有在数据库缺失时，entrypoint 才回退到联网重建。
# ============================================================

# ---------- 阶段 1：前端构建 ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.12-slim
WORKDIR /app

# 依赖集中声明，避免漏装（此前漏了 pypinyin，容器里重建数据库会直接崩）
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY pipelines/ ./pipelines/

# data/ 下由 .dockerignore 决定实际内容：保留 external/（人工审编 JSON）与 saferx.sqlite，
# 排除 raw/interim/processed（原始 CSV 与评测中间产物，体积大且可重建）
COPY data/ ./data/

COPY deploy/docker-entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

COPY --from=web /web/dist ./frontend/dist

ENV SAFERX_DB=/app/data/saferx.sqlite \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2).status==200 else 1)"

ENTRYPOINT ["./entrypoint.sh"]
