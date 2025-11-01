@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
cd backend
python app.py
pause

