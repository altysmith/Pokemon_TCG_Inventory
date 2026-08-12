@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\erica\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON_EXE%" (
  echo The bundled Python runtime could not be found.
  echo Open this folder in Codex once to restore it, then try again.
  pause
  exit /b 1
)

echo Starting local Pokemon card API at http://127.0.0.1:8770/docs
"%PYTHON_EXE%" -m card_api serve

if errorlevel 1 pause
