# -*- coding: utf-8 -*-
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
b = open(r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\_uwacpi.sys", "rb").read()
md = Cs(CS_ARCH_X86, CS_MODE_64)
for name, start, length in (("WRITE-handler", 0x19B8, 0x120), ("READ-handler", 0x1530, 0x120)):
    print("=" * 16, name)
    for ins in md.disasm(b[start:start + length], start):
        s = "0x%04X %-18s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str)
        if ins.mnemonic in ("out", "in") or "dx" in ins.op_str:
            s += "   <<<< PORT"
        print(s)
        if ins.mnemonic == "ret":
            break
