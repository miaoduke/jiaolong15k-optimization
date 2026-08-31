# -*- coding: utf-8 -*-
"""EC direct read via ACPIDriverDll.ReadEC(int addr)->int. VERIFIED SIGNATURE ONLY."""
import ctypes, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DLL = r"C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
dll = ctypes.CDLL(DLL)
dll.ReadEC.restype = ctypes.c_int
dll.ReadEC.argtypes = [ctypes.c_int]
def ec(a): return dll.ReadEC(a) & 0xFF
REGS = [
    (0x43E, "CPU temp"), (0x44F, "GPU temp"),
    (0x461, "CPU duty"), (0x462, "CPU duty2"), (0x469, "GPU duty"), (0x46A, "GPU duty2"),
    (0x464, "RPM hi"), (0x465, "RPM lo"), (0x46C, "GPU-RPM hi"), (0x46D, "GPU-RPM lo"),
]
print("== sample1 ==")
s1 = {a: ec(a) for a, _ in REGS}
for a, n in REGS: print("0x%03X %-10s = %3d" % (a, n, s1[a]))
rpm = (s1[0x464] << 8) | s1[0x465]
grpm = (s1[0x46C] << 8) | s1[0x46D]
print("CPU fan RPM ~%d   GPU fan RPM ~%d" % (rpm, grpm))
import time; time.sleep(2)
print("== sample2 (+2s) ==")
for a, n in REGS:
    v = ec(a)
    mark = "  <-- changed" if v != s1[a] else ""
    print("0x%03X %-10s = %3d%s" % (a, n, v, mark))