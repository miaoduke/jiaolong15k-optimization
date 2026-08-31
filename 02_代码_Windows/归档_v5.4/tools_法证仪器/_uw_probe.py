# -*- coding: utf-8 -*-
import ctypes, struct, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def ps(c):
    r = subprocess.run(["powershell","-NoProfile","-Command",c], capture_output=True, text=True, errors="replace", timeout=40)
    return (r.stdout or "").strip() or "(empty)"
print("== UWACPIDriver service ==")
print(ps("Get-CimInstance Win32_SystemDriver | Where-Object {$_.Name -match 'UW|Acpi' -and $_.PathName -match 'OEM|'} | Format-Table Name,State,PathName -AutoSize -Wrap | Out-String"))
GENERIC_READ = 0x80000000; GENERIC_WRITE = 0x40000000; OPEN_EXISTING = 3
k32 = ctypes.windll.kernel32
for dev in ("\\\\.\\UWACPIDriver", "\\\\.\\UWACPI", "\\\\.\\ACPIDriver"):
    h = k32.CreateFileW(ctypes.c_wchar_p(dev), GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
    err = k32.GetLastError()
    print("open", dev, "-> handle", h, "gle", err)
    if h != -1 and h != 0xFFFFFFFFFFFFFFFF: k32.CloseHandle(h)
print("== ACPIDriverDll.dll exports (PE parse) ==")
path = r"C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
b = open(path, "rb").read()
pe = struct.unpack_from("<I", b, 0x3C)[0]
opt = pe + 24
magic = struct.unpack_from("<H", b, opt)[0]
ddir = opt + (112 if magic == 0x20B else 96)   # PE32+ has 16 data dirs after standard+windows fields minus one
exp_rva, exp_sz = struct.unpack_from("<II", b, ddir)
sec_n = struct.unpack_from("<H", b, pe + 6)[0]
opt_sz = struct.unpack_from("<H", b, pe + 20)[0]
secs = []
off = opt + opt_sz
for i in range(sec_n):
    va, vsz = struct.unpack_from("<I", b, off + 12)[0], struct.unpack_from("<I", b, off + 8)[0]
    raw, rsz = struct.unpack_from("<II", b, off + 20)[0], struct.unpack_from("<I", b, off + 16)[0]
    secs.append((va, max(vsz, rsz), raw)); off += 40
def rva2off(rva):
    for va, sz, raw in secs:
        if va <= rva < va + sz: return raw + (rva - va)
    return None
eo = rva2off(exp_rva)
nfuncs, nnames = struct.unpack_from("<II", b, eo + 16)[0], struct.unpack_from("<II", b, eo + 24)[0]
anames_rva = struct.unpack_from("<I", b, eo + 32)[0]
names = []
for i in range(nnames):
    nrva = struct.unpack_from("<I", b, rva2off(anames_rva) + i * 4)[0]
    o = rva2off(nrva)
    end = b.index(b"\x00", o)
    names.append(b[o:end].decode())
print("exports:", names)