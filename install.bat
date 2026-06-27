@echo off
chcp 65001 >nul 2>&1
title WinVMService 安装程序
setlocal enabledelayedexpansion

echo ============================================
echo  WinVMService - Windows VM 控制服务安装程序
echo ============================================
echo.

:: ─── 检测 Python ──────────────────────────────────
echo [1/5] 检测 Python 环境...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo        下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

python --version 2>&1 | findstr "3." >nul
if %ERRORLEVEL% NEQ 0 (
    echo [错误] Python 版本过低，需要 Python 3.8+
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   - 检测到: %%i

:: 获取 Python 完整路径
for /f "tokens=*" %%p in ('where python') do (
    set PYTHON_PATH=%%p
    goto :found_python
)
:found_python
echo   - 路径: %PYTHON_PATH%

:: ─── 安装目录 ────────────────────────────────────
echo.
echo [2/5] 选择安装目录...
if "%INSTALL_DIR%"=="" (
    set INSTALL_DIR=%LOCALAPPDATA%\WinVMService
)
echo   - 默认: %INSTALL_DIR%
echo   - 可通过 set INSTALL_DIR=路径 自定义
echo.

:: ─── 创建目录 ────────────────────────────────────
echo [3/5] 创建安装目录...
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo   - 已创建目录
) else (
    echo   - 目录已存在
)

:: ─── 复制文件 ────────────────────────────────────
echo [4/5] 复制服务文件...
copy /Y "%~dp0winvm_service.py" "%INSTALL_DIR%\winvm_service.py" >nul
if %ERRORLEVEL% EQU 0 (
    echo   - winvm_service.py - OK
) else (
    echo   - winvm_service.py - 失败！
    echo   - 请将本脚本与 winvm_service.py 放在同一目录
    pause
    exit /b 1
)

:: ─── 安装 Python 依赖 ────────────────────────────
echo.
echo [5/5] 安装 Python 依赖...
pip install flask pyautogui pillow numpy waitress mss -q
if %ERRORLEVEL% NEQ 0 (
    echo   - pip 失败，尝试 pip3...
    pip3 install flask pyautogui pillow numpy waitress mss -q
)
echo   - Python 依赖安装完成

:: ─── 创建开机自启任务 ────────────────────────────
echo.
echo -- 配置开机自启（强制 Session 1）...

set TASK_NAME=WinVMService

:: 删除旧任务
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: 创建任务：登录时启动，Interactive 模式 = Session 1
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON_PATH%\" \"%INSTALL_DIR%\winvm_service.py\"" ^
    /sc onlogon ^
    /ru "%USERNAME%" ^
    /it ^
    /rl limited ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo   - 开机自启任务创建成功
    echo   - 任务名称: %TASK_NAME%
) else (
    echo [警告] 任务创建失败，尝试创建 VBS 启动脚本...
    (
        echo Set WshShell = CreateObject^("WScript.Shell"^)
        echo WshShell.Run "%PYTHON_PATH% %INSTALL_DIR%\winvm_service.py", 0, False
    ) > "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start_winvm.vbs"
    echo   - VBS 启动脚本已创建（备选方案）
)

:: ─── 显示配置摘要 ───────────────────────────────
echo.
echo ============================================
echo  安装完成！
echo ============================================
echo.
echo  安装位置: %INSTALL_DIR%
echo  服务端口: 5000
echo  Python:   %PYTHON_PATH%
echo.
echo  [环境变量配置]
echo  变量名              默认值     说明
echo  ─────────────────────────────────────
echo  PORT                5000       HTTP 端口
echo  HOST                0.0.0.0    监听地址
echo  SCREENSHOT_MAX_W    0          缩图上限(0=不限)
echo  JPEG_QUALITY        85         JPEG 质量(1-100)
echo  FRAME_INTERVAL      0.5        截图间隔(秒)
echo  DIFF_THRESHOLD      0.05       像素变化阈值(5%%)
echo  LOG_LEVEL           INFO      日志级别
echo.
echo  设置方式: set PORT=8080 ^&^& python "%INSTALL_DIR%\winvm_service.py"
echo.
echo  [启动方式]
echo  1. 立即启动:
echo     start /B python "%INSTALL_DIR%\winvm_service.py"
echo.
echo  2. 重启后自动启动: 重新登录即可
echo.
echo  3. 调试模式:
echo     python "%INSTALL_DIR%\winvm_service.py"
echo.
echo  4. 卸载:
echo     schtasks /delete /tn "%TASK_NAME%" /f
echo     rmdir /s /q "%INSTALL_DIR%"

:: ─── 立即启动 ──────────────────────────────────
echo.
set /p START_NOW=是否立即启动服务？(Y/N):
if /i "!START_NOW!"=="Y" (
    echo 正在启动服务（端口 5000）...
    start /B python "%INSTALL_DIR%\winvm_service.py"
    echo 服务已启动，请稍候 5-10 秒等待 waitress 就绪
)

endlocal
echo.
pause
