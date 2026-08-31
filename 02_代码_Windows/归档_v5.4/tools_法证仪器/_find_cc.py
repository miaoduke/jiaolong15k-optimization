# -*- coding: utf-8 -*-
import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def ps(c):
    r = subprocess.run(["powershell","-NoProfile","-Command",c], capture_output=True, text=True, errors="replace", timeout=40)
    return (r.stdout or "").strip() or "(empty)"
print("== windowed processes ==")
print(ps("Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object Name,Id,MainWindowTitle | Format-Table -AutoSize | Out-String"))
print("== process paths (non-system) ==")
print(ps("Get-Process | Where-Object {$_.Path -and $_.Path -notmatch '^C:\\\\Windows'} | Select-Object Name,Path -Unique | Format-Table -AutoSize -Wrap | Out-String"))