@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================
echo Pharma News RSS Dashboard - Launcher
echo ========================================
echo.

echo [1/5] Select Python launcher
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

echo Using: %PY%
%PY% --version
if errorlevel 1 (
    echo [FAIL] Python was not found. Install Python 3.10+ and enable PATH.
    pause
    exit /b 1
)

echo.
echo [2/5] Upgrade pip
%PY% -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARN] pip upgrade failed. Continue with current pip.
)

echo.
echo [3/5] Install required packages
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [FAIL] Package installation failed.
    echo Try running: %PY% -m pip install feedparser streamlit pandas plotly requests beautifulsoup4 openpyxl python-dateutil
    pause
    exit /b 1
)

echo.
echo [4/5] Verify packages
%PY% -c "import feedparser, pandas, streamlit, plotly, requests, bs4, openpyxl; print('Package check OK')"
if errorlevel 1 (
    echo [FAIL] Package check failed.
    pause
    exit /b 1
)

echo.
echo [5/5] Start Streamlit dashboard
if not exist data mkdir data
%PY% -m streamlit run app.py

echo.
echo Dashboard was closed.
pause
