@echo off
REM WavePoint Setup Script for Windows
REM Sets up Python virtual environment and installs dependencies

setlocal enabledelayedexpansion

echo ========================================
echo WavePoint Setup Script
echo ========================================
echo.

REM Check for Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Please install Python 3.9+ and add it to PATH.
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

echo Project directory: %PROJECT_DIR%
echo.

cd /d "%PROJECT_DIR%"

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo ========================================
echo Installing dependencies...
echo ========================================
echo.

pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to install dependencies.
    exit /b 1
)

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo To activate the virtual environment, run:
echo   venv\Scripts\activate.bat
echo.
echo To build the C++ core (optional, for better performance):
echo   scripts\build.bat
echo.
echo To run the application:
echo   python -m gesture_mouse
echo.

exit /b 0
