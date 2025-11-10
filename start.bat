@echo off
echo 启动PDF黑白打印优化工具...
echo.

REM 检查虚拟环境是否存在
if not exist "black_white_env" (
    echo 错误: 虚拟环境不存在，请先运行 install.bat 安装依赖
    pause
    exit /b 1
)

REM 激活虚拟环境并启动程序
echo 正在启动程序...
call black_white_env\Scripts\activate.bat
python modern_pdf_processor_gui.py

REM 如果程序异常退出，暂停以查看错误信息
if %errorlevel% neq 0 (
    echo.
    echo 程序异常退出，错误代码: %errorlevel%
    pause
)