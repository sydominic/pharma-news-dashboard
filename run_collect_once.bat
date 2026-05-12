@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================
echo Pharma News RSS Collector - One Time Run
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% --version
if errorlevel 1 (
    echo [FAIL] Python was not found. Install Python 3.10+ and enable PATH.
    pause
    exit /b 1
)

%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [FAIL] Package installation failed.
    pause
    exit /b 1
)

%PY% collect_once.py

echo.
echo Done.
pause
