@echo off
chcp 65001 >nul
title 试试我试试好 - 视频下载工具 Web

echo ============================================
echo   试试我试试好 - 视频下载工具 Web 1.0
echo ============================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

:: 检查依赖是否安装
echo [信息] 正在检查依赖...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [信息] 正在安装依赖...
    pip install -r requirements.txt
)

echo.
echo [信息] 正在启动服务器...
echo [信息] 访问地址: http://localhost:5000
echo [信息] 按 Ctrl+C 停止服务
echo.

:: 使用waitress作为生产服务器
python -c "from waitress import serve; from app import app; print('服务已启动，请访问 http://localhost:5000'); serve(app, host='0.0.0.0', port=5000)"

pause
