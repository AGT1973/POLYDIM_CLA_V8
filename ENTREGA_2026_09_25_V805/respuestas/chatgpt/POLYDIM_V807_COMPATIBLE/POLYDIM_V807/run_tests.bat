@echo off
cd /d "%~dp0"
python tools\verify.py
if errorlevel 1 exit /b 1
