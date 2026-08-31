#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MR Console GUI v5 — 依据《GUI布局科学性调研方案》重构
核心升级:
  1. 总览仪表卡(模式/CPU/GPU/风扇/电池) + 模式大卡直点
  2. 性能中心 = 模式+OC滑条(释放即发)+风扇强冷+曲线工具 合一页
  3. 灯光页内直发(消灭跨页3步): 26灯效/颜色选择/亮度滑条
  4. 外设独立页(唯一入口, ServCMD实证实现) — 消灭6处双入口
  5. 全局撤销栈(Ctrl+Z / ↩按钮) + 会话快照/一键还原
  6. 滑条 ButtonRelease 即发; 危险指令双确认; 双层安全锁保留
"""
import json
import os
import subprocess
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

import mr_console as mc
import mr_win_ctrl as wc          # v5.4 新增: Windows原生电源/显示/系统控制层(W4-W8/W12/W15-W19)

REFRESH_MS = 5000
S = mc.TOPIC_SET_CTRL
F = mc.TOPIC_FAN_CTRL
KB = mc.TOPIC_KB_CTRL
BAT = mc.TOPIC_BAT_CTRL

# ================= 字段注释库(89条, 沿用) =================
FIELD_DOC = {
    "OperatingMode": ("当前性能档位", "0办公/1均衡/2狂暴/3自定义", "切狂暴=性能↑风扇↑"),
    "ProfileName": ("生效的配置文件", "Mode{档}_Profile{n}", "-"),
    "OverClockingSwitch": ("超频总开关", "1=开 0=关", "开后OC参数才生效"),
    "TurboModeOption": ("狂暴子档", "1~4(默认2)", "↑=更激进"),
    "PowerMode": ("Windows电源方案", "1平衡", "-"),
    "CPU_PL1": ("CPU持续功耗墙(W)", "本机10~80, 原厂80", "↑性能↑温度↑风扇"),
    "CPU_PL2": ("CPU短时爆发墙(W)", "本机10~80", "同上"),
    "CPU_PL4": ("CPU瞬时峰值(W)", "本机10~100", "毫秒级冲刺"),
    "CPU_PL1Maximum": ("PL1硬件上限", "80", "UI提示值"),
    "CPU_PL2Maximum": ("PL2上限", "80", "-"),
    "CPU_PL4Maximum": ("PL4上限", "100", "-"),
    "CPU_TccOffset": ("CPU温度墙(°C)", "原厂99~100", "↓=提前降频降温"),
    "CPU_TccOffsetSwitch": ("自定义温度墙开关", "0/1", "-"),
    "CPU_OffsetCoreVoltage": ("核心电压偏移(mV)", "Intel专属,AMD恒0", "负=降压(本机不可用)"),
    "CPU_AmdSPL": ("AMD长时功耗(W)", "≤80", "↑性能↑热"),
    "CPU_AmdSPPT": ("AMD短时功耗(W)", "≤80", "-"),
    "CPU_AmdFPPT": ("AMD峰值功耗(W)", "≤100", "-"),
    "CPU_AmdTccTarget": ("AMD温度目标(°C)", "92~99", "↓降温"),
    "CPU_AmdOverClockSupport": ("AMD超频支持", "0=SMU锁死", "终局"),
    "GPU_CoreClockOffsetOC": ("GPU核心偏移(MHz)", "0~+250", "↑帧率↑功耗"),
    "GPU_MemoryClockOffsetOC": ("显存偏移(MHz)", "±1000(HWOC±1800)", "-"),
    "GPU_TargetTemperature": ("GPU目标温度(°C)", "75~87", "↓=更早降频·实测87钉死向下不可调"),
    "GPU_ConfigurableTGPTarget": ("TGP功耗(W)", "本机115锁死", "-"),
    "GPU_DynamicBoostSwitch": ("DynamicBoost开关", "0/1", "自动挪功率"),
    "GPU_DynamicBoost": ("动态增强量(W)", "5~25自动", "-"),
    "CustomTGPinGCUforGN21_Value": ("隐藏cTGP(GN21)", "-", "研究"),
    "MEM_MemoryOverClockSupport": ("内存OC支持", "0=不支持", "-"),
    "FAN_TableName": ("风扇曲线表", "M{档}T{表}", "-"),
    "FAN_FanSwitchSpeedEnabled": ("起转控制开关", "0/1", "-"),
    "FAN_FanSwitchSpeed": ("起转转速(RPM)", "原厂300", "↑低载噪音"),
    "FAN_SafetyProtect": ("安全保护", "0正常", "1=已触发"),
    "FanBoostEnable": ("风扇强冷", "0/1", "ServCMD可绕过无按钮限制"),
    "WinKey": ("Win键锁", "LOCK游戏防误触", "-"),
    "OSD": ("屏幕悬浮OSD", "OFF隐藏", "-"),
    "DisplayFeatureStatus": ("显示增强总开关", "OFF=原生", "-"),
    "DisplayMode": ("画面模式", "STANDARD标准", "GAMING鲜艳/READ护眼"),
    "GamingBrightness": ("游戏亮度", "0~100", "↑亮"),
    "GamingColorTemp": ("色温", "↑偏冷↓偏暖", "-"),
    "GamingContrast": ("对比度", "0默认", "-"),
    "SingleColorKBBL": ("键盘灯电源", "ON/OFF", "-"),
    "CloseTimer": ("自动关屏(分)", "0=永不", "-"),
    "NumPad": ("小键盘", "LOCK/UNLOCK", "-"),
    "FnKey": ("Fn交换", "UNLOCK常规", "-"),
    "TouchpadToggle": ("触控板", "ON/OFF", "-"),
    "AcRecoverySwitch_Status": ("断电恢复来电自启", "ON=来电开机", "-"),
    "BatteryPercent": ("电量%", "0~100", "-"),
    "HealthProtectionStatus": ("健康保护档", "2=均衡", "-"),
    "BatteryAbnormal": ("电池异常", "0正常", "1=送检"),
}

RGB_EFFECTS = [
    ("Single 单色", "Single", "✅"), ("Breathing 呼吸", "Breathing", "✅"),
    ("Rainbow 彩虹", "Rainbow", "✅"), ("Reactive 星光", "Reactive", "⚠️"),
    ("Wave 波浪", "Wave", "✅实测"), ("UserMode 自定义", "UserMode", "✅"),
    ("Gaming 游戏", "Gaming", "✅"), ("BatteryPercent 电量", "BatteryPercent", "✅"),
    ("Ripple 涟漪", "Ripple", "⚠️多区"), ("Raindrop 雨滴", "Raindrop", "⚠️"),
    ("Neon 霓虹", "Neon", "⚠️"), ("Marquee 贪吃蛇", "Marquee", "⚠️"),
    ("Stack 堆叠", "Stack", "⚠️多区"), ("Impact 冲击", "Impact", "⚠️"),
    ("Spark 火花", "Spark", "⚠️"), ("Music 音乐", "Music", "⚠️需0x76F"),
    ("Flash 闪烁", "Flash", "⚠️"), ("Mix 混合", "Mix", "⚠️多区"),
    ("RippleO 反涟漪", "RippleO", "⚠️多区"), ("Alphabet 字母", "Alphabet", "⚠️"),
    ("StarHitting 星击", "StarHitting", "⚠️"), ("StarSpark 星火", "StarSpark", "⚠️"),
    ("Thinking 思考", "Thinking", "⚠️"), ("Manual 逐键", "Manual", "⚠️HID"),
    ("ColorfulWave 彩浪", "ColorfulWave", "⚠️多区"), ("Dawn 黎明", "Dawn", "⚠️"),
]
DISPLAY_MODES = ["DISPLAY_STANDARD_MODE", "DISPLAY_GAMING_MODE", "DISPLAY_VIDEO_MODE",
                 "DISPLAY_READ_MODE", "DISPLAY_CUSTOMIZED_MODE"]
BATTERY_ACTIONS = [("健康模式", {"Action": "HEALTHYMODE"})]


def doc_line(k, v):
    vs = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    base = f"  {k:<34} = {vs[:60]}"
    d = FIELD_DOC.get(k)
    if d:
        return f"{base}\n      └ {d[0]} | 参考: {d[1]} | {d[2]}"
    return base


class GuiApp:
    MODE_KEY = {"0": "office", "1": "gaming", "2": "turbo", "3": "custom"}
    MODE_CN = {"0": "办公", "1": "均衡", "2": "狂暴", "3": "自定义"}

    def __init__(self, app):
        self.app = app
        self.q = queue.Queue()
        self.undo_stack = []          # (kind, topic, key, old_value)
        self.snapshot = None
        self._debounce = {}
        self._build_root()
        self.write_enabled = tk.BooleanVar(value=False)
        self.research = tk.BooleanVar(value=False)
        self.auto = tk.BooleanVar(value=True)
        self.mode_var = tk.StringVar(value="")
        self.replay_name = tk.StringVar()
        self.manual_topic = tk.StringVar(value="Fan/Control")
        self.manual_payload = tk.StringVar(value='{"Action":"GETSTATUS"}')
        self.kb_r = tk.IntVar(value=0); self.kb_g = tk.IntVar(value=255); self.kb_b = tk.IntVar(value=0)
        self.kb_effect = tk.StringVar(value="Wave")
        self.sliders = {}; self.toggles = {}; self._touch = {}
        self._build_widgets()
        self._connect_bg()
        self.root.after(300, self._poll)
        self.root.after(900, self.refresh_all)

    def log(self, m): self.q.put(("log", f"[{time.strftime('%H:%M:%S')}] {m}\n"))
    def cap(self, m): self.q.put(("capture", m + "\n"))

    def _connect_bg(self):
        def worker():
            try:
                self.app.start()
                self.q.put(("conn", ("ok", "已连接 MQTT 13688 (PluginClient_5)")))
            except Exception as e:
                self.q.put(("conn", ("fail", f"连接失败: {e}")))
        threading.Thread(target=worker, daemon=True).start()

    # ================= 构建 =================
    def _build_root(self):
        self.root = tk.Tk(); self.root.withdraw()

    def _build_widgets(self):
        r = self.root
        r.title("MR Console v5.4 · 机械革命电竞控制台")
        r.geometry("1180x780")
        # 顶栏
        top = ttk.Frame(r); top.pack(fill="x", padx=12, pady=(8, 2))
        ttk.Label(top, text="MR Console", font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        self.conn_lbl = tk.Label(top, text="● 连接中...", fg="#c08000"); self.conn_lbl.pack(side="left", padx=14)
        self.hint_lbl = tk.Label(r, text="💡 悬停参数名查看说明", fg="#5e5ae4",
                                 font=("Microsoft YaHei UI", 8), anchor="w")
        self.hint_lbl.pack(fill="x", padx=14)
        self.undo_lbl = tk.Label(top, text="", fg="#666"); self.undo_lbl.pack(side="left")
        ttk.Button(top, text="↩撤销", width=6, command=self.undo).pack(side="right", padx=4)
        ttk.Button(top, text="📸快照/还原", width=12, command=self.snapshot_toggle).pack(side="right", padx=4)
        ttk.Checkbutton(top, text="自动刷新5s", variable=self.auto).pack(side="right")
        self.write_chk = tk.Checkbutton(top, text="✍ 启用写入(只读模式)", variable=self.write_enabled,
                                        font=("Microsoft YaHei UI", 10, "bold"), fg="#1a7f37")
        self.write_chk.pack(side="right", padx=8)
        self.write_enabled.trace_add("write", self._write_state)
        self.root.bind("<Control-z>", lambda e: self.undo())

        self.nb = nb = ttk.Notebook(r); nb.pack(fill="both", expand=True, padx=6, pady=4)
        self._tab_home(nb); self._tab_perf(nb); self._tab_fan(nb)
        self._tab_kb(nb); self._tab_display(nb); self._tab_battery(nb)
        self._tab_powersys(nb)   # v5.4 新增页
        self._tab_periph(nb); self._tab_learn(nb); self._tab_research(nb)
        self._tab_log(nb)

    # ---------- 通用行(即时应用) ----------
    def _slider_instant(self, parent, label, status_key, mn, mx, sup="✅", unit="",
                        def_val=None):
        """滑条: 释放即发 + 悬停说明 + 状态值同步 + 可选[默认]钮"""
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        color = "#b00020" if sup.startswith("⛔") else ("#b26a00" if sup.startswith("⚠") else "#1a1a1a")
        lab = ttk.Label(fr, text=f"{sup} {label}", width=30, foreground=color)
        lab.pack(side="left")
        doc = FIELD_DOC.get(status_key)
        help_txt = f"{label} | 是什么: {doc[0]} | 参考: {doc[1]} | {doc[2]}" if doc else f"{label}"
        lab.bind("<Enter>", lambda e: self.hint_lbl.config(text=help_txt))
        lab.bind("<Leave>", lambda e: self.hint_lbl.config(text=""))
        var = tk.IntVar(value=def_val if def_val is not None else mn)
        sc = ttk.Scale(fr, from_=mn, to=mx, orient="horizontal", variable=var, length=260)
        sc.pack(side="left", padx=6)
        lb = ttk.Label(fr, text=f"{def_val if def_val is not None else mn}{unit}", width=8)
        lb.pack(side="left")
        var.trace_add("write", lambda *a, v=var, l=lb, u=unit: l.config(text=f"{v.get()}{u}"))
        cur = ttk.Label(fr, text="-", width=13, foreground="#555"); cur.pack(side="left", padx=3)
        key = f"{F}|{status_key}"
        self.sliders[key] = (var, cur)
        old = {"v": None}

        def on_press(e): 
            self._touch[key] = time.time(); old["v"] = var.get()
        def on_release(e):
            self._touch[key] = time.time()
            if not self._gate(sup): return
            v = var.get()
            if old["v"] is not None and old["v"] != v:
                self.undo_stack.append(("detail", F, status_key, old["v"]))
                self._undo_hint()
            self.app.set_field(F, status_key, v)
            self._verify_async(status_key, v, cur)
        sc.bind("<ButtonPress-1>", on_press)
        sc.bind("<ButtonRelease-1>", on_release)
        if def_val is not None:
            ttk.Button(fr, text="默认", width=4,
                       command=lambda: self._gated(lambda: (
                           var.set(def_val),
                           self.app.set_field(F, status_key, def_val),
                           self._verify_async(status_key, def_val, cur)))
                       ).pack(side="left", padx=3)

    def _verify_async(self, status_key, expect, result_lbl):
        """写入后回读验证, 结果写入标签"""
        def w():
            for _ in range(4):
                time.sleep(1.2)
                f = self.app.get_fan()
                v = f.get(status_key)
                if v is not None and str(v) == str(expect):
                    self.q.put(("verify", (result_lbl, f"✅已生效({v})", "#1a7f37")))
                    self.log(f"[验证] {status_key}={v} ✅")
                    return
            self.q.put(("verify", (result_lbl, "⚠️未回读确认", "#b26a00")))
            self.log(f"[验证] {status_key} 未见回读(可能仍生效)")
        threading.Thread(target=w, daemon=True).start()

    def _toggle_dual(self, parent, label, topic, field, on_val, off_val,
                     sup="✅", status_key=None, def_val=None):
        """开关: 当前状态显示 + 开/关后回读验证 + 悬停说明 + 可选默认钮"""
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        color = "#b00020" if sup.startswith("⛔") else ("#b26a00" if sup.startswith("⚠") else "#1a1a1a")
        lab = ttk.Label(fr, text=f"{sup} {label}", width=30, foreground=color)
        lab.pack(side="left")
        doc = FIELD_DOC.get(field) or FIELD_DOC.get(status_key)
        if doc:
            help_txt = f"{label} | 是什么: {doc[0]} | 参考: {doc[1]} | {doc[2]}"
            lab.bind("<Enter>", lambda e: self.hint_lbl.config(text=help_txt))
            lab.bind("<Leave>", lambda e: self.hint_lbl.config(text=""))
        res = ttk.Label(fr, text="", width=16, font=("Microsoft YaHei UI", 8))

        def apply(v):
            if not self._gate(sup): return
            old = None
            if status_key:
                st = {**self.app.status.get(mc.TOPIC_FAN_STA, {}),
                      **self.app.status.get(mc.TOPIC_SET_STA, {}),
                      **self.app.status.get("Tray/Status", {})}
                old = st.get(status_key)
            if old is not None:
                self.undo_stack.append(("field", topic, field, old)); self._undo_hint()
            self.app.set_field(topic, field, v)
            if status_key:
                res.config(text="验证中...", foreground="#b26a00")
                self._verify_async(status_key, v, res)

        ttk.Button(fr, text="开", width=4, command=lambda: apply(on_val)).pack(side="left", padx=2)
        ttk.Button(fr, text="关", width=4, command=lambda: apply(off_val)).pack(side="left", padx=2)
        res.pack(side="left", padx=4)
        if status_key:
            lb = ttk.Label(fr, text="-", width=22, foreground="#555"); lb.pack(side="left", padx=6)
            self.toggles[status_key] = (lb, {str(on_val): "当前: 开", str(off_val): "当前: 关"})
        if def_val is not None:
            dv = def_val
            ttk.Button(fr, text="默认", width=4, command=lambda: apply(dv)).pack(side="left", padx=2)

    def _serv_row(self, parent, label, cmd, topic, sup="⚠️", danger=False, note=""):
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        color = "#d00000" if danger else ("#1a1a1a" if sup == "✅" else ("#b00020" if sup.startswith("⛔") else "#b26a00"))
        txt = f"{sup} {label}" + (f" ({note})" if note else "")
        ttk.Label(fr, text=txt, width=52, foreground=color).pack(side="left")
        def go():
            if danger and not messagebox.askyesno("危险操作", "确认执行?"):
                return
            if not self._gate(sup): return
            self.app.write_servcmd(cmd, topic)
        ttk.Button(fr, text="发送", width=6, command=go).pack(side="left", padx=6)

    def _set_refresh(self, hz):
        """刷新率切换"""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # 获取当前设置
            class DEVMODE(ctypes.Structure):
                _fields_ = [
                    ("dmDeviceName", ctypes.c_wchar * 32),
                    ("dmSpecVersion", ctypes.c_ushort),
                    ("dmDriverVersion", ctypes.c_ushort),
                    ("dmSize", ctypes.c_ushort),
                    ("dmDriverExtra", ctypes.c_ushort),
                    ("dmFields", ctypes.c_uint),
                    ("dmPositionX", ctypes.c_int),
                    ("dmPositionY", ctypes.c_int),
                    ("dmDisplayOrientation", ctypes.c_uint),
                    ("dmDisplayFixedOutput", ctypes.c_uint),
                    ("dmColor", ctypes.c_short),
                    ("dmDuplex", ctypes.c_short),
                    ("dmYResolution", ctypes.c_short),
                    ("dmTTOption", ctypes.c_short),
                    ("dmCollate", ctypes.c_short),
                    ("dmFormName", ctypes.c_wchar * 32),
                    ("dmLogPixels", ctypes.c_ushort),
                    ("dmBitsPerPel", ctypes.c_uint),
                    ("dmPelsWidth", ctypes.c_uint),
                    ("dmPelsHeight", ctypes.c_uint),
                    ("dmDisplayFlags", ctypes.c_uint),
                    ("dmDisplayFrequency", ctypes.c_uint),
                    ("dmICMMethod", ctypes.c_uint),
                    ("dmICMIntent", ctypes.c_uint),
                    ("dmMediaType", ctypes.c_uint),
                    ("dmDitherType", ctypes.c_uint),
                    ("dmReserved1", ctypes.c_uint),
                    ("dmReserved2", ctypes.c_uint),
                    ("dmPanningWidth", ctypes.c_uint),
                    ("dmPanningHeight", ctypes.c_uint),
                ]
            dm = DEVMODE()
            dm.dmSize = ctypes.sizeof(DEVMODE)
            dm.dmFields = 0x00800000  # DM_DISPLAYFREQUENCY
            dm.dmDisplayFrequency = hz
            ENUM_CURRENT_SETTINGS = -1
            # 先获取当前设置
            if user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
                dm.dmDisplayFrequency = hz
                dm.dmFields = 0x00800000
                DISP_CHANGE_SUCCESSFUL = 0
                ret = user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)
                if ret == 0:
                    self.log(f"[刷新率] {hz}Hz 切换成功")
                else:
                    self.log(f"[刷新率] {hz}Hz 切换失败 ret={ret}")
        except Exception as e:
            self.log(f"[刷新率] 错误: {e}")

    def _admin_cmd(self, cmd):
        """管理员命令(弹UAC)"""
        try:
            r = subprocess.run(["powershell", "-Command",
                f"Start-Process cmd -ArgumentList '/c {cmd}' -Verb RunAs -Wait"],
                capture_output=True, text=True, timeout=15)
            self.log(f"[Admin] {cmd} 已执行")
        except Exception as e:
            self.log(f"[Admin] 错误: {e}")

    def _gate(self, sup):
        if sup.startswith("⛔"):
            if not self.research.get():
                if messagebox.askyesno("研究模式", "⛔本机不支持项。\n开启[允许研究发送]并继续?"):
                    self.research.set(True)
                else: return False
            if not self.write_enabled.get():
                if messagebox.askyesno("安全锁", "写入未启用。启用并继续?"):
                    self.write_enabled.set(True)
                else: return False
            return True
        if not self.write_enabled.get():
            if messagebox.askyesno("安全锁", "写入未启用(顶部✍)。\n启用并执行本次操作?"):
                self.write_enabled.set(True)
                self.log("[安全锁] 写入已启用(经确认)")
            else:
                self.log("[安全锁] 已拦截: 写入未启用且用户拒绝")
                return False
        return True

    def _write_state(self, *a):
        if self.write_enabled.get():
            self.write_chk.config(text="✍ 写入已启用(点击关闭)", fg="#d00000")
            self.log("[安全锁] 写入已启用")
        else:
            self.write_chk.config(text="✍ 启用写入(只读模式)", fg="#1a7f37")
            self.log("[安全锁] 只读模式")

    def _undo_hint(self):
        self.undo_lbl.config(text=f"可撤销×{len(self.undo_stack)} (Ctrl+Z)")

    def undo(self):
        if not self.undo_stack:
            self.log("[撤销] 栈空"); return
        kind, topic, key, old = self.undo_stack.pop()
        if kind == "mode":
            self.app.set_mode(old)
        else:
            self.app.set_field(topic, key, old)
        self.log(f"[↩撤销] {key} ← {old}")
        self._undo_hint()

    def snapshot_toggle(self):
        if self.snapshot is None:
            f = self.app.get_fan()
            keys = ["CPU_PL1","CPU_PL2","CPU_PL4","CPU_TccOffset","CpuAmdTccTarget",
                    "CpuAmdSPL","CpuAmdSPPT","CpuAmdFPPT","GPU_CoreClockOffsetOC",
                    "GPU_MemoryClockOffsetOC","GPU_DynamicBoost","FanSwitchSpeed"]
            snap = {k: f.get(k) for k in keys if f.get(k) is not None}
            self.snapshot = snap
            self.log(f"[📸] 已快照 {len(snap)} 项 → 再点此钮=一键还原")
        else:
            for k, v in self.snapshot.items():
                w = self.app.WIRE_KEY.get(k, k)
                self.app.mqtt.publish(F, json.dumps({"Action": "SET_OPERATING_MODE_DETAIL", w: v}))
                time.sleep(0.45)
            self.log(f"[📸] 已还原 {len(self.snapshot)} 项")
            self.snapshot = None

    # ================= Tabs =================
    def _tab_home(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 总览 ")
        # 模式大卡
        mf = ttk.LabelFrame(f, text="性能模式(点击直切)")
        mf.pack(fill="x", padx=8, pady=6)
        self.mode_cards = {}
        for key, cn, sub in [("office","办公","静音续航"),("gaming","均衡","日常"),
                             ("turbo","狂暴","性能释放"),("custom","自定义","自由")]:
            b = tk.Button(mf, text=f"{cn}\n{sub}", font=("Microsoft YaHei UI", 12, "bold"),
                          width=12, height=3, relief="flat", bg="#2d2d2d", fg="white",
                          activebackground="#5e5ae4",
                          command=lambda k=key: self._mode_click(k))
            b.pack(side="left", expand=True, padx=6, pady=6)
            self.mode_cards[key] = b
        # 仪表卡
        gf = ttk.LabelFrame(f, text="状态仪表(设定值, 5s自动刷新)")
        gf.pack(fill="both", expand=True, padx=8, pady=6)
        self.cards = {}
        defs = [("CPU", ["CPU_PL1","CPU_PL2","CPU_PL4","CPU_TccOffset"]),
                ("GPU", ["GPU_CoreClockOffsetOC","GPU_MemoryClockOffsetOC","GPU_ConfigurableTGPTarget","GPU_DynamicBoost"]),
                ("风扇", ["FAN_TableName","FAN_FanSwitchSpeed","FanBoostEnable","FAN_SafetyProtect"]),
                ("电池", ["BatteryPercent","HealthProtectionStatus","BatteryAbnormal","AcRecoverySwitch_Status"])]
        for title, keys in defs:
            card = tk.Canvas(gf, width=250, height=130, bg="#1e1e1e", highlightthickness=0)
            card.pack(side="left", expand=True, padx=5, pady=5)
            self.cards[title] = (card, keys)
        # EC 实时卡(温度/风扇, 需管理员)
        try:
            ecard = tk.Canvas(gf, width=250, height=130, bg="#2a1a1a", highlightthickness=0)
            ecard.pack(side="left", expand=True, padx=5, pady=5)
            self.cards["EC实时"] = (ecard, ["__ec_cpu", "__ec_gpu", "__ec_duty", "__ec_gduty", "__ec_rpm"])
        except Exception:
            pass

        # GPU 实时卡(pynvml)
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml_h = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.pynvml = pynvml
            gcard = tk.Canvas(gf, width=250, height=130, bg="#1a2a1a", highlightthickness=0)
            gcard.pack(side="left", expand=True, padx=5, pady=5)
            self.cards["GPU实时"] = (gcard, ["__nvml_temp", "__nvml_power", "__nvml_util", "__nvml_clock"])
        except Exception:
            self.nvml_h = None

        # 底部快捷
        qf = ttk.Frame(f); qf.pack(fill="x", padx=8, pady=4)
        for name, fn in [("风扇/OC", lambda: self.dump_query(mc.TOPIC_FAN_CTRL, {"Action":"GETSTATUS"}, ("Fan/",), "风扇")),
                         ("设置", lambda: self.dump_query(mc.TOPIC_SET_CTRL, {"Action":"GETSTATUS"}, ("Setting/",), "设置")),
                         ("电池", lambda: self.dump_query(BAT, {"Report":"GET"}, ("System/BatteryProtection","Battery"), "电池")),
                         ("键盘", lambda: self.dump_query(KB, {"Action":"GETSTATUS"}, ("Keyboard",), "键盘")),
                         ("显卡", lambda: self.dump_query(mc.TOPIC_SYS_CTRL, {"Action":"GetGraphicInfo"}, ("System/HardwareInfo",), "显卡")),
                         ("OEM支持", lambda: self.dump_query("Customize/Control", {"Action":"GETSUPPORT"}, ("Customize/Support",), "支持"))]:
            ttk.Button(qf, text="🔍"+name, command=fn).pack(side="left", padx=3)
        self.status_text = scrolledtext.ScrolledText(f, height=8, font=("Consolas", 9))
        self.status_text.pack(fill="both", expand=True, padx=8, pady=4)

    def _tab_perf(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 性能中心 ")
        lf = ttk.LabelFrame(f, text="OC 参数(滑条释放即发 · Ctrl+Z撤销)")
        lf.pack(fill="x", padx=8, pady=6)
        self._slider_instant(lf, "CPU PL1 (W)", "CPU_PL1", 10, 80)
        self._slider_instant(lf, "CPU PL2 (W)", "CPU_PL2", 10, 80)
        self._slider_instant(lf, "CPU PL4 (W)", "CPU_PL4", 10, 100)
        self._slider_instant(lf, "温度墙 TccOffset(°C)", "CPU_TccOffset", 80, 100)
        self._slider_instant(lf, "AMD SPL(W)", "CPU_AmdSPL", 10, 80)
        self._slider_instant(lf, "AMD SPPT(W)", "CPU_AmdSPPT", 10, 80)
        self._slider_instant(lf, "AMD FPPT(W)", "CPU_AmdFPPT", 10, 100)
        self._slider_instant(lf, "AMD温度目标(°C)", "CPU_AmdTccTarget", 85, 99)
        lf2 = ttk.LabelFrame(f, text="GPU")
        lf2.pack(fill="x", padx=8, pady=6)
        self._slider_instant(lf2, "核心偏移(MHz)", "GPU_CoreClockOffsetOC", 0, 250)
        self._slider_instant(lf2, "显存偏移(MHz)", "GPU_MemoryClockOffsetOC", -1000, 1000)
        self._slider_instant(lf2, "目标温度(°C)", "GPU_TargetTemperature", 75, 87)
        self._slider_instant(lf2, "Dynamic Boost(W)", "GPU_DynamicBoost", 5, 25)
        lf3 = ttk.LabelFrame(f, text="开关")
        lf3.pack(fill="x", padx=8, pady=6)
        self._toggle_dual(lf3, "超频总开关", F, "OverClockingSwitch", 1, 0, status_key="OverClockingSwitch", def_val=1)
        self._toggle_dual(lf3, "Whisper低功耗(GPU)", F, "GPU_WhisperModeSwitch", 1, 0, status_key="GPU_WhisperModeSwitch", def_val=0)
        self._toggle_dual(lf3, "DynamicBoost开关", F, "GPU_DynamicBoostSwitch", 1, 0, status_key="GPU_DynamicBoostSwitch", def_val=1)
        lf4 = ttk.LabelFrame(f, text="🔥 风扇强冷(实测✓·超越官方无按钮) + 恢复")
        lf4.pack(fill="x", padx=8, pady=6)
        ttk.Button(lf4, text="🔥强冷 开", command=lambda: self._gated(lambda: self.app.set_fan_boost(True))).pack(side="left", padx=4)
        ttk.Button(lf4, text="强冷 关", command=lambda: self._gated(lambda: self.app.set_fan_boost(False))).pack(side="left", padx=4)
        ttk.Button(lf4, text="恢复默认曲线", command=lambda: self._gated(lambda: self.app.restore_fan_curve("M3T1"))).pack(side="left", padx=4)
        ttk.Button(lf4, text="恢复模式默认", command=lambda: self._gated(self.app.restore_mode_detail)).pack(side="left", padx=4)

        lf5 = ttk.LabelFrame(f, text="GPU降压锁频(实测✓ · 等效VF曲线降压@0.900V)")
        lf5.pack(fill="x", padx=8, pady=6)
        ttk.Label(lf5, text="原理: 锁定GPU最高频率→限制最大电压→温度↓功耗↓", foreground="#888").pack(anchor="w", padx=8)
        uvrow = ttk.Frame(lf5); uvrow.pack(fill="x", padx=8, pady=4)
        ttk.Button(uvrow, text="🔥降压 2100MHz", width=14,
                   command=lambda: self._gated(lambda: self._lock_clock(2100))).pack(side="left", padx=3)
        ttk.Button(uvrow, text="降压 2400MHz", width=14,
                   command=lambda: self._gated(lambda: self._lock_clock(2400))).pack(side="left", padx=3)
        ttk.Button(uvrow, text="恢复默认", width=10,
                   command=lambda: self._gated(lambda: self._unlock_clock())).pack(side="left", padx=3)
        ttk.Label(lf5, text="2100MHz=温度↓8-10°C功耗↓15-20W 性能↓10-15% | 2400MHz=温度↓3-5°C 性能↓3%",
                  foreground="#888", font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=8)

    def _gated(self, fn):
        if not self.write_enabled.get():
            if messagebox.askyesno("安全锁", "写入未启用(顶部✍)。\n启用并执行?"):
                self.write_enabled.set(True)
            else: return
        fn()

    def _tab_fan(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 风扇曲线 ")
        lf = ttk.LabelFrame(f, text="智能风扇表 (CPU 0xF00/F10 · GPU 0xF30/F40 · 写入=实证指令)")
        lf.pack(fill="x", padx=8, pady=6)
        row = ttk.Frame(lf); row.pack(fill="x", padx=8, pady=4)
        ttk.Button(row, text="读取曲线", command=lambda: self.app.mqtt.publish(
            mc.TOPIC_FAN_CTRL, '{"Action":"GET_FAN_SPEED_CURVE_SETTING"}')).pack(side="left", padx=3)
        ttk.Button(row, text="恢复默认(M3T1)", command=lambda: self._gated(lambda: self.app.restore_fan_curve("M3T1"))).pack(side="left", padx=3)
        self._slider_instant(lf, "起转转速(RPM)", "FAN_FanSwitchSpeed", 0, 1500, unit="RPM")
        self._toggle_dual(lf, "起转控制启用", F, "FAN_FanSwitchSpeedEnabled", 1, 0,
                          status_key="FAN_FanSwitchSpeedEnabled", def_val=0)
        self.curve_text = scrolledtext.ScrolledText(f, height=12, font=("Consolas", 9))
        self.curve_text.pack(fill="both", expand=True, padx=8, pady=6)

    def _tab_kb(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 灯光键盘 ")
        # 颜色选择+预览+直发
        cf = ttk.LabelFrame(f, text="颜色(拖动RGB → 释放即发 Single色)")
        cf.pack(fill="x", padx=8, pady=6)
        prev = tk.Canvas(cf, width=90, height=60, highlightthickness=1)
        prev.grid(row=0, column=3, rowspan=3, padx=8)
        for i,(ch,var,init) in enumerate([("R",self.kb_r,0),("G",self.kb_g,255),("B",self.kb_b,0)]):
            ttk.Label(cf, text=ch, width=2).grid(row=i, column=0, padx=(10,2))
            sc = ttk.Scale(cf, from_=0, to=255, orient="horizontal", variable=var, length=220)
            sc.grid(row=i, column=1, sticky="we", padx=2)
            def upd(*a, pv=prev):
                c = f"#{self.kb_r.get():02x}{self.kb_g.get():02x}{self.kb_b.get():02x}"
                pv.config(bg=c)
            var.trace_add("write", upd)
        def send_color():
            if not self.write_enabled.get():
                if messagebox.askyesno("安全锁", "启用写入并设置颜色?"): self.write_enabled.set(True)
                else: return
            p = self._kb_seteffect("Single", rgb=(self.kb_r.get(), self.kb_g.get(), self.kb_b.get()))
            self.app.mqtt.publish(KB, json.dumps(p)); self.log("[KB] 颜色已发送")
        ttk.Button(cf, text="应用颜色", command=send_color).grid(row=3, column=1, pady=4)
        prev.config(bg="#00ff00")
        # 亮度
        bf = ttk.LabelFrame(f, text="亮度(function协议·释放即发)")
        bf.pack(fill="x", padx=8, pady=6)
        bl = ttk.Scale(bf, from_=0, to=4, orient="horizontal")
        bl.pack(fill="x", padx=10)
        def bl_release(e):
            if not self.write_enabled.get(): return
            lv = int(float(bl.get()))
            self.app.mqtt.publish(KB, json.dumps({"MqttID": None, "function": "SetLightingLevel", "level": lv}))
            self.log(f"[KB] 亮度→{lv}")
        bl.bind("<ButtonRelease-1>", bl_release)
        # 灯效(直发)
        ef = ttk.LabelFrame(f, text="灯效(点击直发·官方SetEffectALL格式)")
        ef.pack(fill="both", expand=True, padx=8, pady=6)
        grid = ttk.Frame(ef); grid.pack(fill="both", expand=True)
        cols = 4
        for i, (name, key, tag) in enumerate(RGB_EFFECTS):
            ttk.Button(grid, text=f"{tag}{name}",
                       command=lambda k=key: self._kb_send(k)).grid(
                row=i//cols, column=i%cols, sticky="we", padx=3, pady=2)
        # 外设提示
        ttk.Label(f, text="外设(摄像头/WiFi/蓝牙/Win键等)已独立为[外设]页").pack(anchor="w", padx=10)

    def _kb_send(self, effect):
        if not self.write_enabled.get():
            if messagebox.askyesno("安全锁", "启用写入并发送灯效?"): self.write_enabled.set(True)
            else: return
        p = self._kb_seteffect(effect=effect)
        self.app.mqtt.publish(KB, json.dumps(p))
        self.log(f"[KB] 灯效 {effect} 已直发")

    @staticmethod
    def _kb_seteffect(effect="Wave", light="4", speed="2", direction="None",
                      nv_save="0", rgb=(0, 255, 0)):
        rainbow = [(255,0,0),(255,165,0),(255,255,0),(0,255,0),(0,0,255),(0,255,255),(139,0,255)]
        buf = [{"ID": i, "R": r, "G": g, "B": b} for i,(r,g,b) in enumerate(rainbow)]
        if rgb:
            buf = [{"ID": 0, "R": rgb[0], "G": rgb[1], "B": rgb[2]}] * 7
        return {"MqttID": None, "function": "SetEffectALL", "mode": "Lighting",
                "effect": effect, "light": str(light), "speed": str(speed),
                "direction": direction, "nv_save": nv_save,
                "color": {"isCircular": True, "ColorBlocks": 7, "ColorBuffer": buf}}

    def _tab_display(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 显示器 ")
        lf = ttk.LabelFrame(f, text="画面模式(ServCMD实证·点击直切)")
        lf.pack(fill="x", padx=8, pady=6)
        for name, cmd in [("标准", "DISPLAY_STANDARD_MODE"), ("游戏", "DISPLAY_GAMING_MODE"),
                          ("视频", "DISPLAY_VIDEO_MODE"), ("阅读", "DISPLAY_READ_MODE"),
                          ("自定义", "DISPLAY_CUSTOMIZED_MODE"), ("游戏恢复默认", "DISPLAY_GAMING_MODE_RECOVERY")]:
            ttk.Button(lf, text=name, width=14,
                       command=lambda c=cmd: self._gated(lambda: self.app.write_servcmd(c, S))
                       ).pack(side="left", padx=4, pady=4)
        lf2 = ttk.LabelFrame(f, text="游戏画面参数(释放即发)")
        lf2.pack(fill="x", padx=8, pady=6)
        for lab, key, mn, mx in [("亮度","GamingBrightness",0,100),("色温","GamingColorTemp",0,100),
                                 ("对比","GamingContrast",0,100),("红","GamingRed",0,128),
                                 ("绿","GamingGreen",0,128),("蓝","GamingBlue",0,128)]:
            self._slider_instant(lf2, lab, key, mn, mx)
        self._toggle_dual(lf2, "显示增强总开关", S, "DisplayFeatureStatus",
                          "DISPLAY_FEATURE_STATUS_ON", "DISPLAY_FEATURE_STATUS_OFF",
                          status_key="DisplayFeatureStatus", def_val="DISPLAY_FEATURE_STATUS_OFF")
        self._toggle_dual(lf2, "OSD悬浮显示", S, "OSD", "OSD_HIDDEN_OFF", "OSD_HIDDEN_ON",
                          status_key="OSD")
        self._slider_instant(lf2, "自动关屏(分)", "CloseTimer", 0, 120)

        # ===== 亮度滑条(WMI 免管理员) =====
        bf = ttk.LabelFrame(f, text="屏幕亮度(WMI·即发)")
        bf.pack(fill="x", padx=8, pady=6)
        self.bright_var = tk.IntVar(value=80)
        bright_scale = ttk.Scale(bf, from_=0, to=100, orient="horizontal",
                                 variable=self.bright_var, length=300)
        bright_scale.pack(side="left", padx=8)
        bright_lbl = ttk.Label(bf, text="80%", width=5)
        bright_lbl.pack(side="left")
        self.bright_var.trace_add("write", lambda *a, l=bright_lbl: l.config(text=f"{self.bright_var.get()}%"))

        def _bright_release(e):
            v = self.bright_var.get()
            try:
                import wmi
                c = wmi.WMI(namespace="wmi")
                methods = c.WmiMonitorBrightnessMethods()[0]
                methods.WmiSetBrightness(1, v)
                self.log(f"[亮度] {v}%")
            except Exception:
                # fallback: PowerShell
                ps = f'(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{v})'
                subprocess.run(["powershell", "-Command", ps], capture_output=True)
                self.log(f"[亮度] {v}% (PS)")
        bright_scale.bind("<ButtonRelease-1>", _bright_release)

        # ===== 刷新率切换 =====
        rf = ttk.LabelFrame(f, text="刷新率(165Hz原生)")
        rf.pack(fill="x", padx=8, pady=6)
        for hz, label in [(165, "165Hz(游戏)"), (60, "60Hz(省电)")]:
            ttk.Button(rf, text=label, width=14,
                       command=lambda h=hz: self._set_refresh(h)).pack(side="left", padx=4)

        # ===== GPU TGP 快捷(v5.4: 回读验证内建, 结果即 E1 仲裁记录) =====
        tf = ttk.LabelFrame(f, text="GPU 功耗墙(E1已仲裁: 本机驱动拒绝-pl·仅留验证入口)")
        tf.pack(fill="x", padx=8, pady=6)
        for label, watt in [("TGP 140W(已仲裁✗)", 140), ("TGP 115W默认", 115)]:
            ttk.Button(tf, text=label, width=14,
                       command=lambda w=watt: self._gpu_wall_verified(w)
                       ).pack(side="left", padx=4)

    def _tab_battery(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 电池电源 ")
        lf = ttk.LabelFrame(f, text="电池保护(HEALTHYMODE实证)")
        lf.pack(fill="x", padx=8, pady=6)
        for name, payload in BATTERY_ACTIONS:
            ttk.Button(lf, text=name, command=lambda p=payload: self._gated(
                lambda: self.app.mqtt.publish(BAT, json.dumps(p)))).pack(side="left", padx=4)
        ttk.Button(lf, text="查询状态", command=lambda: self.app.mqtt.publish(
            BAT, '{"Report":"GET"}')).pack(side="left", padx=4)
        lf2 = ttk.LabelFrame(f, text="充电阈值(释放即发)")
        lf2.pack(fill="x", padx=8, pady=6)
        self._slider_instant(lf2, "充电上限(%)", "ChargeMaximumLimit", 60, 100, unit="%")

        # ===== EC UWACPIDriver 直写充电阈值(v5.4 实测✓ 免管理员) =====
        ef = ttk.LabelFrame(f, text="🔋 充电阈值 EC直写(UWACPIDriver·免管理员·超越官方)")
        ef.pack(fill="x", padx=8, pady=6)
        ttk.Label(ef, text="经官方驱动 WriteEC 直写 0x7A9(停止阈值), 0x7A8 起始值保持不变", foreground="#888").pack(anchor="w", padx=8)
        erow = ttk.Frame(ef); erow.pack(fill="x", padx=8, pady=4)
        self.charge_var = tk.IntVar(value=80)
        ttk.Label(erow, text="阈值%", width=6).pack(side="left")
        csc = ttk.Scale(erow, from_=60, to=100, orient="horizontal", variable=self.charge_var, length=250)
        csc.pack(side="left", padx=6)
        clb = ttk.Label(erow, text="80%", width=6)
        clb.pack(side="left")
        self.charge_var.trace_add("write", lambda *a, l=clb: l.config(text=f"{self.charge_var.get()}%"))
        cres = ttk.Label(erow, text="", width=20, font=("Microsoft YaHei UI", 8))
        cres.pack(side="left", padx=6)
        self.charge_result = cres

        def apply_charge():
            if not self.write_enabled.get():
                if messagebox.askyesno("安全锁", "启用写入并设置充电阈值?"):
                    self.write_enabled.set(True)
                else: return
            pct = self.charge_var.get()
            cres.config(text="写入中...", foreground="#b26a00")
            def w():
                try:
                    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                    import mr_ec_hw as ec
                    ok = ec.set_charge_limit(int(pct))
                    t = ec.get_charge_thresholds()
                    if ok:
                        self.q.put(("charge_result", (f"✅ 已设为{pct}% (起始{t['start']}%)", "#1a7f37")))
                        self.log(f"[充电阈值] WriteEC直写 {pct}% → 回读{t['stop']}% ✅")
                    else:
                        self.q.put(("charge_result", (f"⚠️ 回读不符: {t}", "#b26a00")))
                        self.log(f"[充电阈值] 写入 {pct}% 回读异常: {t}")
                except Exception as e:
                    self.q.put(("charge_result", (f"❌ {e}", "#c00")))
                    self.log(f"[充电阈值] 异常: {e}")
            threading.Thread(target=w, daemon=True).start()

        ttk.Button(erow, text="应用", width=6, command=apply_charge).pack(side="left", padx=4)
        # 快捷按钮
        for pct_val, pct_lab in [(60, "60%"), (70, "70%"), (80, "80%")]:
            ttk.Button(erow, text=pct_lab, width=4,
                       command=lambda p=pct_val: (self.charge_var.set(p), apply_charge())
                       ).pack(side="left", padx=2)
        lf3 = ttk.LabelFrame(f, text="电源计划(ServCMD)")
        lf3.pack(fill="x", padx=8, pady=6)
        for name, cmd in [("游戏","POWER_PLAN_GAMING"),("高性能","POWER_PLAN_HIPERFORMANCE"),
                          ("平衡","POWER_PLAN_BALANCED"),("省电","POWER_PLAN_POWERSAVING")]:
            ttk.Button(lf3, text=name, command=lambda c=cmd: self._gated(
                lambda: self.app.write_servcmd(c, S))).pack(side="left", padx=4)
        self._toggle_dual(lf3, "AC断电恢复", S, "AcRecoverySwitch_Status",
                          "ACRECOVERY_TOGGLE_ON", "ACRECOVERY_TOGGLE_OFF",
                          status_key="AcRecoverySwitch_Status", sup="⚠️")

        # ===== 电源场景(自制独有: Windows计划+EC模式+显示联动) =====
        sf = ttk.LabelFrame(f, text="⚡ 电源场景(一键全栈: Windows计划+EC模式+显示+风扇)")
        sf.pack(fill="x", padx=8, pady=6)
        ttk.Label(sf, text="基于本机实测: 高性能计划/平衡计划 + OPERATING_* + 显示模式 + 亮度(WMI)",
                  foreground="#666").pack(anchor="w", padx=8)
        srow = ttk.Frame(sf); srow.pack(fill="x", padx=8, pady=4)
        import subprocess as _sp
        def _brightness(v):
            """v5.4: 统一走 mr_win_ctrl(内部已含 PS 兜底), 清除原残缺死代码"""
            threading.Thread(target=lambda: wc.set_brightness(v), daemon=True).start()
        def scenario(name):
            if not self.write_enabled.get():
                if messagebox.askyesno("安全锁", "启用写入并应用场景?"): self.write_enabled.set(True)
                else: return
            self.log(f"[场景] 应用 {name} ...")
            def w():
                try:
                    if name == "游戏":
                        _sp.run(["powercfg","/setactive","8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], capture_output=True)
                        self.app.mqtt.publish(F, '{"Action":"OPERATING_TURBO_MODE","ProfileIndex":"0"}')
                        self.app.mqtt.publish(S, '{"Action":"DISPLAY_GAMING_MODE"}')
                        self.app.set_fan_boost(True)
                        _brightness(100)
                    elif name == "办公":
                        _sp.run(["powercfg","/setactive","381b4222-f694-41f0-9685-ff5bb260df2e"], capture_output=True)
                        self.app.mqtt.publish(F, '{"Action":"OPERATING_OFFICE_MODE","ProfileIndex":"0"}')
                        self.app.mqtt.publish(S, '{"Action":"DISPLAY_READ_MODE"}')
                        _brightness(60)
                    elif name == "影音":
                        _sp.run(["powercfg","/setactive","381b4222-f694-41f0-9685-ff5bb260df2e"], capture_output=True)
                        self.app.mqtt.publish(F, '{"Action":"OPERATING_GAMING_MODE","ProfileIndex":"0"}')
                        self.app.mqtt.publish(S, '{"Action":"DISPLAY_VIDEO_MODE"}')
                        _brightness(80)
                    elif name == "移动节能":
                        _sp.run(["powercfg","/setactive","381b4222-f694-41f0-9685-ff5bb260df2e"], capture_output=True)
                        self.app.mqtt.publish(F, '{"Action":"OPERATING_OFFICE_MODE","ProfileIndex":"0"}')
                        self.app.set_fan_boost(False)
                        _brightness(40)
                    self.log(f"[场景] {name} 应用完成(计划+EC模式+显示+亮度)")
                except Exception as e:
                    self.log(f"[场景] 错误: {e}")
            threading.Thread(target=w, daemon=True).start()
        for nm, tip in [("🎮游戏","高性能计划+狂暴+游戏显示+强冷+100%亮度"),
                        ("💼办公","平衡计划+办公+护眼显示+60%亮度"),
                        ("🎬影音","平衡+均衡+视频模式+80%亮度"),
                        ("🔋移动节能","平衡+办公+强冷关+40%亮度")]:
            ttk.Button(srow, text=nm, width=10,
                       command=lambda n=nm: scenario(n)).pack(side="left", padx=4)
        ttk.Label(sf, text="提示: 移动节能建议配合充电阈值80%使用(EC直写已在上方实测区)",
                  foreground="#888").pack(anchor="w", padx=8)
        self._apply_scenario = scenario   # v5.4: 供智能场景自动调用

    def _tab_powersys(self, nb):
        """v5.4 新增: Windows 原生电源/显示/系统页 (W4-W8/W12/W15-W19/E1)"""
        f = ttk.Frame(nb); nb.add(f, text=" 电源·系统 ")
        def gate():
            if not self.write_enabled.get():
                if messagebox.askyesno("安全锁", "启用写入并执行?"): self.write_enabled.set(True)
                else: return False
            return True
        def bg(fn, done=None):
            def w():
                try: r = fn()
                except Exception as e: r = (False, str(e))
                if done: self.root.after(0, lambda: done(r))
            threading.Thread(target=w, daemon=True).start()

        # ---- W4/W5/W6 处理器电源三件套 ----
        pf = ttk.LabelFrame(f, text="处理器电源(AC=插电 / DC=电池 · 实测✓)")
        pf.pack(fill="x", padx=8, pady=6)
        rows = {}
        for pid, cn, mn, mx in [("PERFEPP","EPP能效(0性能~100效率)",0,100),
                                ("PROCTHROTTLEMAX","最大处理器状态%",5,100)]:
            fr = ttk.Frame(pf); fr.pack(fill="x", padx=8, pady=2)
            ttk.Label(fr, text=cn, width=24).pack(side="left")
            va, vd = tk.IntVar(value=0), tk.IntVar(value=0)
            ttk.Label(fr, text="AC").pack(side="left")
            ttk.Scale(fr, from_=mn, to=mx, orient="horizontal", variable=va, length=110).pack(side="left", padx=3)
            ttk.Label(fr, text="DC").pack(side="left", padx=(8,0))
            ttk.Scale(fr, from_=mn, to=mx, orient="horizontal", variable=vd, length=110).pack(side="left", padx=3)
            res = ttk.Label(fr, text="-", width=26, foreground="#555"); res.pack(side="left", padx=4)
            rows[pid] = (va, vd, res)
        fb = ttk.Frame(pf); fb.pack(fill="x", padx=8, pady=2)
        ttk.Label(fb, text="Boost加速模式", width=24).pack(side="left")
        boost_names = ["0关", "1开", "2激进", "3高效开", "4高效激进"]
        vba, vbd = tk.StringVar(value=boost_names[2]), tk.StringVar(value=boost_names[0])
        ttk.Label(fb, text="AC").pack(side="left")
        ttk.Combobox(fb, textvariable=vba, values=boost_names, width=9, state="readonly").pack(side="left", padx=3)
        ttk.Label(fb, text="DC").pack(side="left", padx=(8,0))
        ttk.Combobox(fb, textvariable=vbd, values=boost_names, width=9, state="readonly").pack(side="left", padx=3)
        fres = ttk.Label(fb, text="-", width=26, foreground="#555"); fres.pack(side="left", padx=4)
        def pwr_load():
            def w():
                return {p: wc.powercfg_get(p) for p in wc.POWER_PARAMS}
            def done(d):
                for pid, vals in d.items():
                    if not vals: continue
                    if pid == "PERFBOOSTMODE":
                        vba.set(boost_names[min(int(vals["ac"]), 4)])
                        vbd.set(boost_names[min(int(vals["dc"]), 4)])
                    else:
                        va, vd, res = rows[pid]
                        va.set(int(vals["ac"])); vd.set(int(vals["dc"]))
                self.log("[电源] 已读取当前 AC/DC 值")
            bg(w, done)
        def pwr_apply():
            if not gate(): return
            def w():
                out = []
                for pid, (va, vd, _) in rows.items():
                    ok, dt = wc.powercfg_set(pid, ac=va.get(), dc=vd.get())
                    out.append(f"{pid}:{'OK' if ok else 'FAIL'}({dt})")
                ba = boost_names.index(vba.get()); bd = boost_names.index(vbd.get())
                ok, dt = wc.powercfg_set("PERFBOOSTMODE", ac=ba, dc=bd)
                out.append(f"BOOST:{'OK' if ok else 'FAIL'}")
                return all("OK" in o for o in out), " ".join(out)
            def done(r):
                ok, dt = r
                fres.config(text=("✅ " if ok else "⚠️ ") + dt[:46],
                            foreground="#1a7f37" if ok else "#b26a00")
                self.log(f"[电源] 应用完成: {dt}")
            bg(w, done)
        ttk.Button(fb, text="读取当前", command=pwr_load).pack(side="left", padx=4)
        ttk.Button(fb, text="应用全部", command=pwr_apply).pack(side="left", padx=4)

        # ---- W7 刷新率 ----
        rf = ttk.LabelFrame(f, text="刷新率(完整DEVMODE·只改频率不碰分辨率)")
        rf.pack(fill="x", padx=8, pady=6)
        rrow = ttk.Frame(rf); rrow.pack(fill="x", padx=8, pady=4)
        def refresh_rates():
            def w(): return wc.list_refresh_rates()
            def done(rs):
                for wid in rrow.winfo_children(): wid.destroy()
                for hz in rs:
                    ttk.Button(rrow, text=f"{hz}Hz", width=8,
                               command=lambda h=hz: self._set_refresh(h)).pack(side="left", padx=3)
                self.log(f"[刷新率] 可用: {rs}")
            bg(w, done)
        ttk.Button(rf, text="枚举可用刷新率", command=refresh_rates).pack(side="left", padx=8, pady=4)
        ttk.Label(rf, text="点击按钮生成各档位", foreground="#888").pack(side="left")

        # ---- W8 已在显示器页; 此处不重复 ----

        # ---- 注册表开关组(W15/W19/W18) + 节电计划(W17) ----
        rf2 = ttk.LabelFrame(f, text="系统开关(HKLM项会弹一次UAC)")
        rf2.pack(fill="x", padx=8, pady=6)
        st = ttk.Label(rf2, text="", foreground="#555"); 
        def reg_btn(text, fn):
            ttk.Button(rf2, text=text, width=18,
                       command=lambda: bg(lambda: fn(), lambda r: (
                           st.config(text=str(r[1])[:60], foreground="#1a7f37" if r[0] else "#b26a00"),
                           self.log(f"[注册表] {text}: {r[1]}")))).pack(side="left", padx=4)
        reg_btn("HAGS 开(需重启)", lambda: wc.hags_set(True))
        reg_btn("HAGS 关", lambda: wc.hags_set(False))
        reg_btn("游戏模式 开", lambda: wc.gamemode_set(True))
        reg_btn("游戏模式 关", lambda: wc.gamemode_set(False))
        reg_btn("GameDVR 关(省后台)", lambda: wc.gamedvr_set(False))
        reg_btn("WiFi偏5GHz", lambda: wc.wifi_band_prefer(
            (wc.wifi_adapters() or [{"index": "0001"}])[0]["index"], 2))
        reg_btn("创建节电计划", lambda: wc.power_plan_create_saver())
        st.pack(side="left", padx=8)

        # ---- E1 GPU功耗墙(带回读验证) ----
        gf = ttk.LabelFrame(f, text="GPU 功耗墙(E1仲裁实验 · 回读验证)")
        gf.pack(fill="x", padx=8, pady=6)
        wall_lbl = ttk.Label(gf, text="当前: 未读取", width=44, foreground="#555")
        wall_lbl.pack(side="left", padx=8)
        def wall_refresh():
            def w(): return wc.gpu_wall_get()
            def done(wl):
                wl = wl or {}
                wall_lbl.config(text="current={0}W default={1}W min={2}W max={3}W".format(
                    wl.get("current_w"), wl.get("default_w"), wl.get("min_w"), wl.get("max_w")))
            bg(w, done)
        def wall_set(watt):
            if not gate(): return
            def w(): return wc.gpu_wall_set(watt)
            def done(r):
                ok, dt = r
                self.log(f"[E1] -pl {watt}: {'✅生效' if ok else '❌被驱动拒绝'} | {dt}")
                messagebox.showinfo("E1 结果", ("✅ 功耗墙已设为 {0}W\n" if ok else "❌ 驱动拒绝 {0}W\n").format(watt) + dt +
                                    "\n(此即主文档 W1/R12 矛盾的仲裁结果, 请记录)")
                wall_refresh()
            bg(w, done)
        ttk.Button(gf, text="140W", width=8, command=lambda: wall_set(140)).pack(side="left", padx=3)
        ttk.Button(gf, text="115W默认", width=10, command=lambda: wall_set(115)).pack(side="left", padx=3)
        ttk.Button(gf, text="读取当前", width=10, command=wall_refresh).pack(side="left", padx=3)

        # ---- W9-lite 智能场景自动切换 ----
        sf = ttk.LabelFrame(f, text="智能场景(拔电→移动节能 / 插电→办公 · 关闭=仅提示)")
        sf.pack(fill="x", padx=8, pady=6)
        self.auto_scene = tk.BooleanVar(value=False)
        ttk.Checkbutton(sf, text="启用自动应用(状态翻转时全栈联动)",
                        variable=self.auto_scene).pack(anchor="w", padx=8, pady=4)
        ttk.Label(sf, text="说明: 仅监听 AC/DC 翻转并应用既有场景; 全屏检测留待后续版本",
                  foreground="#888").pack(anchor="w", padx=8)

    def _tab_periph(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 外设 ")
        lf = ttk.LabelFrame(f, text="硬件外设 (ServCMD实证 · 唯一入口)")
        lf.pack(fill="both", expand=True, padx=8, pady=8)
        items = [("摄像头", "WEBCAM_ON", "WEBCAM_OFF"), ("WiFi", "WIFI_ON", "WIFI_OFF"),
                 ("蓝牙", "BT_ON", "BT_OFF"), ("Win键锁", "WINKEY_LOCK", "WINKEY_UNLOCK"),
                 ("Fn锁", "FNKEY_LOCK", "FNKEY_UNLOCK"), ("小键盘", "NUMPAD_LOCK", "NUMPAD_UNLOCK"),
                 ("触控板", "TOUCHPAD_ON", "TOUCHPAD_OFF")]
        for i, (name, on, off) in enumerate(items):
            fr = ttk.Frame(lf); fr.grid(row=i//2, column=i%2, sticky="we", padx=8, pady=4)
            ttk.Label(fr, text=name, width=10, font=("Microsoft YaHei UI", 10)).pack(side="left")
            ttk.Button(fr, text="开", width=5, command=lambda o=on: self._gated(
                lambda: self.app.write_servcmd(o, S))).pack(side="left", padx=3)
            ttk.Button(fr, text="关", width=5, command=lambda o=off: self._gated(
                lambda: self.app.write_servcmd(o, S))).pack(side="left", padx=3)
        lf.columnconfigure(0, weight=1); lf.columnconfigure(1, weight=1)

    def _tab_learn(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 协议学习·手动 ")
        top = ttk.Frame(f); top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="● 开始抓包20s", command=self.learn).pack(side="left", padx=4)
        ttk.Button(top, text="命令库", command=self.show_lib).pack(side="left", padx=4)
        ttk.Label(top, text="回放:").pack(side="left", padx=(14, 2))
        ttk.Entry(top, textvariable=self.replay_name, width=20).pack(side="left")
        ttk.Button(top, text="回放", command=self.replay).pack(side="left", padx=4)
        bar2 = ttk.Frame(f); bar2.pack(fill="x", padx=8, pady=2)
        ttk.Label(bar2, text="Topic:").pack(side="left")
        ttk.Entry(bar2, textvariable=self.manual_topic, width=24).pack(side="left", padx=3)
        ttk.Label(bar2, text="Payload:").pack(side="left", padx=6)
        ttk.Entry(bar2, textvariable=self.manual_payload, width=50).pack(side="left", padx=3)
        ttk.Button(bar2, text="发布", command=self.manual_send).pack(side="left", padx=4)
        ttk.Button(bar2, text="存库", command=self.save_manual).pack(side="left")
        ttk.Button(bar2, text="📸保存场景", command=self.save_scenario).pack(side="left", padx=6)
        self.scen_sel = tk.StringVar()
        self.scen_cb = ttk.Combobox(bar2, textvariable=self.scen_sel, width=16, state="readonly")
        self.scen_cb.pack(side="left", padx=(10, 2))
        ttk.Button(bar2, text="📂应用场景", command=self.load_scenario).pack(side="left", padx=4)
        self._reload_scenarios()
        self.capture_text = scrolledtext.ScrolledText(f, font=("Consolas", 9))
        self.capture_text.pack(fill="both", expand=True, padx=8, pady=6)

    def _tab_research(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 🔴研究模式 ")
        head = ttk.Frame(f); head.pack(fill="x", padx=8, pady=6)
        ttk.Label(head, text="本机⛔不支持项集中地(供调研突破)", foreground="#b00020",
                  font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        ttk.Checkbutton(head, text="允许研究发送", variable=self.research).pack(side="right")
        g1 = ttk.LabelFrame(f, text="功耗突破")
        g1.pack(fill="x", padx=8, pady=4)
        self._slider_instant(g1, "Intel降压通道(AMD无效)", "CPU_OffsetCoreVoltage", -300, 0, sup="⛔")
        self._slider_instant(g1, "TGP解锁尝试(116~175)", "GPU_ConfigurableTGPTarget", 116, 175, sup="⛔")
        self._slider_instant(g1, "cTGP-GN21隐藏值", "CustomTGPinGCUforGN21_Value", 60, 175, sup="⛔")
        self._toggle_dual(g1, "内存OC", F, "MEM_MemoryOverClockSwitch", 1, 0, sup="⛔")
        g2 = ttk.LabelFrame(f, text="风扇/安全")
        g2.pack(fill="x", padx=8, pady=4)
        self._toggle_dual(g2, "跳过安全异常保护", F, "FAN_SafetyProtect", 1, 0, sup="⛔")
        g3 = ttk.LabelFrame(f, text="MUX/独显直连(本机无MUX)")
        g3.pack(fill="x", padx=8, pady=4)
        self._toggle_dual(g3, "独显直连", S, "DiscreteGpuDirectConnectionSwitch_Status",
                          "DGPU_DIRECT_CONNECT_TOGGLE_ON", "DGPU_DIRECT_CONNECT_TOGGLE_OFF", sup="⛔")
        g4 = ttk.LabelFrame(f, text="供电扩展")
        g4.pack(fill="x", padx=8, pady=4)
        self._toggle_dual(g4, "TypeC供电优先", S, "TypeCAdaptorPrioritySwitch", 1, 0, sup="⛔")
        self._toggle_dual(g4, "USB关机充电", S, "UsbCharger",
                          "USB_CHARGER_STATUS_ON", "USB_CHARGER_STATUS_OFF", sup="⛔")
        # v5.4 E2 实验: EC 寄存器写1→40ms后回读(CSV日志由调用方留痕; 需管理员)
        e2 = ttk.Frame(g4); e2.pack(fill="x", padx=8, pady=2)
        ttk.Label(e2, text="EC实验(未验证·先记录):", foreground="#b00020").pack(side="left")
        def ec_exp(addr):
            def w():
                import mr_ec_hw as hw
                hw.ec_write(addr, 1)
                time.sleep(0.4)
                rb = hw.ec_read(addr)
                self.log(f"[E2] EC 0x{addr:03X}←1 → 回读={rb}"
                         + (" (None=需管理员)" if rb is None else ""))
            threading.Thread(target=w, daemon=True).start()
        for addr, lab in [(0x7C1, "0x7C1关机USB供电"), (0x7C2, "0x7C2来电开机")]:
            ttk.Button(e2, text=f"试写{lab}", width=16,
                       command=lambda a=addr: ec_exp(a)).pack(side="left", padx=3)
        g5 = ttk.LabelFrame(f, text="新版5.56特性(字段已逆向)")
        g5.pack(fill="x", padx=8, pady=4)
        for name, field, val in [("游戏白名单","GameWhitelistSwitch",1),("iGPU ECO","igpuEcoEnable",1),
                                 ("静音性能","SilentPerformanceMode",1),("LCD Overdrive","LCDOverdrive",1)]:
            self._action_row(g5, name, F, {"Action":"SET", field:val}, sup="⛔")
        g6 = ttk.LabelFrame(f, text="宏/重映射/系统(危险)")
        g6.pack(fill="x", padx=8, pady=4)
        self._toggle_dual(g6, "键位重映射", S, "KeyRemappingEnable", 1, 0, sup="⛔")
        self._action_row(g6, "BIOS级AC断电恢复", S,
                         {"Action":"SET","AcRecoveryBios":1}, sup="⛔")
        g7 = ttk.LabelFrame(f, text="系统(危险区)")
        g7.pack(fill="x", padx=8, pady=4)
        self._action_row(g7, "⚠️危险: System_OFF 关机(实证)", mc.TOPIC_SYS_CTRL,
                         {"Action":"System_OFF"}, sup="⚠️", note="确认已保存", danger=True)

    def _action_row(self, parent, label, topic, payload, sup="⚠️", danger=False, note=""):
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        color = "#d00000" if danger else ("#1a1a1a" if sup=="✅" else ("#b00020" if sup.startswith("⛔") else "#b26a00"))
        ttk.Label(fr, text=f"{sup} {label}" + (f" ({note})" if note else ""),
                  width=54, foreground=color).pack(side="left")
        def go():
            if danger and not messagebox.askyesno("危险操作", "确认执行?"): return
            if not self._gate(sup): return
            self.app.mqtt.publish(topic, json.dumps(payload))
            self.log(f"[SEND] {topic} <- {json.dumps(payload)}")
        ttk.Button(fr, text="发送", width=6, command=go).pack(side="left", padx=6)

    def _tab_log(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 日志 ")
        bar = ttk.Frame(f); bar.pack(fill="x", padx=8, pady=4)
        ttk.Button(bar, text="清空日志", command=lambda: self.log_text.delete("1.0", "end")).pack(side="left")
        self.log_text = scrolledtext.ScrolledText(f, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=8, pady=6)

    # ================= 运行时 =================
    def _mode_click(self, key):
        if not self._gate("✅"): return
        for k, b in self.mode_cards.items():     # 乐观高亮
            b.config(bg="#5e5ae4" if k == key else "#2d2d2d",
                     fg="white" if k == key else "#cccccc")
        cur = self.app.get_fan().get("OperatingMode")
        if cur is not None:
            for k, v in self.MODE_KEY.items():
                if str(cur) == k:
                    self.undo_stack.append(("mode", None, None, v)); self._undo_hint()
        threading.Thread(target=lambda: self.app.set_mode(key), daemon=True).start()

    def dump_query(self, ctrl, payload, prefixes, title):
        st = self.status_text
        st.delete("1.0", "end"); st.insert("end", f"[{title}] 查询中...\n")
        try: self.app.mqtt.publish(ctrl, json.dumps(payload))
        except Exception as e: st.insert("end", f"失败:{e}"); return
        def collect(n):
            hits = {k: v for k, v in self.app.status.items()
                    if k != ctrl and not k.endswith(("/Control", "/Ctrl"))
                    and any(k.startswith(p) for p in prefixes)}
            if hits:
                out = [f"═══ [{title}] ═══"]
                for k in sorted(hits):
                    v = hits[k]
                    if isinstance(v, dict):
                        out.append(f"── {k} ──")
                        for kk, vv in v.items(): out.append(doc_line(kk, vv))
                    else: out.append(f"{k}={v}")
                st.delete("1.0", "end"); st.insert("end", "\n".join(out))
            elif n > 0:
                st.delete("1.0", "end")
                st.insert("end", f"[{title}] 等待{n*0.4:.1f}s... (无响应=本机无此通道)")
                self.root.after(400, lambda: collect(n-1))
            else:
                st.delete("1.0", "end")
                st.insert("end", f"[{title}] ⛔无应答")
        collect(8)

    def _poll(self):
        while True:
            try:
                kind, msg = self.q.get_nowait()
                if kind == "log":
                    self.log_text.insert("end", msg); self.log_text.see("end")
                elif kind == "capture":
                    self.capture_text.insert("end", msg); self.capture_text.see("end")
                elif kind == "charge_result":
                    txt, color = msg
                    self.charge_result.config(text=txt, foreground=color)
                elif kind == "conn":
                    ok, txt = msg
                    self.conn_lbl.config(text=f"● {txt}", fg="#1a7f37" if ok else "#d00000")
                elif kind == "verify":
                    lbl, txt, color = msg
                    try: lbl.config(text=txt, foreground=color)
                    except Exception: pass
            except queue.Empty:
                break
        self._update_home()
        # 智能场景切换(检测前台全屏 + 电池状态)
        self._smart_scene_check()
        if self.auto.get():
            self.root.after(REFRESH_MS, self.refresh_all_silent)
        self.root.after(400, self._poll)

    def _smart_scene_check(self):
        """W9-lite 智能场景: AC/DC 翻转→提示; 勾选[启用自动应用]时全栈联动。
        ponytail: 全屏检测留待后续(需前台窗口枚举, 收益存疑), 升级点在下方单一函数内。"""
        try:
            bat = self.app.status.get("System/BatteryProtection", {})
            power = bat.get("BatteryPowerStatus")      # 1=电池 0=AC(抓包口径)
            if power is None:
                return
            if not hasattr(self, "_last_power"):
                self._last_power = power
                return
            if power != self._last_power:
                on_battery = str(power) == "1"
                name = "移动节能" if on_battery else "办公"
                self.log("[⚡智能] 电源翻转: " + ("拔电" if on_battery else "插电"))
                if getattr(self, "auto_scene", None) and self.auto_scene.get() \
                        and hasattr(self, "_apply_scenario"):
                    self._apply_scenario(name)
                    self.log(f"[⚡智能] 已自动应用场景: {name}")
                else:
                    self.log(f"[⚡智能] 建议: {name} (电源·系统页可开自动)")
            self._last_power = power
        except Exception:
            pass

    def _update_home(self):
        fan = self.app.status.get(mc.TOPIC_FAN_STA, {})
        setting = self.app.status.get(mc.TOPIC_SET_STA, {})
        bat = self.app.status.get("System/BatteryProtection", {})
        tray = self.app.status.get("Tray/Status", {})
        merged = {**fan, **setting, **bat, **tray}   # Tray的OperatingMode是真源(抓包证实)
        om = str(merged.get("OperatingMode") if merged.get("OperatingMode") is not None else "")
        for k, b in self.mode_cards.items():
            mk = self.MODE_KEY.get(om)          # 正向: om("1")→"gaming"
            b.config(bg="#5e5ae4" if mk == k else "#2d2d2d",
                     fg="white" if mk == k else "#cccccc")
        # 重绘卡片文本
        for title, (card, keys) in self.cards.items():
            card.delete("all")
            card.create_text(10, 14, text=title, anchor="w", fill="#5e5ae4",
                             font=("Microsoft YaHei UI", 10, "bold"))
            y = 36
            for k in keys:
                v = merged.get(k, "-")
                if k == "FanBoostEnable": v = "🔥开" if str(v) == "1" else ("关" if str(v) == "0" else v)
                if k == "FAN_SafetyProtect": v = "⚠️触发" if str(v) == "1" else "正常"
                if k == "BatteryAbnormal": v = "⚠️异常" if str(v) == "1" else "正常"
                if k == "HealthProtectionStatus": v = {"1": "激进", "2": "均衡保护", "3": "养生"}.get(str(v), v)
                if k == "AcRecoverySwitch_Status": v = "开" if "ON" in str(v) and "OFF" not in str(v) else "关"
                if k == "FAN_TableName": v = f"曲线表 {v}"
                if k == "FAN_FanSwitchSpeed": v = f"{v} RPM"
                if "Offset" in k or "Target" in k and "Tcc" not in k: v = f"{v}"
                doc = FIELD_DOC.get(k)
                lab = doc[0].split("(")[0] if doc else k[:20]
                card.create_text(10, y, text=lab, anchor="w", fill="#888", font=("Microsoft YaHei UI", 8))
                card.create_text(240, y, text=str(v)[:24], anchor="e", fill="#ddd", font=("Consolas", 9))
                y += 22
        # 开关当前状态更新(v5遗漏修复)
        for k, (lb, mapping) in self.toggles.items():
            v = str(merged.get(k, "-"))
            lb.config(text=mapping.get(v, v[:22]))
        # EC实时(温度/风扇)
        ec = self.app.status.get("EC/Realtime", {})
        if ec and "EC实时" in self.cards:
            card, keys = self.cards["EC实时"]
            card.delete("all")
            card.create_text(10, 14, text="EC实时", anchor="w", fill="#ff6b6b",
                             font=("Microsoft YaHei UI", 10, "bold"))
            yy = 36
            labels = {"__ec_cpu": "CPU温度", "__ec_gpu": "GPU温度",
                      "__ec_duty": "CPU风扇", "__ec_gduty": "GPU风扇",
                      "__ec_rpm": "CPU转速"}
            for k in keys:
                lab = labels.get(k, k[:12])
                v = ec.get(k, "-")
                s = str(v)
                num = int(s) if s.isdigit() else None
                hot = (num is not None and (("温度" in lab and num > 85) or
                                            ("风扇" in lab and "%" not in s and False)))
                if "风扇" in lab and s.endswith("%"):
                    hot = int(s[:-1]) > 90
                color = "#ff6b6b" if hot else "#ffaa4d"
                card.create_text(10, yy, text=lab, anchor="w", fill="#888", font=("Microsoft YaHei UI", 8))
                card.create_text(240, yy, text=str(v), anchor="e", fill=color, font=("Consolas", 10, "bold"))
                yy += 22

        # GPU实时(pynvml)
        if hasattr(self, 'nvml_h') and self.nvml_h:
            try:
                pynvml = self.pynvml
                h = self.nvml_h
                temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                pw = pynvml.nvmlDeviceGetPowerUsage(h) / 1000
                util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
                clk = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM)
                nvvals = {"__nvml_temp": f"{temp}°C", "__nvml_power": f"{pw:.1f}W",
                          "__nvml_util": f"{util}%", "__nvml_clock": f"{clk}MHz"}
                if "GPU实时" in self.cards:
                    card, keys = self.cards["GPU实时"]
                    card.delete("all")
                    card.create_text(10, 14, text="GPU实时", anchor="w", fill="#4caf50",
                                     font=("Microsoft YaHei UI", 10, "bold"))
                    yy = 36
                    labels = ["温度", "功耗", "利用率", "SM时钟"]
                    for k, lab in zip(keys, labels):
                        v = nvvals.get(k, "-")
                        card.create_text(10, yy, text=lab, anchor="w", fill="#888", font=("Microsoft YaHei UI", 8))
                        card.create_text(240, yy, text=str(v), anchor="e", fill="#4caf50", font=("Consolas", 10, "bold"))
                        yy += 22
            except Exception:
                pass
        # 滑条同步当前状态值(用户3秒内拖动过则不覆盖位置)
        now = time.time()
        for key, (var, curlb) in self.sliders.items():
            topic, field = key.split("|", 1)
            src = self.app.status.get(topic.replace("/Ctrl","/Status").replace("/Control","/Status"), {})
            if field in src:
                curlb.config(text=f"当前:{src[field]}")
                if now - self._touch.get(key, 0) > 3:
                    try:
                        iv = int(float(src[field]))
                        if iv != var.get(): var.set(iv)
                    except Exception: pass

    def refresh_all(self): self.refresh_worker(); self.root.after(1200, self._render_status)
    def refresh_all_silent(self): self.refresh_worker()

    def refresh_worker(self):
        def w():
            try:
                self.app.get_fan(); self.app.get_setting()
                self.app.mqtt.publish(mc.TOPIC_BAT_CTRL, '{"Report":"GET"}')
                self._ec_read()
            except Exception: pass
        threading.Thread(target=w, daemon=True).start()

    def _ec_read(self):
        """EC 实时(v5.4): 经 mr_ec_hw 的 UWACPIDriver 直读(免管理员, 官方ACPIDriverDll通道)。
        RPM 字节序: 0x464=高字节 0x465=低字节; GPU温度0x44F为死地址,GPU卡有nvidia-smi兜底"""
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import mr_ec_hw as ec
            c = ec.get_cpu_temp()
            if c is None:
                return
            self.app.status["EC/Realtime"] = {
                "__ec_cpu": c,
                "__ec_gpu": ec.get_gpu_temp(),
                "__ec_duty": "%s%%" % ec.get_fan_duty(),
                "__ec_gduty": "%s%%" % ec.get_gpu_duty(),
                "__ec_rpm": ec.get_fan_rpm(),
            }
        except Exception:
            pass


    def _render_status(self):
        lines = []
        for tname in sorted(self.app.status.keys()):
            d = self.app.status[tname]
            if isinstance(d, dict):
                lines.append(f"═══ {tname} ═══")
                for k, v in d.items(): lines.append(doc_line(k, v))
        self.status_text.delete("1.0", "end")
        self.status_text.insert("end", "\n".join(lines) if lines else "暂无数据")

    def apply_mode(self):
        if not self._gate("✅"): return
        key = self.MODE_KEY[self.mode_var.get()]
        threading.Thread(target=lambda: self.app.set_mode(key), daemon=True).start()

    def learn(self):
        def worker():
            self.app.start_capture()
            self.cap("─── 抓包开始(20s内操作官方UI) ───")
            time.sleep(20)
            cap = self.app.stop_capture_save()
            for t, p in cap: self.cap(f"[{t}] {p[:160]}")
            self.cap(f"─── 保存{len(cap)}条 ───")
        threading.Thread(target=worker, daemon=True).start()

    def show_lib(self):
        lib = self.app.load_lib()
        self.capture_text.delete("1.0", "end")
        self.capture_text.insert("end", f"=== 命令库 {len(lib)}条 ===\n")
        for k, v in lib.items():
            self.capture_text.insert("end", f"{k:<24} {v['topic']:<34} {v['payload'][:100]}\n")

    def replay(self):
        n = self.replay_name.get().strip()
        if not n: messagebox.showinfo("提示", "输入名称"); return
        if not self.write_enabled.get():
            if messagebox.askyesno("安全锁", "启用写入并回放?"): self.write_enabled.set(True)
            else: return
        try: self.app.replay(n)
        except KeyError as e: messagebox.showerror("错误", str(e))

    def manual_send(self):
        if not self.write_enabled.get():
            if messagebox.askyesno("安全锁", "启用写入并发布?"): self.write_enabled.set(True)
            else: return
        t, p = self.manual_topic.get(), self.manual_payload.get()
        try: json.loads(p)
        except Exception: messagebox.showerror("错误", "Payload非JSON"); return
        self.app.mqtt.publish(t, p); self.log(f"[SEND] {t} <- {p}")

    def save_manual(self):
        lib = self.app.load_lib()
        name = f"manual_{int(time.time())%100000}"
        lib[name] = {"topic": self.manual_topic.get(), "payload": self.manual_payload.get()}
        json.dump(lib, open(mc.LIB_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self.cap(f"已存库: {name}")

    def save_scenario(self):
        """保存当前全部状态为自定义场景"""
        if not self.write_enabled.get():
            messagebox.showwarning("安全锁", "先启用写入"); return
        name = f"custom_{int(time.time())%100000}"
        snap = {}
        f = self.app.get_fan()
        for k in ["CPU_PL1","CPU_PL2","CPU_PL4","CPU_TccOffset","CPU_AmdSPL","CPU_AmdSPPT",
                  "CPU_AmdFPPT","CPU_AmdTccTarget","GPU_CoreClockOffsetOC","GPU_MemoryClockOffsetOC",
                  "GPU_TargetTemperature","GPU_DynamicBoost","OverClockingSwitch"]:
            if f.get(k) is not None: snap[k] = f[k]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_scenarios.json")
        lib = {}
        if os.path.exists(path):
            lib = json.load(open(path, encoding="utf-8"))
        lib[name] = snap
        json.dump(lib, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self._reload_scenarios()
        self.scen_sel.set(name)
        self.log(f"[📸场景] {name} 已保存({len(snap)}参数)")

    def _scen_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_scenarios.json")

    def _reload_scenarios(self):
        names = []
        try:
            pth = self._scen_path()
            if os.path.exists(pth):
                names = list(json.load(open(pth, encoding="utf-8")).keys())
        except Exception:
            pass
        self.scen_cb["values"] = names

    def load_scenario(self):
        """W13 闭环: 应用已保存场景(SET_OPERATING_MODE_DETAIL 逐字段+0.45s间隔)"""
        name = self.scen_sel.get().strip()
        if not name:
            messagebox.showinfo("提示", "先选择要应用的场景"); return
        try:
            snap = json.load(open(self._scen_path(), encoding="utf-8")).get(name)
        except Exception as e:
            messagebox.showerror("错误", str(e)); return
        if not snap:
            messagebox.showerror("错误", f"{name} 不存在"); return
        if not self.write_enabled.get():
            if messagebox.askyesno("安全锁", "启用写入并应用场景?"):
                self.write_enabled.set(True)
            else: return
        self.log(f"[📂场景] 应用 {name}({len(snap)}参数)...")
        def w():
            for k, v in snap.items():
                wk = self.app.WIRE_KEY.get(k, k)
                self.app.mqtt.publish(F, json.dumps(
                    {"Action": "SET_OPERATING_MODE_DETAIL", wk: v}))
                time.sleep(0.45)
            self.log(f"[📂场景] {name} 全部参数已发送")
        threading.Thread(target=w, daemon=True).start()

    def _gpu_wall_verified(self, watt):
        """E1: nvidia-smi -pl 设定后回读验证(拒绝则 current 不变)"""
        def w():
            ok, dt = wc.gpu_wall_set(watt)
            self.log(f"[E1] -pl {watt}: {'✅生效' if ok else '❌被驱动拒绝'} | {dt}")
        threading.Thread(target=w, daemon=True).start()

    def _lock_clock(self, mhz):
        """锁定GPU时钟(等效VF降压)"""
        def w():
            r = subprocess.run(["nvidia-smi", "-lgc", f"{mhz},{mhz}"],
                               capture_output=True, text=True)
            if "All done" in (r.stdout + r.stderr):
                self.log(f"[GPU降压] ✅ 锁定 {mhz}MHz 成功")
            else:
                self.log(f"[GPU降压] 结果: {(r.stdout + r.stderr).strip()[:80]}")
        threading.Thread(target=w, daemon=True).start()

    def _unlock_clock(self):
        """恢复GPU默认时钟"""
        def w():
            r = subprocess.run(["nvidia-smi", "-rgc"], capture_output=True, text=True)
            self.log(f"[GPU降压] 已恢复默认频率")
        threading.Thread(target=w, daemon=True).start()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.deiconify(); self.root.mainloop()

    def _close(self):
        try: self.app.stop()
        finally: self.root.destroy()


def run(app_factory):
    app = app_factory()
    g = GuiApp(app)
    g.run()

if __name__ == "__main__":
    run(lambda: mc.MrConsole())
