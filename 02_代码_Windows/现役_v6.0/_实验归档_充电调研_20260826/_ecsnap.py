# -*- coding: utf-8 -*-
"""EC 快照: 用法 python _ecsnap.py <tag>"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec
tag = sys.argv[1] if len(sys.argv) > 1 else "snap"
lines = []
for base in range(0x700, 0x800, 16):
    row = []
    for off in range(16):
        v = ec.ec_read(base + off)
        row.append("%02X" % v if v is not None else "--")
    lines.append("%03X: %s" % (base, " ".join(row)))
out = "\n".join(lines)
print(out)
open(r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0\snap_%s.txt" % tag, "w").write(out)
