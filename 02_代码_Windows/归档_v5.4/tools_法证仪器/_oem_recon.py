# -*- coding: utf-8 -*-
import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def ps(c):
    r = subprocess.run(["powershell","-NoProfile","-Command",c], capture_output=True, text=True, errors="replace", timeout=40)
    return (r.stdout or "").strip() or "(empty)"
print("== OEM tree files ==")
print(ps("Get-ChildItem 'C:\\Program Files\\OEM' -Recurse -Include *.exe,*.dll,*.sys,*.ini -ErrorAction SilentlyContinue | Select-Object -First 50 | ForEach-Object { $_.FullName }"))
print("== services whose PathLike points into OEM ==")
print(ps("Get-CimInstance Win32_Service | Where-Object {$_.PathName -match 'OEM|Uniwill'} | Format-Table Name,State,PathName -AutoSize -Wrap | Out-String"))
print("== all kernel drivers mapped from OEM/system32 matching vendor ==")
print(ps("driverquery /v /fo csv 2>$null | ConvertFrom-Csv | Where-Object {$_[7] -match 'OEM|uniwill|tongfang'} | Format-Table $_[0],$_[4],$_[7] -AutoSize -Wrap | Out-String"))