# -*- coding: utf-8 -*-
"""LHM net472 full enumeration via powershell.exe"""
import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
DST = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\tools_法证仪器\lhm472"
ps = r"""
Set-Location 'DST'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
try { Add-Type -Path '.\LibreHardwareMonitorLib.dll' } catch { Write-Host ('ADDTYPE ERR: ' + $_.Exception.Message); exit 1 }
$c = New-Object LibreHardwareMonitor.Hardware.Computer
$c.IsCpuEnabled = $true
$c.IsGpuEnabled = $true
$c.IsMemoryEnabled = $true
$c.IsMotherboardEnabled = $true
$c.IsStorageEnabled = $false
$c.IsBatteryEnabled = $true
$c.IsControllerEnabled = $true
$ecProp = $c.GetType().GetProperty('IsEmbeddedEcEnabled')
if ($ecProp) { $ecProp.SetValue($c, $true); Write-Host '[EC] EmbeddedEC flag=ON' } else { Write-Host '[EC] no EmbeddedEC prop' }
$c.Open()
function Walk($hw, $ind) {
    $hw.Update()
    Write-Host ("{0}[HW] {1} | {2}" -f $ind, $hw.Name, $hw.HardwareType)
    foreach ($s in $hw.Sensors) {
        $v = if ($null -ne $s.Value) { [math]::Round([double]$s.Value, 2) } else { '-' }
        Write-Host ("{0}   [{1}] {2} = {3}" -f $ind, $s.SensorType, $s.Name, $v)
    }
    foreach ($sub in $hw.SubHardware) { Walk $sub ($ind + '   ') }
}
foreach ($hw in $c.Hardware) { Walk $hw '' }
$c.Close()
""".replace('DST', DST)
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                   capture_output=True, text=True, errors="replace", timeout=150)
out = r.stdout or ""
print(out)
err = (r.stderr or "").strip()
if err: print("STDERR:", err[:400])
print("lines:", len(out.splitlines()))
