@echo off
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_windows_installer.ps1"
if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Build finished. The installer is in the dist folder:
echo dist\AutoSupportGeneratorSetup.exe
echo.
pause
