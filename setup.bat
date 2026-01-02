@echo off
:: Meeting Summary App - Windows Quick Setup
:: ==========================================
:: Double-click this file to run setup automatically

echo.
echo ========================================
echo    Meeting Summary App - Quick Setup
echo ========================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python found. Starting setup...
echo.

:: Run the setup script
python "%~dp0setup.py" --install

echo.
echo ========================================
echo Setup complete! Press any key to exit.
echo ========================================
pause >nul
