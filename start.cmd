@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -c "import flask, flask_sqlalchemy, sqlalchemy, pymysql, requests, dotenv, waitress" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt --index-url https://pypi.org/simple
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" run.py --open
if errorlevel 1 goto error
exit /b 0
:error
echo.
echo Startup failed. Please check the message above.
echo Python 3.9+ is required. Another running copy may already be using port 5180.
pause
exit /b 1
