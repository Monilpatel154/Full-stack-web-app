@echo off
REM LADLI website — local launcher (Windows)
cd /d "%~dp0"

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo.
echo Starting LADLI website...
python app.py
pause
