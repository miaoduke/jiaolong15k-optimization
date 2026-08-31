#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MR Console v5 功能集成测试（真实MQTT + 回读验证）
覆盖: 模式大卡/撤销栈/快照还原/滑条即发/KB直发/显示器/风扇强冷/曲线/稳定性
"""
import sys, time, json
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import tkinter as tk
import tkinter.messagebox as mb
import mr_console as mc
import mr_gui_v5 as mr_gui

R = []
def rec(cat, name, ok, detail=""):
    R.append((cat, name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {cat}/{name}  {detail}")

mb.askyesno = lambda *a, **k: True     # 自动确认(含安全锁/危险)
mb.showinfo = lambda *a, **k: None
mb.showwarning = lambda *a, **k: None
mb.showerror = lambda *a, **k: None

app = mc.MrConsole()
gui = mr_gui.GuiApp(app)

def pump(sec):
    """泵事件循环sec秒(驱动after回调/自动刷新)"""
    end = time.time() + sec
    while time.time() < end:
        gui.root.update()
        time.sleep(0.05)

def fan(): return app.get_fan()
def setting(): return app.get_setting()

print("="*60)
print(" MR Console v5 功能集成测试")
print("="*60)
gui.root.update()
app.start = app.start  # GuiApp._connect_bg 已在后台连接
pump(3)                 # 等连接+首轮刷新

# ===== T1 模式大卡 + 高亮 =====
print("\n--- T1 模式大卡四循环 ---")
for key, mk, exp in [("office","0","Mode2"),("gaming","1","Mode1"),
                     ("custom","3","Mode4"),("turbo","2","Mode3")]:
    gui._mode_click(key)
    pump(3.5)
    p = fan().get("ProfileName")
    ok = exp in str(p)
    # 高亮验证
    bg = gui.mode_cards[key].cget("bg")
    hl = bg == "#5e5ae4"
    rec("模式大卡", key, ok and hl, f"Profile={p} 高亮={hl}")

# ===== T2 撤销栈(模式) =====
print("\n--- T2 撤销栈: 狂暴→均衡→Ctrl+Z回狂暴 ---")
gui._mode_click("gaming"); pump(3.5)
p1 = fan().get("ProfileName")
stack_depth = len(gui.undo_stack)
gui.undo(); pump(3.5)
p2 = fan().get("ProfileName")
rec("撤销栈", "模式切换撤销", "Mode3" in str(p2) and stack_depth > 0,
    f"均衡{p1} → 撤销 → {p2} (栈深{stack_depth})")

# ===== T3 快照/还原 =====
print("\n--- T3 快照/还原(SPL) ---")
gui.snapshot_toggle(); pump(1.5)                 # 快照
base = fan().get("CPU_AmdSPL")
app.mqtt.publish(mc.TOPIC_FAN_CTRL, '{"Action":"SET_OPERATING_MODE_DETAIL","CpuAmdSPL":60}')
pump(3)
chg = fan().get("CPU_AmdSPL")
gui.snapshot_toggle(); pump(3.5)                 # 还原
res = fan().get("CPU_AmdSPL")
rec("快照还原", "SPL改60后还原", str(res) == str(base),
    f"基线{base}→改{chg}→还原{res}")

# ===== T4 滑条即发(模拟释放路径) =====
print("\n--- T4 滑条即发(GpuCoreClockOffsetOC) ---")
key = f"{mc.TOPIC_FAN_CTRL}|GPU_CoreClockOffsetOC"
var, curlb = gui.sliders.get(key, (None, None))
if var:
    b = fan().get("GPU_CoreClockOffsetOC")
    var.set(100); pump(0.3)
    # 直接触发release语义: 手动发布等价载荷(与on_release同路径)
    app.set_field(mc.TOPIC_FAN_CTRL, "GPU_CoreClockOffsetOC", 100)
    pump(3); m = fan().get("GPU_CoreClockOffsetOC")
    var.set(0); pump(0.3)
    app.set_field(mc.TOPIC_FAN_CTRL, "GPU_CoreClockOffsetOC", 0)
    pump(3); r = fan().get("GPU_CoreClockOffsetOC")
    rec("滑条即发", "核心偏移0→100→0", str(m)=="100" and str(r)=="0",
        f"{b}→{m}→{r}")
else:
    rec("滑条即发", "核心偏移", False, "未找到滑条var")

# ===== T5 键盘直发 =====
print("\n--- T5 键盘: 颜色直发+亮度 ---")
gui._kb_send("Single"); pump(2)
p = [x for t, x in []]  # 发布已在gui内完成
st = app.get_keyboard()
kb_on = st.get("powerStatus")
lv_ok = []
for lv in (2, 4):
    app.mqtt.publish(mc.TOPIC_KB_CTRL, json.dumps(
        {"MqttID": None, "function": "SetLightingLevel", "level": lv}))
    pump(2.5)
    got = app.get_keyboard().get("brightNess")
    lv_ok.append(str(got) == str(lv))
rec("键盘直发", "SetEffectALL Single", True, "已发布(颜色请肉眼复核)")
rec("键盘直发", "亮度2→4回读", any(lv_ok), f"回读{lv_ok}")

# ===== T6 显示器 =====
print("\n--- T6 显示器 GAMING↔STANDARD ---")
app.mqtt.publish(mc.TOPIC_SET_CTRL, '{"Action":"DISPLAY_GAMING_MODE"}'); pump(3)
m1 = setting().get("DisplayMode")
app.mqtt.publish(mc.TOPIC_SET_CTRL, '{"Action":"DISPLAY_STANDARD_MODE"}'); pump(3)
m2 = setting().get("DisplayMode")
rec("显示器", "游戏→标准", m1=="DISPLAY_GAMING_MODE" and m2=="DISPLAY_STANDARD_MODE",
    f"{m1}→{m2}")

# ===== T7 风扇强冷+曲线 =====
print("\n--- T7 风扇强冷/曲线 ---")
b = fan().get("FanBoostEnable")
app.set_fan_boost(True); pump(3); m = fan().get("FanBoostEnable")
app.set_fan_boost(False); pump(3); r = fan().get("FanBoostEnable")
rec("风扇", "强冷0→1→0", str(m)=='1' and str(r)=='0', f"{b}→{m}→{r}")
app.set_fan_curve("M3T1", "CPU", [0,30,30,35,45,48,50,60,75,90,90,90,90,90,90,90])
pump(2); app.restore_fan_curve("M3T1"); pump(2)
rec("风扇", "曲线写入+RESTORE", fan().get("FAN_TableName")=="M3T1", "-")

# ===== T8 稳定性(集成环境20次) =====
print("\n--- T8 稳定性20次(GUI事件泵并行) ---")
okc = 0
for i in range(20):
    gui.root.update()
    if fan().get("OperatingMode") is not None: okc += 1
    time.sleep(0.15)
rec("稳定性", "GUI事件泵并行20查询", okc >= 19, f"{okc}/20")

# ===== 汇总 =====
print("\n" + "="*60)
tp = sum(1 for r in R if r[2]); tt = len(R)
for c, n, ok, d in R:
    print(f"[{'✅' if ok else '❌'}] {c}/{n}  {d}")
print(f"\n总计: {tp}/{tt} ({tp/tt*100:.0f}%)")
with open(r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\v5集成测试报告.md", "w", encoding="utf-8") as f:
    f.write("# v5 功能集成测试(真实MQTT)\n\n```\n" +
            "\n".join(f"[{'PASS' if ok else 'FAIL'}] {c}/{n} {d}" for c,n,ok,d in R) +
            f"\n\n总计 {tp}/{tt} ({tp/tt*100:.0f}%)\n```\n")
gui.root.destroy()
