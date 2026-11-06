@echo off
REM LaneRoom one-click start for Windows
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
streamlit run app.py
