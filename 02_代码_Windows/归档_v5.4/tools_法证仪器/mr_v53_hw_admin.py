#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mr_v53_hw_admin.py — 提权段实机验证(需一次UAC)。结果写入 _admin_results.json
覆盖: EC基线读(0x7C1/0x7C2/0x7B9) · HAGS回读环 · WiFi频段回读环 · E1功耗墙真仲裁"""
import ctypes, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mr_win_ctrl as wc
import winreg

R = {"admin": bool(ctypes.windll.shell32.IsUserAnAdmin())}

# --- EC 基线读 ---
import mr_ec_hw as hw
for name, addr in (("ec_0x7C1", 0x7C1), ("ec_0x7C2", 0x7C2), ("charge_0x7B9", 0x7B9)):
    R[name] = hw.ec_read(addr)

# --- HAGS 回读环(HKLM) ---
orig = wc.hags_get()
ok, _ = wc.hags_set(True); time.sleep(0.5)
now = wc.hags_get()
R["hags"] = {"orig": orig, "after_on": now, "write_ok": ok}
if now == 2:
    if orig is None:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, "HwSchMode")
            R["hags"]["restored_to"] = "<deleted=原未设置>"
        except Exception as e:
            R["hags"]["restored_to"] = f"del_fail:{e}"
    else:
        wc.hags_set(orig); R["hags"]["restored_to"] = wc.hags_get()

# --- WiFi 频段回读环(首块物理卡) ---
ads = wc.wifi_adapters()
R["wifi_adapters"] = ads
if ads:
    idx0 = ads[0]["index"]; band0 = ads[0]["band"]
    ok, d = wc.wifi_band_prefer(idx0, 2); time.sleep(0.4)
    cur = [(a["band"], a["index"]) for a in wc.wifi_adapters() if a["index"] == idx0]
    got = cur[0][0] if cur else None
    R["wifi_band"] = {"idx": idx0, "orig": band0, "after": got, "ok": ok}
    if got == 2:
        wc.wifi_band_prefer(idx0, band0); time.sleep(0.4)
        back = [a["band"] for a in wc.wifi_adapters() if a["index"] == idx0]
        R["wifi_band"]["restored"] = back[0] if back else None

# --- E1 真仲裁(管理员下 -pl 140) ---
w0 = wc.gpu_wall_get()
ok, dt = wc.gpu_wall_set(140)
time.sleep(0.6)
w1 = wc.gpu_wall_get()
r115, _ = wc.gpu_wall_set(115)   # 无论成败都尝试回默认115并记录
time.sleep(0.6)
R["e1_arbitration"] = {"before": w0, "set140_ok": ok, "detail": dt,
                       "after140": w1, "restore115_ok": r115, "final": wc.gpu_wall_get()}

json.dump(R, open(os.path.join(HERE, "_admin_results.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(json.dumps(R, ensure_ascii=False))
