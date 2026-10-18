@echo off
setlocal enabledelayedexpansion
title SEO Traffic Bot - Build and Run

REM ============================================================
REM  SEO Traffic Bot - Build and Run
REM
REM  Usage:
REM    run.bat              -> build (venv + deps + Chromium) and launch GUI (ui.py)
REM    run.bat --plan       -> build and run CLI (main.py) with arguments
REM    run.bat --search     -> e.g. run one automation session
REM ============================================================

cd /d "%~dp0"

echo ==============================================
echo  SEO Traffic Bot - Build and Run
echo ==============================================
echo.

echo [1/4] Checking Python installation...
set "PYTHON="
python --version >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON (
    py -3 --version >nul 2>&1 && set "PYTHON=py -3"
)
if not defined PYTHON (
    echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do echo        Found: %%v

echo.
echo [2/4] Creating virtual environment (venv)...
if not exist "venv\Scripts\python.exe" (
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo        venv already exists - skipping.
)
set "VPY=venv\Scripts\python.exe"

echo.
echo [3/4] Installing dependencies (requirements.txt)...
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [4/4] Installing Playwright Chromium browser...
"%VPY%" -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Failed to install Chromium browser.
    pause
    exit /b 1
)

echo.
echo ==============================================
echo  Build OK. Starting application...
echo ==============================================
echo.

if "%~1"=="" (
    "%VPY%" ui.py
) else (
    "%VPY%" main.py %*
)

set "EXITCODE=%errorlevel%"
echo.
if not "%EXITCODE%"=="0" (
    echo [ERROR] Program exited with code %EXITCODE%. Check the log above.
) else (
    echo Program finished.
)
pause
exit /b %EXITCODE%
