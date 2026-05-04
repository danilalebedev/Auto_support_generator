@echo off
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -e .
pause
