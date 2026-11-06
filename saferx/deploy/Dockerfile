# ============================================================
# SafeRx 生产镜像：Node 构建前端 -> Python 运行 FastAPI 单服务
# 构建上下文 = saferx/（compose 已配置），构建后仅 8000 端口对外
# ============================================================

# ---------- 阶段 1：前端构建 ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic

COPY backend/ ./backend/
COPY pipelines/ ./pipelines/
COPY data/external/ ./data/external/

# 容器首次启动时若无数据库则联网执行数据管道（约 30MB）
COPY deploy/docker-entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

COPY --from=web /web/dist ./frontend/dist

ENV SAFERX_DB=/app/data/saferx.sqlite
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
