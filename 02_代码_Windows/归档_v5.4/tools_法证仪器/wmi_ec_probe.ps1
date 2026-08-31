param([switch]$NoPause)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -NoPause"
    exit
}
$log = "D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\wmi_probe_v4.log"
function W($s) { $s | Out-File $log -Append -Encoding utf8; Write-Host $s }
if (Test-Path $log) { Clear-Content $log }
W "=== EC Probe v4: AC00 buffer packing (DSDT-derived) ==="
$o = Get-WmiObject -Namespace root\wmi -Class AcpiTest_MULong | Where-Object { $_.InstanceName -eq "ACPI\PNP0C14\1_0" }
if (-not $o) { W "FATAL"; if(-not $NoPause){Read-Host "Enter"}; exit }

function Read-EC([UInt16]$addr) {
    $data = [UInt64]0x0000010000000000 -bor [UInt64]$addr
    $r = $o.GetSetULong($data)
    if ($null -ne $r -and $null -ne $r.Return) { return [UInt32]$r.Return }
    return $null
}

W ("ProjectID  @0x740 = 0x{0:X} ({0})   [expect 0x10=16]" -f (Read-EC 0x740))
W ("SystemID   @0x456 = 0x{0:X} ({0})   [Linux:0xC0=192]" -f (Read-EC 0x456))
$t = Read-EC 0x43E
W ("CPU temp   @0x43E = {0} C" -f $t)
$t2 = Read-EC 0x44F
W ("GPU temp   @0x44F = {0} C" -f $t2)
W ("FanRPM lo  @0x464 = 0x{0:X2}" -f (Read-EC 0x464))
W ("FanDuty    @0x461 = {0}" -f (Read-EC 0x461))
W ""
$up = Read-EC 0x7B9
W ("ChargeUP   @0x7B9 = 0x{0:X2} ({0})   [expect 0xD0=208 or 0x50=80]" -f $up)
$dn = Read-EC 0x7D0
W ("ChargeDN   @0x7D0 = 0x{0:X2} ({0})" -f $dn)
W ""
W "=== Probe v4 End ==="
if (-not $NoPause) { Read-Host "Press Enter to close" }
