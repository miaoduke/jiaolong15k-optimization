# -*- coding: utf-8 -*-
"""对 UWACPIDriver (\\.\ACPIDriver) 发 ACPI ECWRITE IOCTL — 复刻官方通道"""
import ctypes, sys
from ctypes import wintypes, byref, sizeof, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

k32 = ctypes.windll.kernel32
GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
IOCTL_GPD_ACPI_ECREAD  = 2621482120
IOCTL_GPD_ACPI_ECWRITE = 2621482124

h = k32.CreateFileW(b"\\\\.\\ACPIDriver", GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
print("handle:", h)
if h == -1 or h == 0xFFFFFFFFFFFFFFFF:
    print("CreateFile err", ctypes.GetLastError())
    sys.exit(1)

def ec_read_ioctl(addr):
    buf = create_string_buffer(bytes([addr & 0xFF, 0]) + addr.to_bytes(4, "little"), 16)
    ret = create_string_buffer(16)
    br = wintypes.DWORD()
    ok = k32.DeviceIoControl(h, IOCTL_GPD_ACPI_ECREAD, buf, 8, ret, 16, byref(br), None)
    return ok, ret.raw[:br.value].hex() if ok else "err%d" % ctypes.GetLastError()

# 先试读 0x7B9 看缓冲区格式猜得对不对
for fmt_name, mk in [("addr+pad4", lambda a: a.to_bytes(4,"little") + b"\x00"*4),
                     ("byte+byte", lambda a: bytes([a & 0xFF, 0])),
                     ("cmdBB+addr", lambda a: bytes([0xBB]) + a.to_bytes(4,"little"))]:
    buf = create_string_buffer(mk(0x7B9), 16)
    ret = create_string_buffer(16)
    br = wintypes.DWORD()
    ok = k32.DeviceIoControl(h, IOCTL_GPD_ACPI_ECREAD, buf, len(mk(0x7B9)), ret, 16, byref(br), None)
    print(fmt_name, "->", ok, ret.raw[:max(br.value,1)].hex() if br.value else ret.raw[:4].hex(), "gle=", ctypes.GetLastError())
    ctypes.windll.kernel32.SetLastError(0)
k32.CloseHandle(h)
