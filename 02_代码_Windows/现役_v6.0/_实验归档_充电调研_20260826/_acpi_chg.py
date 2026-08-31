# -*- coding: utf-8 -*-
"""ACPI-EC 正式充电限制: UP(0x7B9)=60 DOWN(0x7D0)=40, 长监控"""
import ctypes, sys, time, subprocess
from ctypes import wintypes, byref, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

k32 = ctypes.windll.kernel32
h = k32.CreateFileW("\\\\.\\ACPIDriver", 0xC0000000, 0, None, 3, 0, None)
assert h not in (-1, 0xFFFFFFFFFFFFFFFF)

def ecread(addr):
    buf = create_string_buffer(addr.to_bytes(2, "little"), 8)
    ret = create_string_buffer(32)
    br = wintypes.DWORD()
    k32.DeviceIoControl(h, 2621482120, buf, 2, ret, 32, byref(br), None)
    return ret.raw[0] if br.value else None

def ecwrite(addr, val):
    inn = addr.to_bytes(4, "little") + val.to_bytes(4, "little")
    buf = create_string_buffer(inn, 8)
    ret = create_string_buffer(32)
    br = wintypes.DWORD()
    return k32.DeviceIoControl(h, 2621482124, buf, 8, ret, 32, byref(br), None)

def bat():
    return subprocess.run(["powershell","-NoProfile","-Command","(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"], capture_output=True, text=True).stdout.strip()

print("before: 7B9=%s 7D0=%s bat=%s%%" % (ecread(0x7B9), ecread(0x7D0), bat()))
ok1 = ecwrite(0x7B9, 60)
ok2 = ecwrite(0x7D0, 40)
time.sleep(0.5)
print("wrote UP=60(%s) DOWN=40(%s)" % (ok1, ok2))
print("immediate: 7B9=%s 7D0=%s" % (ecread(0x7B9), ecread(0x7D0)))
for i in range(10):
    time.sleep(12)
    print("t+%ds: bat=%s%% | 7B9=%s 7D0=%s" % ((i+1)*12, bat(), ecread(0x7B9), ecread(0x7D0)))
k32.CloseHandle(h)
