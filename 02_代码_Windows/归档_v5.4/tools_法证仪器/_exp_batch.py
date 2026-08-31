# -*- coding: utf-8 -*-
"""S0-B batch: PL wall small-step / keyboard backlight visible / trigger NO-OP / touchpad NO-OP"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_ec_hw as ec

print("=== EXP-A: PL1 wall (0x783) small step ===")
o = ec.ec_read(0x783)
print("orig PL1 =", o)
try:
    ec.ec_write(0x783, o + 1)
    time.sleep(2.0)
    v1 = ec.ec_read(0x783); time.sleep(3.0); v2 = ec.ec_read(0x783)
    print("write %d -> t+2s:%s t+5s:%s %s" % (o+1, v1, v2,
          "(HELD - direct control possible)" if v2 == o+1 else "(overwritten by firmware policy)"))
finally:
    ec.ec_write(0x783, o); time.sleep(1.0)
    print("restored ->", ec.ec_read(0x783))

print("\n=== EXP-B: keyboard backlight (0x78C) visible test ===")
ob = ec.ec_read(0x78C)
print("orig =", ob, "level:", (ob or 0)>>5)
try:
    for lv in (2, 0):
        nv = ((ob | 16) & 31) | ((lv & 7) << 5)
        ec.ec_write(0x78C, nv)
        time.sleep(2.5)
        print("set level %d -> reg=%d readback level=%d" % (lv, nv, (ec.ec_read(0x78C) or 0)>>5))
finally:
    ec.ec_write(0x78C, ob); time.sleep(0.5)
    print("restored ->", ec.ec_read(0x78C))

print("\n=== EXP-C: trigger (0x767) NO-OP only ===")
ot = ec.ec_read(0x767)
print("orig =", ot)
if ot is not None:
    ec.ec_write(0x767, ot); time.sleep(0.5)
    print("NO-OP readback =", ec.ec_read(0x767))
else:
    print("(dead on this machine)")

print("\n=== EXP-D: touchpad (0x7A6) NO-OP only ===")
op = ec.ec_read(0x7A6)
print("orig =", op, "(bit6=%d bit3=%d)" % (((op or 0)>>6)&1, ((op or 0)>>3)&1))
if op is not None:
    ec.ec_write(0x7A6, op); time.sleep(0.5)
    print("NO-OP readback =", ec.ec_read(0x7A6))
print("\nALL EXPERIMENTS DONE")
