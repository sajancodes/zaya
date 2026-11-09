@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Zaya - Setup and First Boot

cd /d "%~dp0"

echo ====================================================================
echo   ZAYA - Autonomous AI Desktop Assistant
echo   Setup, Dependency Installer and First Boot
echo   Created and developed by Sajan Rai (https://github.com/sajancodes)
echo ====================================================================
echo.

:: 1. Locate Python Interpreter (3.11 - 3.13 supported)
set "PYTHON_EXE="

py -3.11 -c "import sys" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.11"
    goto :PYTHON_FOUND
)

py -3.12 -c "import sys" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.12"
    goto :PYTHON_FOUND
)

py -3.13 -c "import sys" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py -3.13"
    goto :PYTHON_FOUND
)

py -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py"
    goto :PYTHON_FOUND
)

python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python"
    goto :PYTHON_FOUND
)

:PYTHON_NOT_FOUND
echo [ERROR] Python 3.11 or newer was not detected on your system.
echo Zaya requires Python 3.11 to 3.13.
echo.
echo Please install Python from:
echo   https://www.python.org/downloads/
echo.
echo IMPORTANT: During installation, be sure to check the box:
echo   "[X] Add Python to PATH"
echo.
pause
exit /b 1

:PYTHON_FOUND
echo [*] Python interpreter found: !PYTHON_EXE!
!PYTHON_EXE! --version

:: 2. Set Up Virtual Environment (.venv)
set "USE_VENV=0"
if exist ".venv\Scripts\activate.bat" (
    set "USE_VENV=1"
) else (
    echo.
    echo [*] Creating virtual environment in [.venv]
    !PYTHON_EXE! -m venv .venv
    if !errorlevel! equ 0 (
        set "USE_VENV=1"
    ) else (
        echo [WARNING] Failed to create virtual environment. Falling back to system Python.
    )
)

if "!USE_VENV!"=="1" (
    echo [*] Activating virtual environment [.venv]
    call .venv\Scripts\activate.bat
    set "ACTIVE_PYTHON=python"
) else (
    set "ACTIVE_PYTHON=!PYTHON_EXE!"
)

:: 3. Upgrade pip
echo.
echo [*] Ensuring pip is up to date
!ACTIVE_PYTHON! -m pip install --upgrade pip --quiet

:: 4. Check if launch should be skipped for flag inspection
set "SKIP_LAUNCH=0"
for %%A in (%*) do (
    if /I "%%A"=="--check-only" set "SKIP_LAUNCH=1"
    if /I "%%A"=="--help" set "SKIP_LAUNCH=1"
    if /I "%%A"=="-h" set "SKIP_LAUNCH=1"
    if /I "%%A"=="--no-start" set "SKIP_LAUNCH=1"
)

:: 5. Run Python Setup Installer (Dependencies, Assets, Playwright)
echo.
echo [*] Running Zaya environment setup
!ACTIVE_PYTHON! setup.py %*

if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Setup encountered an issue. Please review the output above.
    pause
    exit /b !errorlevel!
)

:: 6. First Boot Launch
if "!SKIP_LAUNCH!"=="0" (
    echo.
    echo ====================================================================
    echo   Zaya Setup Completed Successfully!
    echo   Launching Zaya First Boot
    echo ====================================================================
    echo.
    !ACTIVE_PYTHON! main.py
    if !errorlevel! neq 0 (
        echo.
        echo [INFO] Zaya session finished with code !errorlevel!.
    )
) else (
    echo.
    echo [*] Skipped first boot launch due to provided arguments.
)

pause
