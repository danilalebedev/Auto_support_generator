@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo Auto Support Generator setup
echo ============================
echo.

set "PY_EXE="
set "PY_PROBE=%TEMP%\auto_si_generator_python.txt"
call :find_python

if not defined PY_EXE (
  echo Python was not found.
  echo.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Please install Python 3.12 or newer from:
    echo https://www.python.org/downloads/windows/
    echo.
    echo During installation, enable "Add python.exe to PATH".
    pause
    exit /b 1
  )
  echo Trying to install Python 3.12 using winget...
  winget install --id Python.Python.3.12 -e --source winget
  if errorlevel 1 (
    echo.
    echo Python installation failed. Please install Python manually:
    echo https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  call :find_python
  if not defined PY_EXE (
    echo.
    echo Python was installed but is not visible in this terminal yet.
    echo Close this window and run "Setup Auto SI Generator.bat" again.
    pause
    exit /b 1
  )
)

echo Using Python:
"%PY_EXE%" --version
echo %PY_EXE%
echo.

if exist ".venv" if not exist ".venv\Scripts\python.exe" (
  echo Removing incomplete .venv from previous failed setup...
  rmdir /s /q ".venv"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local virtual environment .venv ...
  "%PY_EXE%" -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"
"%VENV_PY%" -c "import sys; print(sys.executable)" >nul 2>nul
if errorlevel 1 (
  echo Local virtual environment is broken.
  echo Removing .venv and creating it again...
  rmdir /s /q ".venv"
  "%PY_EXE%" -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
  "%VENV_PY%" -c "import sys; print(sys.executable)" >nul 2>nul
)
if errorlevel 1 (
  echo Failed to use .venv Python.
  pause
  exit /b 1
)

echo Upgrading installer tools...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo Failed to upgrade pip/setuptools/wheel.
  pause
  exit /b 1
)

echo Installing Auto Support Generator and Python packages...
"%VENV_PY%" -m pip install -e .
if errorlevel 1 (
  echo.
  echo Installation failed.
  echo If the error mentions RDKit, try installing Python 3.12 and run this file again.
  pause
  exit /b 1
)

echo Verifying GUI import...
"%VENV_PY%" -c "import si_generator.gui; print('GUI import OK')"
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

:find_python
set "PY_EXE="
call :probe_py -3.12
if not defined PY_EXE call :probe_py -3.11
if not defined PY_EXE call :probe_py -3
if not defined PY_EXE call :probe_python
exit /b 0

:probe_py
del "%PY_PROBE%" >nul 2>nul
py %~1 -c "import sys; print(sys.executable if sys.version_info >= (3, 10) else '')" > "%PY_PROBE%" 2>nul
call :read_probe
exit /b 0

:probe_python
del "%PY_PROBE%" >nul 2>nul
python -c "import sys; print(sys.executable if sys.version_info >= (3, 10) else '')" > "%PY_PROBE%" 2>nul
call :read_probe
exit /b 0

:read_probe
set "FOUND="
for /f "usebackq delims=" %%P in ("%PY_PROBE%") do if not defined FOUND set "FOUND=%%P"
if defined FOUND if exist "!FOUND!" set "PY_EXE=!FOUND!"
exit /b 0
