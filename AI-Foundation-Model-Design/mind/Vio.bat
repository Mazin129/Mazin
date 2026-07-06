@echo off
cd /d "%~dp0"
title Vio - your local assistant
echo Starting Vio... a browser tab will open at http://localhost:8100
echo Keep this window open while you use Vio. Close it to stop.
python web.py
if errorlevel 1 (
  echo.
  echo Could not start. Make sure Python is installed and try: py web.py
  pause
)
