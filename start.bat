@echo off
chcp 65001 >nul
echo 启动PDF黑白打印优化工具...
echo.

REM 检查Python是否已安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到Python，请先安装Python 3.8或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 启动程序
echo 正在启动程序...
python modern_pdf_processor_gui.py

REM 如果程序异常退出，暂停以查看错误信息
if %errorlevel% neq 0 (
    echo.
    echo 程序异常退出，错误代码: %errorlevel%
    pause
)
