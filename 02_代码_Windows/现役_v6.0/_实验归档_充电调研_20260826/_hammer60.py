# -*- coding: utf-8 -*-
"""高频ACPI写入UP=60对抗GCU覆盖 + 电量轨迹判停"""
import ctypes, sys, time, subprocess, threading
from ctypes import wintypes, byref, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

k32 = ctypes.windll.kernel32
h = k32.CreateFileW("\\\\.\\ACPIDriver", 0xC0000000, 0, None, 3, 0, None)
def rd(addr):
    buf = create_string_buffer(addr.to_bytes(2, "little"), 8)
    ret = create_string_buffer(32); br = wintypes.DWORD()
    k32.DeviceIoControl(h, 2621482120, buf, 2, ret, 32, byref(br), None)
    return ret.raw[0] if br.value else None
def wr(addr, val):
    inn = addr.to_bytes(4, "little") + val.to_bytes(4, "little")
    buf = create_string_buffer(inn, 8); ret = create_string_buffer(32); br = wintypes.DWORD()
    return k32.DeviceIoControl(h, 2621482124, buf, 8, ret, 32, byref(br), None)
def bat():
    return subprocess.run(["powershell","-NoProfile","-Command","(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"], capture_output=True, text=True).stdout.strip()

stop_flag = False
def hammer():
    while not stop_flag:
        wr(0x7B9, 60)   # UP=60
        wr(0x7D0, 40)   # DOWN=40
        time.sleep(1.0)
t = threading.Thread(target=hammer, daemon=True)
t.start()
print("hammer started (UP=60 every 1s). watching battery 6min:")
for i in range(12):
    time.sleep(30)
    print("t+%ds: bat=%s%% | UP reg=%s" % ((i+1)*30, bat(), rd(0x7B9)))
stop_flag = True
time.sleep(1.5)
k32.CloseHandle(h)
print("done")
