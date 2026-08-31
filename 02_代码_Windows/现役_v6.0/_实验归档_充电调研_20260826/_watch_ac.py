# -*- coding: utf-8 -*-
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec
keys = [0x742, 0x7A7, 0x7A8, 0x7A9, 0x7AA, 0x7AB, 0x7B9, 0x7C3, 0x7D0, 0x7D1]
prev = {}
t0 = time.time()
while time.time() - t0 < 300:
    cur = {hex(k): ec.ec_read(k) for k in keys}
    if prev and cur != prev:
        diffs = ["%s:%s->%s" % (a, prev.get(a), cur.get(a)) for a in cur if prev.get(a) != cur.get(a)]
        print("t+%ds CHANGE:" % int(time.time()-t0), " ".join(diffs))
    prev = cur
    time.sleep(3)
print("done")
