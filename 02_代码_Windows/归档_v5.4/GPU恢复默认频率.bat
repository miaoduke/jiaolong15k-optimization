@echo off
nvidia-smi -rgc
echo.
echo GPU clock reset to default
nvidia-smi --query-gpu=clocks.sm,clocks.max.sm --format=csv,noheader
echo.
pause