#!/usr/bin/env python3
"""
kbd_bridge.py — 内置键盘 uinput 桥 (MECHREVO 蛟龙15K 专用)
EC 把按键数据直写 0x60 (不触发 IRQ1) → atkbd 无法工作
本守护进程: 轮询 0x64/0x60 → 解析 PS/2 Set 1 扫描码 → uinput 注入内核

用法: sudo python3 kbd_bridge.py
"""
import ctypes
import os
import time
import sys
import fcntl

# ============ iopl + /dev/port ============
libc = ctypes.CDLL(None)
if libc.iopl(3) != 0:
    print("错误: iopl(3) 失败, 需要 root")
    sys.exit(1)
PORT = os.open('/dev/port', os.O_RDWR)

def rd_port(port):
    os.lseek(PORT, port, 0)
    return os.read(PORT, 1)[0]

def wr_port(port, v):
    os.lseek(PORT, port, 0)
    os.write(PORT, bytes([v & 0xFF]))

# ============ uinput ============
UI_DEV_SETUP = 0x405c5503
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_DEV_CREATE = 0x5501
EV_KEY = 0x01
EV_SYN = 0x00
EV_MSC = 0x04
KEY_UP = 0
KEY_DOWN = 1
SYN_REPORT = 0
MSC_SCAN = 4

class UInputSetup(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint16 * 4),
        ("name", ctypes.c_char * 80),
        ("ff_effects_max", ctypes.c_uint32),
    ]

class InputEvent(ctypes.Structure):
    _fields_ = [
        ("time", ctypes.c_long * 2),
        ("type", ctypes.c_ushort),
        ("code", ctypes.c_ushort),
        ("value", ctypes.c_int),
    ]

def uinput_init(name="Built-in Keyboard Bridge"):
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    setup = UInputSetup()
    setup.id[0] = 0x11
    setup.id[1] = 0x4D43
    setup.id[2] = 0x4B42
    setup.id[3] = 1
    setup.name = name.encode()[:79]
    setup.ff_effects_max = 0
    fcntl.ioctl(fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_MSC)
    return fd

def uinput_enable_keys(fd):
    for sc in range(0x01, 0x59):
        if sc not in (0x54, 0x56):
            fcntl.ioctl(fd, UI_SET_KEYBIT, sc)
    fcntl.ioctl(fd, UI_SET_KEYBIT, 55)   # 0x54 KP*
    fcntl.ioctl(fd, UI_SET_KEYBIT, 86)   # 0x56 102ND
    for kc in E0_MAP.values():
        fcntl.ioctl(fd, UI_SET_KEYBIT, kc)
    for kc in [96, 97, 98, 99, 100, 119, 125, 126, 127]:
        fcntl.ioctl(fd, UI_SET_KEYBIT, kc)

def uinput_emit(fd, etype, code, value):
    os.write(fd, bytes(InputEvent((0, 0), etype, code, value)))

def uinput_syn(fd):
    uinput_emit(fd, EV_SYN, SYN_REPORT, 0)

# ============ Set 1 映射 ============
# 通用: 0x01-0x58 keycode = scan; 例外: 0x54=KP*(55), 0x56=102ND(86)
SET1_EXCEPTIONS = {0x54: 55, 0x56: 86}
# E0 扩展键
E0_MAP = {
    0x1C: 96,   # KP_ENTER
    0x1D: 97,   # RIGHT_CTRL
    0x35: 98,   # KP_DIVIDE
    0x37: 99,   # SYSRQ
    0x38: 100,  # RIGHT_ALT
    0x47: 102,  # HOME
    0x48: 103,  # UP
    0x49: 104,  # PAGEUP
    0x4B: 105,  # LEFT
    0x4D: 106,  # RIGHT
    0x4F: 107,  # END
    0x50: 108,  # DOWN
    0x51: 109,  # PAGEDOWN
    0x52: 110,  # INSERT
    0x53: 111,  # DELETE
    0x5B: 125,  # LEFT_META (Win)
    0x5C: 126,  # RIGHT_META
    0x5D: 127,  # COMPOSE (Menu)
}

def scan_to_key(sc, e0):
    if e0:
        return E0_MAP.get(sc)
    if sc in SET1_EXCEPTIONS:
        return SET1_EXCEPTIONS[sc]
    if 0x01 <= sc <= 0x58:
        return sc
    return None

# ============ 主循环 ============
def main():
    print("初始化: 键盘复位...")
    while rd_port(0x64) & 1:
        rd_port(0x60)
    wr_port(0x60, 0xFF)
    time.sleep(0.5)
    while rd_port(0x64) & 1:
        rd_port(0x60)

    print("初始化: uinput...")
    fd = uinput_init()
    uinput_enable_keys(fd)
    fcntl.ioctl(fd, UI_DEV_CREATE, 0)
    print("uinput 键盘桥已启动 (Ctrl+C 退出)")

    e0_pending = False
    stats = {"total": 0, "mapped": 0}
    while True:
        try:
            st = rd_port(0x64)
            if st & 1:
                scan = rd_port(0x60)
                stats["total"] += 1
                if scan == 0xE0:
                    e0_pending = True
                    continue
                if scan == 0xE1:
                    continue
                release = bool(scan & 0x80)
                code = scan & 0x7F
                if e0_pending and code == 0x2A:
                    continue
                key = scan_to_key(code, e0_pending)
                e0_pending = False
                if key is not None:
                    stats["mapped"] += 1
                    uinput_emit(fd, EV_KEY, key, KEY_UP if release else KEY_DOWN)
                    uinput_emit(fd, EV_MSC, MSC_SCAN, scan)
                    uinput_syn(fd)
        except KeyboardInterrupt:
            break
        except Exception:
            pass
        time.sleep(0.002)
    os.close(fd)
    print(f"退出 (共 {stats['total']} 字节, {stats['mapped']} 映射)")

if __name__ == "__main__":
    main()