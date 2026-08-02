@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

title Gen Style Covers (Local LoRA)
echo.
echo ================================================================
echo   Generate style cover images with local LoRA (not web images)
echo ================================================================
echo.

set "PACK_ROOT=%~dp0.."
for %%I in ("%PACK_ROOT%") do set "PACK_ROOT=%%~fI\"
set "ENGINE_ROOT="

if exist "%PACK_ROOT%engine\ComfyUI\main.py" (
  for %%I in ("%PACK_ROOT%engine") do set "ENGINE_ROOT=%%~fI"
  goto engine_ok
)
if exist "%PACK_ROOT%..\ComfyUI-zimage\ComfyUI\main.py" (
  for %%I in ("%PACK_ROOT%..\ComfyUI-zimage") do set "ENGINE_ROOT=%%~fI"
  goto engine_ok
)
echo [ERROR] ComfyUI engine not found.
pause
exit /b 1

:engine_ok
set "PYTHON_EXE=%ENGINE_ROOT%\python\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python not found: %PYTHON_EXE%
  pause
  exit /b 1
)

set "PYTHONPATH=%ENGINE_ROOT%\python\Lib\site-packages"
echo [engine] %ENGINE_ROOT%
echo [python] %PYTHON_EXE%
echo.
echo Make sure Comfy is running on 7777 (start 启动.bat first if needed).
echo This will regenerate ALL style covers with --force.
echo.

"%PYTHON_EXE%" "%PACK_ROOT%app\tools\gen_style_covers.py" --force %*
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo [done] with errors code=%ERR%
) else (
  echo [done] all ok
)
pause
exit /b %ERR%
