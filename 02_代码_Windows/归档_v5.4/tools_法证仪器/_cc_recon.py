import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def ps(c):
    r = subprocess.run(["powershell","-NoProfile","-Command",c], capture_output=True, text=True, errors="replace", timeout=40)
    return (r.stdout or "").strip() or "(empty)"
print("== GCUBridge path ==")
p = ps("(Get-Process GCUBridge).Path")
print(p)
root = p.rsplit("\\",1)[0] if "\\" in p else ""
if root:
    print("== install root files (exe/dll/sys) ==")
    print(ps("Get-ChildItem -Path '" + root + "' -Recurse -Include *.exe,*.dll,*.sys -ErrorAction SilentlyContinue | Select-Object -First 40 | ForEach-Object { $_.FullName.Replace('" + root + "','') }"))
print("== kernel drivers (EC/vendor keywords) ==")
print(ps("Get-CimInstance Win32_SystemDriver | Where-Object {$_.DisplayName -match 'EC|Embedded|Uniwill|TongFang|ITE|Notebook|Adv|GIGA|Mechrevo|OEM' -or $_.Name -match 'ec|hwio|iodrv'} | Format-Table Name,State,DisplayName -AutoSize | Out-String"))