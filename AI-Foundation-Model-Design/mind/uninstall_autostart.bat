@echo off
rem  uninstall_autostart.bat  —  stop Vio from starting automatically at login.
rem  (This does not delete Vio or your data — it only removes the auto-start entry.)
setlocal
set "VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Vio.vbs"
if exist "%VBS%" (
  del "%VBS%"
  echo   Auto-start removed. Vio will no longer launch at login.
) else (
  echo   Auto-start was not installed.
)
echo   ^(To stop the currently running Vio, run stop_vio.bat.^)
timeout /t 3 >nul
