#!/usr/bin/env sh
# 容器入口：数据库已随镜像附带时直接起服务；缺失才联网重建（需要外网）。
set -e
cd /app

if [ ! -f "$SAFERX_DB" ]; then
    echo "[entrypoint] 未找到 $SAFERX_DB，开始构建（需联网下载 DDInter 2.0，约 30MB）"
    python pipelines/download_ddinter.py
    python pipelines/clean_ddinter.py
    python pipelines/download_other_interactions.py || \
        echo "[entrypoint] 警告：DDSI/DFI/重复用药抓取失败，这三类功能将为空（不影响 DDI 主功能）"
    python pipelines/clean_other_interactions.py || true
    python pipelines/build_alias_table.py
    python pipelines/init_db.py
    echo "[entrypoint] 数据库构建完成"
else
    echo "[entrypoint] 数据库已就绪: $SAFERX_DB"
fi

cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
