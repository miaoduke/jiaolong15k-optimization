# -*- coding: utf-8 -*-
"""dump export thunks: ReadEC/WriteEC/others for static analysis"""
import struct, sys
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
secs = []
off = opt + opt_sz
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
nfuncs, nnames = struct.unpack_from("<II", b, eo + 16)[0], struct.unpack_from("<II", b, eo + 24)[0]
afunctions_rva = struct.unpack_from("<I", b, eo + 28)[0]
anames_rva = struct.unpack_from("<I", b, eo + 32)[0]
targets = ["ReadEC", "WriteEC", "TempRead1", "ReadIO", "WriteIO"]
for i in range(nnames):
    nrva = struct.unpack_from("<I", b, rva2off(anames_rva) + i * 4)[0]
    o = rva2off(nrva); end = b.index(b"\x00", o)
    name = b[o:end].decode()
    if name in targets:
        frva = struct.unpack_from("<I", b, rva2off(afunctions_rva) + i * 4)[0]
        fo = rva2off(frva)
        code = b[fo:fo + 80]
        print(name, "rva=0x%X fileoff=0x%X" % (frva, fo))
        print("  " + code.hex())