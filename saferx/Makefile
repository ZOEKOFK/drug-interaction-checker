# SafeRx 用药安全卫士 - 仓库级构建入口（在 saferx/ 目录执行）
# 用法示例：
#   make data        # 下载 DDInter 2.0 原始数据（约 30 MB）
#   make initdb      # 清洗 + 别名表 + 建 SQLite（依赖 data/raw）
#   make test        # 后端单测 + 接口测试（31 个用例）
#   make api         # 启动 FastAPI（127.0.0.1:8000，含 /docs）
#   make web         # 启动前端开发服务器（5173，/api 代理到 8000）
#   make build-web   # 前端生产构建（backend 将自动托管 frontend/dist）
#   make start       # 一键启动（initdb -> uvicorn + vite dev）
#   make prod        # 生产模式：构建前端 + 单服务启动（仅 8000 端口）

PY ?= python
PORT ?= 8000

.PHONY: data clean alias initdb test api web build-web start prod docker help

## 数据管道
data:
	$(PY) pipelines/download_ddinter.py

clean:
	$(PY) pipelines/clean_ddinter.py

alias:
	$(PY) pipelines/build_alias_table.py

initdb: clean alias
	$(PY) pipelines/init_db.py

## 测试
test:
	cd backend && $(PY) -m pytest tests/ -q

## 开发
api:
	cd backend && $(PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

web:
	cd frontend && npm run dev

build-web:
	cd frontend && npm run build

start: initdb
	bash deploy/start_all.sh

## 生产（单服务：FastAPI 托管前端构建产物）
prod: initdb build-web
	cd backend && $(PY) -m uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

## Docker（可选）
docker:
	docker compose -f deploy/docker-compose.yml up --build

help:
	@echo "SafeRx 构建入口：make data | initdb | test | api | web | build-web | start | prod | docker"
