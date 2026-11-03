@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有找到 python。请先安装 Python 3.10+。
  pause
  exit /b 1
)

echo ============================================
echo   二合情报站 - 更新情报
echo ============================================
echo.
echo 正在抓取 App Store 版本 / 榜单 / RSS，然后重新构建站点...
echo.
python tools\collect.py --ai
set RESULT=%ERRORLEVEL%
echo.
if "%RESULT%"=="0" (
  echo [完成] 数据已更新。双击“启动网站.bat”即可查看。
) else (
  echo [提示] 采集未完全成功（退出码 %RESULT%）。旧数据不会被破坏，可稍后重试。
)
echo.
pause
