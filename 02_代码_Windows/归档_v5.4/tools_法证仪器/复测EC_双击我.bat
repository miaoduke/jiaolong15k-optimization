@echo off
rem ASCII-ONLY batch (codepage-proof). Payload: _ecadmin_full.ps1
cd /d "%~dp0"
set "LOG=%~dp0_ec_bat_log.txt"
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting admin - please click YES on UAC...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','\"%~f0\"' -Verb RunAs -WorkingDirectory '%~dp0'"
  echo If no admin window appeared, check _ec_bat_log.txt anyway.
  pause
  exit /b
)
echo [%date% %time%] elevated run start > "%LOG%"
if not exist "%~dp0_ecadmin_full.ps1" (
  echo ERROR: _ecadmin_full.ps1 not found >> "%LOG%"
  echo ERROR: missing script
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_ecadmin_full.ps1" >> "%LOG%" 2>&1
echo [%date% %time%] run finished >> "%LOG%"
type "%~dp0_ecadmin.json" >> "%LOG%" 2>nul
echo.
echo ===== DONE. Full detail: _ec_bat_log.txt =====
pause
