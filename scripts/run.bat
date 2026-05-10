@echo off
REM WavePoint Run Script
REM Activates virtual environment and runs the application

setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

cd /d "%PROJECT_DIR%"

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Running setup first...
    call scripts\setup.bat
    if %ERRORLEVEL% neq 0 (
        echo Setup failed.
        exit /b 1
    )
)

REM Activate and run
call venv\Scripts\activate.bat

REM Add src to PYTHONPATH
set "PYTHONPATH=%PROJECT_DIR%\src;%PYTHONPATH%"

python -m gesture_mouse %*

exit /b %ERRORLEVEL%
