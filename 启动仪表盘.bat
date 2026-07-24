@echo off
cd /d %~dp0
start python scripts\server.py
timeout /t 2 /nobreak >nul
start http://localhost:8765
echo 仪表盘已启动，浏览器打开 http://localhost:8765
pause
