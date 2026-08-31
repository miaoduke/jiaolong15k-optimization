param([switch]$NoPause)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -NoPause"
    exit
}
$log = "D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\\ec_scan_result.log"
function W($s) { $s | Out-File $log -Append -Encoding utf8; Write-Host $s }
if (Test-Path $log) { Clear-Content $log }
$o = Get-WmiObject -Namespace root\wmi -Class AcpiTest_MULong | Where-Object { $_.InstanceName -eq "ACPI\PNP0C14\1_0" }
function Read-EC([UInt16]$addr) {
    $data = [UInt64]0x0000010000000000 -bor [UInt64]$addr
    $r = $o.GetSetULong($data)
    if ($null -ne $r -and $null -ne $r.Return) { return [UInt32]($r.Return -band 0xFF) }
    return $null
}
W "=== EC Scan 0x730-0x7FF + 0x430-0x470 ==="
W "时间: $(Get-Date -Format "HH:mm:ss")"
W ""
W "--- 验证区 0x430-0x470 ---"
for ($a = 0x430; $a -le 0x470; $a++) {
    $v = Read-EC $a
    if ($null -ne $v -and $v -ne 0) { W ("  0x{0:X3} = {1} (0x{1:X2})" -f $a, $v) }
}
W ""
W "--- 目标区 0x730-0x7FF ---"
for ($a = 0x730; $a -le 0x7FF; $a++) {
    $v = Read-EC $a
    if ($null -ne $v -and $v -ne 0) { W ("  0x{0:X3} = {1} (0x{1:X2})" -f $a, $v) }
}
W ""
W "=== 充电阈值候选(非零值) ==="
foreach ($a in @(0x7B9, 0x7BA, 0x7BB, 0x7BC, 0x7BD, 0x7BE, 0x7BF, 0x7C0, 0x7D0, 0x7D1)) {
    $v = Read-EC $a
    W ("  0x{0:X3} = {1}" -f $a, $v)
}
W "=== End ==="
if (-not $NoPause) { Read-Host "Press Enter" }
