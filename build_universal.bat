@echo off
REM Force UTF-8 encoding and clear screen
chcp 65001 >nul 2>&1
if errorlevel 1 chcp 936 >nul 2>&1
cls
if errorlevel 1 echo.
setlocal enabledelayedexpansion

REM ============================================
REM Check admin privileges and auto-elevate
REM ============================================
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

if '%errorlevel%' NEQ '0' (

    REM Create temp VBS script for elevation
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"

    REM Run VBS script
    "%temp%\getadmin.vbs"

    REM Exit current non-admin script
    exit /b
) else (
    REM Delete temp VBS file if exists
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
)

REM ============================================
REM Change back to script directory after elevation
REM ============================================
cd /d "%~dp0"


REM ============================================
REM Universal Python Project Build Script v2.0
REM Nuitka Compilation with Time Tracking & Error Logging
REM ============================================

REM ============================================
REM Configuration section - Modify according to your project
REM ============================================

REM Project basic information (will be auto-detected from version.py if exists)
REM These are fallback values if version.py is not found
set "PROJECT_NAME=Python Packaging Tool"
set "PROJECT_DISPLAY_NAME=Python Packaging Tool"
set "COMPANY_NAME=WKLAN.CN"
set "PROJECT_DESCRIPTION=Python Packaging Tool"
set "PROJECT_VERSION=1.0"
set "PROJECT_COPYRIGHT=Copyright © 2026"

REM Auto-detect version info from version.py (set to true to enable)
set "AUTO_DETECT_VERSION=true"

REM Note: Version supports simplified format, will auto-convert to Windows standard format

REM Main entry file relative to project root
set "MAIN_FILE=main.py"

REM Output executable name without .exe suffix
set "OUTPUT_EXE_NAME=Python打包工具"

REM Icon file relative to project root, leave empty for no icon
set "ICON_FILE=resources\icons\icon.ico"

REM Show console window: true=show, false=hide
set "SHOW_CONSOLE=false"

REM Include Python packages (space-separated, leave empty to auto-detect)
REM Project packages: gui, core, utils
REM Third-party packages: requests (PyQt6 auto-detected by Nuitka)
set "INCLUDE_PACKAGES=requests gui core utils"

REM Exclude imports (space-separated)
REM Auto-exclude test/dev tools and unnecessary dependencies
REM Note: PyQt6 is NOT excluded as it's used by this project
set "EXCLUDE_IMPORTS=pytest test unittest doctest coverage nose mock tox setuptools wheel pip distutils pkg_resources sphinx docutils IPython jupyter notebook ipython ipykernel matplotlib seaborn pandas numpy scipy sklearn tensorflow torch cv2 opencv PIL pillow tkinter wxpy wxpython PyQt5 PySide2 PySide6 PyQt4 PySide polib"

REM Extra Nuitka arguments, leave empty for defaults
set "EXTRA_NUITKA_ARGS="

REM Windows 10/11 compatibility mode: true=enabled, false=standard
set "WIN10_COMPAT_MODE=true"

REM Enable LTO (Link Time Optimization): true=enabled, false=disabled
REM Reduces executable size and improves performance (slightly increases compile time)
set "ENABLE_LTO=true"

REM Enable Python optimization: true=enabled, false=disabled
REM Removes docstrings, disables asserts, enables Python -O flag
set "ENABLE_PYTHON_OPT=true"

REM ============================================
REM Script body below, usually no need to modify
REM ============================================

REM Error handling
if errorlevel 1 (
    echo Warning: Failed to set UTF-8 encoding, may cause display issues
)

echo.
echo ============================================
echo   %PROJECT_DISPLAY_NAME% - Build Script v2.0
echo   Universal Nuitka Compilation System
echo ============================================
echo.

REM Set project root and build directories
set "PROJECT_ROOT=%~dp0"
set "BUILD_DIR=%PROJECT_ROOT%build"
set "TEMP_DIR=%BUILD_DIR%\temp"
set "VENV_DIR=%PROJECT_ROOT%.venv"
REM exe files directly in build directory, no dist subdirectory
set "DIST_DIR=%BUILD_DIR%"

REM ============================================
REM Auto-detect version info from version.py
REM ============================================
if /i "!AUTO_DETECT_VERSION!"=="true" (
    call :detect_version_info
)

REM Record start time
set "START_TIME=%time%"
set "START_DATE=%date%"

REM Set build log file (records all output)
set "ERROR_LOG=%BUILD_DIR%\build.log"
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%" 2>nul
echo ============================================ > "%ERROR_LOG%"
echo Build Log - %PROJECT_DISPLAY_NAME% >> "%ERROR_LOG%"
echo Started at: %START_DATE% %START_TIME% >> "%ERROR_LOG%"
echo ============================================ >> "%ERROR_LOG%"
echo. >> "%ERROR_LOG%"

REM Define log function immediately after ERROR_LOG is set
REM Jump over the function definition to continue with main script
goto :after_log_echo_def
:log_echo
set "LOG_MSG=%~1"
if "!LOG_MSG!"=="" (
echo.
    if defined ERROR_LOG echo. >> "%ERROR_LOG%"
) else (
    echo !LOG_MSG!
    if defined ERROR_LOG echo !LOG_MSG! >> "%ERROR_LOG%"
)
goto :eof
:after_log_echo_def

call :log_echo [TIME] Build started at: %START_DATE% %START_TIME%
call :log_echo ""

REM Display configuration info
call :log_echo [CONFIG] Project Configuration:
call :log_echo   Project Name: !PROJECT_NAME!
call :log_echo   Version: !PROJECT_VERSION!
call :log_echo   Copyright: !PROJECT_COPYRIGHT!
call :log_echo   Main File: !MAIN_FILE!
call :log_echo   Output Name: !OUTPUT_EXE_NAME!.exe
call :log_echo   Console Mode: !SHOW_CONSOLE!
call :log_echo   Win10 Compat: !WIN10_COMPAT_MODE!
call :log_echo   LTO Optimization: !ENABLE_LTO!
call :log_echo   Python Optimization: !ENABLE_PYTHON_OPT!
call :log_echo   Auto-Detect Version: !AUTO_DETECT_VERSION!
call :log_echo ""

REM Set GCC cache path, auto-detect system arch and get latest version
set "GCC_DOWNLOAD_DIR=%LOCALAPPDATA%\Nuitka\Nuitka\Cache\downloads"
REM Detect system arch and get latest GCC version
call :detect_system_arch_and_get_gcc

REM Network connection pre-check
call :log_echo [Pre-check] Running network diagnostics...
call :check_network_advanced 2>nul
if errorlevel 1 call :log_echo [Info] Network check completed with warnings

REM Smart GCC cache management
call :log_echo [GCC Manager] Smart checking GCC compiler cache...
call :manage_gcc_cache

REM Select Python interpreter: prefer project virtualenv, otherwise use system Python
if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [Info] Project virtualenv Python: "%VENV_DIR%\Scripts\python.exe"
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
    if exist "%VENV_DIR%\Scripts\pip.exe" (
        set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
    ) else (
        set "PIP_EXE=%VENV_DIR%\Scripts\python.exe -m pip"
    )
) else (
    echo [Info] Virtual environment not found, system Python will be used
    set "PYTHON_EXE=python"
    set "PIP_EXE=pip"
)

REM Validate Python environment
call :log_echo [Check] Validating Python environment...
"%PYTHON_EXE%" --version >> "%ERROR_LOG%" 2>&1
if errorlevel 1 (
"%PYTHON_EXE%" --version >nul 2>&1
)
if !errorlevel! neq 0 (
    echo.
    echo ============================================
    echo [ERROR] Python environment unavailable!
    echo ============================================
    echo [TIP] Please check Python installation and PATH environment variable
    echo.
    call :show_elapsed_time
    pause
    exit /b 1
)

for /f "delims=" %%i in ('"%PYTHON_EXE%" --version 2^>^&1') do set PYTHON_VERSION=%%i
call :log_echo [INFO] Python version: !PYTHON_VERSION!

REM Check if main entry file exists
if not exist "%PROJECT_ROOT%%MAIN_FILE%" (
    call :log_echo ""
    call :log_echo ============================================
    call :log_echo [ERROR] Main file not found: %MAIN_FILE%
    call :log_echo ============================================
    call :log_echo [TIP] Please check MAIN_FILE configuration
    call :log_echo ""
    call :show_elapsed_time
    pause
    exit /b 1
)
call :log_echo [INFO] Main file found: %MAIN_FILE%

REM Create build directories
call :log_echo [PREPARE] Creating build directories...
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%" >> "%ERROR_LOG%" 2>&1
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%" >> "%ERROR_LOG%" 2>&1

REM Clean previous build files
call :log_echo [CLEANUP] Cleaning previous build files...
if exist "%BUILD_DIR%\*.exe" del /q "%BUILD_DIR%\*.exe" >> "%ERROR_LOG%" 2>&1
if exist "%TEMP_DIR%\*" rmdir /s /q "%TEMP_DIR%" 2>> "%ERROR_LOG%" && mkdir "%TEMP_DIR%" >> "%ERROR_LOG%" 2>&1

REM Check and install Nuitka
call :log_echo [CHECK] Verifying Nuitka installation...
"%PYTHON_EXE%" -c "import nuitka" >> "%ERROR_LOG%" 2>&1
if !errorlevel! neq 0 (
    call :log_echo [INSTALL] Nuitka not found, installing...
    call :install_nuitka_with_mirror
    if !errorlevel! neq 0 (
        call :log_echo ""
        call :log_echo ============================================
        call :log_echo [ERROR] Nuitka installation failed!
        call :log_echo ============================================
        call :log_echo [TIP] Please check network connection or try manual installation
        call :log_echo       Command: pip install nuitka
        call :log_echo ""
        call :show_elapsed_time
        pause
        exit /b 1
    )
) else (
    call :log_echo [SUCCESS] Nuitka is already installed
)

REM Check Nuitka version
call :check_nuitka_version

REM Windows version detection
call :log_echo [CHECK] Windows version detection...
for /f "tokens=4-5 delims=. " %%i in ('ver') do set WIN_VERSION=%%i.%%j
call :log_echo [INFO] Windows version: !WIN_VERSION!

REM Check and install project dependencies
call :log_echo [CHECK] Verifying project dependencies...
if exist "%PROJECT_ROOT%requirements.txt" (
    call :log_echo [INSTALL] Installing project dependencies...
    "%PYTHON_EXE%" -m pip install -r "%PROJECT_ROOT%requirements.txt" --quiet >> "%ERROR_LOG%" 2>&1
    if !errorlevel! neq 0 (
        call :log_echo [WARNING] Some dependencies failed to install, continuing build...
    ) else (
        call :log_echo [SUCCESS] Project dependencies installation completed
    )
) else (
    call :log_echo [INFO] requirements.txt not found, skipping dependency installation
)

REM Start compilation
call :log_echo ""
call :log_echo [Compile] Starting Nuitka compilation...
call :log_echo [Network] First-time use will auto-download GCC compiler (~378MB)
call :log_echo [Tip] Please ensure stable network connection, download may take 5-15 minutes
call :log_echo [LOG] Compilation output will be logged to: %ERROR_LOG%
call :log_echo ============================================

cd /d "%PROJECT_ROOT%"

REM Check icon file
set "ICON_PARAM="
if not "!ICON_FILE!"=="" (
    REM Convert to absolute path for icon file
    set "ICON_FULL_PATH=!PROJECT_ROOT!!ICON_FILE!"
    if exist "!ICON_FULL_PATH!" (
        REM Use the path directly - batch will handle spaces when variable is expanded
        REM Nuitka accepts paths with spaces in the parameter value
        set "ICON_PARAM=--windows-icon-from-ico=!ICON_FULL_PATH!"
        echo [INFO] Icon file: !ICON_FILE!
        echo [INFO] Icon full path: !ICON_FULL_PATH!
    ) else (
        echo [WARNING] Icon file not found: !ICON_FILE!, default icon will be used
        echo [WARNING] Expected path: !ICON_FULL_PATH!
    )
) else (
    echo [INFO] No icon specified, default icon will be used
)


REM Set console mode using new Nuitka parameter format
REM Note: Old parameters --enable-console and --disable-console are deprecated
REM New parameter options: force, disable, attach
if /i "!SHOW_CONSOLE!"=="true" (
    set CONSOLE_PARAM=--windows-console-mode=force
    call :log_echo [INFO] Console mode: enabled
) else (
    set CONSOLE_PARAM=--windows-console-mode=disable
    call :log_echo [INFO] Console mode: disabled
)


REM Build include package parameters
set "INCLUDE_PARAM="
if not "%INCLUDE_PACKAGES%"=="" (
    for %%p in (%INCLUDE_PACKAGES%) do (
        set "INCLUDE_PARAM=!INCLUDE_PARAM! --include-package=%%p"
    )
    call :log_echo [INFO] Including packages: %INCLUDE_PACKAGES%
) else (
    echo [INFO] No additional packages specified, automatic dependency detection enabled
)

REM Build exclude import parameters
set "EXCLUDE_PARAM="
if not "%EXCLUDE_IMPORTS%"=="" (
    for %%e in (%EXCLUDE_IMPORTS%) do (
        set "EXCLUDE_PARAM=!EXCLUDE_PARAM! --nofollow-import-to=%%e"
    )
    call :log_echo [INFO] Excluding imports: %EXCLUDE_IMPORTS%
    call :log_echo [Optimize] Auto-excluding unnecessary dependencies to speed up build...
)

REM First compilation attempt
call :log_echo [ATTEMPT] Starting intelligent compilation process...
call :compile_with_nuitka 1

REM Check compilation result
set "COMPILE_RESULT=!errorlevel!"
if !COMPILE_RESULT! equ 0 (
    call :log_echo ""
    call :log_echo ============================================
    call :log_echo [SUCCESS] Compilation completed!
    call :log_echo ============================================

    REM Find and move generated executable
    call :find_and_move_exe

    REM Clean temp directory immediately exe moved, no longer needed
    echo.
    echo [CLEANUP] Cleaning build temp directory...
    if exist "%TEMP_DIR%" (
        rmdir /s /q "%TEMP_DIR%" 2>nul
        echo [SUCCESS] Temp directory cleaned
    )

    REM Copy necessary config files
    call :copy_runtime_files

    REM Display build info
    call :show_build_info

    REM Display elapsed time
    echo.
    call :show_elapsed_time
    echo.
    echo ============================================
    echo [INFO] Build completed successfully!
    echo ============================================

    REM Clean cache immediately after successful build
    echo.
    echo [CLEANUP] Cleaning build cache after successful build...

    REM Clean Nuitka build cache directories in project root
    if exist "%PROJECT_ROOT%.build" (
        echo [Clean] Removing .build directory...
        rmdir /s /q "%PROJECT_ROOT%.build" 2>nul
    )

    if exist "%PROJECT_ROOT%.dist" (
        echo [Clean] Removing .dist directory...
        rmdir /s /q "%PROJECT_ROOT%.dist" 2>nul
    )

    if exist "%PROJECT_ROOT%.onefile-build" (
        echo [Clean] Removing .onefile-build directory...
        rmdir /s /q "%PROJECT_ROOT%.onefile-build" 2>nul
    )

    REM Clean Nuitka build cache directories in build folder (main.build, main.dist, etc.)
    for /d %%d in ("%BUILD_DIR%\*.build") do (
        echo [Clean] Removing Nuitka cache: %%~nxd
        rmdir /s /q "%%d" 2>nul
    )

    for /d %%d in ("%BUILD_DIR%\*.dist") do (
        echo [Clean] Removing Nuitka dist: %%~nxd
        rmdir /s /q "%%d" 2>nul
    )

    for /d %%d in ("%BUILD_DIR%\*.onefile-build") do (
        echo [Clean] Removing Nuitka onefile cache: %%~nxd
        rmdir /s /q "%%d" 2>nul
    )

    REM Clean runtime-generated icon files in build directory (these should be embedded in exe)
    if exist "%BUILD_DIR%\app_icon.ico" (
        echo [Clean] Removing temp icon: app_icon.ico
        del /q "%BUILD_DIR%\app_icon.ico" 2>nul
    )

    if exist "%BUILD_DIR%\check_dark.png" (
        echo [Clean] Removing runtime icon: check_dark.png
        del /q "%BUILD_DIR%\check_dark.png" 2>nul
    )

    if exist "%BUILD_DIR%\check_light.png" (
        echo [Clean] Removing runtime icon: check_light.png
        del /q "%BUILD_DIR%\check_light.png" 2>nul
    )

    if exist "%BUILD_DIR%\radio_dark.png" (
        echo [Clean] Removing runtime icon: radio_dark.png
        del /q "%BUILD_DIR%\radio_dark.png" 2>nul
    )

    if exist "%BUILD_DIR%\radio_light.png" (
        echo [Clean] Removing runtime icon: radio_light.png
        del /q "%BUILD_DIR%\radio_light.png" 2>nul
    )

    REM Clean config directory if empty or contains only generated files
    if exist "%BUILD_DIR%\config" (
        echo [Clean] Removing config directory...
        rmdir /s /q "%BUILD_DIR%\config" 2>nul
    )

    REM Clean __pycache__ directories
    for /d /r "%PROJECT_ROOT%" %%d in (__pycache__) do (
        if exist "%%d" (
            echo [Clean] Removing __pycache__: %%d
            rmdir /s /q "%%d" 2>nul
        )
    )

    REM Clean .pyc files
    for /r "%PROJECT_ROOT%" %%f in (*.pyc) do (
        if exist "%%f" (
            del /q "%%f" 2>nul
        )
    )

    REM Clean .pyo files
    for /r "%PROJECT_ROOT%" %%f in (*.pyo) do (
        if exist "%%f" (
            del /q "%%f" 2>nul
        )
    )

    REM Clean .pyi files
    for %%f in ("%PROJECT_ROOT%*.pyi") do (
        if exist "%%f" (
            echo [Clean] Removing: %%~nxf
            del /q "%%f" 2>nul
        )
    )

    REM Clean compilation reports
    for %%f in ("%PROJECT_ROOT%compilation_report*.xml") do (
        if exist "%%f" (
            echo [Clean] Removing: %%~nxf
            del /q "%%f" 2>nul
        )
    )

    echo [SUCCESS] Build cache cleanup completed
    echo.

) else (
    call :log_echo ""
    call :log_echo ============================================
    call :log_echo [FAILED] All compilation attempts failed
    call :log_echo ============================================

    REM Execute failure diagnosis and guidance
    call :failure_diagnosis_and_guidance

    REM Display elapsed time
    echo.
    call :show_elapsed_time
)

REM Clean temporary files (residuals from failed build)
if exist "%TEMP_DIR%" (
    call :log_echo ""
    call :log_echo [CLEANUP] Cleaning temporary files...
    call :log_echo [Clean] Removing temp directory: %TEMP_DIR%
    rmdir /s /q "%TEMP_DIR%" >> "%ERROR_LOG%" 2>&1
    call :log_echo [SUCCESS] Cleanup completed
)

call :log_echo ""
call :log_echo Press any key to exit...
pause >nul
goto :eof

REM ============================================
REM Function Definitions
REM ============================================

REM Detect version info from version.py
:detect_version_info
set "VERSION_FILE=!PROJECT_ROOT!version.py"

if not exist "!VERSION_FILE!" (
    echo [Info] version.py not found, using default values
    goto :eof
)

echo [Auto-Detect] Reading version info from version.py...

REM Detect if current environment supports Chinese (check for Windows SDK or Visual Studio)
set "SUPPORTS_CHINESE=false"
REM Check Windows SDK
if exist "%ProgramFiles(x86)%\Windows Kits\10\bin\*" set "SUPPORTS_CHINESE=true"
if exist "%ProgramFiles%\Windows Kits\10\bin\*" set "SUPPORTS_CHINESE=true"
REM Check Visual Studio
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\*" set "SUPPORTS_CHINESE=true"
if exist "%ProgramFiles%\Microsoft Visual Studio\*" set "SUPPORTS_CHINESE=true"

if "!SUPPORTS_CHINESE!"=="true" (
    echo [Auto-Detect] Windows SDK/Visual Studio detected, Chinese version info supported
) else (
    echo [Auto-Detect] No Windows SDK/Visual Studio found, using English version info
)

REM Use PowerShell to parse version.py and write each field to separate temp files
REM This avoids for /f parsing issues with Chinese characters and special characters
set "PS_SCRIPT=%TEMP%\parse_version.ps1"
set "TEMP_VERSION_FILE=%TEMP%\ver_version.txt"
set "TEMP_COPYRIGHT_FILE=%TEMP%\ver_copyright.txt"
set "TEMP_APPNAME_FILE=%TEMP%\ver_appname.txt"
set "TEMP_APPNAME_EN_FILE=%TEMP%\ver_appname_en.txt"
set "TEMP_DESC_FILE=%TEMP%\ver_desc.txt"
set "TEMP_DESC_EN_FILE=%TEMP%\ver_desc_en.txt"

REM Create PowerShell script to parse version.py and write to temp files
> "!PS_SCRIPT!" echo $content = Get-Content -Path '!VERSION_FILE!' -Raw -Encoding UTF8
>> "!PS_SCRIPT!" echo $version = ''
>> "!PS_SCRIPT!" echo $copyright = ''
>> "!PS_SCRIPT!" echo $app_name = ''
>> "!PS_SCRIPT!" echo $app_name_en = ''
>> "!PS_SCRIPT!" echo $description = ''
>> "!PS_SCRIPT!" echo $description_en = ''
>> "!PS_SCRIPT!" echo.
>> "!PS_SCRIPT!" echo # Extract __version__
>> "!PS_SCRIPT!" echo if ($content -match '__version__\s*=\s*[''"]([^''"]+)[''"]') { $version = $matches[1] }
>> "!PS_SCRIPT!" echo # Extract AUTHOR first (needed for COPYRIGHT)
>> "!PS_SCRIPT!" echo $author = ''
>> "!PS_SCRIPT!" echo if ($content -match 'AUTHOR\s*=\s*[''"]([^''"]+)[''"]') { $author = $matches[1] }
>> "!PS_SCRIPT!" echo # Extract COPYRIGHT - check if it's an f-string with AUTHOR
>> "!PS_SCRIPT!" echo if ($content -match 'COPYRIGHT\s*=\s*f[''"]') {
>> "!PS_SCRIPT!" echo     $year = (Get-Date).Year
>> "!PS_SCRIPT!" echo     if ($author -ne '') { $copyright = "Copyright (c) $year $author" }
>> "!PS_SCRIPT!" echo } elseif ($content -match 'COPYRIGHT\s*=\s*[''"]([^''"]+)[''"]') {
>> "!PS_SCRIPT!" echo     $copyright = $matches[1]
>> "!PS_SCRIPT!" echo }
>> "!PS_SCRIPT!" echo # Extract APP_NAME (Chinese name)
>> "!PS_SCRIPT!" echo if ($content -match '(?m)^APP_NAME\s*=\s*[''"]([^''"]+)[''"]') { $app_name = $matches[1] }
>> "!PS_SCRIPT!" echo # Extract APP_NAME_EN (English name)
>> "!PS_SCRIPT!" echo if ($content -match 'APP_NAME_EN\s*=\s*[''"]([^''"]+)[''"]') { $app_name_en = $matches[1] }
>> "!PS_SCRIPT!" echo # Extract DESCRIPTION (Chinese) - match any characters including Chinese
>> "!PS_SCRIPT!" echo if ($content -match '(?m)^DESCRIPTION\s*=\s*[''"](.+?)[''"]') { $description = $matches[1] }
>> "!PS_SCRIPT!" echo # Extract DESCRIPTION_EN (English)
>> "!PS_SCRIPT!" echo if ($content -match '(?m)^DESCRIPTION_EN\s*=\s*[''"](.+?)[''"]') { $description_en = $matches[1] }
>> "!PS_SCRIPT!" echo.
>> "!PS_SCRIPT!" echo # Write each field to separate temp files (UTF-8 without BOM for batch compatibility)
>> "!PS_SCRIPT!" echo [System.IO.File]::WriteAllText('!TEMP_VERSION_FILE!', $version, [System.Text.UTF8Encoding]::new($false))
>> "!PS_SCRIPT!" echo [System.IO.File]::WriteAllText('!TEMP_COPYRIGHT_FILE!', $copyright, [System.Text.UTF8Encoding]::new($false))
>> "!PS_SCRIPT!" echo [System.IO.File]::WriteAllText('!TEMP_APPNAME_FILE!', $app_name, [System.Text.UTF8Encoding]::new($false))
>> "!PS_SCRIPT!" echo [System.IO.File]::WriteAllText('!TEMP_APPNAME_EN_FILE!', $app_name_en, [System.Text.UTF8Encoding]::new($false))
>> "!PS_SCRIPT!" echo [System.IO.File]::WriteAllText('!TEMP_DESC_FILE!', $description, [System.Text.UTF8Encoding]::new($false))
>> "!PS_SCRIPT!" echo [System.IO.File]::WriteAllText('!TEMP_DESC_EN_FILE!', $description_en, [System.Text.UTF8Encoding]::new($false))

REM Execute PowerShell script
echo [DEBUG] Executing PowerShell script: !PS_SCRIPT!
echo [DEBUG] VERSION_FILE: !VERSION_FILE!
powershell -NoProfile -ExecutionPolicy Bypass -File "!PS_SCRIPT!"

REM Read version from temp file (version is pure ASCII, safe to read)
echo [DEBUG] Checking temp file: !TEMP_VERSION_FILE!
if exist "!TEMP_VERSION_FILE!" (
    set /p PROJECT_VERSION=<"!TEMP_VERSION_FILE!"
    echo [DEBUG] Read PROJECT_VERSION: !PROJECT_VERSION!
) else (
    echo [DEBUG] Temp version file NOT found
)
REM Read copyright from temp file
if exist "!TEMP_COPYRIGHT_FILE!" (
    set /p PROJECT_COPYRIGHT=<"!TEMP_COPYRIGHT_FILE!"
)
REM Read app names from temp files
if exist "!TEMP_APPNAME_FILE!" (
    set /p DETECTED_APP_NAME=<"!TEMP_APPNAME_FILE!"
)
if exist "!TEMP_APPNAME_EN_FILE!" (
    set /p DETECTED_APP_NAME_EN=<"!TEMP_APPNAME_EN_FILE!"
)
REM Read descriptions from temp files using PowerShell to handle UTF-8 encoding
set "DETECTED_DESCRIPTION="
set "DETECTED_DESCRIPTION_EN="
if exist "!TEMP_DESC_FILE!" (
    set "PS_READ_DESC=%TEMP%\read_desc_%RANDOM%.ps1"
    > "!PS_READ_DESC!" echo $ErrorActionPreference = 'Stop'
    >> "!PS_READ_DESC!" echo try {
    >> "!PS_READ_DESC!" echo     $content = [System.IO.File]::ReadAllText('!TEMP_DESC_FILE!', [System.Text.Encoding]::UTF8)
    >> "!PS_READ_DESC!" echo     $content = $content.Trim()
    >> "!PS_READ_DESC!" echo     if ($content -ne '') { Write-Output $content }
    >> "!PS_READ_DESC!" echo } catch {
    >> "!PS_READ_DESC!" echo     Write-Output ''
    >> "!PS_READ_DESC!" echo }
    for /f "delims=" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "!PS_READ_DESC!" 2^>nul') do (
        set "DETECTED_DESCRIPTION=%%a"
    )
    del "!PS_READ_DESC!" >nul 2>&1
    if defined DETECTED_DESCRIPTION (
        echo [DEBUG] Read DETECTED_DESCRIPTION from file: !DETECTED_DESCRIPTION!
    ) else (
        echo [DEBUG] DETECTED_DESCRIPTION is empty after reading from file
    )
)
if "!DETECTED_DESCRIPTION!"=="" if exist "!TEMP_DESC_FILE!" (
    for /f "usebackq delims=" %%a in ("!TEMP_DESC_FILE!") do set "DETECTED_DESCRIPTION=%%a"
    if not "!DETECTED_DESCRIPTION!"=="" (
        echo [DEBUG] Fallback DETECTED_DESCRIPTION from file: !DETECTED_DESCRIPTION!
    ) else (
        echo [DEBUG] Fallback DETECTED_DESCRIPTION still empty
    )
)
if exist "!TEMP_DESC_EN_FILE!" (
    set "PS_READ_DESC_EN=%TEMP%\read_desc_en_%RANDOM%.ps1"
    > "!PS_READ_DESC_EN!" echo $ErrorActionPreference = 'Stop'
    >> "!PS_READ_DESC_EN!" echo try {
    >> "!PS_READ_DESC_EN!" echo     $content = [System.IO.File]::ReadAllText('!TEMP_DESC_EN_FILE!', [System.Text.Encoding]::UTF8)
    >> "!PS_READ_DESC_EN!" echo     $content = $content.Trim()
    >> "!PS_READ_DESC_EN!" echo     if ($content -ne '') { Write-Output $content }
    >> "!PS_READ_DESC_EN!" echo } catch {
    >> "!PS_READ_DESC_EN!" echo     Write-Output ''
    >> "!PS_READ_DESC_EN!" echo }
    for /f "delims=" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "!PS_READ_DESC_EN!" 2^>nul') do (
        set "DETECTED_DESCRIPTION_EN=%%a"
    )
    del "!PS_READ_DESC_EN!" >nul 2>&1
    if defined DETECTED_DESCRIPTION_EN (
        echo [DEBUG] Read DETECTED_DESCRIPTION_EN from file: !DETECTED_DESCRIPTION_EN!
    )
)

REM Clean up temp files (disabled for debugging)
REM del "!TEMP_VERSION_FILE!" >nul 2>&1
REM del "!TEMP_COPYRIGHT_FILE!" >nul 2>&1
REM del "!TEMP_APPNAME_FILE!" >nul 2>&1
REM del "!TEMP_APPNAME_EN_FILE!" >nul 2>&1
REM del "!TEMP_DESC_FILE!" >nul 2>&1
REM del "!TEMP_DESC_EN_FILE!" >nul 2>&1

REM Clean temporary script (disabled for debugging)
REM if exist "!PS_SCRIPT!" del "!PS_SCRIPT!" >nul 2>&1
echo [DEBUG] Temp files preserved for inspection
echo [DEBUG] About to check SUPPORTS_CHINESE

REM Select Chinese or English based on environment support
echo [DEBUG] SUPPORTS_CHINESE=!SUPPORTS_CHINESE!

if "!SUPPORTS_CHINESE!"=="true" goto :process_chinese_info
goto :process_english_info

:process_chinese_info
echo [DEBUG] Inside SUPPORTS_CHINESE==true block
REM Prefer Chinese
if defined DETECTED_APP_NAME (
    set "PROJECT_NAME=!DETECTED_APP_NAME!"
    set "PROJECT_DISPLAY_NAME=!DETECTED_APP_NAME!"
) else (
    if defined DETECTED_APP_NAME_EN (
        set "PROJECT_NAME=!DETECTED_APP_NAME_EN!"
        set "PROJECT_DISPLAY_NAME=!DETECTED_APP_NAME_EN!"
    )
)

REM For description, always prefer Chinese if it exists
if not "!DETECTED_DESCRIPTION!"=="" (
    set "PROJECT_DESCRIPTION=!DETECTED_DESCRIPTION!"
    echo [DEBUG] Using Chinese description: !PROJECT_DESCRIPTION!
) else (
    if not "!DETECTED_DESCRIPTION_EN!"=="" (
        set "PROJECT_DESCRIPTION=!DETECTED_DESCRIPTION_EN!"
        echo [DEBUG] Using English description - Chinese not found: !PROJECT_DESCRIPTION!
    )
)
goto :after_process_language

:process_english_info
REM Use English only (but prefer Chinese description if available)
if defined DETECTED_APP_NAME_EN (
    set "PROJECT_NAME=!DETECTED_APP_NAME_EN!"
    set "PROJECT_DISPLAY_NAME=!DETECTED_APP_NAME_EN!"
)
if not "!DETECTED_DESCRIPTION!"=="" (
    set "PROJECT_DESCRIPTION=!DETECTED_DESCRIPTION!"
) else if not "!DETECTED_DESCRIPTION_EN!"=="" (
    set "PROJECT_DESCRIPTION=!DETECTED_DESCRIPTION_EN!"
)
goto :after_process_language

:after_process_language

REM Output detection results
echo [DEBUG] Before output detection results
echo [Auto-Detect] Version: !PROJECT_VERSION!
echo [DEBUG] After Version output
echo [Auto-Detect] Copyright: "!PROJECT_COPYRIGHT!"
echo [DEBUG] After Copyright output
echo [Auto-Detect] Product Name: "!PROJECT_NAME!"
echo [DEBUG] After Product Name output
echo [Auto-Detect] Description: "!PROJECT_DESCRIPTION!"
echo [DEBUG] After Description output
echo [DEBUG] DETECTED_APP_NAME: "!DETECTED_APP_NAME!"
echo [DEBUG] DETECTED_APP_NAME_EN: "!DETECTED_APP_NAME_EN!"
echo [DEBUG] About to return from detect_version_info
echo.

goto :eof

REM Check Nuitka version
REM Returns: NUITKA_VERSION_MAJOR, NUITKA_VERSION_MINOR, NUITKA_SUPPORTS_RC_FILE (true/false)
:check_nuitka_version
set "NUITKA_VERSION_MAJOR=0"
set "NUITKA_VERSION_MINOR=0"
set "NUITKA_SUPPORTS_RC_FILE=false"

REM Get Nuitka version using Python
set "VERSION_CHECK_SCRIPT=%TEMP%\check_nuitka_version_%RANDOM%.py"
> "!VERSION_CHECK_SCRIPT!" echo import nuitka
>> "!VERSION_CHECK_SCRIPT!" echo try:
>> "!VERSION_CHECK_SCRIPT!" echo     version = nuitka.__version__
>> "!VERSION_CHECK_SCRIPT!" echo     parts = version.split('.')
>> "!VERSION_CHECK_SCRIPT!" echo     major = int(parts[0]) if len(parts) ^> 0 else 0
>> "!VERSION_CHECK_SCRIPT!" echo     minor = int(parts[1]) if len(parts) ^> 1 else 0
>> "!VERSION_CHECK_SCRIPT!" echo     print(f"{major}.{minor}")
>> "!VERSION_CHECK_SCRIPT!" echo except:
>> "!VERSION_CHECK_SCRIPT!" echo     print("0.0")

for /f "tokens=1-2 delims=." %%a in ('"%PYTHON_EXE%" "!VERSION_CHECK_SCRIPT!" 2^>nul') do (
    set "NUITKA_VERSION_MAJOR=%%a"
    set "NUITKA_VERSION_MINOR=%%b"
)

del "!VERSION_CHECK_SCRIPT!" >nul 2>&1

REM Note: Nuitka 2.8.9 (latest) does not support --windows-force-rc-file
REM Resource files can be created for Chinese version info, but Nuitka cannot use them directly
REM We will use command line parameters instead and ensure icon is always added separately
set "NUITKA_SUPPORTS_RC_FILE=false"

call :log_echo [INFO] Nuitka version: !NUITKA_VERSION_MAJOR!.!NUITKA_VERSION_MINOR!
call :log_echo [INFO] Note: Nuitka 2.8.9 does not support --windows-force-rc-file, will use command line parameters

goto :eof

REM Create Windows resource file for Chinese version info
REM Returns: RC_FILE_PATH (global variable) - path to compiled .res file, empty if failed
:create_version_resource_file
set "RC_FILE_PATH="
set "RC_SOURCE=!TEMP_DIR!\version_info.rc"
set "RES_FILE=!TEMP_DIR!\version_info.res"

REM Find rc.exe from Windows SDK
set "RC_EXE="
REM Check PATH first
where rc.exe >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%p in ('where rc.exe 2^>nul') do (
        set "RC_EXE=%%p"
        goto :found_rc
    )
)
REM Search Windows SDK
for /d %%d in ("%ProgramFiles(x86)%\Windows Kits\10\bin\10.*") do (
    if exist "%%d\x64\rc.exe" (
        set "RC_EXE=%%d\x64\rc.exe"
        goto :found_rc
    )
)
for /d %%d in ("%ProgramFiles%\Windows Kits\10\bin\10.*") do (
    if exist "%%d\x64\rc.exe" (
        set "RC_EXE=%%d\x64\rc.exe"
        goto :found_rc
    )
)
:found_rc

if not defined RC_EXE (
    call :log_echo [WARNING] rc.exe not found, cannot compile resource file
    goto :eof
)
call :log_echo [INFO] Found resource compiler: !RC_EXE!

REM Parse version to 4-part format for resource file
set "VER_PART1=0"
set "VER_PART2=0"
set "VER_PART3=0"
set "VER_PART4=0"
for /f "tokens=1-4 delims=." %%a in ("!WIN_VERSION!") do (
    if not "%%a"=="" set "VER_PART1=%%a"
    if not "%%b"=="" set "VER_PART2=%%b"
    if not "%%c"=="" set "VER_PART3=%%c"
    if not "%%d"=="" set "VER_PART4=%%d"
)

REM Create .rc file with UTF-8 BOM for Chinese support
REM Use PowerShell to write UTF-8 with BOM
set "RC_PS_SCRIPT=!TEMP_DIR!\create_rc.ps1"

REM Build the RC content - note: OriginalFilename is intentionally omitted
REM Do NOT include windows.h - define constants manually to avoid dependency
> "!RC_PS_SCRIPT!" echo $rcContent = @"
>> "!RC_PS_SCRIPT!" echo // Version info resource - Generated by build_universal.bat
>> "!RC_PS_SCRIPT!" echo // Supports Chinese characters
>> "!RC_PS_SCRIPT!" echo // Self-contained - does not require windows.h
>> "!RC_PS_SCRIPT!" echo.
>> "!RC_PS_SCRIPT!" echo // Define constants manually (from winver.h)
>> "!RC_PS_SCRIPT!" echo #ifndef VS_VERSION_INFO
>> "!RC_PS_SCRIPT!" echo #define VS_VERSION_INFO 1
>> "!RC_PS_SCRIPT!" echo #endif
>> "!RC_PS_SCRIPT!" echo #define VOS_NT_WINDOWS32 0x00040004L
>> "!RC_PS_SCRIPT!" echo #define VFT_APP 0x00000001L
>> "!RC_PS_SCRIPT!" echo.
>> "!RC_PS_SCRIPT!" echo // Include icon if available
if defined ICON_FULL_PATH (
    if exist "!ICON_FULL_PATH!" (
        REM Escape backslashes in icon path for RC file
        set "ICON_PATH_ESCAPED=!ICON_FULL_PATH:\=\\!"
        >> "!RC_PS_SCRIPT!" echo IDI_ICON1 ICON "!ICON_PATH_ESCAPED!"
        >> "!RC_PS_SCRIPT!" echo.
        call :log_echo [INFO] Icon will be included in resource file: !ICON_FILE!
    )
)
>> "!RC_PS_SCRIPT!" echo VS_VERSION_INFO VERSIONINFO
>> "!RC_PS_SCRIPT!" echo  FILEVERSION !VER_PART1!,!VER_PART2!,!VER_PART3!,!VER_PART4!
>> "!RC_PS_SCRIPT!" echo  PRODUCTVERSION !VER_PART1!,!VER_PART2!,!VER_PART3!,!VER_PART4!
>> "!RC_PS_SCRIPT!" echo  FILEFLAGSMASK 0x3fL
>> "!RC_PS_SCRIPT!" echo #ifdef _DEBUG
>> "!RC_PS_SCRIPT!" echo  FILEFLAGS 0x1L
>> "!RC_PS_SCRIPT!" echo #else
>> "!RC_PS_SCRIPT!" echo  FILEFLAGS 0x0L
>> "!RC_PS_SCRIPT!" echo #endif
>> "!RC_PS_SCRIPT!" echo  FILEOS VOS_NT_WINDOWS32
>> "!RC_PS_SCRIPT!" echo  FILETYPE VFT_APP
>> "!RC_PS_SCRIPT!" echo  FILESUBTYPE 0x0L
>> "!RC_PS_SCRIPT!" echo BEGIN
>> "!RC_PS_SCRIPT!" echo     BLOCK "StringFileInfo"
>> "!RC_PS_SCRIPT!" echo     BEGIN
>> "!RC_PS_SCRIPT!" echo         BLOCK "080404b0"
>> "!RC_PS_SCRIPT!" echo         BEGIN
>> "!RC_PS_SCRIPT!" echo             VALUE "CompanyName", "!COMPANY_NAME!"
>> "!RC_PS_SCRIPT!" echo             VALUE "FileDescription", "!FILE_DESC_VALUE!"
>> "!RC_PS_SCRIPT!" echo             VALUE "FileVersion", "!WIN_VERSION!"
>> "!RC_PS_SCRIPT!" echo             VALUE "InternalName", "!OUTPUT_EXE_NAME!"
>> "!RC_PS_SCRIPT!" echo             VALUE "LegalCopyright", "!PROJECT_COPYRIGHT!"
>> "!RC_PS_SCRIPT!" echo             VALUE "ProductName", "!PRODUCT_NAME_VALUE!"
>> "!RC_PS_SCRIPT!" echo             VALUE "ProductVersion", "!WIN_VERSION!"
>> "!RC_PS_SCRIPT!" echo         END
>> "!RC_PS_SCRIPT!" echo     END
>> "!RC_PS_SCRIPT!" echo     BLOCK "VarFileInfo"
>> "!RC_PS_SCRIPT!" echo     BEGIN
>> "!RC_PS_SCRIPT!" echo         VALUE "Translation", 0x804, 1200
>> "!RC_PS_SCRIPT!" echo     END
>> "!RC_PS_SCRIPT!" echo END
>> "!RC_PS_SCRIPT!" echo "@
>> "!RC_PS_SCRIPT!" echo.
>> "!RC_PS_SCRIPT!" echo # Write RC file with UTF-8 BOM
>> "!RC_PS_SCRIPT!" echo [System.IO.File]::WriteAllText('!RC_SOURCE!', $rcContent, [System.Text.UTF8Encoding]::new($true))

REM Execute PowerShell to create RC file
powershell -NoProfile -ExecutionPolicy Bypass -File "!RC_PS_SCRIPT!" >nul 2>&1

if not exist "!RC_SOURCE!" (
    call :log_echo [WARNING] Failed to create RC source file
    del "!RC_PS_SCRIPT!" >nul 2>&1
    goto :eof
)

call :log_echo [INFO] Created resource source file: !RC_SOURCE!

REM Compile RC to RES (no include paths needed - self-contained)
echo [DEBUG-RC] Compiling with command: "!RC_EXE!" /fo "!RES_FILE!" /nologo "!RC_SOURCE!"
"!RC_EXE!" /fo "!RES_FILE!" /nologo "!RC_SOURCE!" 2>&1
set "RC_COMPILE_ERROR=!errorlevel!"
echo [DEBUG-RC] RC.EXE exit code: !RC_COMPILE_ERROR!
if !RC_COMPILE_ERROR! neq 0 (
    call :log_echo [ERROR] Failed to compile resource file, error code: !RC_COMPILE_ERROR!
    call :log_echo [ERROR] Resource compilation failed even without windows.h dependency
    call :log_echo [ERROR] Please check if rc.exe is working correctly
    del "!RC_PS_SCRIPT!" >nul 2>&1
    goto :eof
)

if exist "!RES_FILE!" (
    set "RC_FILE_PATH=!RES_FILE!"
    call :log_echo [INFO] Compiled resource file: !RES_FILE!
    echo [DEBUG-RC] Resource file successfully created
) else (
    call :log_echo [WARNING] Resource file not created despite success exit code
    echo [DEBUG-RC] RES file not found at: !RES_FILE!
)

REM Clean up
del "!RC_PS_SCRIPT!" >nul 2>&1

goto :eof

REM Find and move executable file
:find_and_move_exe
echo [SEARCH] Looking for generated executable files...

set "EXE_FOUND=0"
set "MAIN_FILE_BASE=%MAIN_FILE:.py=%"

REM 1. Check project root directory
if exist "%PROJECT_ROOT%%MAIN_FILE_BASE%.exe" (
    move "%PROJECT_ROOT%%MAIN_FILE_BASE%.exe" "%DIST_DIR%\%OUTPUT_EXE_NAME%.exe"
    echo [SUCCESS] Executable moved: %DIST_DIR%\%OUTPUT_EXE_NAME%.exe
    set "EXE_FOUND=1"
    goto :eof
)

REM 2. Check temp directory
if exist "%TEMP_DIR%\%MAIN_FILE_BASE%.exe" (
    move "%TEMP_DIR%\%MAIN_FILE_BASE%.exe" "%DIST_DIR%\%OUTPUT_EXE_NAME%.exe"
    echo [SUCCESS] Executable moved: %DIST_DIR%\%OUTPUT_EXE_NAME%.exe
    set "EXE_FOUND=1"
    goto :eof
)

REM 3. Search all possible exe files
for %%f in ("%PROJECT_ROOT%*.exe") do (
    if /i not "%%~nxf"=="build_universal.bat" (
        move "%%f" "%DIST_DIR%\%OUTPUT_EXE_NAME%.exe"
        echo [SUCCESS] Executable moved: %DIST_DIR%\%OUTPUT_EXE_NAME%.exe
        set "EXE_FOUND=1"
        goto :eof
    )
)

if !EXE_FOUND! equ 0 (
    echo [WARNING] Generated executable file not found
    echo [TIP] Please check compilation output or manually search for exe file
)

goto :eof

REM Copy runtime files
:copy_runtime_files
echo [DEPLOY] Copying runtime files...

REM No longer copy config files and icons, let the program auto-generate config.json at runtime
REM Icons are already embedded in exe file, no need to copy separately

echo [INFO] Runtime files copy completed (minimal deployment)
goto :eof

REM Display build information
:show_build_info
echo.
echo ============================================
echo           Build Information Summary
echo ============================================
if exist "%DIST_DIR%\%OUTPUT_EXE_NAME%.exe" (
    for %%i in ("%DIST_DIR%\%OUTPUT_EXE_NAME%.exe") do (
        set /a "SIZE_MB=%%~zi / 1048576"
        echo File name: %OUTPUT_EXE_NAME%.exe
        echo File size: %%~zi bytes (about !SIZE_MB! MB)
        echo Build time: %%~ti
        echo File location: %%~fi
    )
    echo.
    echo [SUCCESS] Nuitka compilation completed successfully!
) else (
    echo [ERROR] Executable file not found
)
echo.
echo Build directory: %BUILD_DIR%
echo Executable location: %BUILD_DIR%\%OUTPUT_EXE_NAME%.exe
echo Python version: !PYTHON_VERSION!
echo Build tool: Nuitka
echo.
goto :eof

REM Enhanced network connection check
:check_network_advanced
echo [Network] Testing basic connection...
ping -n 1 -w 3000 8.8.8.8 >nul 2>&1
if !errorlevel! neq 0 (
    echo [Warning] DNS resolution failed or network down
    set "NETWORK_OK=0"
) else (
    set "NETWORK_OK=1"
)

echo [Network] Testing GitHub connection...
ping -n 1 -w 3000 github.com >nul 2>&1
if !errorlevel! neq 0 (
    echo [Warning] GitHub connection abnormal, may affect GCC compiler download
    if !NETWORK_OK! equ 1 (
        echo [Tip] Possible DNS issue or firewall blocking
    )
) else (
    echo [Info] GitHub connection normal
)

echo.
goto :eof

REM Install Nuitka with smart mirror selection
:install_nuitka_with_mirror
echo [Info] Detecting fastest pip mirror source...
set "PIP_MIRROR="
set "MIRROR_NAME=PyPI Official"
set "BEST_TIME=9999"

REM Test PyPI official source
echo Testing: PyPI Official...
powershell -Command "$ProgressPreference='SilentlyContinue'; $sw=[System.Diagnostics.Stopwatch]::StartNew(); try { $null=Invoke-WebRequest -Uri 'https://pypi.org' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; $sw.Stop(); Write-Host $sw.ElapsedMilliseconds } catch { Write-Host 9999 }" > "%TEMP%\mirror_test.txt" 2>&1
set /p PYPI_TIME=<"%TEMP%\mirror_test.txt"
if !PYPI_TIME! lss !BEST_TIME! (
    set "BEST_TIME=!PYPI_TIME!"
    set "MIRROR_NAME=PyPI Official"
    set "PIP_MIRROR=-i https://pypi.org/simple"
)

REM Test Tsinghua mirror
echo Testing: Tsinghua University Mirror...
powershell -Command "$ProgressPreference='SilentlyContinue'; $sw=[System.Diagnostics.Stopwatch]::StartNew(); try { $null=Invoke-WebRequest -Uri 'https://pypi.tuna.tsinghua.edu.cn' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; $sw.Stop(); Write-Host $sw.ElapsedMilliseconds } catch { Write-Host 9999 }" > "%TEMP%\mirror_test.txt" 2>&1
set /p TSINGHUA_TIME=<"%TEMP%\mirror_test.txt"
if !TSINGHUA_TIME! lss !BEST_TIME! (
    set "BEST_TIME=!TSINGHUA_TIME!"
    set "MIRROR_NAME=Tsinghua University Mirror"
    set "PIP_MIRROR=-i https://pypi.tuna.tsinghua.edu.cn/simple"
)

REM Test Aliyun mirror
echo Testing: Aliyun Mirror...
powershell -Command "$ProgressPreference='SilentlyContinue'; $sw=[System.Diagnostics.Stopwatch]::StartNew(); try { $null=Invoke-WebRequest -Uri 'https://mirrors.aliyun.com' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; $sw.Stop(); Write-Host $sw.ElapsedMilliseconds } catch { Write-Host 9999 }" > "%TEMP%\mirror_test.txt" 2>&1
set /p ALIYUN_TIME=<"%TEMP%\mirror_test.txt"
if !ALIYUN_TIME! lss !BEST_TIME! (
    set "BEST_TIME=!ALIYUN_TIME!"
    set "MIRROR_NAME=Aliyun Mirror"
    set "PIP_MIRROR=-i https://mirrors.aliyun.com/pypi/simple/"
)

REM Clean temporary files
if exist "%TEMP%\mirror_test.txt" del "%TEMP%\mirror_test.txt"

REM Display results
if !BEST_TIME! lss 9999 (
    echo [Success] Selected fastest mirror: !MIRROR_NAME! ^(!BEST_TIME!ms^)
) else (
    echo [Info] All mirrors timed out, using default PyPI
    set "MIRROR_NAME=PyPI Official (Fallback)"
    set "PIP_MIRROR=-i https://pypi.org/simple"
)
echo.

REM Upgrade pip
echo [Info] Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip %PIP_MIRROR% >nul 2>&1
if !errorlevel! equ 0 (
    echo [Success] pip upgraded
) else (
    echo [Warning] pip upgrade failed, continuing...
)
echo.

REM Install Nuitka
echo [Info] Installing Nuitka...
"%PYTHON_EXE%" -m pip install nuitka %PIP_MIRROR%
set "INSTALL_RESULT=!errorlevel!"

if !INSTALL_RESULT! neq 0 (
    echo [Error] Nuitka installation failed with mirror: !MIRROR_NAME!
    echo [Retry] Trying with default PyPI...
    "%PYTHON_EXE%" -m pip install nuitka
    set "INSTALL_RESULT=!errorlevel!"
)

exit /b !INSTALL_RESULT!

REM Detect system architecture and get latest GCC version
:detect_system_arch_and_get_gcc

REM Detect system architecture
set "SYSTEM_ARCH=x86_64"
if "%PROCESSOR_ARCHITECTURE%"=="x86" (
    set "SYSTEM_ARCH=i686"
) else if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "SYSTEM_ARCH=x86_64"
) else (
    REM Use PowerShell to detect
    for /f "delims=" %%a in ('powershell -Command "[System.Environment]::Is64BitOperatingSystem"') do set "IS_64BIT=%%a"
    if "!IS_64BIT!"=="True" (
        set "SYSTEM_ARCH=x86_64"
    ) else (
        set "SYSTEM_ARCH=i686"
    )
)

REM Set GCC filename pattern based on architecture
if "!SYSTEM_ARCH!"=="i686" (
    set "GCC_PATTERN=winlibs-i686-posix-dwarf-gcc-"
) else (
    set "GCC_PATTERN=winlibs-x86_64-posix-seh-gcc-"
)

echo.
echo ============================================
echo [GCC Manager] Checking GCC Compiler Cache
echo ============================================
echo.

REM Create download directory
if not exist "%GCC_DOWNLOAD_DIR%" (
    mkdir "%GCC_DOWNLOAD_DIR%" 2>nul
)

REM First check if local GCC file matching architecture already exists
echo [Checking] Searching for existing GCC compiler...
set "LOCAL_GCC_FOUND=0"
set "LOCAL_GCC_ZIP="
set "LOCAL_GCC_EXTRACT_DIR="

REM Search for local GCC zip file matching architecture
for %%f in ("%GCC_DOWNLOAD_DIR%\winlibs-!SYSTEM_ARCH!-posix-*.zip") do (
    if exist "%%f" (
        set "LOCAL_GCC_ZIP=%%~nxf"
        set "LOCAL_GCC_ZIP_PATH=%%f"

        REM winlibs zip package extracts directly to mingw64 directory (64-bit) or mingw32 directory (32-bit)
        REM So we directly check if these directories exist
        if exist "%GCC_DOWNLOAD_DIR%\mingw64\bin\gcc.exe" (
            set "LOCAL_GCC_FOUND=1"
            set "LOCAL_GCC_EXTRACT_DIR=%GCC_DOWNLOAD_DIR%"
            echo [Found] Local GCC found: !LOCAL_GCC_ZIP!
            echo [Found] Extracted directory: %GCC_DOWNLOAD_DIR%\mingw64
            goto :local_gcc_ready
        ) else if exist "%GCC_DOWNLOAD_DIR%\mingw32\bin\gcc.exe" (
            set "LOCAL_GCC_FOUND=1"
            set "LOCAL_GCC_EXTRACT_DIR=%GCC_DOWNLOAD_DIR%"
            echo [Found] Local GCC found: !LOCAL_GCC_ZIP!
            echo [Found] Extracted directory: %GCC_DOWNLOAD_DIR%\mingw32
            goto :local_gcc_ready
        ) else (
            REM Zip file exists but not extracted, mark as found but needs extraction
            set "LOCAL_GCC_FOUND=2"
            echo [Found] Local GCC zip found but not extracted: !LOCAL_GCC_ZIP!
            goto :local_gcc_ready
        )
    )
)

:local_gcc_ready
if !LOCAL_GCC_FOUND! equ 1 (
    REM Local GCC already available, use directly
    echo [Found] Using existing local GCC compiler
    set "GCC_ZIP=!LOCAL_GCC_ZIP!"
    set "GCC_ZIP_PATH=!LOCAL_GCC_ZIP_PATH!"
    set "NUITKA_CACHE=!LOCAL_GCC_EXTRACT_DIR!"
    echo [Status] GCC compiler is ready
    echo ============================================
    echo.
    goto :eof
) else if !LOCAL_GCC_FOUND! equ 2 (
    REM Local zip file exists but not extracted, extract and use
    echo [Found] Local GCC archive found, extracting...
    call :extract_gcc "!LOCAL_GCC_ZIP_PATH!" "%GCC_DOWNLOAD_DIR%"
    if !errorlevel! equ 0 (
        set "GCC_ZIP=!LOCAL_GCC_ZIP!"
        set "GCC_ZIP_PATH=!LOCAL_GCC_ZIP_PATH!"
        set "LOCAL_GCC_EXTRACT_DIR=%GCC_DOWNLOAD_DIR%"
        set "NUITKA_CACHE=!LOCAL_GCC_EXTRACT_DIR!"
        echo [Status] GCC compiler is ready
        echo ============================================
        echo.
        goto :eof
    ) else (
        echo [Warning] Failed to extract local GCC, will download latest version...
    )
)

REM No local GCC available, get latest version from GitHub
echo [Not Found] No local GCC compiler found for architecture: !SYSTEM_ARCH!
echo [Fetching] Getting latest GCC version from GitHub...
set "PS_SCRIPT=%TEMP%\get_gcc_latest.ps1"

echo $ErrorActionPreference = 'Stop' > "%PS_SCRIPT%"
echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 >> "%PS_SCRIPT%"
echo $ProgressPreference = 'SilentlyContinue' >> "%PS_SCRIPT%"
echo try { >> "%PS_SCRIPT%"
echo     $apiUrl = "https://api.github.com/repos/brechtsanders/winlibs_mingw/releases/latest" >> "%PS_SCRIPT%"
echo     $headers = @{'User-Agent' = 'Python-Packaging-Tool'} >> "%PS_SCRIPT%"
echo     $response = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 30 >> "%PS_SCRIPT%"
echo     $assets = $response.assets >> "%PS_SCRIPT%"
echo     $gccPattern = "%GCC_PATTERN%" >> "%PS_SCRIPT%"
echo     $gccAsset = $assets ^| Where-Object { $_.name -like "$gccPattern*.zip" } ^| Select-Object -First 1 >> "%PS_SCRIPT%"
echo     if ($gccAsset) { >> "%PS_SCRIPT%"
echo         Write-Host $gccAsset.name >> "%PS_SCRIPT%"
echo         Write-Host $gccAsset.browser_download_url >> "%PS_SCRIPT%"
echo         Write-Host $response.tag_name >> "%PS_SCRIPT%"
echo         exit 0 >> "%PS_SCRIPT%"
echo     } else { >> "%PS_SCRIPT%"
echo         Write-Host "[ERROR] No matching GCC file found" >> "%PS_SCRIPT%"
echo         exit 1 >> "%PS_SCRIPT%"
echo     } >> "%PS_SCRIPT%"
echo } catch { >> "%PS_SCRIPT%"
echo     Write-Host "[ERROR] Failed to fetch latest version: $_" >> "%PS_SCRIPT%"
echo     exit 1 >> "%PS_SCRIPT%"
echo } >> "%PS_SCRIPT%"

powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" > "%TEMP%\gcc_info.txt" 2>&1
set "GCC_FETCH_RESULT=!errorlevel!"

if !GCC_FETCH_RESULT! neq 0 (
    echo [Warning] Failed to fetch latest version from GitHub, using fallback...
    REM Use default version as fallback
    set "GCC_ZIP=winlibs-x86_64-posix-seh-gcc-15.2.0-mingw-w64msvcrt-13.0.0-r5.zip"
    set "GCC_URL=https://github.com/brechtsanders/winlibs_mingw/releases/download/15.2.0posix-13.0.0-msvcrt-r5/%GCC_ZIP%"
    set "GCC_VERSION=15.2.0posix-13.0.0-msvcrt-r5"
) else (
    REM Read GitHub API response information
    set "LINE_NUM=0"
    for /f "delims=" %%a in ('type "%TEMP%\gcc_info.txt"') do (
        set /a "LINE_NUM+=1"
        if !LINE_NUM! equ 1 set "GCC_ZIP=%%a"
        if !LINE_NUM! equ 2 set "GCC_URL=%%a"
        if !LINE_NUM! equ 3 set "GCC_VERSION=%%a"
    )
)

REM Clean temporary files
del "%PS_SCRIPT%" >nul 2>&1
del "%TEMP%\gcc_info.txt" >nul 2>&1

echo [Latest] GCC Version: !GCC_VERSION!
echo [File] !GCC_ZIP!

REM Check if local file already exists
set "GCC_ZIP_PATH=%GCC_DOWNLOAD_DIR%\!GCC_ZIP!"
if exist "!GCC_ZIP_PATH!" (
    echo [Found] GCC archive already downloaded

    REM Check if already extracted
    set "GCC_EXTRACT_DIR=%GCC_DOWNLOAD_DIR%\!GCC_ZIP:.zip=%"
    if exist "!GCC_EXTRACT_DIR!" (
        echo [Found] GCC already extracted and ready
        set "NUITKA_CACHE=!GCC_EXTRACT_DIR!"
        echo [Status] GCC compiler is ready
        echo ============================================
    ) else (
        call :extract_gcc "!GCC_ZIP_PATH!" "%GCC_DOWNLOAD_DIR%"
        if !errorlevel! equ 0 (
            set "NUITKA_CACHE=!GCC_EXTRACT_DIR!"
            echo [Status] GCC compiler is ready
            echo ============================================
        )
    )
) else (
    echo [Info] Downloading GCC from GitHub (~380MB)...
    echo [Info] This may take 5-15 minutes depending on your network speed
    call :download_gcc "!GCC_URL!" "!GCC_ZIP_PATH!"
    if !errorlevel! equ 0 (
        set "GCC_EXTRACT_DIR=%GCC_DOWNLOAD_DIR%\!GCC_ZIP:.zip=%"
        call :extract_gcc "!GCC_ZIP_PATH!" "%GCC_DOWNLOAD_DIR%"
        if !errorlevel! equ 0 (
            set "NUITKA_CACHE=!GCC_EXTRACT_DIR!"
            echo [Status] GCC compiler is ready
            echo ============================================
        )
    )
)

echo.
REM Set GCC path for Nuitka (if not already set)
if not defined NUITKA_CACHE (
    set "NUITKA_CACHE=%GCC_DOWNLOAD_DIR%\!GCC_ZIP:.zip=%"
)

echo [Success] GCC compiler ready at: !NUITKA_CACHE!
echo.
goto :eof

REM Download GCC
:download_gcc
set "DOWNLOAD_URL=%~1"
set "OUTPUT_PATH=%~2"

echo.
echo [Downloading] Starting GCC download...

set "PS_DOWNLOAD=%TEMP%\download_gcc.ps1"
echo $ErrorActionPreference = 'Stop' > "%PS_DOWNLOAD%"
echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 >> "%PS_DOWNLOAD%"
echo $ProgressPreference = 'SilentlyContinue' >> "%PS_DOWNLOAD%"
echo try { >> "%PS_DOWNLOAD%"
echo     $url = "%DOWNLOAD_URL%" >> "%PS_DOWNLOAD%"
echo     $output = "%OUTPUT_PATH%" >> "%PS_DOWNLOAD%"
echo     Invoke-WebRequest -Uri $url -OutFile $output -TimeoutSec 600 >> "%PS_DOWNLOAD%"
echo     exit 0 >> "%PS_DOWNLOAD%"
echo } catch { >> "%PS_DOWNLOAD%"
echo     Write-Host "[Error]" $_.Exception.Message >> "%PS_DOWNLOAD%"
echo     exit 1 >> "%PS_DOWNLOAD%"
echo } >> "%PS_DOWNLOAD%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_DOWNLOAD%" 2>nul
set "DOWNLOAD_RESULT=!errorlevel!"
del "%PS_DOWNLOAD%" >nul 2>&1

if !DOWNLOAD_RESULT! equ 0 (
    echo [Success] GCC download completed
) else (
    echo [Error] GCC download failed
)
echo.
exit /b !DOWNLOAD_RESULT!

REM Extract GCC
:extract_gcc
set "ZIP_PATH=%~1"
set "EXTRACT_DIR=%~2"

echo [Extracting] Extracting GCC compiler (this may take 1-2 minutes)...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; try { Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%EXTRACT_DIR%' -Force; exit 0 } catch { Write-Host '[Error]' $_.Exception.Message; exit 1 }" 2>nul
set "EXTRACT_RESULT=!errorlevel!"

if !EXTRACT_RESULT! equ 0 (
    echo [Success] Extraction completed
) else (
    echo [Error] Extraction failed
)
exit /b !EXTRACT_RESULT!

REM Smart GCC cache management
:manage_gcc_cache
REM Silent check, no extra output
goto :eof

REM Smart compilation function
:compile_with_nuitka
set "ATTEMPT=%~1"
call :log_echo [COMPILE] Compilation attempt #%ATTEMPT%...
echo. >> "%ERROR_LOG%"
echo -------------------------------------------- >> "%ERROR_LOG%"
echo Compilation Attempt #%ATTEMPT% >> "%ERROR_LOG%"
echo Time: %time% >> "%ERROR_LOG%"
echo -------------------------------------------- >> "%ERROR_LOG%"

REM Build base Nuitka command
REM Note Python path already quoted if contains spaces
REM Use variable directly, batch will handle spaces automatically
set "NUITKA_CMD=!PYTHON_EXE! -m nuitka"
REM 使用 --mode=onefile (Nuitka 2.8.9+ 推荐语法，同时包含 standalone 功能)
set "NUITKA_CMD=!NUITKA_CMD! --mode=onefile"
set "NUITKA_CMD=!NUITKA_CMD! --output-dir=!TEMP_DIR!"
REM Add console mode parameter directly based on configuration
if /i "!SHOW_CONSOLE!"=="true" (
    set "NUITKA_CMD=!NUITKA_CMD! --windows-console-mode=force"
) else (
    set "NUITKA_CMD=!NUITKA_CMD! --windows-console-mode=disable"
)

REM Note: Icon parameter will be added after version info processing
REM If resource file is used, icon is already included in it

REM Process version format auto-convert to x.x.x.x format
REM Use delayed expansion to ensure PROJECT_VERSION is set from detect_version_info
set "WIN_VERSION=!PROJECT_VERSION!"
echo [DEBUG-VERSION] PROJECT_VERSION value: [!PROJECT_VERSION!]
echo [DEBUG-VERSION] WIN_VERSION initial value: [!WIN_VERSION!]
if "!WIN_VERSION!"=="" (
    set "WIN_VERSION=1.0.0"
    echo [DEBUG-VERSION] Set WIN_VERSION to default: !WIN_VERSION!
)
echo [VERSION] Original version: !PROJECT_VERSION!
echo [VERSION] Processing version format conversion...

REM Check and convert version format without nested if blocks
REM Use temporary variable to avoid variable loss in if blocks
set "VERSION_CONVERTED=0"

REM Count dots in version string to determine format
set "DOT_COUNT=0"
set "TEMP_VER=!WIN_VERSION!"
:count_dots
if "!TEMP_VER!"=="" goto :done_counting
if "!TEMP_VER:~0,1!"=="." set /a DOT_COUNT+=1
set "TEMP_VER=!TEMP_VER:~1!"
goto :count_dots
:done_counting

echo [VERSION] Detected !DOT_COUNT! dots in version string

REM Convert based on dot count (use nested if for compatibility)
if "!DOT_COUNT!"=="3" (
    echo [VERSION] Version already in 4-part format: !WIN_VERSION!
    set "VERSION_CONVERTED=1"
)
if "!DOT_COUNT!"=="2" (
    set "WIN_VERSION=!WIN_VERSION!.0"
    echo [VERSION] Converted 3-part to 4-part format: !WIN_VERSION!
    set "VERSION_CONVERTED=1"
)
if "!DOT_COUNT!"=="1" (
    set "WIN_VERSION=!WIN_VERSION!.0.0"
    echo [VERSION] Converted 2-part to 4-part format: !WIN_VERSION!
    set "VERSION_CONVERTED=1"
)
if "!DOT_COUNT!"=="0" (
    set "WIN_VERSION=!WIN_VERSION!.0.0.0"
    echo [VERSION] Converted 1-part to 4-part format: !WIN_VERSION!
    set "VERSION_CONVERTED=1"
)
if "!VERSION_CONVERTED!"=="0" (
    echo [WARNING] Invalid version format, default will be used: 1.0.0.0
    set "WIN_VERSION=1.0.0.0"
)

REM Validate each version component (Windows file version requires each part to be 0-65535)
echo [VERSION] Validating version components...
set "VER_VALID_P1=0"
set "VER_VALID_P2=0"
set "VER_VALID_P3=0"
set "VER_VALID_P4=0"
for /f "tokens=1-4 delims=." %%a in ("!WIN_VERSION!") do (
    set "VER_VALID_P1=%%a"
    set "VER_VALID_P2=%%b"
    set "VER_VALID_P3=%%c"
    set "VER_VALID_P4=%%d"
)
set "VERSION_FIXED=false"
if !VER_VALID_P1! GTR 65535 (
    echo [WARNING] Version part 1 ^(!VER_VALID_P1!^) exceeds 65535, resetting to 0
    set "VER_VALID_P1=0"
    set "VERSION_FIXED=true"
)
if !VER_VALID_P2! GTR 65535 (
    echo [WARNING] Version part 2 ^(!VER_VALID_P2!^) exceeds 65535, resetting to 0
    set "VER_VALID_P2=0"
    set "VERSION_FIXED=true"
)
if !VER_VALID_P3! GTR 65535 (
    echo [WARNING] Version part 3 ^(!VER_VALID_P3!^) exceeds 65535, resetting to 0
    set "VER_VALID_P3=0"
    set "VERSION_FIXED=true"
)
if !VER_VALID_P4! GTR 65535 (
    echo [WARNING] Version part 4 ^(!VER_VALID_P4!^) exceeds 65535, resetting to 0
    set "VER_VALID_P4=0"
    set "VERSION_FIXED=true"
)
if "!VERSION_FIXED!"=="true" (
    set "WIN_VERSION=!VER_VALID_P1!.!VER_VALID_P2!.!VER_VALID_P3!.!VER_VALID_P4!"
    echo [WARNING] Version adjusted to valid Windows format: !WIN_VERSION!
    echo [WARNING] Note: Windows file version requires each component to be 0-65535
    echo [WARNING] Consider changing __version__ in version.py to a format like "1.5.2" instead of including a date suffix
)

REM Add version info - use Windows resource file for Chinese characters support
echo [DEBUG-VERSION] Final WIN_VERSION after conversion: [!WIN_VERSION!]
echo [VERSION] File version: !WIN_VERSION!
echo [VERSION] Product version: !WIN_VERSION!

REM Select product name and description based on Windows compatibility mode
if /i "%WIN10_COMPAT_MODE%"=="true" (
    echo [Windows 10/11] Windows 10/11 compatibility compilation mode
    echo Windows 10/11 Compatibility Mode >> "%ERROR_LOG%"
    set "PRODUCT_NAME_VALUE=!PROJECT_NAME!"
    set "FILE_DESC_VALUE=!PROJECT_DESCRIPTION!"
) else (
    echo [Standard] Standard compilation mode
    echo Standard Compilation Mode >> "%ERROR_LOG%"
    set "PRODUCT_NAME_VALUE=!PROJECT_NAME!"
    set "FILE_DESC_VALUE=!PROJECT_DESCRIPTION!"
)
echo [DEBUG] PROJECT_DESCRIPTION value: !PROJECT_DESCRIPTION!
echo [DEBUG] FILE_DESC_VALUE after setting: !FILE_DESC_VALUE!
echo [DEBUG] DETECTED_DESCRIPTION value: !DETECTED_DESCRIPTION!
echo [DEBUG] DETECTED_DESCRIPTION_EN value: !DETECTED_DESCRIPTION_EN!

REM Check if version info contains Chinese characters (requires resource file)
set "USE_RC_FILE=false"
set "HAS_CHINESE=false"
if "!SUPPORTS_CHINESE!"=="true" (
    REM Check if any field contains non-ASCII characters
    echo !PRODUCT_NAME_VALUE!!FILE_DESC_VALUE!!PROJECT_COPYRIGHT! | findstr /R "[^\x00-\x7F]" >nul 2>&1
    if !errorlevel! equ 0 (
        set "USE_RC_FILE=true"
        set "HAS_CHINESE=true"
    )
    REM Also check for Chinese characters directly
    echo !PRODUCT_NAME_VALUE! | findstr /R "[\u4e00-\u9fff]" >nul 2>&1
    if !errorlevel! equ 0 (
        set "USE_RC_FILE=true"
        set "HAS_CHINESE=true"
    )
    REM Simple heuristic: if product name or description contains non-letter-digit-space, assume Chinese
    for /f "delims=" %%x in ("!PRODUCT_NAME_VALUE!") do (
        echo %%x | findstr /R "^[a-zA-Z0-9 _.-]*$" >nul 2>&1
        if !errorlevel! neq 0 (
            set "USE_RC_FILE=true"
            set "HAS_CHINESE=true"
        )
    )
)

REM Add version info - use Windows resource file for Chinese characters support
echo [DEBUG-VERSION] Final WIN_VERSION after conversion: [!WIN_VERSION!]
echo [VERSION] File version: !WIN_VERSION!
echo [VERSION] Product version: !WIN_VERSION!

REM Add version info - use command line parameters (Nuitka 2.8.9 supports Chinese via command line)
REM Note: Nuitka 2.8.9 does not support --windows-force-rc-file, so we will use command line parameters
set "RC_FILE_PATH="
REM Always use version info directly (prefer Chinese if available, fallback to English)
REM Product name: prefer Chinese (PRODUCT_NAME_VALUE), fallback to English
if not "!PRODUCT_NAME_VALUE!"=="" (
    set "NUITKA_CMD=!NUITKA_CMD! --windows-product-name=^"!PRODUCT_NAME_VALUE!^""
    call :log_echo [INFO] Using product name: !PRODUCT_NAME_VALUE!
) else if defined DETECTED_APP_NAME_EN (
    set "NUITKA_CMD=!NUITKA_CMD! --windows-product-name=^"!DETECTED_APP_NAME_EN!^""
    call :log_echo [INFO] Using English product name: !DETECTED_APP_NAME_EN!
)
REM File description: always prefer Chinese (DETECTED_DESCRIPTION) if available, then FILE_DESC_VALUE, finally English
REM Since product name and copyright can display Chinese, we should use Chinese description too
if not "!DETECTED_DESCRIPTION!"=="" (
    REM Use Chinese description directly (highest priority)
    set "FILE_DESC_RAW=!DETECTED_DESCRIPTION!"
    set "NUITKA_CMD=!NUITKA_CMD! --windows-file-description=^"!FILE_DESC_RAW!^""
    call :log_echo [INFO] Using Chinese description: "!FILE_DESC_RAW!"
    echo [DEBUG] Using DETECTED_DESCRIPTION: "!FILE_DESC_RAW!"
) else if not "!FILE_DESC_VALUE!"=="" (
    REM Fallback to FILE_DESC_VALUE if DETECTED_DESCRIPTION is not available
    set "FILE_DESC_RAW=!FILE_DESC_VALUE!"
    set "NUITKA_CMD=!NUITKA_CMD! --windows-file-description=^"!FILE_DESC_RAW!^""
    call :log_echo [INFO] Using file description: "!FILE_DESC_RAW!"
    echo [DEBUG] FILE_DESC_VALUE: "!FILE_DESC_RAW!"
) else if not "!DETECTED_DESCRIPTION_EN!"=="" (
    REM Last resort: use English description
    set "FILE_DESC_RAW=!DETECTED_DESCRIPTION_EN!"
    set "NUITKA_CMD=!NUITKA_CMD! --windows-file-description=^"!FILE_DESC_RAW!^""
    call :log_echo [INFO] Using English description: "!FILE_DESC_RAW!"
    echo [DEBUG] Using DETECTED_DESCRIPTION_EN: "!FILE_DESC_RAW!"
)
set "NUITKA_CMD=!NUITKA_CMD! --windows-company-name=^"!COMPANY_NAME!^""
set "NUITKA_CMD=!NUITKA_CMD! --windows-file-version=!WIN_VERSION!"
set "NUITKA_CMD=!NUITKA_CMD! --windows-product-version=!WIN_VERSION!"
set "COPYRIGHT_LOG="
if defined PROJECT_COPYRIGHT (
    set "NUITKA_CMD=!NUITKA_CMD! --copyright=^"!PROJECT_COPYRIGHT!^""
    set "COPYRIGHT_LOG=!PROJECT_COPYRIGHT!"
)
if defined COPYRIGHT_LOG (
    set "COPYRIGHT_LOG=!COPYRIGHT_LOG:(=^(!"
    set "COPYRIGHT_LOG=!COPYRIGHT_LOG:)=^)!"
    call :log_echo [INFO] Copyright: !COPYRIGHT_LOG!
)

REM Add icon parameter
REM Note: Nuitka 2.8.9 does not support resource files, so always add icon parameter separately
if not "!ICON_PARAM!"=="" (
    set "NUITKA_CMD=!NUITKA_CMD! !ICON_PARAM!"
    call :log_echo [INFO] Using icon: !ICON_FILE!
) else (
    call :log_echo [WARNING] No icon parameter specified, exe will use default icon
)

REM Add package parameters
REM Enable PyQt6 plugin support fix missing Qt platform plugin issue
set "NUITKA_CMD=!NUITKA_CMD! --enable-plugin=pyqt6"
call :log_echo [INFO] PyQt6 plugin enabled for Qt platform support
if not "!INCLUDE_PARAM!"=="" (
    set "NUITKA_CMD=!NUITKA_CMD! !INCLUDE_PARAM!"
)

REM Add exclude import parameters auto-exclude unnecessary dependencies to reduce build time
if not "!EXCLUDE_PARAM!"=="" (
    set "NUITKA_CMD=!NUITKA_CMD! !EXCLUDE_PARAM!"
    call :log_echo [Optimize] Dependency exclusion enabled to reduce build time
)

REM LTO optimization
if /i "!ENABLE_LTO!"=="true" (
    set "NUITKA_CMD=!NUITKA_CMD! --lto=yes"
    call :log_echo [INFO] LTO link-time optimization enabled
    call :log_echo [INFO]   - Reduces executable size
    call :log_echo [INFO]   - Improves runtime performance
    call :log_echo [INFO]   - Slightly increases compile time
)

REM Python optimization
if /i "!ENABLE_PYTHON_OPT!"=="true" (
    set "NUITKA_CMD=!NUITKA_CMD! --python-flag=no_docstrings"
    set "NUITKA_CMD=!NUITKA_CMD! --python-flag=no_asserts"
    call :log_echo [INFO] Python bytecode optimization enabled
    call :log_echo [INFO]   - Removes docstrings
    call :log_echo [INFO]   - Disables assert statements
)

REM Disable unnecessary plugins and features to speed up build
set "NUITKA_CMD=!NUITKA_CMD! --no-prefer-source-code"

REM PyQt6 specific configuration include Qt platform plugins and resources
call :log_echo [INFO] Configuring PyQt6 platform plugins and dependencies
set "NUITKA_CMD=!NUITKA_CMD! --include-qt-plugins=sensible,platforms,styles,iconengines,imageformats"
REM Include all necessary PyQt6 data files and DLLs
set "NUITKA_CMD=!NUITKA_CMD! --include-package-data=PyQt6"

REM Add progress and report parameters
set "NUITKA_CMD=!NUITKA_CMD! --show-progress"
set "NUITKA_CMD=!NUITKA_CMD! --show-memory"
set "NUITKA_CMD=!NUITKA_CMD! --assume-yes-for-downloads"

REM Add resources directory to package (for runtime use - icons, etc.)
set "RESOURCES_DIR=!PROJECT_ROOT!resources"
if exist "!RESOURCES_DIR!" (
    REM Include entire resources directory for runtime access
    set "NUITKA_CMD=!NUITKA_CMD! --include-data-dir=!RESOURCES_DIR!=resources"
    call :log_echo [INFO] Including resources directory in package
) else (
    REM Fallback: try to include just icon file if resources dir doesn't exist
if not "!ICON_PARAM!"=="" (
        if defined ICON_FULL_PATH (
            if exist "!ICON_FULL_PATH!" (
                set "NUITKA_CMD=!NUITKA_CMD! --include-data-file=!ICON_FULL_PATH!=icon.ico"
                call :log_echo [INFO] Including icon file in package: !ICON_FILE!
            )
        )
    )
)

REM Include icon_convert_helper.py as data file for subprocess icon conversion
REM When running as packaged exe, Pillow is not available in the bundled Python,
REM so icon conversion is done via subprocess using the target project's venv Python.
REM This helper script needs to be accessible as a regular .py file at runtime.
set "HELPER_SCRIPT=!PROJECT_ROOT!core\packaging\icon_convert_helper.py"
if exist "!HELPER_SCRIPT!" (
    set "NUITKA_CMD=!NUITKA_CMD! --include-data-file=!HELPER_SCRIPT!=core/packaging/icon_convert_helper.py"
    call :log_echo [INFO] Including icon_convert_helper.py for subprocess icon conversion
)

REM Add extra parameters check if contains deprecated console parameters
if not "%EXTRA_NUITKA_ARGS%"=="" (
    REM Check and warn if using old console parameters
    echo %EXTRA_NUITKA_ARGS% | findstr /i "--disable-console --enable-console" >nul
    if !errorlevel! equ 0 (
        call :log_echo [WARNING] EXTRA_NUITKA_ARGS contains deprecated console options
        call :log_echo [WARNING] Please use --windows-console-mode instead
    )
    set "NUITKA_CMD=!NUITKA_CMD! !EXTRA_NUITKA_ARGS!"
)
REM Add main file as positional argument
set "NUITKA_CMD=!NUITKA_CMD! !MAIN_FILE!"

REM Execute compilation using delayed expansion to ensure variables are correctly expanded
REM Note: Use delayed expansion !NUITKA_CMD! instead of immediate expansion %NUITKA_CMD%
REM Write command to temporary batch file for reliable execution with complex arguments
set "TEMP_CMD_FILE=%TEMP%\nuitka_cmd_%RANDOM%.bat"
set "TEMP_OUTPUT=%TEMP%\nuitka_output_%RANDOM%.txt"

REM Log the full command for debugging (icon parameter should be visible)
call :log_echo [DEBUG] Full Nuitka command: !NUITKA_CMD!

REM Write the command to temporary batch file
REM Simple approach: write the command directly
> "!TEMP_CMD_FILE!" echo @echo off
>> "!TEMP_CMD_FILE!" echo !NUITKA_CMD!
REM Execute the temporary batch file and capture output
call "!TEMP_CMD_FILE!" > "!TEMP_OUTPUT!" 2>&1
set "COMPILE_RESULT=!errorlevel!"
REM Clean up temporary command file
if exist "!TEMP_CMD_FILE!" del "!TEMP_CMD_FILE!" >nul 2>&1

REM Filter output: only show actual errors, suppress help messages
if exist "!TEMP_OUTPUT!" (
    REM Check if output contains help message (indicates parameter error)
    findstr /C:"Usage:" "!TEMP_OUTPUT!" >nul 2>&1
    if !errorlevel! equ 0 (
        REM Help message detected, only output error lines (lines containing "FATAL", "ERROR", "Error")
        findstr /C:"FATAL" /C:"ERROR" /C:"Error" /C:"error" "!TEMP_OUTPUT!" >> "%ERROR_LOG%" 2>&1
    ) else (
        REM No help message, output all content
        type "!TEMP_OUTPUT!" >> "%ERROR_LOG%" 2>&1
    )
    del "!TEMP_OUTPUT!" >nul 2>&1
)

REM Record compilation result
if !COMPILE_RESULT! neq 0 (
    echo Compilation attempt #%ATTEMPT% FAILED with error code: !COMPILE_RESULT! >> "%ERROR_LOG%"
    echo. >> "%ERROR_LOG%"
) else (
    echo Compilation attempt #%ATTEMPT% SUCCESS >> "%ERROR_LOG%"
    echo. >> "%ERROR_LOG%"
)

REM If failed and attempts less than 3, continue retry
if !COMPILE_RESULT! neq 0 (
    if %ATTEMPT% LSS 3 (
        call :log_echo [RETRY] Compilation attempt #%ATTEMPT% failed with error code !COMPILE_RESULT!, preparing retry...
        set /a "NEXT_ATTEMPT=%ATTEMPT%+1"
        call :compile_with_nuitka !NEXT_ATTEMPT!
        set "COMPILE_RESULT=!errorlevel!"
    )
)

exit /b !COMPILE_RESULT!

REM Failure diagnosis and guidance
:failure_diagnosis_and_guidance
echo [Diagnostics] Starting intelligent failure analysis...

REM Check network status
call :check_network_advanced 2>nul

REM Check disk space
echo [System] Checking disk space...
set "FREE_BYTES="
for /f "tokens=3" %%a in ('dir /-c "%SystemDrive%\" 2^>nul ^| find "bytes free"') do set "FREE_BYTES=%%a"
    if defined FREE_BYTES (
    REM Remove commas from number (e.g., 1,234,567,890 -> 1234567890)
    set "FREE_BYTES=!FREE_BYTES:,=!"
    REM Use PowerShell for large number division to avoid 32-bit limit
    for /f %%b in ('powershell -Command "!FREE_BYTES! / 1073741824"') do set "FREE_GB=%%b"
        if !FREE_GB! LSS 5 (
        echo [Warning] Insufficient disk space: !FREE_GB!GB ^(recommend at least 5GB^)
        ) else (
            echo [Normal] Sufficient disk space: !FREE_GB!GB
        )
    ) else (
        echo [Warning] Unable to determine disk space
)

REM Check temporary directory permissions
echo [Permission] Checking temporary directory permissions...
echo test > "%TEMP%\nuitka_test.tmp" 2>nul
if !errorlevel! neq 0 (
    echo [Warning] Insufficient write permission for temporary directory
    echo [Suggestion] Run script as administrator
) else (
    del /q "%TEMP%\nuitka_test.tmp" 2>nul
    echo [Normal] Temporary directory permissions normal
)

echo.
echo ============================================
echo [Smart Solutions] Please try the following methods by priority:
echo ============================================
echo.
echo [Quick Solutions]
echo 1. Re-run this script as administrator
echo 2. Temporarily disable antivirus and firewall (except Windows Defender)
echo 3. Ensure stable network connection, avoid using VPN
echo 4. Clean disk space, ensure at least 5GB available
echo.
echo [Alternative Solutions]
echo 1. Try PyInstaller instead: pip install pyinstaller
echo 2. Use virtual environment: python -m venv venv
echo 3. Update Nuitka: pip install --upgrade nuitka
echo 4. Check Python version compatibility
echo.
echo [Build Log]
echo Detailed build log saved to: %ERROR_LOG%
echo Please check the log file for detailed messages
echo.
goto :eof

REM Calculate and display elapsed time
:show_elapsed_time
set "END_TIME=%time%"
set "END_DATE=%date%"

REM Parse start time
for /f "tokens=1-4 delims=:., " %%a in ("%START_TIME%") do (
    set /a "START_H=%%a"
    set /a "START_M=%%b"
    set /a "START_S=%%c"
    set /a "START_MS=%%d"
)

REM Parse end time
for /f "tokens=1-4 delims=:., " %%a in ("%END_TIME%") do (
    set /a "END_H=%%a"
    set /a "END_M=%%b"
    set /a "END_S=%%c"
    set /a "END_MS=%%d"
)

REM Convert to total milliseconds
set /a "START_TOTAL_MS=(START_H*3600000)+(START_M*60000)+(START_S*1000)+START_MS"
set /a "END_TOTAL_MS=(END_H*3600000)+(END_M*60000)+(END_S*1000)+END_MS"

REM Handle cross-day case
if !END_TOTAL_MS! LSS !START_TOTAL_MS! (
    set /a "END_TOTAL_MS+=86400000"
)

REM Calculate elapsed time
set /a "ELAPSED_MS=END_TOTAL_MS-START_TOTAL_MS"
set /a "ELAPSED_S=ELAPSED_MS/1000"
set /a "ELAPSED_M=ELAPSED_S/60"
set /a "ELAPSED_H=ELAPSED_M/60"
set /a "ELAPSED_S_REMAINDER=ELAPSED_S%%60"
set /a "ELAPSED_M_REMAINDER=ELAPSED_M%%60"

echo ============================================
echo           Build Time Summary
echo ============================================
echo Start Time:   %START_DATE% %START_TIME%
echo End Time:     %END_DATE% %END_TIME%
echo.
if !ELAPSED_H! GTR 0 (
    echo Total Elapsed: !ELAPSED_H! hour^(s^) !ELAPSED_M_REMAINDER! minute^(s^) !ELAPSED_S_REMAINDER! second^(s^)
) else if !ELAPSED_M! GTR 0 (
    echo Total Elapsed: !ELAPSED_M! minute^(s^) !ELAPSED_S_REMAINDER! second^(s^)
) else (
    echo Total Elapsed: !ELAPSED_S! second^(s^)
)
echo ============================================
goto :eof
