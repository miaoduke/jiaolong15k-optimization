# -*- coding: utf-8 -*-
"""round-2: corrected addr map validation (read-only)"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_ec_hw as ec

print("== 功耗墙组(修正换算) ==")
for a, n in [(0x783,"PL1 W"), (0x784,"PL2 W"), (0x785,"PL4 W"), (0x786,"TCC offset"), (0x787,"FAN_SWITCH_SPEED")]:
    v = ec.ec_read(a)
    print("0x%03X = %-6s %s" % (a, "--" if v is None else v, n))

print("== 风扇曲线表采样(CPU upt@0xF00 / downt@0xF10 / duty@0xF20) ==")
for base_a, tag in [(0xF00,"CPU-UPT"), (0xF10,"CPU-DOWN"), (0xF20,"CPU-DUTY"), (0xF30,"GPU-UPT")]:
    vals = [ec.ec_read(base_a + i) for i in range(6)]
    print("%-9s @0x%03X: %s" % (tag, base_a, vals))

print("== duty 语义复核 ==")
raw = ec.ec_read(0x461)
print("0x461 raw=%s -> duty=%s%% (roj234: /2)" % (raw, (raw/2) if raw is not None else "?"))
rpm_hi = ec.ec_read(0x464); rpm_lo = ec.ec_read(0x465)
if rpm_hi is not None and rpm_lo is not None:
    print("RPM = %d*256+%d = %d" % (rpm_hi, rpm_lo, rpm_hi*256+rpm_lo))
