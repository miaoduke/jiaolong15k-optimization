# -*- coding: utf-8 -*-
"""开启 0x742 bit2 充电限制门控 + 实时观察充电是否停止"""
import sys, time, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec

def bat_status():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"],
            capture_output=True, text=True, timeout=10).stdout.strip()
        return out
    except Exception:
        return "?"

o = ec.ec_read(0x742)
print("gate orig =", "0b{:08b}".format(o))
try:
    ec.ec_write(0x742, o | 0x04)
    time.sleep(1)
    now = ec.ec_read(0x742)
    print("gate now  =", "0b{:08b}".format(now), "->", "ENABLED" if now & 0x04 else "STILL OFF")
    b9 = ec.ec_read(0x7B9)
    print("limit reg 0x7B9 =", b9)
    if not b9 or b9 == 100 or b9 < 60:
        # 门控开了但限值为空/满 -> 补写 80
        ec.ec_write(0x7B9, 80); time.sleep(0.5)
        print("wrote 0x7B9=80 -> readback:", ec.ec_read(0x7B9))

    print("\n观察 40s (当前86%>80%, 若生效应停充):")
    prev = None
    for i in range(5):
        pct = bat_status()
        g = ec.ec_read(0x742) & 0x04
        print("  t+%ds: charge%%=%s gate=%s" % (i*10, pct, bool(g)))
        time.sleep(10)
finally:
    # 不恢复! 保持门控开启让用户验证; 如需还原手动执行: ec_write(0x742, o)
    print("\n[保持门控开启供验证; 还原命令: ec_write(0x742, %d)]" % o)
