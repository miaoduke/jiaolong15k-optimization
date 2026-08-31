# -*- coding: utf-8 -*-
"""scan OEM binaries for import of WriteEC"""
import struct, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\Program Files\OEM"
def imports(path):
    try:
        b = open(path, "rb").read()
        if b[:2] != b"MZ": return None
        pe = struct.unpack_from("<I", b, 0x3C)[0]
        if b[pe:pe+4] != b"PE\x00\x00": return None
        opt = pe + 24; magic = struct.unpack_from("<H", b, opt)[0]
        ddir = opt + (112 if magic == 0x20B else 96) + 8  # import dir = data dir index 1
        imp_rva, imp_sz = struct.unpack_from("<II", b, ddir)
        if not imp_rva: return None
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
            return None
        io = rva2off(imp_rva)
        names = []
        while io:
            oft_rva, ts, fc, name_rva, ft_rva = struct.unpack_from("<IIIII", b, io)
            if not name_rva: break
            no = rva2off(name_rva); dllname = b[no:b.index(b"\x00", no)].decode(errors="replace")
            thunk = oft_rva or ft_rva
            to = rva2off(thunk)
            funcs = []
            while to:
                val = struct.unpack_from("<Q", b, to)[0] if magic == 0x20B else struct.unpack_from("<I", b, to)[0]
                if not val: break
                if magic == 0x20B and val >> 63: val &= 0x7FFFFFFF
                elif magic != 0x20B and val >> 31: val &= 0x7FFFFFFF
                else:
                    fo = rva2off(val)
                    if fo:
                        fo += 2
                        end = b.index(b"\x00", fo)
                        funcs.append(b[fo:end].decode(errors="replace"))
                to += 8 if magic == 0x20B else 4
            names.append((dllname, funcs))
            io += 20
        return names
    except Exception as e:
        return None
hits = []
for dirpath, dirs, files in os.walk(ROOT):
    for f in files:
        if f.lower().endswith((".exe", ".dll")):
        
            p = os.path.join(dirpath, f)
            imps = imports(p)
            if imps:
                for dn, fs in imps:
                    if "WriteEC" in fs:
                        hits.append((p, dn))
print("=== binaries importing WriteEC ===")
for p, dn in hits: print(p, "->", dn)
if not hits: print("(none found)")