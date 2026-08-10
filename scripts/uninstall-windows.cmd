@echo off
setlocal EnableExtensions
set "PROJECT=SRIC Core"
set "CMD=sric"
set "INSTALL_ROOT=%LOCALAPPDATA%\SRIC"
set "VENV=%INSTALL_ROOT%\venv"
set "BIN_DIR=%USERPROFILE%\.local\bin"

if exist "%BIN_DIR%\%CMD%.cmd" del /q "%BIN_DIR%\%CMD%.cmd" >nul 2>&1
if exist "%VENV%" rmdir /s /q "%VENV%"
if exist "%INSTALL_ROOT%\install-check.log" del /q "%INSTALL_ROOT%\install-check.log" >nul 2>&1

rem Do not remove BIN_DIR from PATH: it is shared by other Sentinel Forge tools.
rem Preserve configuration, workspaces, plugins, evidence and other user data.
echo %PROJECT% runtime removed. User configuration and research data were preserved.
exit /b 0
