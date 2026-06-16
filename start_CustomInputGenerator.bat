@echo off
REM Start Script for GNPy Custom Input Generator

echo ========================================
echo   GNPy Custom Input Generator
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo [1/2] Checking Python installation...
python --version
echo.

echo [2/2] Starting Custom Input Generator...
echo.
echo The application will open in your browser at http://localhost:8502
echo Press Ctrl+C to stop the server
echo.

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate (
    call .venv\Scripts\activate
    streamlit run app_CustomInputGenerator.py --server.port 8502
) else (
    streamlit run app_CustomInputGenerator.py --server.port 8502
)

pause
