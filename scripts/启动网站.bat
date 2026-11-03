@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有找到 python。请先安装 Python 3.10+，安装时勾选 Add to PATH。
  pause
  exit /b 1
)

echo ============================================
echo   二合情报站 - 启动
echo ============================================
echo.
python tools\build.py
if errorlevel 1 (
  echo.
  echo [错误] 构建失败。请查看上面的提示，修好 data\curated 里的 JSON 后再试。
  pause
  exit /b 1
)
echo.
echo 正在启动本地服务... 手机需要和电脑连同一个 Wi-Fi。
echo 关闭本窗口即停止服务。
echo.
python tools\serve.py
pause
