@echo off
set "SCANNER_PY=C:\Users\erica\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%SCANNER_PY%" (
  echo The bundled Python runtime could not be found.
  echo Open this folder in Codex once to restore it, then try again.
  pause
  exit /b 1
)
"%SCANNER_PY%" "%~dp0app.py"
if errorlevel 1 pause
