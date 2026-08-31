# -*- coding: utf-8 -*-
"""decisive NO-OP experiment for WriteEC(arg1,arg2) order.
Test: WriteEC(0x7A9, 100) where mem[0x7A9]==100.
  If H1 WriteEC(addr,val): pure no-op.
  If H2 WriteEC(val,addr): writes 0xA9 to addr 0x64 -> detect via baseline, then restore."""
import ctypes, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
DLL = "C:/Program Files/OEM/机械革命电竞控制台/UniwillService/MyControlCenter/ACPIDriverDll.dll"
dll = ctypes.CDLL(DLL)
dll.ReadEC.restype = ctypes.c_int
dll.ReadEC.argtypes = [ctypes.c_int]
def rd(a): return dll.ReadEC(a) & 0xFF
base64, base78, base79 = rd(0x64), rd(0x7A8), rd(0x7A9)
print("baselines: 0x64=%d  0x7A8=%d  0x7A9=%d" % (base64, base78, base79))
if base79 != 100:
    print("ABORT: 0x7A9 != 100, environment changed"); sys.exit(1)
try:
    dll.WriteEC.restype = None
    dll.WriteEC.argtypes = [ctypes.c_int, ctypes.c_int]
    dll.WriteEC(0x7A9, 100)     # H1 order: (addr, val) -> no-op if H1 true
    print("WriteEC(0x7A9, 100) returned without crash")
except Exception as e:
    print("call failed:", repr(e)); sys.exit(1)
import time; time.sleep(0.5)
a64, a78, a79 = rd(0x64), rd(0x7A8), rd(0x7A9)
print("after:      0x64=%d  0x7A8=%d  0x7A9=%d" % (a64, a78, a79))
if a64 != base64:
    print("VERDICT: H2 TRUE (value-first). 0x64 was clobbered %d->%d, restoring..." % (base64, a64))
    dll.WriteEC(base64, 0x64)   # H2 semantics: WriteEC(value, addr)
    time.sleep(0.3)
    print("restore check 0x64 =", rd(0x64), "(baseline %d)" % base64)
elif a79 == 100 and a78 == base78:
    print("VERDICT: H1 TRUE - WriteEC(addr, value), no-op confirmed, nothing disturbed")
else:
    print("UNEXPECTED: 0x7A8 %d->%d, 0x7A9 %d->%d" % (base78, a78, base79, a79))
