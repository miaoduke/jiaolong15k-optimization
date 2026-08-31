# -*- coding: utf-8 -*-
"""三档对照: 连续监控 EC 700-7FF 区变化"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec

prev = {}
t0 = time.time()
n = 0
while time.time() - t0 < 200:
    cur = {}
    for a in range(0x740, 0x800):
        v = ec.ec_read(a)
        if v is not None:
            cur[a] = v
    if prev and cur != prev:
        diffs = [(a, prev.get(a), cur.get(a)) for a in set(prev) | set(cur) if prev.get(a) != cur.get(a)]
        n += 1
        print("CHANGE #%d t+%ds:" % (n, int(time.time()-t0)), " ".join("0x%03X:%s->%s" % (a, p, c) for a, p, c in sorted(diffs)))
    prev = cur
    time.sleep(4)
print("monitor done,", n, "changes")
