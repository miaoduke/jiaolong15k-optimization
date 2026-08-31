# -*- coding: utf-8 -*-
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
b = open(r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\_uwacpi.sys", "rb").read()
md = Cs(CS_ARCH_X86, CS_MODE_64)
start = 0x1C80   # a bit before the compare chain
chunk = b[start:0x2000]
for ins in md.disasm(chunk, start):
    s = "0x%04X %-20s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str)
    print(s)
