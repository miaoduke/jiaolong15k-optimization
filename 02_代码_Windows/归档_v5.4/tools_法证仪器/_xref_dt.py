# -*- coding: utf-8 -*-
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
p = r"C:\Program Files\OEM\机械革命电竞控制台\DefaultTool\DefaultTool.exe"
b = open(p, "rb").read()
pe = struct.unpack_from("<I", b, 0x3C)[0]
opt = pe + 24
magic = struct.unpack_from("<H", b, opt)[0]
imgbase = struct.unpack_from("<Q", b, opt + 24)[0] if magic == 0x20B else struct.unpack_from("<I", b, opt + 28)[0]
sec_n = struct.unpack_from("<H", b, pe + 6)[0]
opt_sz = struct.unpack_from("<H", b, pe + 20)[0]
secs = []; off = opt + opt_sz
for i in range(sec_n):
    name = b[off:off+8].rstrip(b"\x00").decode(errors="replace")
    vsz = struct.unpack_from("<I", b, off + 8)[0]
    va = struct.unpack_from("<I", b, off + 12)[0]
    rsz = struct.unpack_from("<I", b, off + 16)[0]
    raw = struct.unpack_from("<I", b, off + 20)[0]
    secs.append((name, va, max(vsz, rsz), raw))
    off += 40
def off2va(o):
    for name, va, sz, raw in secs:
        if raw <= o < raw + sz:
            return imgbase + va + (o - raw)
    return None
def va2off(v):
    for name, va, sz, raw in secs:
        if va <= v < va + sz:
            return raw + (v - va)
    return None
pos_w = b.find(b"W\x00r\x00i\x00t\x00e\x00E\x00C\x00")
sva = off2va(pos_w)
print("string WriteEC utf16 @file 0x%X -> va 0x%X" % (pos_w, sva))
md = Cs(CS_ARCH_X86, CS_MODE_64)
tname, tva, tsz, traw = [s for s in secs if s[0] == ".text"][0]
text = b[traw:traw + tsz]
xrefs = []
i = 0
while True:
    i = text.find(b"\x48\x8d", i)
    if i < 0:
        break
    try:
        ins = next(md.disasm(text[i:i+16], tva + i))
    except Exception:
        i += 2; continue
    if ins.mnemonic == "lea" and "rip" in ins.op_str:
        import re as _re
        mm = _re.search(r"rip \+ (0x[0-9a-f]+)|rip - (0x[0-9a-f]+)", ins.op_str)
        if mm:
            d = int(mm.group(1), 16) if mm.group(1) else -int(mm.group(2), 16)
            tgt = ins.address + ins.size + d
            if tgt == sva:
                xrefs.append(i)
                print("XREF lea at va 0x%X (file 0x%X): %s %s" % (ins.address, traw + i, ins.mnemonic, ins.op_str))
    i += 2
print("total xrefs:", len(xrefs))
for xi in xrefs[:3]:
    start = max(0, xi - 96)
    chunk = text[start:xi + 80]
    print("=" * 12, "context around file 0x%X" % (traw + xi))
    for ins in md.disasm(chunk, tva + start):
        mark = " <<<" if ins.address == tva + xi else ""
        print("  0x%X %-20s %s %s%s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, mark))
