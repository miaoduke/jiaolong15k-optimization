# -*- coding: utf-8 -*-
"""cross-validate roj234 register map on OUR machine (read-only!)"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_ec_hw as ec

checks = [
    (0x043E, "CPU温度(我方基线)"),
    (0x044C, "GPU温度(我方基线)"),
    (0x0461, "CPU duty?(我方旧猜)"),
    (0x075B, "REG_FAN1_DUTY CPU PWM (roj234=1883)"),
    (0x075C, "REG_FAN2_DUTY GPU PWM (roj234=1884)"),
    (0x0751, "REG_MAFAN_CTRL 硬件曲线开关"),
    (0x07C3, "REG_CPU_PL1 功耗墙W"),
    (0x07C4, "REG_CPU_PL2"),
    (0x07C5, "REG_CPU_PL4"),
    (0x07C6, "REG_CPU_TCC offset"),
    (0x07B9, "charge limit/start?(roj234=limit; 我读80=start)"),
    (0x07A8, "start(我方)"),
    (0x07A9, "stop(我方)"),
    (0x074E, "REG_FN_KEY_CTRL Fn锁"),
    (0x07A6, "REG_TOUCHPAD"),
    (0x078C, "REG_KEYBOARD_BACKLIGHT"),
    (0x049F, "REG_ADAPTER_WATT 适配器功率"),
    (0x0464, "FAN1 RPM high(我方RPM源)"),
    (0x0743, "GPU TGP ctrl"),
    (0x0746, "DYNAMIC_BOOST_MAX"),
    (0x0726, "AC_RECOVERY bit3"),
]
for addr, name in checks:
    v = ec.ec_read(addr)
    print("0x%03X = %-10s %s" % (addr, ("--" if v is None else v), name))
