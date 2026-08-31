import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def ps(c):
    r = subprocess.run(["powershell","-NoProfile","-Command",c], capture_output=True, text=True, errors="replace", timeout=40)
    return (r.stdout or "").strip() or "(empty)"
print("BatteryTemperature:", ps("$i=Get-CimInstance -Namespace root/wmi -ClassName BatteryTemperature -ErrorAction SilentlyContinue; if($i){$i | ForEach-Object{ '{} = {}'.Format($_.InstanceName,$_.Temperature)} } else {'none'})"))
print("BatteryCycleCount:", ps("$i=Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount -ErrorAction SilentlyContinue; if($i){$i | ForEach-Object{ '{} = {}'.Format($_.InstanceName,$_.CycleCount)} } else {'none'})"))