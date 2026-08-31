# -*- coding: utf-8 -*-
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec
stop = int(sys.argv[1]) if len(sys.argv) > 1 else 80
r1 = ec.ec_write(0x7A9, stop)
r3 = ec.ec_write(0x7B9, stop & 0x7F)
r2 = ec.ec_write(0x7A8, max(stop - 20, 0))
time.sleep(1)
print("wrote", stop, "->", r1, r3, r2, "| readback:", ec.ec_read(0x7A9), ec.ec_read(0x7B9))
