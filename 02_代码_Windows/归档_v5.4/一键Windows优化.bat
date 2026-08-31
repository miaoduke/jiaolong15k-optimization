@echo off
:: 一键Windows优化 — EPP/Boost/MaxState 三件套 (2026-08-25 重建)
:: 依据: Windows生态全量整理 #66-68 实测生效配置
:: 检查管理员权限, 无则自提权重启
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo === 应用电源优化配置 ===
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFEPP 0
powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFEPP 80
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE 2
powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX 100
powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX 80
powercfg /setactive SCHEME_CURRENT

echo.
echo [完成] EPP AC=0/DC=80 | Boost AC=2/DC=0 | MaxState AC=100%%/DC=80%%
echo (AC=插电性能优先, DC=电池续航优先)
pause
