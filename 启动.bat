@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title DavinciZ-ZImage
echo.
echo ================================================================
echo   Davinci Seven  Z-Image
echo   https://x.com/davinci_seven
echo ================================================================
echo.
echo Starting launcher...
echo.
where powershell >nul 2>&1
if errorlevel 1 goto no_ps
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_ui.ps1"
exit /b %ERRORLEVEL%

:no_ps
echo [ERROR] PowerShell not found.
pause
exit /b 1
