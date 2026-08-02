@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title DavinciZ Diagnostic

where powershell >nul 2>&1
if errorlevel 1 goto no_ps

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0diagnostics.ps1"
set "ec=%ERRORLEVEL%"
echo.
pause
exit /b %ec%

:no_ps
echo [ERROR] PowerShell not found.
pause
exit /b 1
