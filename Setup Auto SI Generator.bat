@echo off
setlocal
cd /d "%~dp0"

echo.
echo Auto Support Generator setup
echo ============================
echo.

set "PY_CMD="
call :try_python "py -3.12"
if not defined PY_CMD call :try_python "py -3.11"
if not defined PY_CMD call :try_python "py -3"
if not defined PY_CMD call :try_python "python"

if not defined PY_CMD (
  echo Python was not found.
  echo.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Please install Python 3.11 or newer from:
    echo https://www.python.org/downloads/windows/
    echo.
    echo During installation, enable "Add python.exe to PATH".
    pause
    exit /b 1
  )
  echo Trying to install Python 3.11 using winget...
  winget install --id Python.Python.3.11 -e --source winget
  if errorlevel 1 (
    echo.
    echo Python installation failed. Please install Python manually:
    echo https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  call :try_python "py -3.12"
  if not defined PY_CMD call :try_python "py -3.11"
  if not defined PY_CMD call :try_python "py -3"
  if not defined PY_CMD call :try_python "python"
  if not defined PY_CMD (
    echo.
    echo Python was installed but is not visible in this terminal yet.
    echo Close this window and run "Setup Auto SI Generator.bat" again.
    pause
    exit /b 1
  )
)

echo Using Python:
%PY_CMD% --version
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating local virtual environment .venv ...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo Failed to activate .venv.
  pause
  exit /b 1
)

echo Upgrading installer tools...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo Failed to upgrade pip/setuptools/wheel.
  pause
  exit /b 1
)

echo Installing Auto Support Generator and Python packages...
python -m pip install -e .
if errorlevel 1 (
  echo.
  echo Installation failed.
  echo If the error mentions RDKit, try installing Python 3.11 and run this file again.
  pause
  exit /b 1
)

echo Verifying GUI import...
python -c "import si_generator.gui; print('GUI import OK')"
if errorlevel 1 (
  echo Verification failed.
  pause
  exit /b 1
)

echo.
echo Setup finished.
echo Start the program with:
echo Run Auto SI Generator.bat
echo.
pause
exit /b 0

:try_python
set "CANDIDATE=%~1"
%CANDIDATE% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY_CMD=%CANDIDATE%"
exit /b 0
