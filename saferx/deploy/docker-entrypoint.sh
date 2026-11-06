#!/usr/bin/env sh
# 容器入口：数据库不存在则执行数据管道（需联网下载 DDInter 2.0 约 30MB）
set -e
cd /app

if [ ! -f "$SAFERX_DB" ]; then
    echo "[entrypoint] 数据库不存在，执行数据管道..."
    python pipelines/download_ddinter.py
    python pipelines/clean_ddinter.py
    python pipelines/build_alias_table.py
    python pipelines/init_db.py
    echo "[entrypoint] 数据库构建完成"
else
    echo "[entrypoint] 数据库已就绪: $SAFERX_DB"
fi

cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
