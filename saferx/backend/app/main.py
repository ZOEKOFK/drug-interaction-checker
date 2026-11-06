"""
SafeRx 用药安全卫士 - FastAPI 入口。

- API 路由统一挂载在 /api 前缀下，自动文档: /docs
- 若存在 frontend/dist（生产构建），挂载为静态站点 -> 单服务即可部署
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import check, drugs, graph, lab, report
from .config import DB_PATH, FRONTEND_DIST, get_data_version, get_stats
from .core.db import open_conn

app = FastAPI(
    title="SafeRx 用药安全卫士 API",
    description="基于 DDInter 2.0 审编数据库的药物相互作用智能检查系统（教学与科普用途，非诊断工具）",
    version="0.1.0",
)

# 开发期前端 vite dev server 跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["meta"])
def health():
    """健康检查：数据库状态 + 数据规模。"""
    if not DB_PATH.exists():
        return JSONResponse(
            status_code=503,
            content={"status": "db_missing", "db_path": str(DB_PATH),
                     "hint": "请先运行 make data && make initdb（或 pipelines 下脚本）"},
        )
    conn = open_conn()
    try:
        return {
            "status": "ok",
            "db_path": str(DB_PATH),
            "data_version": get_data_version(conn),
            "stats": get_stats(conn),
        }
    finally:
        conn.close()


# ---- API 路由 ----
app.include_router(drugs.router)
app.include_router(check.router)
app.include_router(graph.router)
app.include_router(report.router)
app.include_router(lab.router)


# ---- 生产模式：托管前端构建产物（单服务部署） ----
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """SPA 兜底：非 /api、非静态资源路径一律回 index.html。"""
        target = FRONTEND_DIST / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
else:

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "name": "SafeRx API",
            "docs": "/docs",
            "health": "/api/health",
            "hint": "前端开发模式: cd frontend && npm run dev（代理 /api -> 本服务）",
        }
