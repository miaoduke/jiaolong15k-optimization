# -*- coding: utf-8 -*-
"""EC full-domain READ-ONLY sweep via verified ReadEC(int)->int. Two samples, delta-marked."""
import ctypes, json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DLL = "C:/Program Files/OEM/机械革命电竞控制台/UniwillService/MyControlCenter/ACPIDriverDll.dll"
dll = ctypes.CDLL(DLL)
dll.ReadEC.restype = ctypes.c_int
dll.ReadEC.argtypes = [ctypes.c_int]
def ec(a): return dll.ReadEC(a) & 0xFF
s1 = {}
for a in range(0x000, 0x800): s1[a] = ec(a)
time.sleep(1.5)
changed, nonzero = {}, {}
for a in range(0x000, 0x800):
    v2 = ec(a)
    if v2 != s1[a]: changed[a] = (s1[a], v2)
    if v2 != 0: nonzero[a] = v2
out = {
  "nonzero": {"0x%03X" % a: v for a, v in sorted(nonzero.items())},
  "changed": {"0x%03X" % a: [p, c] for a, (p, c) in sorted(changed.items())},
}
with open("_ec_sweep.json", "w", encoding="utf-8") as f: json.dump(out, f, indent=1)
print("non-zero count:", len(nonzero), " changed count:", len(changed))
print("--- live (changed) registers ---")
NAMES = {0x43E:"CPUtemp?",0x461:"CPUduty",0x464:"RPMhi",0x465:"RPMlo",0x469:"GPUduty",0x46C:"GRPMhi",0x46D:"GRPMlo"}
for a, (p, c) in sorted(changed.items()):
    print("0x%03X %-10s %3d -> %3d" % (a, NAMES.get(a, ""), p, c))
print("--- stable non-zero in temp/charge regions ---")
for a, v in sorted(nonzero.items()):
    if (0x440 <= a <= 0x460) or (0x780 <= a <= 0x7FF) or (0x4B0 <= a <= 0x4F0):
        print("0x%03X = %3d" % (a, v))