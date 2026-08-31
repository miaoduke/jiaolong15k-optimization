# -*- coding: utf-8 -*-
"""充电限制失效根因诊断 — 实时状态快照"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec

print("=== 实时状态 (插电充电中, 电量>80%) ===")
for i in range(4):
    a8 = ec.ec_read(0x7A8); a9 = ec.ec_read(0x7A9); b9 = ec.ec_read(0x7B9)
    g42 = ec.ec_read(0x742)
    bat = ec.ec_read(0x7B1)  # 电量? 未知
    print("  t+%ds: 0x7A8(start)=%s | 0x7A9(stop)=%s | 0x7B9(limit)=%s | 0x742(gate)=%s" % (
        i*3, a8, a9, b9, ("0b{:08b}".format(g42) if g42 is not None else None)))
    time.sleep(3)

print("\n=== nvidia-smi / 电源状态 ===")
import subprocess
out = subprocess.run(["powershell", "-NoProfile", "-Command",
    "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining,BatteryStatus | Format-List"],
    capture_output=True, text=True).stdout
print(out)
