@echo off
REM Escriba - start the app. Double-click to run (after setup.bat).
cd /d "%~dp0"
if not exist ".venv" (
  echo   Please run setup.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python run.py
