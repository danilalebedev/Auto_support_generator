@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo Windows PowerShell was not found.
  echo Please run "Setup Auto SI Generator.ps1" from PowerShell.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup Auto SI Generator.ps1"
set "SETUP_EXIT=%ERRORLEVEL%"

if not "%SETUP_EXIT%"=="0" (
  echo.
  echo Setup failed with exit code %SETUP_EXIT%.
  exit /b %SETUP_EXIT%
)

exit /b 0
