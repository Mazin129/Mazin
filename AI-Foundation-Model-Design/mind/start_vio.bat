@echo off
rem  start_vio.bat  —  start Vio manually in a visible window (good for seeing errors).
rem  Close the window to stop Vio. For always-on background use, run install_autostart.bat.
cd /d "%~dp0"
echo Starting Vio at http://localhost:8100  (close this window to stop)
rem first run (or after an update): install the file readers Vio needs — PDF, OCR
python -c "import pymupdf, pypdf, rapidocr_onnxruntime" 2>nul || (
  echo Installing file readers ^(PDF, OCR^) - one time only...
  python -m pip install -q -r requirements.txt
)
python web.py
pause
