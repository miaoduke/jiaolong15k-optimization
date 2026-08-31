param([switch]$NoPause)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -NoPause"
    exit
}
$log = "D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\\charge_test.log"
function W($s) { $s | Out-File $log -Append -Encoding utf8; Write-Host $s }
if (Test-Path $log) { Clear-Content $log }
$o = Get-WmiObject -Namespace root\wmi -Class AcpiTest_MULong | Where-Object { $_.InstanceName -eq "ACPI\PNP0C14\1_0" }

function Read-EC([UInt16]$addr) {
    $data = [UInt64]0x0000010000000000 -bor [UInt64]$addr
    $r = $o.GetSetULong($data)
    if ($null -ne $r -and $null -ne $r.Return) { return [UInt32]($r.Return -band 0xFF) }
    return $null
}
function Write-EC([UInt16]$addr, [byte]$val) {
    # SAC1=0(默认) → WKBC(SA00=lo, SA01=hi, SA02=val, SA03=0)
    $data = [UInt64]$val * 0x10000 + [UInt64]$addr
    $r = $o.GetSetULong($data)
    return $r
}

W "=== Charge Threshold Write Test ==="
W "时间: $(Get-Date -Format HH:mm:ss)"

# Step1: 读当前值
$before = Read-EC 0x7B9
W ("[1] 写入前 0x7B9 = 0x{0:X2} ({0})" -f $before)

# Step2: 写入 0xD0 (80% + 0x80标志)
Write-Host "  写入 0xD0 (80%阈值)..."
Write-EC 0x7B9 0xD0
Start-Sleep -Milliseconds 500

# Step3: 读回验证
$after = Read-EC 0x7B9
W ("[2] 写入后 0x7B9 = 0x{0:X2} ({0})" -f $after)

# 判定
if ([byte]$after -eq 0xD0) {
    W "[✅✅✅] 充电阈值写入成功! Windows 也能控制充电阈值!"
    W "  → 后续可在自制台加入阈值滑条"
} elseif ([byte]$after -eq 0x00) {
    W "[⛔] 写入无效 — EC 不响应此地址的写入(硬件不支持)"
} else {
    W "[?] 写入后值变化但不是0xD0: 0x{0:X2}" -f $after
}

# Step4: 同时检查 Windows 是否识别到变化
Start-Sleep -Seconds 2
$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
if ($bat) { W ("[Windows] Battery: {0}% Status={1}" -f $bat.EstimatedChargeRemaining, $bat.BatteryStatus) }

W "=== Test End ==="
if (-not $NoPause) { Read-Host "Press Enter to close" }
