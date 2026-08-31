import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec
print("RPM stability x10:")
ok = 0
for i in range(10):
    r = ec.get_fan_rpm()
    if r is not None: ok += 1
    print("  %d: %s" % (i, r))
    time.sleep(0.5)
print("success rate:", ok, "/10")
