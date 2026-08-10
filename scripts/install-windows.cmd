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
if exist "%VENV%\Scripts\python.exe" (
  "%VENV%\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
  if errorlevel 1 (
    echo Rebuilding obsolete or broken runtime environment: %VENV%
    rmdir /s /q "%VENV%" || exit /b 3
  )
) else if exist "%VENV%" (
  echo Rebuilding incomplete runtime environment: %VENV%
  rmdir /s /q "%VENV%" || exit /b 3
)
if not exist "%VENV%\Scripts\python.exe" (
  %PY_CMD% -m venv "%VENV%" || (echo Failed to create isolated Python environment.& exit /b 3)
)

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel || (echo Failed to bootstrap pip/setuptools/wheel.& exit /b 3)
if exist "%FIRST_PARTY%" (
  "%VENV%\Scripts\python.exe" -m pip install --upgrade -c "%CONSTRAINTS%" -r "%FIRST_PARTY%" || (echo Failed to install Sentinel Forge first-party dependencies.& exit /b 3)
)
"%VENV%\Scripts\python.exe" -m pip install --upgrade -c "%CONSTRAINTS%" "%REPO_ROOT%" || (echo Failed to install SRIC Core runtime.& exit /b 3)
"%VENV%\Scripts\python.exe" -m pip check || (echo Installed dependency graph is inconsistent.& exit /b 3)
"%VENV%\Scripts\python.exe" -c "import sric; import sric.web_console; import sric.web_workbench; import sric.web_catalog" || (echo SRIC Core import integrity check failed.& exit /b 3)

>"%BIN_DIR%\%CMD%.cmd" echo @"%VENV%\Scripts\%CMD%.exe" %%*
"%VENV%\Scripts\python.exe" -m sric.install_path "%BIN_DIR%" || exit /b 3

set "SENTINEL_BANNER=never"
set "CHECK_LOG=%INSTALL_ROOT%\install-check.log"
>"%CHECK_LOG%" type nul
"%VENV%\Scripts\%CMD%.exe" doctor >>"%CHECK_LOG%" 2>&1 || goto :validation_failed
"%VENV%\Scripts\%CMD%.exe" capabilities >>"%CHECK_LOG%" 2>&1 || goto :validation_failed
"%VENV%\Scripts\%CMD%.exe" --help >>"%CHECK_LOG%" 2>&1 || goto :validation_failed
"%VENV%\Scripts\%CMD%.exe" -h >>"%CHECK_LOG%" 2>&1 || goto :validation_failed
"%VENV%\Scripts\%CMD%.exe" help >>"%CHECK_LOG%" 2>&1 || goto :validation_failed
del /q "%CHECK_LOG%" >nul 2>&1
echo %PROJECT% installed/repaired successfully.
echo Open a new Command Prompt and run: %CMD% --help
exit /b 0

:validation_failed
echo Installation validation failed.
type "%CHECK_LOG%"
exit /b 4