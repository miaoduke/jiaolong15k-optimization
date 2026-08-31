# -*- coding: utf-8 -*-
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_ec_hw as ec
print("0x7B9 =", ec.ec_read(0x7B9), " (当前停止阈值应为100)")
print("0x7B8 =", ec.ec_read(0x7B8))
print("0x7BA =", ec.ec_read(0x7BA))
t = ec.get_charge_thresholds()
print("0x7A8/0x7A9 =", t)
# 连续采样看稳定性
vals = [ec.ec_read(0x7B9) for _ in range(3)]
print("0x7B9 x3:", vals)
