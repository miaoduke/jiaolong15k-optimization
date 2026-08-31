# -*- coding: utf-8 -*-
"""find IOCTL 0x9C40A488/8C handlers in UWACPIDriver.sys and disassemble around them"""
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
src = r"C:\Windows\System32\drivers\UWACPIDriver.sys"
dst = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\_uwacpi.sys"
b = open(src, "rb").read()
open(dst, "wb").write(b)
print("sys size:", len(b))
pe = struct.unpack_from("<I", b, 0x3C)[0]
opt = pe + 24
magic = struct.unpack_from("<H", b, opt)[0]
sec_n = struct.unpack_from("<H", b, pe + 6)[0]
opt_sz = struct.unpack_from("<H", b, pe + 20)[0]
secs = []; off = opt + opt_sz
for i in range(sec_n):
    name = b[off:off+8].rstrip(b"\x00").decode(errors="replace")
    va = struct.unpack_from("<I", b, off + 12)[0]
    vsz = struct.unpack_from("<I", b, off + 8)[0]
    raw = struct.unpack_from("<I", b, off + 20)[0]
    rsz = struct.unpack_from("<I", b, off + 16)[0]
    secs.append((name, va, max(vsz, rsz), raw))
    print("  sec %-8s va 0x%X size 0x%X raw 0x%X" % (name, va, max(vsz, rsz), raw))
    off += 40
# search for ioctl constants in whole file
for target, tag in ((0x9C40A488, "READ"), (0x9C40A48C, "WRITE")):
    pat = struct.pack("<I", target)
    hits = []
    start = 0
    while True:
        i = b.find(pat, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    print(tag, hex(target), "hits at file offsets:", [hex(h) for h in hits])
