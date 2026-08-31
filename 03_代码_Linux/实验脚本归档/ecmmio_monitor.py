#!/usr/bin/env python3
"""ECMG (0xFED50000) 扩展区域满载采样
用法: sudo python3 ecmmio_monitor.py [间隔秒]
"""
import os, time, sys

fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
BASE = 0xFED50000

def read_region(off, size):
    return os.pread(fd, size, BASE + off)

def main():
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    # 关注区域: 0x400-0x500 (状态), 0x700-0x800 (电源)
    regions = [(0x430, 0x60), (0x780, 0x80)]
    prev = {r: read_region(*r) for r in regions}
    print("时间\tCPTM(43E)\tVGAT(44F)\tFFAN(460)\t变化寄存器(off:old→new)")
    print("=" * 100)
    try:
        while True:
            t = time.strftime('%H:%M:%S')
            changes = []
            cur = {r: read_region(*r) for r in regions}
            for (off, size) in regions:
                for i in range(size):
                    if cur[off, size][i] != prev[off, size][i]:
                        changes.append(f"0x{off+i:03X}:{prev[off, size][i]:02X}→{cur[off, size][i]:02X}")
            cptm = cur[0x430, 0x60][0x43E-0x430]
            vgat = cur[0x430, 0x60][0x44F-0x430]
            ffan = cur[0x430, 0x60][0x460-0x430] & 0x0F
            print(f"{t}\t{cptm}\t{vgat}\t{ffan}\t{', '.join(changes[:12])}")
            prev = cur
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
