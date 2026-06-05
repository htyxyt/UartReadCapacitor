@echo off
echo === TH2817B 采集助手 构建脚本 ===
echo.

echo [1/3] 创建虚拟环境并安装依赖...
uv sync
if errorlevel 1 (
    echo 依赖安装失败，请检查 uv 是否正确安装
    pause
    exit /b 1
)

echo.
echo [2/3] 使用 PyInstaller 打包...
uv run pyinstaller --onefile --windowed --name "TH2817B采集助手" app.py
if errorlevel 1 (
    echo 打包失败
    pause
    exit /b 1
)

echo.
echo [3/3] 清理构建临时文件...
if exist build rmdir /s /q build
if exist "*.spec" del /q "*.spec"

echo.
echo 构建完成！
echo 输出文件: dist\TH2817B采集助手.exe
echo 文件大小:
for %%F in ("dist\TH2817B采集助手.exe") do echo   %%~zF bytes
echo.
pause
