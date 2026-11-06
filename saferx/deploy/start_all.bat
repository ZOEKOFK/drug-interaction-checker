@echo off
REM ============================================================
REM SafeRx 一键启动（开发模式：后端 8000 + 前端 5173）
REM 用法：双击本文件，或在命令行执行 deploy\start_all.bat
REM ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

where python >nul 2>nul || (echo [错误] 未找到 python，请先安装 Python 3.10+ & pause & exit /b 1)

REM 1) 数据库不存在则先跑数据管道（下载约 30MB，需联网）
if not exist "data\saferx.sqlite" (
    echo [1/4] 数据库不存在，开始构建数据管道...
    python pipelines\download_ddinter.py || (echo [错误] 数据下载失败 & pause & exit /b 1)
    python pipelines\clean_ddinter.py
    python pipelines\build_alias_table.py
    python pipelines\init_db.py
) else (
    echo [1/4] 数据库已就绪：data\saferx.sqlite
)

REM 2) 后端依赖检查
python -c "import fastapi, uvicorn" 2>nul || (
    echo [2/4] 安装后端依赖...
    python -m pip install fastapi "uvicorn[standard]"
)
echo [2/4] 后端依赖就绪

REM 3) 前端依赖检查
if not exist "frontend\node_modules" (
    echo [3/4] 安装前端依赖（首次约 1-2 分钟）...
    cd frontend && call npm install && cd ..
)
echo [3/4] 前端依赖就绪

REM 4) 启动服务
echo [4/4] 启动服务...
echo    后端: http://127.0.0.1:8000  （API 文档 /docs）
echo    前端: http://localhost:5173   （开发模式，自动代理 /api）
echo    生产模式单服务: make prod 或 uvicorn 直接托管 frontend/dist
echo.

start "SafeRx API" cmd /k "cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
timeout /t 3 /nobreak >nul
cd frontend && start "SafeRx Web" cmd /k "npm run dev"

echo 两个服务窗口已启动，关闭对应窗口即可停止。
endlocal
