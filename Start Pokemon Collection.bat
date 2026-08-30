@echo off
setlocal
cd /d "%~dp0"
set "COLLECTION_PY=C:\Users\erica\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%COLLECTION_PY%" (
  echo The bundled Python runtime could not be found.
  echo Open this folder in Codex once to restore it, then try again.
  pause
  exit /b 1
)
call "%~dp0tools\_ensure_dependencies.bat" "%COLLECTION_PY%" "%~dp0requirements.txt"
if errorlevel 1 (
  pause
  exit /b 1
)
"%COLLECTION_PY%" "%~dp0app.py" %*
if errorlevel 1 pause
