@echo off
chcp 65001 >nul
echo 正在安装PDF黑白打印优化工具的依赖包...
echo.

REM 检查Python是否已安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到Python，请先安装Python 3.8或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo 检测到Python已安装
python --version

REM 升级pip
echo.
echo 正在升级pip...
python -m pip install --upgrade pip

REM 安装依赖
echo.
echo 正在安装依赖包...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo 错误: 依赖包安装失败，请检查网络连接或尝试使用国内镜像源
    echo 您可以尝试手动运行以下命令:
    echo pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
    pause
    exit /b 1
)

echo.
echo 依赖包安装完成！
echo.
echo 使用方法:
echo 运行 python modern_pdf_processor_gui.py 启动程序
echo.
echo 或者直接运行 start.bat 启动程序
echo.
pause
