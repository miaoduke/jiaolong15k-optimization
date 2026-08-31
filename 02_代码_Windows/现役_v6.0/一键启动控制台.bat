@echo off
title MR Control Center v6.0 Launcher
setlocal enabledelayedexpansion

set "DIR=%~dp0"
set "SCRIPT=%DIR%mr_gui_v6.py"

if not exist "%SCRIPT%" (
    echo [Error] mr_gui_v6.py not found
    pause & exit /b 1
)

set "PYW="
set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
for /f "tokens=*" %%i in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%i"
for /f "tokens=*" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY (
    echo [Error] Python not found
    pause & exit /b 1
)

sc query GCUBridge | findstr RUNNING >nul || (
    echo [Service] Starting GCUBridge...
    net start GCUBridge >nul 2>&1
)

echo [OK] Starting MR Control Center v6.0 ...
start "" "%PY%" "%SCRIPT%"
timeout /t 2 >nul
exit /b 0
