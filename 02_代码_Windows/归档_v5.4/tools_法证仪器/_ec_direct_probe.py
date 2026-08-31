# -*- coding: utf-8 -*-
"""probe v2: staged, fully guarded, every step logged to file immediately"""
import ctypes, subprocess, sys, traceback
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DLL = r"C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
LOG = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\_ec_direct_log.txt"
def log(m):
    with open(LOG, "a", encoding="utf-8") as fh: fh.write(m + "\n")
    print(m, flush=True)

# stage 1 in-process: can we even load it?
try:
    dll = ctypes.CDLL(DLL)
    log("[main] LoadLibrary OK, handle=%s" % dll._handle)
except Exception as e:
    log("[main] LoadLibrary FAILED: %r" % e); sys.exit(1)

CHILD = """
import ctypes, sys
dll = ctypes.CDLL(r"%DLL%")
name, mode = sys.argv[1], sys.argv[2]
f = getattr(dll, name)
if mode == "load":
    print("loaded-ok", flush=True)
elif mode == "noargs":
    f.restype = ctypes.c_int
    print("ret=", f(), flush=True)
elif mode == "addr":
    f.restype = ctypes.c_int; f.argtypes = [ctypes.c_int]
    print("ret=", f(int(sys.argv[3],16)), flush=True)
elif mode == "ref":
    v = ctypes.c_ubyte(0)
    f.restype = ctypes.c_int; f.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
    rc = f(ctypes.byref(v), int(sys.argv[3],16))
    print("rc=", rc, "val=", v.value, flush=True)
""".replace("%DLL%", DLL)

def probe(name, mode, extra):
    tag = "%s %s %s" % (name, mode, extra)
    try:
        r = subprocess.run([sys.executable, "-c", CHILD, name, mode] + extra,
                           capture_output=True, text=True, errors="replace", timeout=10)
        out = (r.stdout or "").strip().replace("\n", " | ")
        errl = (r.stderr or "").strip().splitlines()
        err = errl[-1][:100] if errl else ""
        if r.returncode == 0 and out: log("  %-34s => %s" % (tag, out))
        else: log("  %-34s => rc=%s out=%q err=%s" % (tag, r.returncode, out[:40], err))
    except subprocess.TimeoutExpired:
        log("  %-34s => TIMEOUT(10s) - device call blocked" % tag)
    except Exception as e:
        log("  %-34s => EXC %r" % (tag, e))

open(LOG, "w").close()
log("== stage2: load-only ==")
probe("TempRead1", "load", [])
log("== stage3: temp readers (guarded) ==")
for n in ("TempRead1","TempRead2","TempRead3"): probe(n, "noargs", [])
log("== stage4: ReadEC guesses @0x43E ==")
probe("ReadEC", "addr", ["0x43E"])
probe("ReadEC", "ref", ["0x43E"])