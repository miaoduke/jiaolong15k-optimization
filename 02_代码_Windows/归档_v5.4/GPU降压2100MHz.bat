@echo off
nvidia-smi -lgc 2100,2100
echo.
echo GPU SM clock locked to 2100MHz
echo (equivalent to VF curve undervolt @ 0.900V)
echo.
nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,power.draw,temperature.gpu --format=csv,noheader
echo.
pause