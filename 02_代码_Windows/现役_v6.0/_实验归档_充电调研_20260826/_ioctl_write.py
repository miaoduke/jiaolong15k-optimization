# -*- coding: utf-8 -*-
"""ACPI-EC 决定性写入: UP(0x7B9)=60 DOWN(0x7D0)=40, 监控充电"""
import ctypes, sys, time, subprocess
from ctypes import wintypes, byref, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

k32 = ctypes.windll.kernel32
h = k32.CreateFileW("\\\\.\\ACPIDriver", 0xC0000000, 0, None, 3, 0, None)
assert h not in (-1, 0xFFFFFFFFFFFFFFFF), "open fail"

def ecread(addr):
    buf = create_string_buffer(addr.to_bytes(2, "little"), 8)
    ret = create_string_buffer(32)
    br = wintypes.DWORD()
    ok = k32.DeviceIoControl(h, 2621482120, buf, 2, ret, 32, byref(br), None)
    return ret.raw[0] if ok and br.value else None

def ecwrite(addr, val):
    inn = addr.to_bytes(2, "little") + bytes([val & 0xFF])
    buf = create_string_buffer(inn, 8)
    br = wintypes.DWORD()
    ok = k32.DeviceIoControl(h, 2621482124, buf, len(inn), None, 0, byref(br), None)
    return ok

def bat():
    return subprocess.run(["powershell","-NoProfile","-Command","(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"], capture_output=True, text=True).stdout.strip()

print("readback check: 7B9=%s 7D0=%s bat=%s%%" % (ecread(0x7B9), ecread(0x7D0), bat()))
print("write UP=60 DOWN=40 ->", ecwrite(0x7B9, 60), ecwrite(0x7D0, 40))
time.sleep(1)
print("immediate: 7B9=%s 7D0=%s" % (ecread(0x7B9), ecread(0x7D0)))
for i in range(12):
    time.sleep(10)
    print("t+%ds: bat=%s%% | 7B9=%s 7D0=%s" % ((i+1)*10, bat(), ecread(0x7B9), ecread(0x7D0)))
k32.CloseHandle(h)
