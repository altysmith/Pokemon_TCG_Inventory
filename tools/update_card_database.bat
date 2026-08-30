@echo off
setlocal
cd /d "%~dp0.."
set "PYTHON_EXE=C:\Users\erica\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON_EXE%" (
  echo The bundled Python runtime could not be found.
  pause
  exit /b 1
)
call "%~dp0_ensure_dependencies.bat" "%PYTHON_EXE%" "%~dp0..\requirements.txt"
if errorlevel 1 (
  pause
  exit /b 1
)

echo Checking Malie and rebuilding the local catalog from preserved raw JSON...
"%PYTHON_EXE%" -m card_api sync
pause
