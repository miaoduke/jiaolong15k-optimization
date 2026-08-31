#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MR Console GUI 自动化穷举点击测试器
方式: 进程内实例化真实GUI → monkeypatch(弹窗/网络=记录模式) → 递归invoke全部按钮
覆盖: 9个标签页 × 全部按钮 × 门控逻辑(拒绝/放行两轮) × 滑条极值
输出: 每按钮结果 + 捕获的全部MQTT载荷 + 异常清单
"""
import sys, time, json, traceback
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as mb

import mr_console as mc
import mr_gui_v5 as mr_gui

# ================= 记录器 =================
PUB = []          # (topic, payload) 捕获的发布
DIALOGS = []      # 弹窗记录
MODE = {"yes": False}   # askyesno 返回值(第一轮False测门控, 第二轮True测放行)

# ---- monkeypatch 弹窗 ----
def _askyesno(*a, **k):
    DIALOGS.append(("askyesno", a[0] if a else ""))
    return MODE["yes"]
def _showinfo(*a, **k):
    DIALOGS.append(("showinfo", a[0] if a else ""))
    return "ok"
def _showwarning(*a, **k):
    DIALOGS.append(("showwarning", a[1] if len(a) > 1 else (a[0] if a else "")))
    return "ok"
def _showerror(*a, **k):
    DIALOGS.append(("showerror", a[0] if a else ""))
    return "ok"
mb.askyesno = _askyesno
mb.showinfo = _showinfo
mb.showwarning = _showwarning
mb.showerror = _showerror

# ================= 构建App(网络=假) =================
class FakeMqtt:
    def __init__(self):
        self.published = []
    def publish(self, t, p):
        self.published.append((t, p)); PUB.append((t, p))
    def subscribe(self, *a): pass
    def close(self): pass

app = mc.MrConsole()
app.start = lambda: None                       # 不连真实broker
app.mqtt = FakeMqtt()
app.request = lambda *a, **k: ({}, 0)          # 查询即时空返回(不等待)
app.get_fan = lambda: dict(mc.MrConsole.WIRE_KEY)  # 返回含全部键的假状态
app.get_setting = lambda: {"WinKey": "WINKEY_STATUS_UNLOCK", "DisplayMode": "DISPLAY_STANDARD_MODE",
                           "TouchpadToggle": "TOUCHPAD_TOGGLE_ON", "SingleColorKBBL": "SINGLE_COLOR_KBBL_STATUS_ON",
                           "NumPad": "NUMPAD_LOCK", "FnKey": "FNKEY_UNLOCK", "OSD": "OSD_HIDDEN_OFF",
                           "AcRecoverySwitch_Status": "ACRECOVERY_TOGGLE_ON"}
app.get_lc = lambda: {}
app.get_battery = lambda: {"BatteryPercent": 88}
app.get_keyboard = lambda: {}
app.get_rgb = lambda: {}
app.get_graphic_info = lambda: {"GraphicInfo": "TEST"}

gui = mr_gui.GuiApp(app)

# ================= 工具 =================
def all_children(w):
    for c in w.winfo_children():
        yield c
        yield from all_children(c)

def sweep_buttons(label):
    """遍历当前Tab全部按钮并invoke, 返回(总数, 异常数, 异常列表)"""
    total = 0; errs = []
    before = len(PUB)
    for w in list(all_children(gui.root)):
        if isinstance(w, ttk.Button):
            txt = w.cget("text")
            total += 1
            try:
                w.invoke()
                gui.root.update()
            except Exception as e:
                errs.append((txt, repr(e)[:120]))
    print(f"  [{label}] 按钮{total}个, 发布{len(PUB)-before}条, 异常{len(errs)}")
    for t, e in errs:
        print(f"      ✗ [{t}] {e}")
    return total, errs

def set_all_sliders(pct):
    for key, (var, cur) in gui.sliders.items():
        # var是IntVar; 找min/max不可得, 用常见范围: 直接设为当前+固定值无意义 → 用key里的topic无范围...
        pass
    # 改为: 遍历Scale控件取from/to
    for w in all_children(gui.root):
        if isinstance(w, ttk.Scale):
            try:
                mx = w.cget("to"); mn = w.cget("from")
                w.set(mn + (mx - mn) * pct)
            except Exception:
                pass
    gui.root.update()

# ================= 主流程 =================
print("="*60)
print(" MR Console GUI 穷举点击自动测试")
print("="*60)
gui.root.update()

tabs = gui.nb.tabs()
print(f"标签页数: {len(tabs)}")

# ---- 第一轮: 全部拒绝(门控测试) MODE.yes=False ----
print("\n───── 第一轮: 门控拒绝(askyesno=False) ─────")
gui.write_enabled.set(False)
gui.research.set(False)
stat = {}
for i, tid in enumerate(tabs):
    gui.nb.select(tid); gui.root.update()
    t, e = sweep_buttons(f"Tab{i}")
    stat[f"tab{i}"] = (t, e)
blocked_pub = len(PUB)
print(f"  第一轮总发布(应≈0): {blocked_pub}")
rec_gate = [d for d in DIALOGS if d[0] == "askyesno"]

# ---- 第二轮: 全部放行 ----
print("\n───── 第二轮: 放行(askyesno=True + 启用写入) ─────")
DIALOGS.clear()
MODE["yes"] = True
gui.write_enabled.set(True)
PUB.clear()
# 滑条推到75%再扫一遍(让滑条类发送带值)
set_all_sliders(0.75)
for i, tid in enumerate(tabs):
    gui.nb.select(tid); gui.root.update()
    sweep_buttons(f"Tab{i}")
print(f"  第二轮总发布: {len(PUB)}")

# ---- 键盘灯效按钮专项(验证SetEffectALL真实格式) ----
print("\n───── 键盘灯效载荷抽检 ─────")
kb = [p for t, p in PUB if t == mc.TOPIC_KB_CTRL]
ok_fmt = 0
for p in kb:
    try:
        d = json.loads(p)
        if d.get("function") in ("SetEffectALL", "SetLightingLevel") and "MqttID" in d:
            ok_fmt += 1
    except Exception:
        pass
print(f"  KB发布{len(kb)}条, function协议格式正确{ok_fmt}条")

# ---- ServCMD格式抽检 ----
serv = [p for t, p in PUB if "ServCMD" in p or '"Action":"FAN_BOOST' in p or '"Action":"OPERATING' in p or '"Action":"DISPLAY' in p or '"Action":"SET_OPERATING_MODE_DETAIL' in p]
print(f"  ServCMD/OPERATING/DISPLAY/DETAIL格式: {len(serv)}条")

# ---- 汇总 ----
total_btn = sum(v[0] for v in stat.values())
total_err = sum(len(v[1]) for v in stat.values())
print("\n" + "="*60)
print(f"  按钮总数: {total_btn} | 异常: {total_err} | 弹窗拦截记录: {len(rec_gate)}")
print(f"  捕获发布总数(第二轮): {len(PUB)}")
uniq_topics = sorted(set(t for t, _ in PUB))
print(f"  覆盖Topic: {uniq_topics}")
print(f"  通过率: {(total_btn-total_err)/total_btn*100:.0f}%" if total_btn else "无按钮")

# 保存载荷库供人工审阅
with open(r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\GUI穷举点击_捕获载荷_v52.json", "w", encoding="utf-8") as f:
    json.dump([{"topic": t, "payload": p} for t, p in PUB], f, ensure_ascii=False, indent=1)
print("  载荷已存: GUI穷举点击_捕获载荷_v52.json")

gui.root.destroy()


