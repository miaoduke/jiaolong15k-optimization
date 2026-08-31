# -*- coding: utf-8 -*-
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = r"C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
b = open(path, "rb").read()
pe = struct.unpack_from("<I", b, 0x3C)[0]
opt = pe + 24; magic = struct.unpack_from("<H", b, opt)[0]
ddir = opt + (112 if magic == 0x20B else 96)
exp_rva = struct.unpack_from("<I", b, ddir)[0]
sec_n = struct.unpack_from("<H", b, pe + 6)[0]
opt_sz = struct.unpack_from("<H", b, pe + 20)[0]
secs = []; off = opt + opt_sz
for i in range(sec_n):
    va = struct.unpack_from("<I", b, off + 12)[0]
    vsz = struct.unpack_from("<I", b, off + 8)[0]
    raw = struct.unpack_from("<I", b, off + 20)[0]
    rsz = struct.unpack_from("<I", b, off + 16)[0]
    secs.append((va, max(vsz, rsz), raw)); off += 40
def rva2off(rva):
    for va, sz, raw in secs:
        if va <= rva < va + sz: return raw + (rva - va)
md = Cs(CS_ARCH_X86, CS_MODE_64)
# ReadEC success path @0x348F, WriteEC success path @0x3573
for name, start in (("ReadEC-success", 0x348F), ("WriteEC-success", 0x3573)):
    fo = rva2off(start)
    code = b[fo:fo + 260]
    print("=" * 20, name)
    n = 0
    for ins in md.disasm(code, start):
        print("0x%04X  %-22s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
        n += 1
        if n > 55: print("...(truncated)"); break