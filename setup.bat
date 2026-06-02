@echo off
REM Escriba - one-time setup for Windows. Double-click to run.
cd /d "%~dp0"

echo ============================================
echo   Setting up Escriba
echo ============================================
echo.

REM 1. Python
where python >nul 2>nul
if errorlevel 1 (
  echo   X Python isn't installed.
  echo     Install it from https://www.python.org/downloads/  ^(check "Add to PATH"^) then run this again.
  echo.
  pause
  exit /b 1
)
echo   - Python found

REM 2. ffmpeg
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo   - ffmpeg not found - trying to install via winget...
  winget install --id Gyan.FFmpeg -e --source winget
  echo.
  echo     If that failed, install ffmpeg manually from https://ffmpeg.org/download.html
  echo     and make sure it's on your PATH, then run this again.
) else (
  echo   - ffmpeg found
)

REM 3. venv + packages
echo.
echo   Creating a private environment and installing packages.
echo   The transcription engine is several GB - this can take a while.
echo.
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

echo.
echo ============================================
echo   All set!  Double-click  start.bat  to run Escriba.
echo ============================================
pause
