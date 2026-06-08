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
    echo winget failed. Trying to reset winget sources and install again...
    winget source reset --force
    winget install --id Python.Python.3.12 -e --source winget
  )
  call :find_python
  if not defined PY_EXE (
    echo.
    echo Setup still cannot find a supported Python.
    echo Please install Python 3.12 from:
    echo https://www.python.org/downloads/windows/
    echo.
    echo If Python is already installed, add it to PATH or install the Python launcher.
    echo Then close this window and run "Setup Auto SI Generator.bat" again.
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
if not defined PY_EXE call :probe_common_paths 312
if not defined PY_EXE call :probe_registry 3.12
if not defined PY_EXE call :probe_py -3.13
if not defined PY_EXE call :probe_common_paths 313
if not defined PY_EXE call :probe_registry 3.13
if not defined PY_EXE call :probe_py -3.11
if not defined PY_EXE call :probe_common_paths 311
if not defined PY_EXE call :probe_registry 3.11
if not defined PY_EXE call :probe_py -3.10
if not defined PY_EXE call :probe_common_paths 310
if not defined PY_EXE call :probe_registry 3.10
if not defined PY_EXE call :probe_py -3
if not defined PY_EXE call :probe_python
exit /b 0

:probe_py
del "%PY_PROBE%" >nul 2>nul
py %~1 -c "import sys; v=sys.version_info; print(sys.executable if (v >= (3, 10) and v < (3, 14)) else '')" > "%PY_PROBE%" 2>nul
call :read_probe
exit /b 0

:probe_python
del "%PY_PROBE%" >nul 2>nul
python -c "import sys; v=sys.version_info; print(sys.executable if (v >= (3, 10) and v < (3, 14)) else '')" > "%PY_PROBE%" 2>nul
call :read_probe
exit /b 0

:probe_common_paths
set "PY_SUFFIX=%~1"
if defined LOCALAPPDATA call :probe_candidate "%LOCALAPPDATA%\Programs\Python\Python%PY_SUFFIX%\python.exe"
if defined ProgramFiles call :probe_candidate "%ProgramFiles%\Python%PY_SUFFIX%\python.exe"
if defined ProgramFiles(x86) call :probe_candidate "%ProgramFiles(x86)%\Python%PY_SUFFIX%-32\python.exe"
call :probe_candidate "C:\Python%PY_SUFFIX%\python.exe"
exit /b 0

:probe_registry
set "PY_VERSION=%~1"
call :probe_registry_key "HKCU\Software\Python\PythonCore\%PY_VERSION%\InstallPath"
if not defined PY_EXE call :probe_registry_key "HKLM\Software\Python\PythonCore\%PY_VERSION%\InstallPath"
if not defined PY_EXE call :probe_registry_key "HKLM\Software\WOW6432Node\Python\PythonCore\%PY_VERSION%\InstallPath"
exit /b 0

:probe_registry_key
for /f "tokens=2,*" %%A in ('reg query "%~1" /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do (
  if not defined PY_EXE call :probe_candidate "%%B"
)
exit /b 0

:probe_candidate
if defined PY_EXE exit /b 0
set "CANDIDATE=%~1"
if not exist "%CANDIDATE%" exit /b 0
del "%PY_PROBE%" >nul 2>nul
"%CANDIDATE%" -c "import sys; v=sys.version_info; print(sys.executable if (v >= (3, 10) and v < (3, 14)) else '')" > "%PY_PROBE%" 2>nul
call :read_probe
exit /b 0

:read_probe
set "FOUND="
for /f "usebackq delims=" %%P in ("%PY_PROBE%") do if not defined FOUND set "FOUND=%%P"
if defined FOUND if exist "!FOUND!" set "PY_EXE=!FOUND!"
exit /b 0
