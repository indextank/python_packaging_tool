@echo off
:: Fix PATH to ensure standard Windows commands work
set PATH=%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%

:: ============================================
:: Check admin privileges and auto-elevate
:: ============================================
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    :: Create temp VBS script for elevation
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"

    :: Run VBS script
    "%temp%\getadmin.vbs"

    :: Exit current non-admin script
    exit /b
) else (
    :: Delete temp VBS file if exists
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
)

:: ============================================
:: Change back to script directory after elevation
:: ============================================
cd /d "%~dp0"

:: Set title
title Python Packaging Tool

echo ==================================================
echo Environment Check
echo ==================================================

:: 1. Check Virtual Environment
if exist ".venv\Scripts\python.exe" goto :check_deps

echo [INFO] Virtual environment not found. Creating...
python -m venv .venv
if errorlevel 1 goto :error_venv

:: If we just created the venv, we force dependency installation
goto :install_deps

:check_deps
:: 2. Check Dependencies
if not exist "requirements.txt" goto :run_app

:: If marker file exists, assume dependencies are installed
if exist ".venv\installed.marker" goto :run_app

:install_deps
echo [INFO] Installing dependencies from requirements.txt...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --no-input
if errorlevel 1 goto :error_install

:: Create a marker file to indicate success
echo installed > ".venv\installed.marker"
echo [INFO] Dependencies installed successfully.
goto :run_app

:run_app
echo.
echo ==================================================
echo Starting Application
echo ==================================================
echo.

if not exist "main.py" goto :error_main

:: Run the main application
".venv\Scripts\python.exe" main.py

:: Capture exit code
set EXIT_CODE=%errorlevel%

:: Exit immediately - console will close automatically
exit /b %EXIT_CODE%

:: ----------------------------------------------------
:: Error Handlers
:: ----------------------------------------------------

:error_venv
echo.
echo [ERROR] Failed to create virtual environment.
echo Please ensure 'python' is installed and added to your PATH.
echo.
pause
exit /b 1

:error_install
echo.
echo [ERROR] Failed to install dependencies.
echo Please check your internet connection or requirements.txt.
echo.
pause
exit /b 1

:error_main
echo.
echo [ERROR] main.py not found in the current directory.
echo.
pause
exit /b 1
