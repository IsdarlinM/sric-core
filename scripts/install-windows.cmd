@echo off
setlocal EnableExtensions
set "PROJECT=SRIC Core"
set "CMD=sric"
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "CONSTRAINTS=%REPO_ROOT%\requirements\runtime-py311.lock"
set "FIRST_PARTY=%REPO_ROOT%\requirements\first-party.txt"
set "INSTALL_ROOT=%LOCALAPPDATA%\SRIC"
set "VENV=%INSTALL_ROOT%\venv"
set "BIN_DIR=%USERPROFILE%\.local\bin"
set "PY_CMD="

where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
  )
)
if not defined PY_CMD (
  echo Python 3.11+ is required.
  exit /b 2
)

if not exist "%INSTALL_ROOT%" mkdir "%INSTALL_ROOT%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
if not exist "%VENV%\Scripts\python.exe" (
  %PY_CMD% -m venv "%VENV%" || exit /b 1
)

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel || (echo Failed to bootstrap pip/setuptools/wheel.& exit /b 3)
if exist "%FIRST_PARTY%" (
  "%VENV%\Scripts\python.exe" -m pip install --upgrade -c "%CONSTRAINTS%" -r "%FIRST_PARTY%" || (echo Failed to install Sentinel Forge first-party dependencies.& exit /b 3)
)
"%VENV%\Scripts\python.exe" -m pip install --upgrade -c "%CONSTRAINTS%" "%REPO_ROOT%" || (echo Failed to install SRIC Core runtime.& exit /b 3)
"%VENV%\Scripts\python.exe" -m pip check || (echo Installed dependency graph is inconsistent.& exit /b 3)
"%VENV%\Scripts\python.exe" -c "import sric; import sric.web_console; import sric.web_workbench" || (echo SRIC Core import integrity check failed.& exit /b 3)

>"%BIN_DIR%\%CMD%.cmd" echo @"%VENV%\Scripts\%CMD%.exe" %%*
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v Path 2^>nul ^| findstr /I "Path"') do set "USER_PATH=%%B"
echo ;%USER_PATH%; | find /I ";%BIN_DIR%;" >nul
if errorlevel 1 (
  if defined USER_PATH (
    setx PATH "%USER_PATH%;%BIN_DIR%" >nul
  ) else (
    setx PATH "%BIN_DIR%" >nul
  )
)

"%VENV%\Scripts\%CMD%.exe" doctor || exit /b 1
"%VENV%\Scripts\%CMD%.exe" capabilities || exit /b 1
"%VENV%\Scripts\%CMD%.exe" --help >nul || exit /b 1
"%VENV%\Scripts\%CMD%.exe" -h >nul || exit /b 1
"%VENV%\Scripts\%CMD%.exe" help >nul || exit /b 1
echo %PROJECT% installed/repaired successfully.
echo Open a new Command Prompt and run: %CMD% --help
exit /b 0
