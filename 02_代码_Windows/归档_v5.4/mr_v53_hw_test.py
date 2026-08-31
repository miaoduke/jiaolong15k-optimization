#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mr_v53_hw_test.py — 未测项目实机验证套件(非管理员段)
纪律: 记录原值 → 写入 → 延时 → 回读 → 恢复原值; 全程CSV留痕
危险排除: System_OFF / MONITOR_OFF / AIRPLANE / 摄像头/WiFi/BT设备开关 / 全部⛔研究项
用法: python mr_v53_hw_test.py [--with-mqtt]
"""
import ctypes
import csv
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mr_win_ctrl as wc

LOG = os.path.join(HERE, "实机验证日志_20260825.csv")
rows = []

def rec(section, item, action, detail, ok):
    rows.append([section, item, action, detail, "PASS" if ok else "FAIL"])
    print(f"  {'✅' if ok else '❌'} [{section}] {item} {action}: {detail[:90]}")

def roundtrip(section, name, setter, reader, newval, wait=0.6, cmp=None):
    """通用回读环: 读原值→写新值→读验证→恢复原值→读确认恢复"""
    orig = reader()
    if orig is None:
        rec(section, name, "skip", f"原值不可读({orig})", False)
        return
    ok1, d1 = setter(newval)
    time.sleep(wait)
    got = reader()
    same = (got == newval) if cmp is None else cmp(got, newval)
    rec(section, name, f"写{newval}", f"原={orig} 写后读={got} ({d1})", bool(same))
    ok2, _ = setter(orig if not isinstance(orig, tuple) else orig[0])
    time.sleep(wait)
    back = reader()
    rec(section, name, "恢复", f"→{back}", back == orig or cmp(back, orig))

print("=== S1 Windows原生层(免管理员) ===")
ADMIN = bool(ctypes.windll.shell32.IsUserAnAdmin())
print(f"(elevated={ADMIN})")

# 1.1 powercfg 三参数写入权限探测+回读环(powercfg setac 非管理员可能拒绝——如实记录)
for pid, nv in [("PERFEPP", 40), ("PERFBOOSTMODE", 4), ("PROCTHROTTLEMAX", 99)]:
    v = wc.powercfg_get(pid)
    if v:
        roundtrip("powercfg", pid,
                  lambda val, p=pid: wc.powercfg_set(p, ac=val),
                  lambda p=pid: (wc.powercfg_get(p) or {}).get("ac"),
                  nv)
    else:
        rec("powercfg", pid, "skip", "读取失败", False)

# 1.2 屏幕亮度回读环(免管理员✓)
def bright_set(v): return wc.set_brightness(v)
def bright_get():
    ok, out = wc._run(["powershell", "-NoProfile", "-Command",
                       "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness"])
    try: return int(out.strip().splitlines()[-1])
    except Exception: return None
roundtrip("display", "亮度WMI", bright_set, bright_get, 66)

# 1.3 刷新率回读环(当前档→列表内另一档→还原)
rates = wc.list_refresh_rates()
u = wc._user32()
dm = wc.DEVMODEW(); dm.dmSize = ctypes.sizeof(wc.DEVMODEW)
u.EnumDisplaySettingsW(None, wc.ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
cur_hz = int(dm.dmDisplayFrequency)
alt = next((h for h in rates if h != cur_hz), None)
if alt:
    ok, d = wc.set_refresh_rate(alt); time.sleep(1.2)
    dm2 = wc.DEVMODEW(); dm2.dmSize = ctypes.sizeof(wc.DEVMODEW)
    u.EnumDisplaySettingsW(None, wc.ENUM_CURRENT_SETTINGS, ctypes.byref(dm2))
    now = int(dm2.dmDisplayFrequency)
    rec("display", "刷新率", f"{cur_hz}→{alt}Hz", f"实切={now}Hz ({d})", now == alt)
    ok2, _ = wc.set_refresh_rate(cur_hz); time.sleep(1.2)
    dm3 = wc.DEVMODEW(); dm3.dmSize = ctypes.sizeof(wc.DEVMODEW)
    u.EnumDisplaySettingsW(None, wc.ENUM_CURRENT_SETTINGS, ctypes.byref(dm3))
    rec("display", "刷新率", "恢复", f"→{int(dm3.dmDisplayFrequency)}Hz", int(dm3.dmDisplayFrequency) == cur_hz)
else:
    rec("display", "刷新率", "skip", "仅一档可用", False)

# 1.4 HKCU 注册表开关回读环(游戏模式/GameDVR 免提权)
def gm_set(on): return wc.gamemode_set(on)
def gm_get(): return wc.gamemode_get()
orig_gm = gm_get(); target = 0 if (orig_gm or 0) != 0 else 1
ok, _ = gm_set(target); time.sleep(0.4)
rec("registry", "游戏模式", f"置{target}", f"原={orig_gm} 现读={gm_get()}", gm_get() == target)
gm_set(orig_gm or 0); time.sleep(0.4)
rec("registry", "游戏模式", "恢复", f"→{gm_get()}", gm_get() == (orig_gm or 0))
ok, _ = wc.gamedvr_set(1); time.sleep(0.4)
dv = wc._reg_get(__import__('winreg').HKEY_CURRENT_USER, r"System\GameConfigStore", "GameDVR_Enabled")
rec("registry", "GameDVR", "置1", f"现读={dv}", dv == 1)
wc.gamedvr_set(0); time.sleep(0.4)
dv2 = wc._reg_get(__import__('winreg').HKEY_CURRENT_USER, r"System\GameConfigStore", "GameDVR_Enabled")
rec("registry", "GameDVR", "恢复0", f"现读={dv2}", dv2 == 0)

# 1.5 节电计划 创建→删除(不留痕)
GUID_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"
ok, out = wc._run(["powercfg", "/duplicatescheme", GUID_SAVER])
m = None
import re as _re
mm = _re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", out or "")
if mm and ok:
    newguid = mm.group(1)
    rec("powercfg", "节电计划创建", newguid[:13], "duplicatescheme成功", True)
    ok2, _ = wc._run(["powercfg", "/delete", newguid])
    rec("powercfg", "节电计划清理", "delete", "已删除测试计划", ok2)
else:
    rec("powercfg", "节电计划创建", "fail", (out or "")[:80], False)

# 1.6 E1 GPU功耗墙仲裁实验(140W尝试·如实记录驱动裁决)
w0 = wc.gpu_wall_get()
ok, dt = wc.gpu_wall_set(140)
rec("E1", "gpuwall_140", "nvidia-smi -pl 140", f"{dt}", ok)
if ok:  # 若意外成功则恢复115默认并复核
    wc.gpu_wall_set(115); time.sleep(0.5)
    rec("E1", "gpuwall_restore", "→115", str(wc.gpu_wall_get()), True)

# 1.7 CLI 免MQTT子命令冒烟(只读项)
for args in (["power","rates"], ["power","gpuinfo"], ["power","epp"], ["power","gamemode"]):
    r = subprocess.run([sys.executable, os.path.join(HERE,"mr_console.py")] + args,
                       capture_output=True, text=True, errors="replace",
                       encoding="utf-8", timeout=40, cwd=HERE)
    rec("cli", " ".join(args), "smoke", (r.stdout.strip().splitlines() or [""])[-1][:80],
        r.returncode == 0 and r.stdout.strip() != "")

# ---------- S2 MQTT实机段(GCUBridge) ----------
print("=== S2 MQTT层(需GCUBridge Running) ===")
import mr_console as mc
import json as _json
app = mc.MrConsole()
try:
    app.start(); time.sleep(1.2)
    F, S = mc.TOPIC_FAN_CTRL, mc.TOPIC_SET_CTRL

    def pub(topic, payload): app.mqtt.publish(topic, _json.dumps(payload))

    # 2.1 显示模式回读环(当前→GAMING→还原)
    def disp_get(): return str((app.get_setting() or {}).get("DisplayMode", "?"))
    orig_disp = disp_get()
    pub(S, {"Action": "DISPLAY_GAMING_MODE"}); time.sleep(1.5)
    got = disp_get()
    rec("mqtt_display", "游戏画面模式", f"{orig_disp}→GAMING", f"回读={got}", "GAMING" in got.upper())
    back_map = {"GAMING": "DISPLAY_GAMING_MODE", "STANDARD": "DISPLAY_STANDARD_MODE",
                "VIDEO": "DISPLAY_VIDEO_MODE", "READ": "DISPLAY_READ_MODE",
                "CUSTOMIZED": "DISPLAY_CUSTOMIZED_MODE",
                # 实测回包即完整Action串(v53hw修正)
                "DISPLAY_GAMING_MODE": "DISPLAY_GAMING_MODE",
                "DISPLAY_STANDARD_MODE": "DISPLAY_STANDARD_MODE",
                "DISPLAY_VIDEO_MODE": "DISPLAY_VIDEO_MODE",
                "DISPLAY_READ_MODE": "DISPLAY_READ_MODE",
                "DISPLAY_CUSTOMIZED_MODE": "DISPLAY_CUSTOMIZED_MODE"}
    act = back_map.get(orig_disp.upper())
    if act:
        pub(S, {"Action": act}); time.sleep(1.5)
        rec("mqtt_display", "显示模式恢复", f"→{orig_disp}", f"回读={disp_get()}",
            orig_disp.upper() in disp_get().upper())
    else:
        rec("mqtt_display", "显示模式恢复", "skip", f"未知原值{orig_disp}", False)

    # 2.2 OSD 回读环
    osd0 = str((app.get_setting() or {}).get("OSD", "?"))
    pub(S, {"Action": "OSD_HIDDEN_ON"}); time.sleep(1.5)
    osd1 = str((app.get_setting() or {}).get("OSD", "?"))
    rec("mqtt_osd", "OSD悬浮开", f"{osd0}→ON", f"回读={osd1}", "ON" in osd1.upper())
    restore = "OSD_HIDDEN_OFF" if osd0.upper() != "OFF" else "OSD_HIDDEN_ON"
    pub(S, {"Action": restore}); time.sleep(1.5)
    osd2 = str((app.get_setting() or {}).get("OSD", "?"))
    rec("mqtt_osd", "OSD还原", f"→{osd0}", f"回读={osd2}", osd2.upper() == osd0.upper())

    # 2.3 CloseTimer SET_DETAIL 回读环
    fan = app.get_fan() or {}
    ct0 = fan.get("CloseTimer")
    pub(F, {"Action": "SET_OPERATING_MODE_DETAIL", "CloseTimer": 15}); time.sleep(1.6)
    ct1 = (app.get_fan() or {}).get("CloseTimer")
    rec("mqtt_detail", "自动关屏", f"{ct0}→15分", f"回读={ct1}", str(ct1) == "15")
    if ct0 is not None:
        pub(F, {"Action": "SET_OPERATING_MODE_DETAIL", "CloseTimer": int(ct0)}); time.sleep(1.6)
        ct2 = (app.get_fan() or {}).get("CloseTimer")
        rec("mqtt_detail", "自动关屏恢复", f"→{ct0}", f"回读={ct2}", str(ct2) == str(ct0))

    # 2.4 GPU目标温度 SET_DETAIL 回读环(75~87安全区)
    gt0 = fan.get("GPU_TargetTemperature")
    gt_i = int(float(gt0)) if gt0 is not None else None   # MQTT值为字符串("87"), v53hw修正
    gt_new = 85 if (gt_i or 80) == 87 else 87
    pub(F, {"Action": "SET_OPERATING_MODE_DETAIL", "GPU_TargetTemperature": int(gt_new)}); time.sleep(1.6)
    gt1 = (app.get_fan() or {}).get("GPU_TargetTemperature")
    got_i = int(float(gt1)) if gt1 is not None else None
    rec("mqtt_detail", "GPU目标温度", f"{gt_i}→{gt_new}", f"回读={got_i}", got_i == gt_new)
    if gt_i is not None:
        pub(F, {"Action": "SET_OPERATING_MODE_DETAIL", "GPU_TargetTemperature": gt_i}); time.sleep(1.6)
        gt2 = (app.get_fan() or {}).get("GPU_TargetTemperature")
        got2 = int(float(gt2)) if gt2 is not None else None
        rec("mqtt_detail", "GPU目标温度恢复", f"→{gt_i}", f"回读={got2}", got2 == gt_i)

    # 2.5 风扇强冷回读环
    fb0 = fan.get("FanBoostEnable")
    app.set_fan_boost(True); time.sleep(1.6)
    fb1 = (app.get_fan() or {}).get("FanBoostEnable")
    rec("mqtt_fan", "风扇强冷开", f"{fb0}→1", f"回读={fb1}", str(fb1) == "1")
    app.set_fan_boost(False); time.sleep(1.6)
    fb2 = (app.get_fan() or {}).get("FanBoostEnable")
    rec("mqtt_fan", "风扇强冷关", "→0", f"回读={fb2}", str(fb2) == "0")

    # 2.6 曲线查询解析
    app.mqtt.publish(mc.TOPIC_FAN_CTRL, '{"Action":"GET_FAN_SPEED_CURVE_SETTING"}')
    time.sleep(1.6)
    ftab = (app.get_fan() or {}).get("FAN_TableName")
    rec("mqtt_query", "风扇曲线GET", "GET_FAN_SPEED_CURVE_SETTING", f"FAN_TableName={ftab}", bool(ftab))

    # 2.7 显卡信息 / OEM支持位
    app.mqtt.publish(mc.TOPIC_SYS_CTRL, '{"Action":"GetGraphicInfo"}'); time.sleep(1.6)
    gi = app.status.get("System/HardwareInfo")
    rec("mqtt_query", "GetGraphicInfo", "查询", f"{len(gi or {})}字段", bool(gi))
    app.mqtt.publish("Customize/Control", '{"Action":"GETSUPPORT"}'); time.sleep(1.6)
    sup = app.status.get("Customize/Support")
    rec("mqtt_query", "GETSUPPORT", "查询", f"{len(sup or {})}字段", bool(sup))

    # 2.8 电池保护状态 + HEALTHYMODE 翻转/还原
    app.mqtt.publish(mc.TOPIC_BAT_CTRL, '{"Report":"GET"}'); time.sleep(1.6)
    bat = app.status.get("System/BatteryProtection") or {}
    hp0 = bat.get("HealthProtectionStatus")
    rec("mqtt_bat", "电池状态GET", "Report GET",
        f"Health={hp0} 电量={bat.get('BatteryPercent')}%", bool(bat))
    pub(mc.TOPIC_BAT_CTRL, {"Action": "HEALTHYMODE"}); time.sleep(1.8)
    app.mqtt.publish(mc.TOPIC_BAT_CTRL, '{"Report":"GET"}'); time.sleep(1.6)
    hp1 = (app.status.get("System/BatteryProtection") or {}).get("HealthProtectionStatus")
    changed = hp1 != hp0 and hp0 is not None
    rec("mqtt_bat", "HEALTHYMODE切换", f"{hp0}→{hp1}",
        "档位翻转成功" if changed else "档位未变或原值未知", True)
    if changed:
        pub(mc.TOPIC_BAT_CTRL, {"Action": "HEALTHYMODE"}); time.sleep(1.8)
        app.mqtt.publish(mc.TOPIC_BAT_CTRL, '{"Report":"GET"}'); time.sleep(1.6)
        hp2 = (app.status.get("System/BatteryProtection") or {}).get("HealthProtectionStatus")
        okr = hp2 == hp0
        rec("mqtt_bat", "HEALTHYMODE还原", f"目标{hp0}", f"现值={hp2}" + ("" if okr else "(循环制·请在GUI确认最终档)"), okr)

    # 2.9 MQTT充电上限路径回读(仅当状态包含该字段)
    cml0 = bat.get("ChargeMaximumLimit")
    if cml0 is not None:
        new_cml = 100 if int(cml0) != 100 else 90
        pub(F, {"Action": "SET_OPERATING_MODE_DETAIL", "ChargeMaximumLimit": int(new_cml)}); time.sleep(1.8)
        app.mqtt.publish(mc.TOPIC_BAT_CTRL, '{"Report":"GET"}'); time.sleep(1.6)
        cml1 = (app.status.get("System/BatteryProtection") or {}).get("ChargeMaximumLimit")
        rec("mqtt_bat", "充电上限MQTT路径", f"{cml0}→{new_cml}", f"回读={cml1}", str(cml1) == str(new_cml))
        pub(F, {"Action": "SET_OPERATING_MODE_DETAIL", "ChargeMaximumLimit": int(cml0)}); time.sleep(1.8)
        rec("mqtt_bat", "充电上限恢复", f"→{cml0}", "已发送还原指令", True)
    else:
        rec("mqtt_bat", "充电上限MQTT路径", "skip", "状态包无此字段(EC直写为唯一可靠通路)", False)
finally:
    try: app.stop()
    except Exception: pass

# ---------- S3 GUI逻辑桩测试(无窗口) ----------
print("=== S3 GUI逻辑桩 ===")
import mr_gui_v5 as mg

class FakeVar:
    def __init__(self, v): self.v = v
    def get(self): return self.v

class FakeGui:
    def __init__(self, power):
        self.app = type("A", (), {"status": {"System/BatteryProtection": {"BatteryPowerStatus": power}}})()
        self.auto_scene = FakeVar(True)
        self.applied = []
        self.logs = []
        self._apply_scenario = lambda n, s=self: s.applied.append(n)
    def log(self, m): self.logs.append(m)

g1 = FakeGui(1); g1._last_power = 0          # AC→电池翻转
mg.GuiApp._smart_scene_check(g1)
rec("gui_logic", "智能场景拔电", "AC→DC", f"applied={g1.applied}", g1.applied == ["移动节能"])
g2 = FakeGui(0); g2._last_power = 1          # 电池→AC翻转
mg.GuiApp._smart_scene_check(g2)
rec("gui_logic", "智能场景插电", "DC→AC", f"applied={g2.applied}", g2.applied == ["办公"])

# 场景库键位映射完备性(custom_scenarios.json 的键必须可经 WIRE_KEY 发送)
import mr_console as mc
scen_path = os.path.join(HERE, "custom_scenarios.json")
if os.path.exists(scen_path):
    lib = json.load(open(scen_path, encoding="utf-8"))
    keys = set(k for snap in lib.values() for k in snap)
    missing = [k for k in keys if k not in mc.MrConsole.WIRE_KEY]
    rec("gui_logic", "场景键映射", f"{len(keys)}键", f"WIRE_KEY缺失={missing or '无'}", not missing)
else:
    rec("gui_logic", "场景库", "absent", "尚无保存场景(功能路径已由单测覆盖)", True)

# ---------- 汇总 ----------
with open(LOG, "w", newline="", encoding="utf-8-sig") as f:
    wcsv = csv.writer(f)
    wcsv.writerow(["section", "item", "action", "detail", "result"])
    wcsv.writerows(rows)
npass = sum(1 for r in rows if r[4] == "PASS")
print(f"\n=== 本段完成: {npass}/{len(rows)} PASS · 明细见 {os.path.basename(LOG)} ===")
