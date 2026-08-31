# -*- coding: utf-8 -*-
import ctypes, sys, time
from ctypes import wintypes, byref, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
k32 = ctypes.windll.kernel32
h = k32.CreateFileW("\\\\.\\ACPIDriver", 0xC0000000, 0, None, 3, 0, None)
def ecread(addr):
    buf = create_string_buffer(addr.to_bytes(2, "little"), 8)
    ret = create_string_buffer(32); br = wintypes.DWORD()
    k32.DeviceIoControl(h, 2621482120, buf, 2, ret, 32, byref(br), None)
    return ret.raw[0] if br.value else None
def ecwrite(addr, val):
    inn = addr.to_bytes(4, "little") + val.to_bytes(4, "little")
    buf = create_string_buffer(inn, 8); ret = create_string_buffer(32); br = wintypes.DWORD()
    return k32.DeviceIoControl(h, 2621482124, buf, 8, ret, 32, byref(br), None)
print("before:", ecread(0x7B9), ecread(0x7D0))
print("write:", ecwrite(0x7B9, 60), ecwrite(0x7D0, 40))
time.sleep(1)
print("after:", ecread(0x7B9), ecread(0x7D0))
# 保持句柄打开 160 秒防驱动卸载, 期间周期性重申
for i in range(10):
    time.sleep(15)
    ecwrite(0x7B9, 60); ecwrite(0x7D0, 40)
    print("reassert t+%ds:" % ((i+1)*15), ecread(0x7B9), ecread(0x7D0))
k32.CloseHandle(h)
