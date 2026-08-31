#!/usr/bin/env python3
"""EC RAM 读写工具: /dev/mem 访问 0x000-0xFFF; acpi_call WKBC/RKBC 访问 0x1800+."""
import mmap, struct, subprocess, sys, os, re

EC_BASE = 0xFED50000  # DSDT ECMG 操作区(非FEDC0000)

def read_mem(addr):
    with open("/dev/mem", "r+b") as f:
        f.seek(EC_BASE + addr); return f.read(1)[0]

def write_mem(addr, val):
    with open("/dev/mem", "r+b") as f:
        f.seek(EC_BASE + addr); f.write(bytes([val]))

def wmi_cmd(inp):
    with open("/proc/acpi/call", "w") as f:
        f.write(inp)
    with open("/proc/acpi/call") as f:
        return f.read().strip()

def read_hi(addr):
    out = wmi_cmd(f"\\_SB.AMW0.RKBC 0x{addr & 0xFF:02X} 0x{(addr >> 8) & 0xFF:02X}")
    m = re.search(r'0x([0-9A-Fa-f]{2})', out)
    return int(m.group(1), 16) if m else 0

def write_hi(addr, val):
    return wmi_cmd(f"\\_SB.AMW0.WKBC 0x{addr & 0xFF:02X} 0x{(addr >> 8) & 0xFF:02X} 0x{val:02X} 0x00")

def read_ec(addr):
    return read_mem(addr)  # 基址 FED50000 (DSDT ECMG), RKBC 备用

def write_ec(addr, val):
    write_mem(addr, val)  # 基址 FED50000, WKBC 备用

if __name__ == "__main__":
    if sys.argv[1] == "r": print(f"0x{int(sys.argv[2],16):04X} = 0x{read_ec(int(sys.argv[2],16)):02X}")
    elif sys.argv[1] == "w": write_ec(int(sys.argv[2],16), int(sys.argv[3],16)); print(f"wrote 0x{int(sys.argv[2],16):04X} = 0x{int(sys.argv[3],16):02X}")
    elif sys.argv[1] == "dump":
        for a in range(int(sys.argv[2],16), int(sys.argv[3],16)+1):
            print(f"0x{a:04X} = 0x{read_ec(a):02X}")
