#!/usr/bin/env python3
"""kbd_rgb.py v3 — 蛟龙15K RGB 键盘背光控制（本机 EC 协议，保留 Fn+F6/F7 硬件亮度）

用法:
  kbd_rgb.py <color>           设置静态色: red green blue white cyan magenta yellow orange
  kbd_rgb.py <r> <g> <b>       自定义色 (0-255)
  kbd_rgb.py rainbow           彩虹模式
  kbd_rgb.py breathe <1-4>     呼吸模式(1-4 种颜色)
  kbd_rgb.py static            静态模式(清除彩虹/呼吸)
  kbd_rgb.py status            读当前状态

协议(Source: ControlCenter 5.17.49.19 DefaultTool SingleZone.cs):
  颜色为 LEVEL 制(0-50, = RGB值/5): 0x769=R 0x76A=G 0x76B=B
  触发: 0x767 读改写置 bit5(0x20), EC 消费后清零=应用成功
  彩虹: 0x769-76B=0 + 0x767 bit7; 呼吸: 0x7C5 &=0xF8 + 1-4
  不碰 0x78C(bit4 亮度接管位会破坏 Fn+F6/F7)
"""
import re, subprocess, sys, os

RKBC = r"\_SB.AMW0.RKBC"
WKBC = r"\_SB.AMW0.WKBC"

def call(inp):
    with open("/proc/acpi/call", "w") as f: f.write(inp)
    with open("/proc/acpi/call") as f: return f.read().strip()

def rb(addr):
    s = call(f"{RKBC} 0x{addr & 0xFF:02X} 0x{addr >> 8:02X}")
    m = re.findall(r"0x([0-9a-fA-F]+)", s)
    return int(m[0], 16) if m else None

def wb(addr, v):
    call(f"{WKBC} 0x{addr & 0xFF:02X} 0x{addr >> 8:02X} 0x{v:02X} 0x00")

# COLOR_CELL 表 (Index, R, G, B, R_Level, G_Level, B_Level) — 30 色
COLORS = [
    (1,255,0,0,50,0,0),(2,255,50,0,50,5,0),(3,255,80,0,50,10,0),(4,145,60,0,29,13,0),
    (5,255,102,0,40,10,0),(6,255,128,0,40,15,0),(7,255,180,0,40,25,0),(8,150,128,2,35,20,0),
    (9,255,204,0,50,40,0),(10,204,225,0,40,44,0),(11,120,255,0,24,50,0),(12,60,115,18,12,23,4),
    (13,0,255,0,0,50,0),(14,0,255,80,0,50,16),(15,0,255,180,0,50,35),(16,60,125,135,13,25,26),
    (17,0,255,255,0,50,50),(18,0,180,255,0,35,50),(19,0,80,255,0,16,50),(20,0,35,102,0,8,20),
    (21,0,0,255,0,0,50),(22,80,0,255,16,0,50),(23,180,0,255,35,0,50),(24,110,45,100,21,9,19),
    (25,255,0,255,50,0,50),(26,255,0,180,50,0,36),(27,255,0,80,50,0,6),(28,180,5,0,36,0,0),
    (29,0,0,0,0,0,0),(30,255,255,255,50,40,40)]
NAMED = {"red":(255,0,0),"green":(0,255,0),"blue":(0,0,255),"white":(255,255,255),
         "cyan":(0,255,255),"magenta":(255,0,255),"yellow":(255,255,0),"orange":(255,128,0)}

def levels(r, g, b):
    for idx, R, G, B, rl, gl, bl in COLORS:
        if (R, G, B) == (r, g, b): return rl, gl, bl
    return max(1, min(50, r // 5)), max(1, min(50, g // 5)), max(1, min(50, b // 5))

def set_color(r, g, b):
    rl, gl, bl = levels(r, g, b)
    wb(0x769, rl); wb(0x76A, gl); wb(0x76B, bl)
    v = rb(0x767) or 0
    wb(0x767, v | 0x20)  # 触发
    print(f"颜色 Level {rl}/{gl}/{bl} 已写入并触发")

def rainbow():
    wb(0x769, 0); wb(0x76A, 0); wb(0x76B, 0)
    v = rb(0x767) or 0
    wb(0x767, v | 0x80)
    print("彩虹模式开启")

def breathe(idx):
    v = rb(0x7C5) or 0
    wb(0x7C5, (v & 0xF8) | (idx & 7))
    print(f"呼吸模式开启(色 {idx})")

def static():
    v = rb(0x767) or 0
    wb(0x767, v & ~0x80)  # 清彩虹
    v = rb(0x7C5) or 0
    wb(0x7C5, v & 0xF8)   # 清呼吸
    print("静态模式(彩虹/呼吸已关闭)")

def power(state):
    v = rb(0x78C) or 0
    if state == "off":
        wb(0x78C, v | 0x02)
    else:
        wb(0x78C, v & ~0x02)
    print(f"键盘灯电源{'关' if state == 'off' else '开'} (0x78C=0x{rb(0x78C):02X})")

def status():
    print(f"颜色Level: R={rb(0x769)} G={rb(0x76A)} B={rb(0x76B)}  (DEFAULT: {rb(0x76C)},{rb(0x76D)},{rb(0x76E)})")
    print(f"模式: 0x767=0x{rb(0x767):02X} (bit7=彩虹 bit5=触发)  0x7C5=0x{rb(0x7C5):02X} (bits0-2=呼吸)")
    print(f"亮度/电源: 0x78C=0x{rb(0x78C):02X} (bit4=软件接管, bits5-7=亮度, bit3=硬件模式)")

if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "status": status()
    elif cmd == "rainbow": rainbow()
    elif cmd == "breathe": breathe(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    elif cmd == "static": static()
    elif cmd == "power":
        if len(sys.argv) < 3 or sys.argv[2] not in ("on", "off"):
            print("用法: kbd_rgb.py power on|off"); sys.exit(1)
        power(sys.argv[2])
    elif cmd in NAMED: set_color(*NAMED[cmd])
    elif len(sys.argv) >= 4: set_color(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
    else: print(__doc__); sys.exit(1)