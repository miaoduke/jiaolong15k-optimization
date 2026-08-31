# -*- coding: utf-8 -*-
"""插电后充电行为长监控: 电量+ACPI层EC读(不干扰)"""
import ctypes, sys, time, subprocess
from ctypes import wintypes, byref, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

k32 = ctypes.windll.kernel32
h = k32.CreateFileW("\\\\.\\ACPIDriver", 0xC0000000, 0, None, 3, 0, None)
def rd(addr):
    buf = create_string_buffer(addr.to_bytes(2, "little"), 8)
    ret = create_string_buffer(32); br = wintypes.DWORD()
    k32.DeviceIoControl(h, 2621482120, buf, 2, ret, 32, byref(br), None)
    return ret.raw[0] if br.value else None
def bat():
    r = subprocess.run(["powershell","-NoProfile","-Command","$b=Get-CimInstance Win32_Battery; Write-Host ($b.EstimatedChargeRemaining.ToString()+","+$b.BatteryStatus)"], capture_output=True, text=True).stdout.strip()
    return r
print("t0: UP(7B9)=%s DOWN(7D0)=%s bat,ac=%s" % (rd(0x7B9), rd(0x7D0), bat()))
for i in range(20):
    time.sleep(30)
    print("t+%ds: UP=%s DOWN=%s bat,ac=%s" % ((i+1)*30, rd(0x7B9), rd(0x7D0), bat()))
k32.CloseHandle(h)
