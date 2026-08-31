@echo off
setlocal
cd /d "%~dp0"
set "SCANNER_PY=C:\Users\erica\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%SCANNER_PY%" (
  echo The bundled Python runtime could not be found.
  echo Open this folder in Codex once to restore it, then try again.
  pause
  exit /b 1
)
call "%~dp0..\tools\_ensure_dependencies.bat" "%SCANNER_PY%" "%~dp0..\requirements.txt"
if errorlevel 1 (
  pause
  exit /b 1
)
"%SCANNER_PY%" "%~dp0..\app.py" --start-path /legacy-webcam-scanner %*
if errorlevel 1 pause
