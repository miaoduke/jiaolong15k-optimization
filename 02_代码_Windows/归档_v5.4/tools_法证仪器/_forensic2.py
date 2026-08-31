#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_forensic2.py — 补刀三案: PL1钳制真伪 / AcpiTest各类实例 / 目标温度模式门控"""
import json, os, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = {}
def sec(n): print(f"\n=== {n} ===")

# ---------- A. PL1=200 钳制真伪(安全关键) ----------
sec("A. PL1越界钳制复测(3次采样)")
import mr_console as mc
import mr_win_ctrl as wc
app = mc.MrConsole()
F = mc.TOPIC_FAN_CTRL
def pub(p): app.mqtt.publish(F, json.dumps(p))
try:
    app.start(); time.sleep(1.2)
    p0 = (app.get_fan() or {}).get("CPU_PL1")
    samples = []
    for i in range(3):
        pub({"Action":"SET_OPERATING_MODE_DETAIL","PL1":200}); time.sleep(2.2)
        v = (app.get_fan() or {}).get("CPU_PL1")
        samples.append(v)
        pub({"Action":"SET_OPERATING_MODE_DETAIL","CPU_PL1":p0}); time.sleep(1.8)  # 每轮都拉回
        v2 = (app.get_fan() or {}).get("CPU_PL1")
        samples.append(f"restore={v2}")
    OUT["pl1_200_test"] = {"orig": p0, "samples": samples}
    print("原值:", p0, "| 序列:", samples)
finally:
    try: app.stop()
    except Exception: pass

# ---------- B. AcpiTest 各类实例与方法普查 ----------
sec("B. AcpiTest* 类实例普查")
ps = r'''
$classes = Get-CimClass -Namespace root/wmi | Where-Object {$_.CimClassName -match '^AcpiTest'} 
$r = @{}
foreach ($c in $classes) {
  $inst = Get-CimInstance -Namespace root/wmi -ClassName $c.CimClassName -ErrorAction SilentlyContinue
  $r[$c.CimClassName] = @{
    count = @($inst).Count
    inst  = @($inst | ForEach-Object { $_.InstanceName })
    methods = @($c.CimClass.CimClassMethods.Name)
  }
}
$r | ConvertTo-Json -Depth 4
'''
r = subprocess.run(["powershell","-NoProfile","-Command",ps], capture_output=True,
                   text=True, errors="replace", timeout=40)
try:
    OUT["acpitest"] = json.loads(r.stdout or "{}")
    for k, v in OUT["acpitest"].items():
        if isinstance(v, dict) and v.get("count"):
            print(f"  {k}: n={v['count']} inst={v['inst']} methods={v['methods']}")
    dead = [k for k,v in OUT["acpitest"].items() if isinstance(v,dict) and not v.get("count")]
    print("  零实例类:", dead)
except Exception as e:
    OUT["acpitest_raw"] = (r.stdout or "")[:400]
    print("parse fail:", e)

# ---------- C. 目标温度·办公模式门控 ----------
sec("C. GPU目标温度@办公模式")
app = mc.MrConsole()
try:
    app.start(); time.sleep(1.2)
    m0 = str((app.status.get("Tray/Status") or {}).get("OperatingMode") or "")
    gt0 = (app.get_fan() or {}).get("GPU_TargetTemperature")
    # 切办公
    app.set_mode("office"); time.sleep(2.5)
    gt_o = None
    pub_r = app.mqtt.publish(F, json.dumps({"Action":"SET_OPERATING_MODE_DETAIL","GPU_TargetTemperature":83}))
    time.sleep(2.2)
    gt_o = (app.get_fan() or {}).get("GPU_TargetTemperature")
    print(f"原模式{m0} 温度{gt0} → 办公模式写83 → {gt_o}")
    OUT["target_temp_office"] = {"mode0": m0, "gt0": gt0, "gt_office_write83": gt_o}
    # 还原温度与模式(切回turbo若原是2, 否则按原值)
    pub({"Action":"SET_OPERATING_MODE_DETAIL","GPU_TargetTemperature":int(float(gt0 or 87))}); time.sleep(1.6)
    back = {"office":"gaming","gaming":"gaming","turbo":"turbo","custom":"custom"}.get(m0, "gaming")
    app.set_mode(back); time.sleep(2.0)
    OUT["target_temp_office"]["restored_mode"] = back
finally:
    try: app.stop()
    except Exception: pass

json.dump(OUT, open(os.path.join(HERE,"_forensic2_out.json"),"w",encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n=== 补刀完成 ===")
