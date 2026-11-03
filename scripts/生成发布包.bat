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

echo 正在重新构建并打包 site 目录...
python tools\build.py
if errorlevel 1 (
  echo [错误] 构建失败，未生成发布包。
  pause
  exit /b 1
)
python tools\zip_release.py
echo.
echo 生成完成后，把 zip 解压，上传里面的内容到任意静态托管即可。
pause
