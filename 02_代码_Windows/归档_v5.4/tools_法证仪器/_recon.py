# -*- coding: utf-8 -*-
import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def ps(cmd, t=60):
    r = subprocess.run(["powershell","-NoProfile","-Command",cmd], capture_output=True, text=True, errors="replace", timeout=t)
    return (r.stdout or "").strip()
print("== 1) root_wmi classes (EC/Thermal/Temp/Fan/vendor) ==")
print(ps("Get-CimClass -Namespace root/wmi | Where-Object {$_.CimClassName -match 'EC|Thermal|Temp|Fan|Uniwill|TongFang|Notebook|Adv'} | Select-Object -ExpandProperty CimClassName"))
print("== 2) MSAcpi_ThermalZoneTemperature ==")
print(ps("$t=Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue; if($t){ $t | ForEach-Object { '{0} = {1:N1} C' -f $_.InstanceName, (($_.CurrentTemperature/10)-273.15) } } else { 'none' }"))
print("== 3) processes ==")
print(ps("Get-Process | Where-Object {$_.Name -match 'ControlCenter|CCenter|UwpHid|GCUBridge'} | Select-Object Name,Id | Format-Table -AutoSize | Out-String"))
print("== 4) services ==")
print(ps("Get-Service | Where-Object {$_.Name -match 'Control|Bridge|Uwp'} | Format-Table Name,Status,DisplayName -AutoSize | Out-String"))
print("== 5) install dirs ==")
print(ps("@('C:\\Program Files (x86)\\ControlCenter','C:\\Program Files\\ControlCenter') | ForEach-Object { if(Test-Path $_){ $_ } }"))
print(ps("Get-ItemProperty 'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue | Where-Object {$_.DisplayName -match 'Control Center|ControlCenter'} | Select-Object DisplayName,InstallLocation | Format-List | Out-String"))
print("== 6) procmon ==")
print(ps("(Get-Command Procmon -ErrorAction SilentlyContinue).Source; @('C:\Tools\\Procmon.exe','C:\Windows\\System32\\Procmon.exe') | ForEach-Object { if(Test-Path $_){ $_ } }"))