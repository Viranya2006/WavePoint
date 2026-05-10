@echo off
REM WavePoint Build Script for Windows
REM Builds the C++ core library with pybind11 bindings

setlocal enabledelayedexpansion

echo ========================================
echo WavePoint Build Script
echo ========================================
echo.

REM Check for Visual Studio
where cl >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Visual Studio C++ compiler not found.
    echo Please run this script from a Visual Studio Developer Command Prompt.
    echo Or run: "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    exit /b 1
)

REM Check for CMake
where cmake >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: CMake not found. Please install CMake and add it to PATH.
    exit /b 1
)

REM Check for Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Please install Python 3.9+ and add it to PATH.
    exit /b 1
)

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

echo Project directory: %PROJECT_DIR%
echo.

REM Create build directory
set "BUILD_DIR=%PROJECT_DIR%\build"
if not exist "%BUILD_DIR%" (
    echo Creating build directory...
    mkdir "%BUILD_DIR%"
)

cd /d "%BUILD_DIR%"

REM Configure with CMake
echo.
echo ========================================
echo Configuring with CMake...
echo ========================================
echo.

cmake .. -G "Visual Studio 17 2022" -A x64
if %ERRORLEVEL% neq 0 (
    echo.
    echo Trying Visual Studio 2019...
    cmake .. -G "Visual Studio 16 2019" -A x64
    if %ERRORLEVEL% neq 0 (
        echo ERROR: CMake configuration failed.
        exit /b 1
    )
)

REM Build
echo.
echo ========================================
echo Building Release configuration...
echo ========================================
echo.

cmake --build . --config Release --parallel
if %ERRORLEVEL% neq 0 (
    echo ERROR: Build failed.
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo The gesture_mouse_core module has been built to:
echo   %PROJECT_DIR%\src\gesture_mouse\
echo.
echo You can now run the application with:
echo   cd %PROJECT_DIR%
echo   python -m gesture_mouse
echo.

cd /d "%PROJECT_DIR%"
exit /b 0
