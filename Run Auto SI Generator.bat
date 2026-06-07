@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Local Python environment was not found.
  echo Please run "Setup Auto SI Generator.bat" first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m si_generator.gui
if errorlevel 1 pause
