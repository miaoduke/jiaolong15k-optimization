# -*- coding: utf-8 -*-
"""UWACPIDriver ACPI-EC 通道复刻: ECREAD 探格式 -> ECWRITE 设限 -> 观察"""
import ctypes, sys, time, subprocess
from ctypes import wintypes, byref, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

k32 = ctypes.windll.kernel32
GENERIC_RW = 0xC0000000
OPEN_EXISTING = 3
ECREAD  = 2621482120
ECWRITE = 2621482124

h = k32.CreateFileW("\\\\.\\ACPIDriver", GENERIC_RW, 0, None, OPEN_EXISTING, 0, None)
err = ctypes.GetLastError()
print("handle:", h, "err:", err)
if h in (-1, 0xFFFFFFFFFFFFFFFF):
    sys.exit(1)

def ioctl(code, inb, outsz=32):
    buf = create_string_buffer(inb, max(len(inb), 8))
    ret = create_string_buffer(outsz)
    br = wintypes.DWORD()
    ok = k32.DeviceIoControl(h, code, buf, len(inb), ret, outsz, byref(br), None)
    gle = ctypes.GetLastError()
    return ok, ret.raw[:br.value].hex() if ok and br.value else ("GLE%d" % gle)

# ECREAD 格式探测: 目标地址 0x7B9 (当前应=80)
addrs = [(0x7B9).to_bytes(4, "little"), bytes([0xB9, 0x07]), (0x7B9).to_bytes(2, "little")]
for i, a in enumerate(addrs):
    for extra in (b"", b"\x00"):
        inn = a + extra
        ok, outv = ioctl(ECREAD, inn)
        print("READ fmt%d (%s):" % (i, (a+extra).hex()), ok, outv)
k32.CloseHandle(h)
