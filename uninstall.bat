@echo off
chcp 65001 >nul 2>&1
title WinVMService 卸载程序
setlocal enabledelayedexpansion

echo ============================================
echo  WinVMService 卸载程序
echo ============================================
echo.

:: ─── 确认卸载 ──────────────────────────────────
set /p CONFIRM=确定要卸载 WinVMService？(Y/N):
if /i not "!CONFIRM!"=="Y" (
    echo 取消卸载。
    pause
    exit /b 0
)

:: ─── 查找安装目录 ──────────────────────────────
if "%INSTALL_DIR%"=="" (
    :: 尝试默认路径 + 查找当前目录
    if exist "%LOCALAPPDATA%\WinVMService\winvm_service.py" (
        set INSTALL_DIR=%LOCALAPPDATA%\WinVMService
    ) else if exist "%~dp0winvm_service.py" (
        set INSTALL_DIR=%~dp0
        set INSTALL_DIR=!INSTALL_DIR:~0,-1!
    ) else (
        echo [错误] 未找到安装目录
        echo         请设置 INSTALL_DIR 环境变量
        pause
        exit /b 1
    )
)

echo   - 安装目录: %INSTALL_DIR%

:: ─── 停止服务 ──────────────────────────────────
echo.
echo [1/3] 停止运行中的服务...
taskkill /f /im python.exe /fi "WINDOWTITLE eq *winvm*" 2>nul
echo   - 已尝试停止

:: ─── 删除开机自启任务 ──────────────────────────
echo [2/3] 删除开机自启任务...
schtasks /delete /tn "WinVMService" /f >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   - 计划任务 WinVMService 已删除
) else (
    echo   - 未找到计划任务（可能已删除）
)

:: 清理 VBS 备用方案
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start_winvm.vbs" (
    del /f "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start_winvm.vbs"
    echo   - VBS 启动脚本已删除
)

:: ─── 删除文件 ──────────────────────────────────
echo [3/3] 删除服务文件...
rmdir /s /q "%INSTALL_DIR%" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   - 目录已删除
) else (
    echo   - 部分文件可能仍在，可手动删除: %INSTALL_DIR%
)

:: ─── 完成 ──────────────────────────────────────
echo.
echo ============================================
echo  卸载完成！
echo ============================================
echo.
echo  注意：Python 依赖包 (flask, pillow, waitress 等)
echo  未被删除，如需清理请手动执行:
echo    pip uninstall flask pyautogui pillow numpy waitress mss
echo.

endlocal
pause
