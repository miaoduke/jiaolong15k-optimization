# -*- coding: utf-8 -*-
"""charge-limit full scientific cycle: read -> set 90 -> verify reg+physical -> restore 100 -> verify"""
import ctypes, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_ec_hw as ec

def battery():
    try:
        r = subprocess.run(["powershell","-NoProfile","-Command",
            "Get-CimInstance Win32_Battery | ForEach-Object { '{0}/{1}' -f $_.EstimatedChargeRemaining, $_.BatteryStatus }"],
            capture_output=True, text=True, timeout=15)
        return r.stdout.strip()
    except Exception:
        return "?"
def ac_online():
    try:
        r = subprocess.run(["powershell","-NoProfile","-Command",
            "(Get-CimInstance Win32_Battery).BatteryStatus"],
            capture_output=True, text=True, timeout=15)
        return int(r.stdout.strip() or 0)
    except Exception:
        return 0

print("== step0 baseline ==")
print("thresholds:", ec.get_charge_thresholds(), " battery%%/status:", battery())
st = ac_online()
print("(BatteryStatus: 2=charging/AC, 1=discharging/on-battery) current:", st)

print("== step1 set stop-threshold = 90 ==")
ok = ec.set_charge_limit(90)
print("set_charge_limit(90) ->", ok)
t = ec.get_charge_thresholds()
print("readback:", t)

print("== step2 physical observation 20s ==")
for i in range(4):
    time.sleep(5)
    print("  t+%ds  battery=%s" % ((i+1)*5, battery()))

print("== step3 restore 100 ==")
ok2 = ec.set_charge_limit(100)
print("set_charge_limit(100) ->", ok2)
print("final thresholds:", ec.get_charge_thresholds())
