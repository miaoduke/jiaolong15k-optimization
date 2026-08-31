# -*- coding: utf-8 -*-
import ctypes, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DLL = "C:/Program Files/OEM/机械革命电竞控制台/UniwillService/MyControlCenter/ACPIDriverDll.dll"
dll = ctypes.CDLL(DLL)
dll.ReadEC.restype = ctypes.c_int
dll.ReadEC.argtypes = [ctypes.c_int]
def ec(a): return dll.ReadEC(a) & 0xFF
print("== GPU温度对照: EC 0x44C vs nvidia-smi ==")
for i in range(3):
    e = ec(0x44C)
    nv = subprocess.run(["C:/Windows/System32/nvidia-smi.exe","--query-gpu=temperature.gpu","--format=csv,noheader"], capture_output=True, text=True, timeout=10)
    print("sample%d: EC(0x44C)=%d C   nvidia-smi=%s" % (i+1, e, nv.stdout.strip()))
    time.sleep(2)
print("== 充电阈值簇 0x7A6-0x7AB ==")
for a in range(0x7A6, 0x7AC): print("0x%03X = %d" % (a, ec(a)))
print("== MQTT BatteryProtection 现状 ==")
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_console as mc
app = mc.MrConsole(); app.start()
time.sleep(2)
for t in list(app.status.keys()):
    if "attery" in t or "harge" in t:
        print(t, "->", app.status[t])
app.stop()