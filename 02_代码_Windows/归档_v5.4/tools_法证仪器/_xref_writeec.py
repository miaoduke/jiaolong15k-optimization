# -*- coding: utf-8 -*-
import os, re, struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\Program Files\OEM"

def sections(b):
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
    return secs, imgbase

for dirpath, dirs, files in os.walk(ROOT):
    for f in files:
        if not f.lower().endswith((".exe", ".dll")):
            continue
        p = os.path.join(dirpath, f)
        try:
            b = open(p, "rb").read()
            pos_a = b.find(b"WriteEC\x00")
            pos_w = b.find("W\x00r\x00i\x00t\x00e\x00E\x00C\x00")
            if pos_a < 0 and pos_w < 0:
                continue
            secs, imgbase = sections(b)
            def off2va(o):
                for name, va, sz, raw in secs:
                    if raw <= o < raw + sz:
                        return imgbase + va + (o - raw)
                return None
            print("=" * 10, p)
            for label, pos in (("ascii", pos_a), ("utf16", pos_w)):
                if pos < 0:
                    continue
                sva = off2va(pos)
                print(" %s string @file 0x%X va %s" % (label, pos, hex(sva) if sva else "?"))
                if not sva:
                    continue
                for name, va, sz, raw in secs:
                    if name != ".text":
                        continue
                    text = b[raw:raw + sz]
                    md = Cs(CS_ARCH_X86, CS_MODE_64)
                    count = 0
                    for m in re.finditer(re.escape(b"\x48\x8d"), text):
                        o = m.start()
                        try:
                            ins = next(md.disasm(text[o:o+16], va + o))
                        except Exception:
                            continue
                        if ins.mnemonic != "lea" or "rip" not in ins.op_str:
                            continue
                        mm = re.search(r"rip \+ (0x[0-9a-f]+)|rip - (0x[0-9a-f]+)", ins.op_str)
                        if not mm:
                            continue
                        d = int(mm.group(1), 16) if mm.group(1) else -int(mm.group(2), 16)
                        tgt = ins.address + ins.size + d
                        if tgt == sva:
                            print("   XREF at va 0x%X: %s %s" % (ins.address, ins.mnemonic, ins.op_str))
                            count += 1
                            if count >= 4:
                                break
        except Exception:
            pass
