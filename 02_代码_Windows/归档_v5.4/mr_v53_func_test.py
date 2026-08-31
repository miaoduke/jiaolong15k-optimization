#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mr_v53_func_test.py — v5.3 新增功能回归测试(assert式, 无GUI窗口)
运行: python mr_v53_func_test.py   全部通过输出 ALL PASS
覆盖: DEVMODE结构 / 刷新率自洽 / 隐藏电源参数读取 / GPU监控与功耗墙 /
      电源状态 / 注册表读 / EC字节序 / GUI新方法存在性 / CLI免MQTT分支
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PASS = []

def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ✅ {name}" + (f" ({detail})" if detail else ""))

# ---------- 1) DEVMODEW 结构 ----------
import ctypes
import mr_win_ctrl as wc
check("DEVMODEW.sizeof==220(x64)", ctypes.sizeof(wc.DEVMODEW) == 220,
      str(ctypes.sizeof(wc.DEVMODEW)))
check("DEVMODEW含频率字段", hasattr(wc.DEVMODEW, "dmDisplayFrequency"))

# ---------- 2) 刷新率自洽 ----------
rates = wc.list_refresh_rates()
cur = ctypes.wintypes if False else None
u = wc._user32()
dm = wc.DEVMODEW(); dm.dmSize = ctypes.sizeof(wc.DEVMODEW)
ok = u.EnumDisplaySettingsW(None, wc.ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
check("EnumDisplaySettings成功", ok == 1)
check("刷新率非空且升序", rates and rates == sorted(rates), str(rates))
check("当前频率在列表内", int(dm.dmDisplayFrequency) in rates,
      f"{dm.dmDisplayFrequency}Hz in {rates}")

# ---------- 3) 隐藏电源参数(EPP/BOOST/MaxState) ----------
for pid, lo, hi in [("PERFEPP", 0, 100), ("PERFBOOSTMODE", 0, 5), ("PROCTHROTTLEMAX", 5, 100)]:
    v = wc.powercfg_get(pid)
    check(f"powercfg_get({pid})", isinstance(v, dict) and isinstance(v["ac"], int)
          and lo <= v["ac"] <= hi and lo <= v["dc"] <= hi, str(v))

# ---------- 4) GPU监控与功耗墙 ----------
gs = wc.gpu_stats()
check("gpu_stats温度合理", gs and 20 <= gs.get("temp", 999) <= 120, f"{gs and gs['temp']}°C")
check("E1基线max=140W", gs and gs.get("max_w") == 140, str(gs and gs.get("max_w")))
wall = wc.gpu_wall_get()
check("功耗墙四值齐全", wall and all(k in wall for k in
      ("current_w", "default_w", "min_w", "max_w")), str(wall))

# ---------- 5) 电源状态 ----------
ps = wc.power_status()
check("power_status", ps and isinstance(ps["ac_online"], bool) and 0 <= ps["battery_pct"] <= 100, str(ps))

# ---------- 6) 注册表读(未设置=None 合法) ----------
hv, gv = wc.hags_get(), wc.gamemode_get()
check("hags/gamemode读安全", (hv is None or isinstance(hv, int)) and (gv is None or isinstance(gv, int)),
      f"hags={hv} gamemode={gv}")
ad = wc.wifi_adapters()
check("wifi_adapters结构", isinstance(ad, list) and all("desc" in x and "band" in x for x in ad), f"{len(ad)}块")

# ---------- 7) EC 字节序(monkeypatch, 不触真实EC) ----------
import mr_ec_hw as hw
orig = hw._wmi_read_ec
hw._wmi_read_ec = lambda a: {0x464: 0x07, 0x465: 0x1D}.get(a)
check("RPM高字节在前(合理区间1500-4000)", (lambda v: v is not None and 1500 <= v <= 4000)(hw.get_fan_rpm()), str(hw.get_fan_rpm()))
hw._wmi_read_ec = lambda a: {0x469: 180}.get(a)
check("GPU风扇Duty映射%(0-100合理区间)", (lambda v: v is not None and 0 <= v <= 100)(hw.get_gpu_duty()), str(hw.get_gpu_duty()))
hw._wmi_read_ec = orig

# ---------- 8) GUI 新方法存在性(不实例化Tk) ----------
import mr_gui_v5 as mg
for m in ("_tab_powersys", "_reload_scenarios", "load_scenario",
          "_gpu_wall_verified", "_smart_scene_check"):
    check(f"GuiApp.{m}", hasattr(mg.GuiApp, m))
check("FIELD_DOC注释保留", len(mg.FIELD_DOC) >= 45, f"{len(mg.FIELD_DOC)}条(实测; 文档'89条'系虚报, 见审计)")
check("GUI引用wc模块", mg.wc is wc)

# ---------- 9) CLI power 分支不依赖MQTT ----------
r = subprocess.run([sys.executable, os.path.join(HERE, "mr_console.py"), "power", "epp"],
                   capture_output=True, text=True, errors="replace", timeout=30, cwd=HERE)
check("CLI power免MQTT可跑", r.returncode == 0 and "EPP:" in r.stdout, r.stdout.strip()[:60])

# ---------- 10) 协议常量不变(升级锚点) ----------
import mr_console as mc
check("BROKER端口13688", mc.BROKER_PORT == 13688)
check("客户端槽位5", mc.CLIENT_SLOT == 5)

print(f"\n=== ALL PASS ({len(PASS)}项) ===")
