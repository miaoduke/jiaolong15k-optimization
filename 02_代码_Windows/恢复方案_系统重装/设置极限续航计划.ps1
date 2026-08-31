# 极限续航电源计划配置脚本
# 需要管理员权限运行

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "需要管理员权限！正在请求提升..."
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "=== 已获得管理员权限 ==="

# 选择要修改的计划
$ecoGuid = "3a99624d-672a-43d3-93d6-9f78114bb9ae"  # MR-超级省电

Write-Host "修改MR-超级省电计划为极限续航..."

# 1. CPU功耗墙 (PL1=25W, PL2=25W)
Write-Host "设置CPU功耗墙..."
powercfg /setacvalueindex $ecoGuid 5d76a2ca-1286-4843-9a20-d15c46252980 75b7aeab-199c-4a69-a8c7-9913a1fd2a54 25
powercfg /setacvalueindex $ecoGuid 5d76a2ca-1286-4843-9a20-d15c46252980 bc5038f7-23e0-4960-96da-33abaf5935ec 25

# 2. 限制CPU最大性能 (70%)
Write-Host "限制CPU性能..."
powercfg /setacvalueindex $ecoGuid 5d76a2ca-1286-4843-9a20-d15c46252980 75b7aeab-199c-4a69-a8c7-9913a1fd2a54 70

# 3. 禁用CPU Turbo Boost
Write-Host "禁用Turbo Boost..."
powercfg /setacvalueindex $ecoGuid 5d76a2ca-1286-4843-9a20-d15c46252980 be337238-0d82-4146-a960-4f3749d470c7 0

# 4. 设置最小CPU状态 (5%)
powercfg /setacvalueindex $ecoGuid 5d76a2ca-1286-4843-9a20-d15c46252980 893dee8e-2bef-41e0-89c6-b55d0929964c 5

# 5. 启用PCIe链路状态电源管理
Write-Host "启用PCIe节能..."
powercfg /setacvalueindex $ecoGuid 501a4d13-42af-4429-9fd1-a8218c268e20 ee12f906-d277-404b-b6da-e5fa1a576df5 2

# 6. 设置硬盘关闭时间 (3分钟)
powercfg /setacvalueindex $ecoGuid 6738db2b-4d43-4d6b-9a04-a63f0a2f7a9c 6738db2b-4d43-4d6b-9a04-a63f0a2f7a9c 180

# 7. 关闭USB选择性挂起
powercfg /setacvalueindex $ecoGuid 2a737441-1930-4402-8d77-b2bebba308a3 48 0

# 8. 设置显示器关闭时间 (5分钟)
powercfg /setacvalueindex $ecoGuid 75b0ae3f-bce0-45a7-8c89-c9611c25e100 3c0bc82f-4266-4b6b-9507-2b90d3eff560 300

Write-Host "`n=== 验证设置 ==="
powercfg /query $ecoGuid 5d76a2ca-1286-4843-9a20-d15c46252980 2>&1 | Select-String -Pattern "最大处理器状态|最小处理器状态" -Context 0,2

Write-Host "`n=== 完成 ==="
Write-Host "MR-超级省电计划已优化为极限续航模式"
Write-Host "CPU功耗墙: 25W, 最大性能: 70%, Turbo Boost: 已禁用"