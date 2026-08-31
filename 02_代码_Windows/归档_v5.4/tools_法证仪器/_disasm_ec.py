# -*- coding: utf-8 -*-
"""full disasm of ReadEC & WriteEC via capstone - trace global var usage"""
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = r"C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
b = open(path, "rb").read()
pe = struct.unpack_from("<I", b, 0x3C)[0]
opt = pe + 24
magic = struct.unpack_from("<H", b, opt)[0]
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
eo = rva2off(exp_rva)
nnames = struct.unpack_from("<I", b, eo + 24)[0]
afunctions_rva = struct.unpack_from("<I", b, eo + 28)[0]
anames_rva = struct.unpack_from("<I", b, eo + 32)[0]
targets = {}
for i in range(nnames):
    nrva = struct.unpack_from("<I", b, rva2off(anames_rva) + i * 4)[0]
    o = rva2off(nrva); end = b.index(b"\x00", o)
    name = b[o:end].decode()
    if name in ("ReadEC", "WriteEC"):
        targets[name] = struct.unpack_from("<I", b, rva2off(afunctions_rva) + i * 4)[0]
md = Cs(CS_ARCH_X86, CS_MODE_64)
for name in ("ReadEC", "WriteEC"):
    rva = targets[name]; fo = rva2off(rva)
    code = b[fo:fo + 220]
    print("=" * 20, name, "rva=0x%X" % rva)
    for ins in md.disasm(code, rva):
        s = "0x%04X  %-24s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str)
        print(s)
        if ins.mnemonic == "ret": break