@echo off
:: Force UTF-8 encoding and clear screen
chcp 65001 >nul 2>&1
cls
setlocal enabledelayedexpansion

:: ============================================
:: Check admin privileges and auto-elevate
:: ============================================
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

if '%errorlevel%' NEQ '0' (

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


:: ============================================
:: Universal Python Project Build Script v2.0
:: Nuitka Compilation with Time Tracking & Error Logging
:: ============================================

:: ============================================
:: Configuration section - Modify according to your project
:: ============================================

:: Project basic information
set "PROJECT_NAME=Python Packaging Tool"
set "PROJECT_DISPLAY_NAME=Python Packaging Tool"
set "COMPANY_NAME=WKLAN.CN"
set "PROJECT_DESCRIPTION=Python Packaging Tool"
set "PROJECT_VERSION=1.0"

:: Note: Version supports simplified format, will auto-convert to Windows standard format

:: Main entry file relative to project root
set "MAIN_FILE=main.py"

:: Output executable name without .exe suffix
set "OUTPUT_EXE_NAME=python_packaging_tool"

:: Icon file relative to project root, leave empty for no icon
set "ICON_FILE=resources\icons\icon.ico"

:: Show console window: true=show, false=hide
set "SHOW_CONSOLE=false"

:: Include Python packages (space-separated, leave empty to auto-detect)
:: Project packages: gui, core, utils
:: Third-party packages: requests (PyQt6 auto-detected by Nuitka)
set "INCLUDE_PACKAGES=requests gui core utils"

:: Exclude imports (space-separated)
:: Auto-exclude test/dev tools and unnecessary dependencies
:: Note: PyQt6 is NOT excluded as it's used by this project
set "EXCLUDE_IMPORTS=pytest test unittest doctest coverage nose mock tox setuptools wheel pip distutils pkg_resources sphinx docutils IPython jupyter notebook ipython ipykernel matplotlib seaborn pandas numpy scipy sklearn tensorflow torch cv2 opencv PIL pillow tkinter wxpy wxpython PyQt5 PySide2 PySide6 PyQt4 PySide polib"

:: Extra Nuitka arguments, leave empty for defaults
set "EXTRA_NUITKA_ARGS="

:: Windows 10/11 compatibility mode: true=enabled, false=standard
set "WIN10_COMPAT_MODE=true"

:: Enable LTO (Link Time Optimization): true=enabled, false=disabled
:: Reduces executable size and improves performance (slightly increases compile time)
set "ENABLE_LTO=true"

:: Enable Python optimization: true=enabled, false=disabled
:: Removes docstrings, disables asserts, enables Python -O flag
set "ENABLE_PYTHON_OPT=true"

:: ============================================
:: Script body below, usually no need to modify
:: ============================================

:: Error handling
if errorlevel 1 (
    echo Warning: Failed to set UTF-8 encoding, may cause display issues
)

echo.
echo ============================================
echo   %PROJECT_DISPLAY_NAME% - Build Script v2.0
echo   Universal Nuitka Compilation System
echo ============================================
echo.

:: Set project root and build directories
set "PROJECT_ROOT=%~dp0"
set "BUILD_DIR=%PROJECT_ROOT%build"
set "TEMP_DIR=%BUILD_DIR%\temp"
set "VENV_DIR=%PROJECT_ROOT%.venv"
:: exe files directly in build directory, no dist subdirectory
set "DIST_DIR=%BUILD_DIR%"

:: Record start time
set "START_TIME=%time%"
set "START_DATE=%date%"

:: Set error log file (now records all output)
set "ERROR_LOG=%BUILD_DIR%\build_error.log"
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%" 2>nul
echo ============================================ > "%ERROR_LOG%"
echo Build Error Log - %PROJECT_DISPLAY_NAME% >> "%ERROR_LOG%"
echo Started at: %START_DATE% %START_TIME% >> "%ERROR_LOG%"
echo ============================================ >> "%ERROR_LOG%"
echo. >> "%ERROR_LOG%"

:: Define log function immediately after ERROR_LOG is set
:: Jump over the function definition to continue with main script
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

:: Display configuration info
call :log_echo [CONFIG] Project Configuration:
call :log_echo   Project Name: !PROJECT_NAME!
call :log_echo   Main File: !MAIN_FILE!
call :log_echo   Output Name: !OUTPUT_EXE_NAME!.exe
call :log_echo   Console Mode: !SHOW_CONSOLE!
call :log_echo   Win10 Compat: !WIN10_COMPAT_MODE!
call :log_echo   LTO Optimization: !ENABLE_LTO!
call :log_echo   Python Optimization: !ENABLE_PYTHON_OPT!
call :log_echo ""

:: Set GCC cache path, auto-detect system arch and get latest version
set "GCC_DOWNLOAD_DIR=%LOCALAPPDATA%\Nuitka\Nuitka\Cache\downloads"
:: Detect system arch and get latest GCC version
call :detect_system_arch_and_get_gcc

:: Network connection pre-check
call :log_echo [Pre-check] Running network diagnostics...
call :check_network_advanced 2>nul
if errorlevel 1 call :log_echo [Info] Network check completed with warnings

:: Smart GCC cache management
call :log_echo [GCC Manager] Smart checking GCC compiler cache...
call :manage_gcc_cache

:: Select Python interpreter: prefer project virtualenv, otherwise use system Python
if exist "%VENV_DIR%\Scripts\python.exe" (
    call :log_echo [Info] Using project virtualenv Python: "%VENV_DIR%\Scripts\python.exe"
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
    if exist "%VENV_DIR%\Scripts\pip.exe" (
        set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
    ) else (
        set "PIP_EXE=%VENV_DIR%\Scripts\python.exe -m pip"
    )
) else (
    call :log_echo [Info] Virtual environment not found, using system Python
    set "PYTHON_EXE=python"
    set "PIP_EXE=pip"
)

:: Validate Python environment
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

:: Check if main entry file exists
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

:: Create build directories
call :log_echo [PREPARE] Creating build directories...
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%" >> "%ERROR_LOG%" 2>&1
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%" >> "%ERROR_LOG%" 2>&1

:: Clean previous build files
call :log_echo [CLEANUP] Cleaning previous build files...
if exist "%BUILD_DIR%\*.exe" del /q "%BUILD_DIR%\*.exe" >> "%ERROR_LOG%" 2>&1
if exist "%TEMP_DIR%\*" rmdir /s /q "%TEMP_DIR%" 2>> "%ERROR_LOG%" && mkdir "%TEMP_DIR%" >> "%ERROR_LOG%" 2>&1

:: Check and install Nuitka
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

:: Windows version detection
call :log_echo [CHECK] Windows version detection...
for /f "tokens=4-5 delims=. " %%i in ('ver') do set WIN_VERSION=%%i.%%j
call :log_echo [INFO] Windows version: !WIN_VERSION!

:: Check and install project dependencies
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

:: Start compilation
call :log_echo ""
call :log_echo [Compile] Starting Nuitka compilation...
call :log_echo [Network] First-time use will auto-download GCC compiler (~378MB)
call :log_echo [Tip] Please ensure stable network connection, download may take 5-15 minutes
call :log_echo [LOG] Compilation output will be logged to: %ERROR_LOG%
call :log_echo ============================================

cd /d "%PROJECT_ROOT%"

:: Check icon file
set "ICON_PARAM="
if not "!ICON_FILE!"=="" (
    :: Convert to absolute path for icon file
    set "ICON_FULL_PATH=!PROJECT_ROOT!!ICON_FILE!"
    if exist "!ICON_FULL_PATH!" (
        :: Use the path directly - batch will handle spaces when variable is expanded
        :: Nuitka accepts paths with spaces in the parameter value
        set "ICON_PARAM=--windows-icon-from-ico=!ICON_FULL_PATH!"
        call :log_echo [INFO] Using icon: !ICON_FILE!
        call :log_echo [INFO] Icon full path: !ICON_FULL_PATH!
    ) else (
        call :log_echo [WARNING] Icon file not found: !ICON_FILE!, using default icon
        call :log_echo [WARNING] Expected path: !ICON_FULL_PATH!
    )
) else (
    call :log_echo [INFO] No icon specified, using default icon
)


:: Set console mode using new Nuitka parameter format
:: Note: Old parameters --enable-console and --disable-console are deprecated
:: New parameter options: force, disable, attach
if /i "!SHOW_CONSOLE!"=="true" (
    set CONSOLE_PARAM=--windows-console-mode=force
    call :log_echo [INFO] Console mode: enabled
) else (
    set CONSOLE_PARAM=--windows-console-mode=disable
    call :log_echo [INFO] Console mode: disabled
)


:: Build include package parameters
set "INCLUDE_PARAM="
if not "%INCLUDE_PACKAGES%"=="" (
    for %%p in (%INCLUDE_PACKAGES%) do (
        set "INCLUDE_PARAM=!INCLUDE_PARAM! --include-package=%%p"
    )
    call :log_echo [INFO] Including packages: %INCLUDE_PACKAGES%
) else (
    call :log_echo [INFO] No additional packages specified, using automatic dependency detection
)

:: Build exclude import parameters
set "EXCLUDE_PARAM="
if not "%EXCLUDE_IMPORTS%"=="" (
    for %%e in (%EXCLUDE_IMPORTS%) do (
        set "EXCLUDE_PARAM=!EXCLUDE_PARAM! --nofollow-import-to=%%e"
    )
    call :log_echo [INFO] Excluding imports: %EXCLUDE_IMPORTS%
    call :log_echo [Optimize] Auto-excluding unnecessary dependencies to speed up build...
)

:: First compilation attempt
call :log_echo [ATTEMPT] Starting intelligent compilation process...
call :compile_with_nuitka 1

:: Check compilation result
set "COMPILE_RESULT=!errorlevel!"
if !COMPILE_RESULT! equ 0 (
    call :log_echo ""
    call :log_echo ============================================
    call :log_echo [SUCCESS] Compilation completed!
    call :log_echo ============================================

    :: Find and move generated executable
    call :find_and_move_exe

    :: Clean temp directory immediately exe moved, no longer needed
    echo.
    echo [CLEANUP] Cleaning build temp directory...
    if exist "%TEMP_DIR%" (
        rmdir /s /q "%TEMP_DIR%" 2>nul
        echo [SUCCESS] Temp directory cleaned
    )

    :: Copy necessary config files
    call :copy_runtime_files

    :: Display build info
    call :show_build_info

    :: Display elapsed time
    echo.
    call :show_elapsed_time
    echo.
    echo ============================================
    echo [INFO] Build completed successfully!
    echo ============================================

    :: Clean cache immediately after successful build
    echo.
    echo [CLEANUP] Cleaning build cache after successful build...

    :: Clean Nuitka build cache directories in project root
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

    :: Clean Nuitka build cache directories in build folder (main.build, main.dist, etc.)
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

    :: Clean runtime-generated icon files in build directory (these should be embedded in exe)
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

    :: Clean config directory if empty or contains only generated files
    if exist "%BUILD_DIR%\config" (
        echo [Clean] Removing config directory...
        rmdir /s /q "%BUILD_DIR%\config" 2>nul
    )

    :: 清理 __pycache__ 目录
    for /d /r "%PROJECT_ROOT%" %%d in (__pycache__) do (
        if exist "%%d" (
            echo [Clean] Removing __pycache__: %%d
            rmdir /s /q "%%d" 2>nul
        )
    )

    :: 清理 .pyc 文件
    for /r "%PROJECT_ROOT%" %%f in (*.pyc) do (
        if exist "%%f" (
            del /q "%%f" 2>nul
        )
    )

    :: 清理 .pyo 文件
    for /r "%PROJECT_ROOT%" %%f in (*.pyo) do (
        if exist "%%f" (
            del /q "%%f" 2>nul
        )
    )

    :: 清理 .pyi 文件
    for %%f in ("%PROJECT_ROOT%*.pyi") do (
        if exist "%%f" (
            echo [Clean] Removing: %%~nxf
            del /q "%%f" 2>nul
        )
    )

    :: 清理编译报告
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

    :: 执行失败诊断和指导
    call :failure_diagnosis_and_guidance

    :: 显示耗时
    echo.
    call :show_elapsed_time
)

:: 清理临时文件（构建失败时的残留）
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

:: ============================================
:: 函数定义区域
:: ============================================

:: 查找并移动可执行文件
:find_and_move_exe
echo [SEARCH] Looking for generated executable files...

set "EXE_FOUND=0"
set "MAIN_FILE_BASE=%MAIN_FILE:.py=%"

:: 1. 检查项目根目录
if exist "%PROJECT_ROOT%%MAIN_FILE_BASE%.exe" (
    move "%PROJECT_ROOT%%MAIN_FILE_BASE%.exe" "%DIST_DIR%\%OUTPUT_EXE_NAME%.exe"
    echo [SUCCESS] Executable moved: %DIST_DIR%\%OUTPUT_EXE_NAME%.exe
    set "EXE_FOUND=1"
    goto :eof
)

:: 2. 检查temp目录
if exist "%TEMP_DIR%\%MAIN_FILE_BASE%.exe" (
    move "%TEMP_DIR%\%MAIN_FILE_BASE%.exe" "%DIST_DIR%\%OUTPUT_EXE_NAME%.exe"
    echo [SUCCESS] Executable moved: %DIST_DIR%\%OUTPUT_EXE_NAME%.exe
    set "EXE_FOUND=1"
    goto :eof
)

:: 3. 搜索所有可能的exe文件
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

:: 复制运行时文件
:copy_runtime_files
echo [DEPLOY] Copying runtime files...

:: 不再复制配置文件和图标，让程序在运行时自动生成config.json
:: 图标已经集成到exe文件中，无需单独复制

echo [INFO] Runtime files copy completed (minimal deployment)
goto :eof

:: 显示构建信息
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

:: 增强的网络连接检查
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

:: 使用智能镜像源安装 Nuitka
:install_nuitka_with_mirror
echo [Info] Detecting fastest pip mirror source...
set "PIP_MIRROR="
set "MIRROR_NAME=PyPI 官方源"
set "BEST_TIME=9999"

:: 测试 PyPI 官方源
echo Testing: PyPI 官方源...
powershell -Command "$ProgressPreference='SilentlyContinue'; $sw=[System.Diagnostics.Stopwatch]::StartNew(); try { $null=Invoke-WebRequest -Uri 'https://pypi.org' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; $sw.Stop(); Write-Host $sw.ElapsedMilliseconds } catch { Write-Host 9999 }" > "%TEMP%\mirror_test.txt" 2>&1
set /p PYPI_TIME=<"%TEMP%\mirror_test.txt"
if !PYPI_TIME! lss !BEST_TIME! (
    set "BEST_TIME=!PYPI_TIME!"
    set "MIRROR_NAME=PyPI 官方源"
    set "PIP_MIRROR=-i https://pypi.org/simple"
)

:: 测试清华源
echo Testing: 清华大学镜像源...
powershell -Command "$ProgressPreference='SilentlyContinue'; $sw=[System.Diagnostics.Stopwatch]::StartNew(); try { $null=Invoke-WebRequest -Uri 'https://pypi.tuna.tsinghua.edu.cn' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; $sw.Stop(); Write-Host $sw.ElapsedMilliseconds } catch { Write-Host 9999 }" > "%TEMP%\mirror_test.txt" 2>&1
set /p TSINGHUA_TIME=<"%TEMP%\mirror_test.txt"
if !TSINGHUA_TIME! lss !BEST_TIME! (
    set "BEST_TIME=!TSINGHUA_TIME!"
    set "MIRROR_NAME=清华大学镜像源"
    set "PIP_MIRROR=-i https://pypi.tuna.tsinghua.edu.cn/simple"
)

:: 测试阿里云源
echo Testing: 阿里云镜像源...
powershell -Command "$ProgressPreference='SilentlyContinue'; $sw=[System.Diagnostics.Stopwatch]::StartNew(); try { $null=Invoke-WebRequest -Uri 'https://mirrors.aliyun.com' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; $sw.Stop(); Write-Host $sw.ElapsedMilliseconds } catch { Write-Host 9999 }" > "%TEMP%\mirror_test.txt" 2>&1
set /p ALIYUN_TIME=<"%TEMP%\mirror_test.txt"
if !ALIYUN_TIME! lss !BEST_TIME! (
    set "BEST_TIME=!ALIYUN_TIME!"
    set "MIRROR_NAME=阿里云镜像源"
    set "PIP_MIRROR=-i https://mirrors.aliyun.com/pypi/simple/"
)

:: 清理临时文件
if exist "%TEMP%\mirror_test.txt" del "%TEMP%\mirror_test.txt"

:: 显示结果
if !BEST_TIME! lss 9999 (
    echo [Success] Selected fastest mirror: !MIRROR_NAME! ^(!BEST_TIME!ms^)
) else (
    echo [Info] All mirrors timed out, using default PyPI
    set "MIRROR_NAME=PyPI 官方源 (备用)"
    set "PIP_MIRROR=-i https://pypi.org/simple"
)
echo.

:: 升级 pip
echo [Info] Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip %PIP_MIRROR% >nul 2>&1
if !errorlevel! equ 0 (
    echo [Success] pip upgraded
) else (
    echo [Warning] pip upgrade failed, continuing...
)
echo.

:: 安装 Nuitka
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

:: 检测系统架构并获取最新GCC版本
:detect_system_arch_and_get_gcc

:: 检测系统架构
set "SYSTEM_ARCH=x86_64"
if "%PROCESSOR_ARCHITECTURE%"=="x86" (
    set "SYSTEM_ARCH=i686"
) else if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "SYSTEM_ARCH=x86_64"
) else (
    :: 使用 PowerShell 检测
    for /f "delims=" %%a in ('powershell -Command "[System.Environment]::Is64BitOperatingSystem"') do set "IS_64BIT=%%a"
    if "!IS_64BIT!"=="True" (
        set "SYSTEM_ARCH=x86_64"
    ) else (
        set "SYSTEM_ARCH=i686"
    )
)

:: 根据架构设置 GCC 文件名模式
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

:: 创建下载目录
if not exist "%GCC_DOWNLOAD_DIR%" (
    mkdir "%GCC_DOWNLOAD_DIR%" 2>nul
)

:: 先检查本地是否已有匹配架构的 GCC 文件
echo [Checking] Searching for existing GCC compiler...
set "LOCAL_GCC_FOUND=0"
set "LOCAL_GCC_ZIP="
set "LOCAL_GCC_EXTRACT_DIR="

:: 搜索本地匹配架构的 GCC zip 文件
for %%f in ("%GCC_DOWNLOAD_DIR%\winlibs-!SYSTEM_ARCH!-posix-*.zip") do (
    if exist "%%f" (
        set "LOCAL_GCC_ZIP=%%~nxf"
        set "LOCAL_GCC_ZIP_PATH=%%f"

        :: winlibs 的 zip 包解压后直接是 mingw64 目录（64位）或 mingw32 目录（32位）
        :: 所以我们直接检查这些目录是否存在
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
            :: 有 zip 文件但未解压，标记为找到但需要解压
            set "LOCAL_GCC_FOUND=2"
            echo [Found] Local GCC zip found but not extracted: !LOCAL_GCC_ZIP!
            goto :local_gcc_ready
        )
    )
)

:local_gcc_ready
if !LOCAL_GCC_FOUND! equ 1 (
    :: 本地已有可用的 GCC，直接使用
    echo [Found] Using existing local GCC compiler
    set "GCC_ZIP=!LOCAL_GCC_ZIP!"
    set "GCC_ZIP_PATH=!LOCAL_GCC_ZIP_PATH!"
    set "NUITKA_CACHE=!LOCAL_GCC_EXTRACT_DIR!"
    echo [Status] GCC compiler is ready
    echo ============================================
    echo.
    goto :eof
) else if !LOCAL_GCC_FOUND! equ 2 (
    :: 本地有 zip 文件但未解压，直接解压使用
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

:: 本地没有可用的 GCC，从 GitHub 获取最新版本
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
    :: 使用默认版本作为后备
    set "GCC_ZIP=winlibs-x86_64-posix-seh-gcc-15.2.0-mingw-w64msvcrt-13.0.0-r5.zip"
    set "GCC_URL=https://github.com/brechtsanders/winlibs_mingw/releases/download/15.2.0posix-13.0.0-msvcrt-r5/%GCC_ZIP%"
    set "GCC_VERSION=15.2.0posix-13.0.0-msvcrt-r5"
) else (
    :: 读取 GitHub API 返回的信息
    set "LINE_NUM=0"
    for /f "delims=" %%a in ('type "%TEMP%\gcc_info.txt"') do (
        set /a "LINE_NUM+=1"
        if !LINE_NUM! equ 1 set "GCC_ZIP=%%a"
        if !LINE_NUM! equ 2 set "GCC_URL=%%a"
        if !LINE_NUM! equ 3 set "GCC_VERSION=%%a"
    )
)

:: 清理临时文件
del "%PS_SCRIPT%" >nul 2>&1
del "%TEMP%\gcc_info.txt" >nul 2>&1

echo [Latest] GCC Version: !GCC_VERSION!
echo [File] !GCC_ZIP!

:: 检查本地是否已有该文件
set "GCC_ZIP_PATH=%GCC_DOWNLOAD_DIR%\!GCC_ZIP!"
if exist "!GCC_ZIP_PATH!" (
    echo [Found] GCC archive already downloaded

    :: 检查是否已解压
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
:: 设置 Nuitka 使用的 GCC 路径（如果还未设置）
if not defined NUITKA_CACHE (
    set "NUITKA_CACHE=%GCC_DOWNLOAD_DIR%\!GCC_ZIP:.zip=%"
)

echo [Success] GCC compiler ready at: !NUITKA_CACHE!
echo.
goto :eof

:: 下载 GCC
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

:: 解压 GCC
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

:: 智能GCC缓存管理
:manage_gcc_cache
:: 静默检查，不输出多余信息
goto :eof

:: Smart compilation function
:compile_with_nuitka
set "ATTEMPT=%~1"
call :log_echo [COMPILE] Compilation attempt #%ATTEMPT%...
echo. >> "%ERROR_LOG%"
echo -------------------------------------------- >> "%ERROR_LOG%"
echo Compilation Attempt #%ATTEMPT% >> "%ERROR_LOG%"
echo Time: %time% >> "%ERROR_LOG%"
echo -------------------------------------------- >> "%ERROR_LOG%"

:: Build base Nuitka command
:: Note Python path already quoted if contains spaces
:: Use variable directly, batch will handle spaces automatically
set "NUITKA_CMD=!PYTHON_EXE! -m nuitka"
set "NUITKA_CMD=!NUITKA_CMD! --standalone"
set "NUITKA_CMD=!NUITKA_CMD! --onefile"
set "NUITKA_CMD=!NUITKA_CMD! --output-dir=!TEMP_DIR!"
:: Add console mode parameter directly based on configuration
if /i "!SHOW_CONSOLE!"=="true" (
    set "NUITKA_CMD=!NUITKA_CMD! --windows-console-mode=force"
) else (
    set "NUITKA_CMD=!NUITKA_CMD! --windows-console-mode=disable"
)

if not "!ICON_PARAM!"=="" (
    set "NUITKA_CMD=!NUITKA_CMD! !ICON_PARAM!"
)

:: Process version format auto-convert to x.x.x.x format
set "WIN_VERSION=%PROJECT_VERSION%"
echo %WIN_VERSION% | findstr /R "^[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*$" >nul
if !errorlevel! neq 0 (
    echo %WIN_VERSION% | findstr /R "^[0-9]*\.[0-9]*$" >nul
    if !errorlevel! equ 0 (
        set "WIN_VERSION=%PROJECT_VERSION%.0.0"
    ) else (
        echo %WIN_VERSION% | findstr /R "^[0-9]*\.[0-9]*\.[0-9]*$" >nul
        if !errorlevel! equ 0 (
            set "WIN_VERSION=%PROJECT_VERSION%.0"
        ) else (
            set "WIN_VERSION=1.0.0.0"
        )
    )
)

:: Process company name may contain spaces, need quotes
set "NUITKA_CMD=!NUITKA_CMD! --windows-company-name=!COMPANY_NAME!"
set "NUITKA_CMD=!NUITKA_CMD! --windows-file-version=!WIN_VERSION!"
set "NUITKA_CMD=!NUITKA_CMD! --windows-product-version=!WIN_VERSION!"

:: Select parameters based on Windows compatibility mode
if /i "%WIN10_COMPAT_MODE%"=="true" (
    call :log_echo [Windows 10/11] Using Windows 10/11 compatibility compilation parameters
    echo Windows 10/11 Compatibility Mode >> "%ERROR_LOG%"
    :: Build product name and file description with Win10 suffix
    set "PRODUCT_NAME_VALUE=!PROJECT_NAME! Win10"
    set "FILE_DESC_VALUE=!PROJECT_DESCRIPTION! - Windows 10/11 Compatible"
) else (
    call :log_echo [Standard] Using standard compilation parameters
    echo Standard Compilation Mode >> "%ERROR_LOG%"
    :: Use original project name and description
    set "PRODUCT_NAME_VALUE=!PROJECT_NAME!"
    set "FILE_DESC_VALUE=!PROJECT_DESCRIPTION!"
)

:: Add Windows version info parameters
:: Note: Replace spaces in values with underscores to avoid parameter parsing issues
:: Nuitka will still work correctly with underscores in product names
set "PRODUCT_NAME_SAFE=!PRODUCT_NAME_VALUE: =_!"
set "FILE_DESC_SAFE=!FILE_DESC_VALUE: =_!"
set "NUITKA_CMD=!NUITKA_CMD! --windows-product-name=!PRODUCT_NAME_SAFE!"
set "NUITKA_CMD=!NUITKA_CMD! --windows-file-description=!FILE_DESC_SAFE!"

:: Add package parameters
:: Enable PyQt6 plugin support fix missing Qt platform plugin issue
set "NUITKA_CMD=!NUITKA_CMD! --enable-plugin=pyqt6"
call :log_echo [INFO] PyQt6 plugin enabled for Qt platform support
if not "!INCLUDE_PARAM!"=="" (
    set "NUITKA_CMD=!NUITKA_CMD! !INCLUDE_PARAM!"
)

:: Add exclude import parameters auto-exclude unnecessary dependencies to reduce build time
if not "!EXCLUDE_PARAM!"=="" (
    set "NUITKA_CMD=!NUITKA_CMD! !EXCLUDE_PARAM!"
    call :log_echo [Optimize] Dependency exclusion enabled to reduce build time
)

:: LTO optimization
if /i "!ENABLE_LTO!"=="true" (
    set "NUITKA_CMD=!NUITKA_CMD! --lto=yes"
    call :log_echo [INFO] LTO link-time optimization enabled
    call :log_echo [INFO]   - Reduces executable size
    call :log_echo [INFO]   - Improves runtime performance
    call :log_echo [INFO]   - Slightly increases compile time
)

:: Python optimization
if /i "!ENABLE_PYTHON_OPT!"=="true" (
    set "NUITKA_CMD=!NUITKA_CMD! --python-flag=no_docstrings"
    set "NUITKA_CMD=!NUITKA_CMD! --python-flag=no_asserts"
    set "NUITKA_CMD=!NUITKA_CMD! --python-flag=-O"
    call :log_echo [INFO] Python bytecode optimization enabled
    call :log_echo [INFO]   - Removes docstrings
    call :log_echo [INFO]   - Disables assert statements
    call :log_echo [INFO]   - Enables Python -O flag
)

:: Disable unnecessary plugins and features to speed up build
set "NUITKA_CMD=!NUITKA_CMD! --no-prefer-source-code"

:: PyQt6 specific configuration include Qt platform plugins and resources
call :log_echo [INFO] Configuring PyQt6 platform plugins and dependencies
set "NUITKA_CMD=!NUITKA_CMD! --include-qt-plugins=sensible,platforms,styles,iconengines,imageformats"
:: Include all necessary PyQt6 data files and DLLs
set "NUITKA_CMD=!NUITKA_CMD! --include-package-data=PyQt6"

:: Add progress and report parameters
set "NUITKA_CMD=!NUITKA_CMD! --show-progress"
set "NUITKA_CMD=!NUITKA_CMD! --show-memory"
set "NUITKA_CMD=!NUITKA_CMD! --assume-yes-for-downloads"

:: Add resources directory to package (for runtime use - icons, etc.)
set "RESOURCES_DIR=!PROJECT_ROOT!resources"
if exist "!RESOURCES_DIR!" (
    :: Include entire resources directory for runtime access
    set "NUITKA_CMD=!NUITKA_CMD! --include-data-dir=!RESOURCES_DIR!=resources"
    call :log_echo [INFO] Including resources directory in package
) else (
    :: Fallback: try to include just icon file if resources dir doesn't exist
    if not "!ICON_PARAM!"=="" (
        if defined ICON_FULL_PATH (
            if exist "!ICON_FULL_PATH!" (
                set "NUITKA_CMD=!NUITKA_CMD! --include-data-file=!ICON_FULL_PATH!=icon.ico"
                call :log_echo [INFO] Including icon file in package: !ICON_FILE!
            )
        )
    )
)

:: Add extra parameters check if contains deprecated console parameters
if not "%EXTRA_NUITKA_ARGS%"=="" (
    :: Check and warn if using old console parameters
    echo %EXTRA_NUITKA_ARGS% | findstr /i "--disable-console --enable-console" >nul
    if !errorlevel! equ 0 (
        call :log_echo [WARNING] EXTRA_NUITKA_ARGS contains deprecated console options
        call :log_echo [WARNING] Please use --windows-console-mode instead
    )
    set "NUITKA_CMD=!NUITKA_CMD! !EXTRA_NUITKA_ARGS!"
)
:: Add main file as positional argument
set "NUITKA_CMD=!NUITKA_CMD! !MAIN_FILE!"

:: Execute compilation using delayed expansion to ensure variables are correctly expanded
:: Note: Use delayed expansion !NUITKA_CMD! instead of immediate expansion %NUITKA_CMD%
:: Write command to temporary batch file for reliable execution with complex arguments
set "TEMP_CMD_FILE=%TEMP%\nuitka_cmd_%RANDOM%.bat"
set "TEMP_OUTPUT=%TEMP%\nuitka_output_%RANDOM%.txt"

:: Log the full command for debugging (icon parameter should be visible)
call :log_echo [DEBUG] Full Nuitka command: !NUITKA_CMD!

:: Write the command to temporary batch file
:: Simple approach: write the command directly
> "!TEMP_CMD_FILE!" echo @echo off
>> "!TEMP_CMD_FILE!" echo !NUITKA_CMD!
:: Execute the temporary batch file and capture output
call "!TEMP_CMD_FILE!" > "!TEMP_OUTPUT!" 2>&1
set "COMPILE_RESULT=!errorlevel!"
:: Clean up temporary command file
if exist "!TEMP_CMD_FILE!" del "!TEMP_CMD_FILE!" >nul 2>&1

:: Filter output: only show actual errors, suppress help messages
if exist "!TEMP_OUTPUT!" (
    :: Check if output contains help message (indicates parameter error)
    findstr /C:"Usage:" "!TEMP_OUTPUT!" >nul 2>&1
    if !errorlevel! equ 0 (
        :: Help message detected, only output error lines (lines containing "FATAL", "ERROR", "Error")
        findstr /C:"FATAL" /C:"ERROR" /C:"Error" /C:"error" "!TEMP_OUTPUT!" >> "%ERROR_LOG%" 2>&1
    ) else (
        :: No help message, output all content
        type "!TEMP_OUTPUT!" >> "%ERROR_LOG%" 2>&1
    )
    del "!TEMP_OUTPUT!" >nul 2>&1
)

:: Record compilation result
if !COMPILE_RESULT! neq 0 (
    echo Compilation attempt #%ATTEMPT% FAILED with error code: !COMPILE_RESULT! >> "%ERROR_LOG%"
    echo. >> "%ERROR_LOG%"
) else (
    echo Compilation attempt #%ATTEMPT% SUCCESS >> "%ERROR_LOG%"
    echo. >> "%ERROR_LOG%"
)

:: If failed and attempts less than 3, continue retry
if !COMPILE_RESULT! neq 0 (
    if %ATTEMPT% LSS 3 (
        call :log_echo [RETRY] Compilation attempt #%ATTEMPT% failed with error code !COMPILE_RESULT!, preparing retry...
        set /a "NEXT_ATTEMPT=%ATTEMPT%+1"
        call :compile_with_nuitka !NEXT_ATTEMPT!
        set "COMPILE_RESULT=!errorlevel!"
    )
)

exit /b !COMPILE_RESULT!

:: 失败诊断和指导
:failure_diagnosis_and_guidance
echo [Diagnostics] Starting intelligent failure analysis...

:: 检查网络状态
call :check_network_advanced 2>nul

:: 检查磁盘空间
echo [System] Checking disk space...
for /f "tokens=3" %%a in ('dir /-c "%SystemDrive%\" 2^>nul ^| find "bytes free"') do (
    set "FREE_BYTES=%%a"
    if defined FREE_BYTES (
        set /a "FREE_GB=!FREE_BYTES! / 1073741824"
        if !FREE_GB! LSS 5 (
            echo [Warning] Insufficient disk space: !FREE_GB!GB (recommend at least 5GB)
        ) else (
            echo [Normal] Sufficient disk space: !FREE_GB!GB
        )
    ) else (
        echo [Warning] Unable to determine disk space
    )
)

:: 检查临时目录权限
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
echo [Error Log]
echo Detailed error log saved to: %ERROR_LOG%
echo Please check the log file for detailed error messages
echo.
goto :eof

:: Calculate and display elapsed time
:show_elapsed_time
set "END_TIME=%time%"
set "END_DATE=%date%"

:: 解析开始时间
for /f "tokens=1-4 delims=:., " %%a in ("%START_TIME%") do (
    set /a "START_H=%%a"
    set /a "START_M=%%b"
    set /a "START_S=%%c"
    set /a "START_MS=%%d"
)

:: 解析结束时间
for /f "tokens=1-4 delims=:., " %%a in ("%END_TIME%") do (
    set /a "END_H=%%a"
    set /a "END_M=%%b"
    set /a "END_S=%%c"
    set /a "END_MS=%%d"
)

:: 转换为总毫秒数
set /a "START_TOTAL_MS=(START_H*3600000)+(START_M*60000)+(START_S*1000)+START_MS"
set /a "END_TOTAL_MS=(END_H*3600000)+(END_M*60000)+(END_S*1000)+END_MS"

:: 处理跨天情况
if !END_TOTAL_MS! LSS !START_TOTAL_MS! (
    set /a "END_TOTAL_MS+=86400000"
)

:: 计算耗时
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
