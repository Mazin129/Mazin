@echo off
rem  start_vio.bat  —  start Vio manually in a visible window (good for seeing errors).
rem  Close the window to stop Vio. For always-on background use, run install_autostart.bat.
cd /d "%~dp0"
echo Starting Vio at http://localhost:8100  (close this window to stop)
python web.py
pause
