# -*- coding: utf-8 -*-
"""ECWRITE 格式穷举: 用无害地址 0x7D1 (DOWN旁路,当前None) 测试哪种格式能让驱动接受"""
import ctypes, sys, time
from ctypes import wintypes, byref, create_string_buffer
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

k32 = ctypes.windll.kernel32
h = k32.CreateFileW("\\\\.\\ACPIDriver", 0xC0000000, 0, None, 3, 0, None)
assert h not in (-1, 0xFFFFFFFFFFFFFFFF)

def ecread(addr):
    buf = create_string_buffer(addr.to_bytes(2, "little"), 8)
    ret = create_string_buffer(32)
    br = wintypes.DWORD()
    ok = k32.DeviceIoControl(h, 2621482120, buf, 2, ret, 32, byref(br), None)
    return ret.raw[0] if ok and br.value else None

def trywrite(inn, use_out=False):
    buf = create_string_buffer(inn, max(len(inn), 8))
    ret = create_string_buffer(32)
    br = wintypes.DWORD()
    ob = ret if use_out else None
    obs = 32 if use_out else 0
    ok = k32.DeviceIoControl(h, 2621482124, buf, len(inn), ob, obs, byref(br), None)
    return ok

A = 0x7D1
variants = [
    ("addr2+val1",      A.to_bytes(2,"little") + bytes([0x30]),        False),
    ("addr2+val1 pad",  A.to_bytes(2,"little") + bytes([0x30,0,0,0,0,0]), False),
    ("addr4+val4",      A.to_bytes(4,"little") + (0x30).to_bytes(4,"little"), False),
    ("val4+addr4",      (0x30).to_bytes(4,"little") + A.to_bytes(4,"little"), False),
    ("addr2+val1 OUT",  A.to_bytes(2,"little") + bytes([0x30]),        True),
    ("addr4+val4 OUT",  A.to_bytes(4,"little") + (0x30).to_bytes(4,"little"), True),
]
for name, inn, uo in variants:
    ok = trywrite(inn, uo)
    print(name.ljust(18), "->", ok, "| readback 7D1 =", ecread(A))
    if ok and ecread(A) == 0x30:
        print("*** FORMAT FOUND ***"); break
k32.CloseHandle(h)
