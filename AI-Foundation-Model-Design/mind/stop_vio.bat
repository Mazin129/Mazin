@echo off
rem  stop_vio.bat  —  stop the running Vio server (whatever is listening on port 8100).
setlocal
set "PORT=8100"
set "FOUND="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "127.0.0.1:%PORT%" ^| findstr LISTENING') do (
  taskkill /f /pid %%p >nul 2>&1
  set "FOUND=1"
)
if defined FOUND (echo   Vio stopped.) else (echo   Vio was not running.)
timeout /t 2 >nul
