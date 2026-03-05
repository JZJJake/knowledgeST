@echo off
setlocal EnableDelayedExpansion

echo ====================================================
echo Academic Knowledge Graph - Initialization Script
echo Target Environment: Windows Server 2012 R2
echo ====================================================
echo.

:: 1. Environment Detection: Check Python Version
echo [1/4] Detecting Python Environment...
python --version > python_ver.tmp 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in system PATH!
    echo Please install Python 3.11 and ensure it is added to the PATH.
    del python_ver.tmp
    goto ErrorExit
)

set /p PYTHON_VERSION=<python_ver.tmp
del python_ver.tmp
echo Detected: %PYTHON_VERSION%

:: Extract major and minor version numbers (e.g., "Python 3.11.5" -> "3" and "11")
for /f "tokens=2 delims= " %%a in ("%PYTHON_VERSION%") do set VER_STRING=%%a
for /f "tokens=1,2 delims=." %%a in ("%VER_STRING%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if "%MAJOR%" neq "3" (
    echo [ERROR] Unsupported Python major version. Requires Python 3.11.x.
    goto ErrorExit
)
if %MINOR% gtr 11 (
    echo [ERROR] Detected Python %MAJOR%.%MINOR%. Version higher than 3.11 detected!
    echo The dependency pre-compiled binaries (Wheels) are locked specifically for Python 3.11 to prevent C++ compilation on Windows Server 2012 R2.
    echo Please downgrade or use a Python 3.11 environment.
    goto ErrorExit
) else if %MINOR% lss 11 (
    echo [ERROR] Unsupported Python minor version. Requires Python 3.11.x.
    goto ErrorExit
) else (
    echo Python version 3.11 check passed.
)

:: 2. Sandbox Isolation: Check/Create Virtual Environment
echo.
echo [2/4] Initializing Sandbox Environment...
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment '.venv'...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto ErrorExit
    )
) else (
    echo Virtual environment already exists.
)

:: 3. Dependency Injection
echo.
echo [3/4] Activating Environment and Installing Dependencies...
call .venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip -q

echo Installing dependencies from requirements_win2012.txt...
:: --only-binary :all: forces pip to only download wheels and fail if it tries to build from source
pip install --only-binary :all: -r requirements_win2012.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed! Check the output above.
    goto ErrorExit
)

:: 4. Service Startup
echo.
echo [4/4] Starting Backend Service...
echo.
python main.py
if errorlevel 1 (
    echo [ERROR] Application terminated unexpectedly.
    goto ErrorExit
)

echo.
echo Shutdown complete.
goto End

:ErrorExit
echo.
echo ====================================================
echo An error occurred during execution.
echo Please review the logs above.
echo ====================================================
pause
exit /b 1

:End
pause
exit /b 0
