@echo off
title LHM Admin Enum (one-shot)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','%~dp0_lhm_admin.ps1'"
echo [OK] UAC requested. Output: _lhm_admin_out.txt
pause
