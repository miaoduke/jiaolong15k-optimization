# -*- coding: utf-8 -*-
import sys, time, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec

print("before: 7B9=%s 7D0=%s bat=%s%%" % (
    ec.ec_read(0x7B9), ec.ec_read(0x7D0),
    subprocess.run(["powershell","-NoProfile","-Command","(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"], capture_output=True, text=True).stdout.strip()))
# 官方语义: UP=停止阈值 60, DOWN=起始阈值 40 (成对)
r1 = ec.ec_write(0x7B9, 60)
r2 = ec.ec_write(0x7D0, 40)
time.sleep(1)
print("wrote UP=60 DOWN=40 ->", r1, r2)
for i in range(6):
    time.sleep(10)
    b = subprocess.run(["powershell","-NoProfile","-Command","(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"], capture_output=True, text=True).stdout.strip()
    print("t+%ds: bat=%s%% regs: 7B9=%s 7D0=%s" % ((i+1)*10, b, ec.ec_read(0x7B9), ec.ec_read(0x7D0)))
