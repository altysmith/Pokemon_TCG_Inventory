@echo off
setlocal

set "PYTHON_EXE=%~1"
set "REQUIREMENTS_FILE=%~2"

if not exist "%PYTHON_EXE%" (
  echo The bundled Python runtime could not be found.
  echo Open this folder in Codex once to restore it, then try again.
  exit /b 1
)

if not exist "%REQUIREMENTS_FILE%" (
  echo requirements.txt could not be found in the project folder.
  exit /b 1
)

"%PYTHON_EXE%" -c "import PIL, onnxruntime, rapidocr, fastapi, uvicorn, httpx" >nul 2>&1
if not errorlevel 1 exit /b 0

echo Some required Python packages are missing.
echo Installing the packages listed in requirements.txt...
"%PYTHON_EXE%" -m pip install -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
  echo.
  echo Package installation failed. Check the internet connection and try again.
  exit /b 1
)

"%PYTHON_EXE%" -c "import PIL, onnxruntime, rapidocr, fastapi, uvicorn, httpx" >nul 2>&1
if errorlevel 1 (
  echo The packages installed, but Python still cannot import them.
  exit /b 1
)

exit /b 0
