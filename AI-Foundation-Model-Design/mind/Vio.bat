@echo off
cd /d "%~dp0"
title Vio - your local assistant
echo Starting Vio... a browser tab will open at http://localhost:8100
echo Keep this window open while you use Vio. Close it to stop.
rem first run (or after an update): install the file readers Vio needs — PDF, OCR
python -c "import pymupdf, pypdf" 2>nul || (
  echo Installing file readers ^(PDF^) - one time only...
  python -m pip install -q -r requirements.txt
)
python -c "import rapidocr" 2>nul || (
  echo Installing OCR for scanned PDFs and images - optional, one time only...
  python -m pip install -q -r requirements-ocr.txt || echo OCR not installed - scanned PDFs will be skipped.
)
python web.py
if errorlevel 1 (
  echo.
  echo Could not start. Make sure Python is installed and try: py web.py
  pause
)
