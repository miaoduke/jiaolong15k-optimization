@echo off
title MR Console v5.4 Launcher (admin-free)
setlocal enabledelayedexpansion

set "DIR=%~dp0"
set "SCRIPT=%DIR%mr_console.py"

if not exist "%SCRIPT%" (
    echo [Error] mr_console.py not found
    pause & exit /b 1
)

rem v5.4: EC read/write via UWACPIDriver needs NO admin. No UAC prompt.

set "PYW="
set "PY="
if exist "%DIR%runtime\pythonw.exe" (
    set "PYW=%DIR%runtime\pythonw.exe"
    set "PY=%DIR%runtime\python.exe"
    goto :found
)
for /f "tokens=*" %%i in (''where pythonw 2^>nul'') do if not defined PYW set "PYW=%%i"
for /f "tokens=*" %%i in (''where python 2^>nul'') do if not defined PY set "PY=%%i"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

:found
if not defined PY (
    echo [Error] Python not found
    pause & exit /b 1
)

sc query GCUBridge | findstr RUNNING >nul || (
    echo [Service] Starting GCUBridge...
    net start GCUBridge >nul 2>&1
)

if defined PYW ( start "" "%PYW%" "%SCRIPT%" gui ) else ( start "" "%PY%" "%SCRIPT%" gui )
timeout /t 2 >nul
echo [OK] MR Console v5.4 started (admin-free)
timeout /t 2 >nul
exit /b 0