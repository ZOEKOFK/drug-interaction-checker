#!/usr/bin/env bash
# ============================================================
# SafeRx 一键启动（开发模式：后端 8000 + 前端 5173）
# 用法：bash deploy/start_all.sh
# ============================================================
set -e
cd "$(dirname "$0")/.."

PY="${PY:-python}"

command -v "$PY" >/dev/null || { echo "[错误] 未找到 python"; exit 1; }

# 1) 数据库不存在则先跑数据管道（下载约 30MB，需联网）
if [ ! -f data/saferx.sqlite ]; then
    echo "[1/4] 数据库不存在，开始构建数据管道..."
    "$PY" pipelines/download_ddinter.py
    "$PY" pipelines/clean_ddinter.py
    "$PY" pipelines/build_alias_table.py
    "$PY" pipelines/init_db.py
else
    echo "[1/4] 数据库已就绪：data/saferx.sqlite"
fi

# 2) 后端依赖
"$PY" -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "[2/4] 安装后端依赖..."
    "$PY" -m pip install fastapi "uvicorn[standard]"
}
echo "[2/4] 后端依赖就绪"

# 3) 前端依赖
if [ ! -d frontend/node_modules ]; then
    echo "[3/4] 安装前端依赖（首次约 1-2 分钟）..."
    (cd frontend && npm install)
fi
echo "[3/4] 前端依赖就绪"

# 4) 启动（Ctrl+C 停止；或用 & 后台并记 PID）
echo "[4/4] 启动服务..."
echo "   后端: http://127.0.0.1:8000  （API 文档 /docs）"
echo "   前端: http://localhost:5173"
echo

(cd backend && "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
API_PID=$!
(cd frontend && npm run dev) &
WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null' EXIT INT TERM
wait
