#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_forensic.py — 历史失败项法证复测(全部操作带恢复)
F0 电源漂移归因 · F1 EC实例普查 · F2 MQTT全量差分法证(GETSUPPORT/健康三档盲点/
充电上限官方路径/DynamicBoost双拼写/CloseTimer回声/键盘亮度回声/GPU目标温度OC门控)
· F3 GPU功耗墙下调实验 · F4 稳定性30查分类"""
import json, os, re, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = {}
def sec(n): print(f"\n=== {n} ===")

# ---------- F0 电源漂移归因 ----------
sec("F0 电源漂移归因")
def run_ps(c):
    r = subprocess.run(["powershell","-NoProfile","-Command",c], capture_output=True,
                       text=True, errors="replace", timeout=30)
    return (r.stdout or "").strip()
scheme = run_ps("powercfg /getactivescheme")
print(scheme)
OUT["active_scheme"] = scheme
import mr_win_ctrl as wc
for name, g in [("高性能", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"),
                ("平衡", "381b4222-f694-41f0-9685-ff5bb260df2e")]:
    ok, out = wc._run(["powercfg","/qh",g,"54533251-82be-4824-96c1-47b60b740d00",
                       "36687f9e-e3a5-4dbf-b1dc-15eb381c6863"])
    hx = re.findall(r"0x[0-9a-fA-F]+", out or "")
    epp = {"ac": int(hx[-2],16), "dc": int(hx[-1],16)} if len(hx) >= 2 else None
    OUT[f"epp_{name}"] = epp
    print(f"EPP@{name}: {epp}")

# ---------- F1 EC实例普查 ----------
sec("F1 EC WMI 实例普查")
ps = ("Get-CimClass -Namespace root/wmi | Where-Object {$_.CimClassName -match 'Acpi|Test'} "
      "| Select-Object -ExpandProperty CimClassName")
OUT["wmi_acpi_classes"] = run_ps(ps).splitlines()
print("Acpi/Test类:", OUT["wmi_acpi_classes"][:10])
ps2 = ("Get-PnpDevice | Where-Object {$_.InstanceId -match 'PNP0C14'} "
       "| ForEach-Object { $_.InstanceId + ' | ' + $_.Status }")
OUT["pnp0c14"] = run_ps(ps2).splitlines()
print("PNP0C14(WMI缓冲设备):", OUT["pnp0c14"])

# ---------- F2 MQTT 法证 ----------
sec("F2 MQTT 全量差分法证")
import mr_console as mc
app = mc.MrConsole()
snap = {}
def snapshot():
    snap.clear(); snap.update({k: json.dumps(v, sort_keys=True, ensure_ascii=False)
                               for k, v in app.status.items()})
def diff(tag):
    newk = [k for k in app.status if k not in snap]
    chg = [k for k in snap if k in app.status and
           json.dumps(app.status[k], sort_keys=True, ensure_ascii=False) != snap[k]]
    d = {"new_topics": newk, "changed": chg}
    OUT.setdefault("diffs", {})[tag] = d
    print(f"  [{tag}] 新主题={newk or '-'} 变化={chg or '-'}")
    return d

try:
    app.start(); time.sleep(1.2)
    F, S, B = mc.TOPIC_FAN_CTRL, mc.TOPIC_SET_CTRL, mc.TOPIC_BAT_CTRL
    def pub(t, p): app.mqtt.publish(t, json.dumps(p))
    def wait(s=1.6): time.sleep(s)

    # 2.1 GETSUPPORT 回包主题定位
    snapshot(); app.get_support(); wait(1.5); d = diff("GETSUPPORT")
    sup_topic = d["new_topics"][0] if d["new_topics"] else None
    OUT["getsupport_reply_topic"] = sup_topic
    if sup_topic: OUT["getsupport_data_sample"] = str(app.status[sup_topic])[:200]

    # 2.2 电池基线
    pub(B, {"Report":"GET"}); wait(1.6)
    bat0 = dict(app.status.get("System/BatteryProtection") or {})
    hp_orig = bat0.get("HealthProtectionStatus")
    OUT["battery_baseline"] = bat0
    print("电池基线:", {k: bat0.get(k) for k in ("HealthProtectionStatus","BatteryPercent")})

    # 2.3 健康三档参数矩阵
    variants = [
        ("HealthType1",  B, {"Action":"HEALTHYMODE","HealthType":1}),
        ("HealthType3",  B, {"Action":"HEALTHYMODE","HealthType":3}),
        ("SetStatus1",   B, {"Action":"SET","HealthProtectionStatus":1}),
        ("SetStatus3",   B, {"Action":"SET","HealthProtectionStatus":3}),
        ("Detail3",      F, {"Action":"SET_OPERATING_MODE_DETAIL","HealthProtectionStatus":3}),
    ]
    res = {}
    for tag, t, pld in variants:
        pub(t, pld); wait(1.8)
        pub(B, {"Report":"GET"}); wait(1.4)
        hp = (app.status.get("System/BatteryProtection") or {}).get("HealthProtectionStatus")
        res[tag] = hp
        print(f"  健康档尝试 {tag}: →{hp}")
    OUT["healthmode_matrix"] = res
    # 还原
    restored = None
    for tag, t, pld in variants:
        want = f"{hp_orig}"
        cur = res.get(tag)
    if hp_orig is not None and str(hp_orig) != "2":
        pub(B, {"Action":"SET","HealthProtectionStatus":hp_orig}); wait(1.6)
    elif str(res.get("Detail3")) != str(hp_orig):
        pass
    pub(B, {"Report":"GET"}); wait(1.4)
    OUT["health_restored"] = (app.status.get("System/BatteryProtection") or {}).get("HealthProtectionStatus")

    # 2.4 充电上限官方MQTT路径(主文档#38: BatteryProtection SET)
    cml0 = bat0.get("ChargeMaximumLimit")
    snapshot()
    pub(B, {"Action":"SET","ChargeMaximumLimit":90}); wait(2.0)
    diff("charge_set90")
    pub(B, {"Report":"GET"}); wait(1.5)
    b1 = app.status.get("System/BatteryProtection") or {}
    OUT["charge_mqtt_path"] = {"before": cml0, "keys_now": sorted(b1.keys()),
                               "ChargeMaximumLimit": b1.get("ChargeMaximumLimit"),
                               "any90": any(str(v)=="90" for v in b1.values())}
    print("充电上限官方路径:", {k: OUT["charge_mqtt_path"][k] for k in ("before","ChargeMaximumLimit","any90")})
    pub(B, {"Action":"SET","ChargeMaximumLimit":100}); wait(1.6)

    # 2.5 DynamicBoost 双拼写 + 全字典diff
    fan0 = app.get_fan() or {}
    snapshot(); app.get_fan()
    pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","GpuDynamicBoost":15}); wait(2.0)
    d1 = app.get_fan() or {}; diff("dynboost_camel")
    pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","GPU_DynamicBoost":20}); wait(2.0)
    d2 = app.get_fan() or {}; diff("dynboost_UPPER")
    keys_changed = {k: (fan0.get(k), d2.get(k)) for k in d2
                    if k not in ("ProfileName",) and str(d2.get(k)) != str(fan0.get(k))
                    and ("Boost" in k or "Dynamic" in k)}
    OUT["dynboost_key_probe"] = keys_changed
    print("DynamicBoost相关键变化:", keys_changed or "无")
    if fan0.get("GPU_DynamicBoost") is not None:
        pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","GPU_DynamicBoost":int(float(fan0["GPU_DynamicBoost"]))}); wait(1.6)

    # 2.6 CloseTimer 回声搜索
    snapshot(); app.get_fan()
    pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","CloseTimer":15}); wait(2.0)
    app.get_fan(); app.get_setting(); wait(1.0)
    d = diff("closetimer15")
    hits = {}
    for k in set(list(d["new_topics"]) + list(d["changed"])):
        v = app.status.get(k)
        if isinstance(v, dict):
            for kk, vv in v.items():
                if str(vv) == "15": hits[f"{k}/{kk}"] = vv
    OUT["closetimer_echo"] = hits
    print("CloseTimer=15 回声位置:", hits or "无(确认盲写)")
    ct0 = None
    # 恢复: 发0(永不)
    pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","CloseTimer":0}); wait(1.5)

    # 2.7 键盘亮度 level3 回声搜索(function协议)
    snapshot(); app.get_keyboard()
    app.mqtt.publish(mc.TOPIC_KB_CTRL, json.dumps(
        {"MqttID": None, "function": "SetLightingLevel", "level": 3}))
    wait(2.0)
    app.get_keyboard(); wait(0.8)
    d = diff("kblevel3")
    hits = {}
    for k in set(list(d["new_topics"]) + list(d["changed"])):
        v = app.status.get(k)
        if isinstance(v, dict):
            for kk, vv in v.items():
                if "ight" in kk or "LED" in kk.upper(): hits[f"{k}/{kk}"] = vv
    OUT["kb_level_echo"] = hits
    print("键盘亮度回声候选:", hits or "无(确认盲写)")

    # 2.8 GPU目标温度 OC门控假设
    oc = (app.get_fan() or {}).get("OverClockingSwitch")
    gt0 = (app.get_fan() or {}).get("GPU_TargetTemperature")
    seq = []
    if str(oc) != "1":
        pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","OverClockingSwitch":1}); wait(2.0)
        seq.append(("oc_on", (app.get_fan() or {}).get("OverClockingSwitch")))
    pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","GPU_TargetTemperature":83}); wait(2.0)
    gt1 = (app.get_fan() or {}).get("GPU_TargetTemperature")
    seq.append(("gt83", gt1))
    OUT["target_temp_oc_gated"] = {"oc_before": oc, "steps": seq}
    print("目标温度OC门控测试:", OUT["target_temp_oc_gated"])
    # 还原
    pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","GPU_TargetTemperature":int(float(gt0 or 87))}); wait(1.6)
    if str(oc) != "1" and oc is not None:
        pub(F, {"Action":"SET_OPERATING_MODE_DETAIL","OverClockingSwitch":int(oc)}); wait(1.6)

finally:
    try: app.stop()
    except Exception: pass

# ---------- F3 GPU功耗墙下调实验 ----------
sec("F3 GPU功耗墙下调(-pl 100?)")
ok100, dt100 = wc.gpu_wall_set(100)
time.sleep(0.5)
mid = wc.gpu_wall_get()
r115, _ = wc.gpu_wall_set(115)
time.sleep(0.5)
OUT["wall_down_test"] = {"set100_ok": ok100, "mid": mid, "detail": dt100, "final": wc.gpu_wall_get()}
print(json.dumps(OUT["wall_down_test"], ensure_ascii=False))

# ---------- F4 稳定性30查分类 ----------
sec("F4 连续查询稳定性分类")
# 用独立连接做稳定性(避免上面已stop的app)
lat, fails = [], []
app2 = mc.MrConsole()
def _f():
    return app2.get_fan()
app2.start(); time.sleep(1.0)
try:
    okn = 0
    for i in range(30):
        t0 = time.time()
        f = _f()
        dtms = int((time.time()-t0)*1000)
        good = bool(f) and f.get("OperatingMode") is not None
        okn += good
        lat.append(dtms)
        if not good: fails.append({"i": i, "ms": dtms, "keys": len(f or {})})
        time.sleep(0.25)
    OUT["stability"] = {"ok": okn, "total": 30,
                        "lat_ms": {"min": min(lat), "max": max(lat),
                                   "avg": sum(lat)//len(lat)}, "fails": fails[:6]}
finally:
    app2.stop()
print(json.dumps(OUT["stability"], ensure_ascii=False))

json.dump(OUT, open(os.path.join(HERE, "_forensic_out.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n=== 法证完成 → _forensic_out.json ===")
