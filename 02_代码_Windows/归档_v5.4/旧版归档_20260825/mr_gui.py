#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MR Console 图形界面 · 全功能版 v3
- 支持项按官方控制台分页；本机全部⛔不支持项集中于「🔴研究模式」单页
- 液冷相关内容已整体移除（按要求）
由 mr_console.py gui 调用
"""
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

import mr_console as mc

REFRESH_MS = 5000

S = mc.TOPIC_SET_CTRL
F = mc.TOPIC_FAN_CTRL
KB = mc.TOPIC_KB_CTRL

RGB_EFFECTS = [
    ("Single 单色", "Single", "✅"), ("Breathing 呼吸", "Breathing", "✅"),
    ("Wave 波浪", "Wave", "⚠️需多区"), ("Reactive 星光", "Reactive", "⚠️"),
    ("Rainbow 彩虹", "Rainbow", "✅"), ("Ripple 涟漪", "Ripple", "⚠️需多区"),
    ("Raindrop 雨滴", "Raindrop", "⚠️"), ("Neon 霓虹", "Neon", "⚠️"),
    ("Marquee 贪吃蛇", "Marquee", "⚠️"), ("Stack 堆叠", "Stack", "⚠️需多区"),
    ("Impact 冲击", "Impact", "⚠️"), ("Spark 火花", "Spark", "⚠️"),
    ("Music 音乐律动", "Music", "⚠️需0x76F"),
    ("UserMode 自定义", "UserMode", "✅"), ("Gaming 游戏", "Gaming", "✅"),
    ("Flash 闪烁", "Flash", "⚠️"), ("Mix 混合", "Mix", "⚠️需多区"),
    ("RippleO 反涟漪", "RippleO", "⚠️需多区"), ("Alphabet 字母", "Alphabet", "⚠️"),
    ("StarHitting 星击", "StarHitting", "⚠️"), ("StarSpark 星火", "StarSpark", "⚠️"),
    ("Thinking 思考", "Thinking", "⚠️"), ("Manual 手动逐键", "Manual", "⚠️需ITE HID"),
    ("BatteryPercent 电量灯", "BatteryPercent", "✅软件模拟"),
    ("ColorfulWave 七彩波浪", "ColorfulWave", "⚠️需多区"), ("Dawn 黎明", "Dawn", "⚠️"),
]

DISPLAY_MODES = ["DISPLAY_STANDARD_MODE", "DISPLAY_GAMING_MODE", "DISPLAY_VIDEO_MODE",
                 "DISPLAY_READ_MODE", "DISPLAY_CUSTOMIZED_MODE"]

BATTERY_ACTIONS = [
    ("健康模式", {"Action": "HEALTHYMODE"}),
    ("均衡模式(推测)", {"Action": "BALANCEDMODE"}),
    ("性能模式(推测)", {"Action": "PERFORMANCEMODE"}),
]

# ============================================================
# 字段注释库: 字段 -> (是什么, 合理/原厂值, 增减代表什么)
# ============================================================
FIELD_DOC = {
    # ---- 性能模式 ----
    "OperatingMode":       ("当前性能档位", "0办公/1均衡/2狂暴/3自定义", "切狂暴=性能↑风扇↑"),
    "ProfileName":         ("生效的配置文件", "Mode{档位}_Profile{n}", "-"),
    "OverClockingSwitch":  ("超频总开关", "1=开 0=关", "开后下方OC参数才生效"),
    "TurboModeOption":     ("狂暴子档", "1~4(默认2)", "↑=更激进"),
    "PowerMode":           ("Windows电源方案", "1平衡/其他", "-"),
    "GamingProfileIndex":  ("均衡档配置号", "0~4", "-"),
    "OfficeProfileIndex":  ("办公档配置号", "0~4", "-"),
    "TurboProfileIndex":   ("狂暴档配置号", "0~4", "-"),
    "CustomProfileIndex":  ("自定义档配置号", "0~4", "-"),
    # ---- CPU ----
    "CPU_PL1":             ("CPU持续功耗墙(W)", "本机10~80, 原厂80", "↑性能↑温度↑风扇"),
    "CPU_PL2":             ("CPU短时爆发墙(W)", "本机10~80, 原厂80", "同上,影响爆发"),
    "CPU_PL4":             ("CPU瞬时峰值(W)", "本机10~100, 原厂100", "毫秒级冲刺"),
    "CPU_PL1Maximum":      ("PL1硬件上限", "80", "服务端钳制值"),
    "CPU_PL1Minimum":      ("PL1下限", "10", "-"),
    "CPU_PL2Maximum":      ("PL2硬件上限", "80", "-"),
    "CPU_PL4Maximum":      ("PL4硬件上限", "100", "-"),
    "CPU_TccOffset":       ("CPU温度墙(°C)", "原厂99~100", "↓=提前降频降温"),
    "CPU_TccOffsetMaximum": ("温度墙上限", "100", "-"),
    "CPU_TccOffsetSwitch": ("自定义温度墙开关", "0/1", "-"),
    "CPU_OffsetCoreVoltage": ("核心电压偏移(mV)", "Intel专属,AMD恒0", "负值=降压(本机不可用)"),
    "CPU_OffsetCoreVoltageSupport": ("降压支持位", "255=按平台判定", "本机AMD=无效"),
    "CPU_AmdSPL":          ("AMD长时功耗(W)", "≤80", "↑性能↑热"),
    "CPU_AmdSPPT":         ("AMD短时功耗(W)", "≤80", "-"),
    "CPU_AmdFPPT":         ("AMD峰值功耗(W)", "≤100", "-"),
    "CPU_AmdTccTarget":    ("AMD温度目标(°C)", "92~99", "↓降温"),
    "CPU_AmdOverClockSupport": ("AMD超频支持", "0=SMU锁死(终局)", "无法改变"),
    "CPU_AmdCoreFreq(OC)": ("AMD频率偏移", "Max=0即不支持", "-"),
    # ---- GPU ----
    "GPU_CoreClockOffset":  ("GPU核心频率偏移(MHz)", "0~+250", "↑帧率↑功耗↑温度"),
    "GPU_CoreClockOffsetOC": ("核心偏移(OC后)", "0~250", "同上"),
    "GPU_CoreClockOffsetMaximum": ("核心上限", "250", "HWOC液冷机型同值"),
    "GPU_MemoryClockOffset": ("显存偏移(MHz)", "-1000~+1000", "↑带宽/基准分"),
    "GPU_MemoryClockOffsetOC": ("显存偏移(OC后)", "±1000", "HWOC±1800"),
    "GPU_MemoryClockOffsetMaximumHWOC": ("显存上限(液冷机型)", "1800", "本机无液冷用不到"),
    "GPU_TargetTemperature": ("GPU目标温度(°C)", "75~87, 原厂83~87", "↓=更早降频更凉"),
    "GPU_ConfigurableTGPSwitch": ("cTGP开关", "0/1", "-"),
    "GPU_ConfigurableTGPTarget": ("TGP功耗(W)", "本机min=max=115锁死", "↑=性能↑(本机改不动)"),
    "GPU_DynamicBoostSwitch": ("DynamicBoost开关", "0/1", "开=CPU/GPU间自动挪功率"),
    "GPU_DynamicBoost":     ("动态增强量(W)", "5~25, 自动", "系统自动管理"),
    "CustomTGPinGCUforGN21_Value": ("隐藏cTGP值(GN21独占)", "-", "官方未公开特性"),
    "CustomTGPinGCUforGN21_Enable": ("隐藏cTGP开关", "-", "-"),
    "GPU_WhisperModeSwitch": ("低语模式开关", "0/1", "开=限帧省电降噪"),
    "GPU_WhisperModeSetting": ("低语档位", "QUIETER/QUIET/BALANCED", "-"),
    # ---- 内存 ----
    "MEM_MemoryOverClockSupport": ("内存OC支持", "本机=0不支持", "-"),
    "MEM_MemoryOverClockSwitch": ("内存OC开关", "-", "本机发送无效"),
    # ---- 风扇 ----
    "FAN_TableName":        ("风扇曲线表编号", "M{档}T{表} 如M3T1", "-"),
    "FAN_FanSwitchSpeedEnabled": ("起转转速控制开关", "0/1", "开=低于此转速停转/降速"),
    "FAN_FanSwitchSpeed":   ("起转转速(RPM)", "原厂300! >1500易异常", "↑低负载噪音↑"),
    "FAN_SafetyProtect":    ("安全保护状态", "0正常", "1=风扇异常已触发保护"),
    "FAN_SafetyProtectNotify": ("保护弹窗通知", "0/1", "-"),
    "FanBoostEnable":       ("风扇强冷", "本机无按钮支持位", "可用ServCMD指令绕过"),
    # ---- 平台/杂项 ----
    "IsAMDPlatform":        ("AMD平台", "True", "-"),
    "IsNvGpu":              ("NVIDIA显卡", "True", "-"),
    "OcSupport":            ("超频页支持", "True", "-"),
    "BSOD_DefaultNotify":   ("蓝屏恢复提示", "0/1", "崩溃后自动恢复配置时弹窗"),
    "BSOD_TimestampRestored": ("上次恢复时间", "-", "-"),
    # ---- Setting/Status ----
    "WinKey":               ("Win键锁", "UNLOCK日常/LOCK游戏防误触", "-"),
    "LightBar":             ("灯条状态", "本机无灯条硬件", "恒ON无效"),
    "UsbCharger":           ("USB关机充电", "本机无支持位", "-"),
    "DGpu":                 ("输出模式", "AUTO推荐", "本机无MUX仅此项"),
    "OSD":                  ("屏幕悬浮OSD", "OFF=隐藏", "调音量亮度时的浮层"),
    "DisplayFeatureStatus": ("显示增强总开关", "OFF=原生画面", "开=下方色彩参数生效"),
    "DisplayMode":          ("画面模式", "STANDARD标准", "GAMING鲜艳/VIDEO影音/READ护眼"),
    "GamingBrightness":     ("游戏模式亮度", "0~100", "↑亮但可能过曝"),
    "GamingColorTemp":      ("色温", "0默认", "↑偏冷蓝 ↓偏暖黄"),
    "GamingContrast":       ("对比度", "0默认", "↑浓烈可丢暗部"),
    "GamingRed/Green/Blue": ("三通道增益", "0~128, 128=中性", "失衡=偏色"),
    "VideoBrightness":      ("视频模式亮度", "0~100", "-"),
    "ReadBrightness":       ("阅读模式亮度", "0~100", "-"),
    "ReadBlue":             ("阅读模式蓝光", "负值=减蓝护眼", "↓越护眼越发黄"),
    "CutomizedBrightness":  ("自定义亮度", "0~100", "(官方拼写如此)"),
    "SingleColorKBBL":      ("键盘灯电源", "ON/OFF", "-"),
    "CloseTimer":           ("自动关屏(分)", "0=永不", "省电"),
    "ColorCalibrationResultCode": ("校准结果码", "1=成功", "其他=失败码"),
    "NumPad":               ("小键盘锁", "LOCK/UNLOCK", "-"),
    "FnKey":                ("Fn键交换", "UNLOCK常规", "LOCK=多媒体键优先"),
    "TouchpadToggle":       ("触控板", "ON/OFF", "外接鼠标可关"),
    "AcRecoverySwitch_Status": ("断电恢复来电自启", "ON=来电开机", "下载/挂机有用"),
    "AcRecoverySwitch_Support": ("断电恢复支持", "Support(软)/BIOS级⛔", "-"),
    "FnWith1HotkeySwitch_Status": ("Fn+1组合热键", "ON/OFF", "-"),
    "DiscreteGpuDirectConnectionSwitch_Status": ("独显直连", "本机⛔无MUX", "研究页可试探"),
    "DiscreteGpuDirectConnectionSwitch_Support": ("独显直连支持", "NotSupport", "-"),
    # ---- 电池 ----
    "BatteryPowerStatus":   ("供电状态", "1=电池供电", "插电另值"),
    "BatteryPercent":       ("电量%", "0~100", "-"),
    "BatteryTime":          ("剩余使用时间", "分钟,-1=计算中", "-"),
    "BatteryFullTime":      ("充满剩余(分)", "-1=未在充", "-"),
    "HealthProtectionStatus": ("健康保护档", "2=均衡保护", "限充延长寿命"),
    "TypeCAdaptorPrioritySwitch": ("TypeC供电优先", "⛔本机不支持", "-"),
    "TypeCAdaptorPrioritySupport": ("TypeC支持", "False", "-"),
    "BatteryAbnormal":      ("电池异常", "0正常", "1建议售后检测"),
}

def doc_line(k, v):
    """渲染带注释的状态行"""
    vs = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    base = f"  {k:<34} = {vs[:60]}"
    doc = FIELD_DOC.get(k)
    if doc:
        what, ok, delta = doc
        return f"{base}\n      └ {what} | 参考: {ok} | {delta}"
    return base


class GuiApp:
    def __init__(self, app: mc.MrConsole):
        self.app = app
        self.q = queue.Queue()
        self._build_root()
        # ---- 变量(root之后) ----
        self.write_enabled = tk.BooleanVar(value=False)   # 全局写入锁
        self.research = tk.BooleanVar(value=False)        # 研究发送使能(研究页内)
        self.auto = tk.BooleanVar(value=True)
        self.mode_var = tk.StringVar(value="")
        self.replay_name = tk.StringVar()
        self.manual_topic = tk.StringVar(value="Fan/Control")
        self.manual_payload = tk.StringVar(value='{"Action":"GETSTATUS"}')
        self.sliders = {}
        self.toggles = {}
        self._build_widgets()
        self._connect_bg()
        self.root.after(300, self._poll)
        self.root.after(900, self.refresh_all)

    def log(self, msg):
        self.q.put(("log", f"[{time.strftime('%H:%M:%S')}] {msg}\n"))

    def cap(self, msg):
        self.q.put(("capture", msg + "\n"))

    def _connect_bg(self):
        def worker():
            try:
                self.app.start()
                self.q.put(("conn", ("ok", "已连接 MQTT 13688 (PluginClient_5)")))
                self.log("已连接 MQTT Broker 13688 (PluginClient_5)")
            except Exception as e:
                self.q.put(("conn", ("fail", f"连接失败: {e}")))
                self.log(f"连接失败: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _write_state_changed(self, *a):
        if self.write_enabled.get():
            self.write_chk.config(text="✍ 写入已启用(点击关闭)", fg="#d00000")
            self.log("[安全锁] ✍ 写入已启用 —— 所有发送按钮生效")
        else:
            self.write_chk.config(text="✍ 启用写入(只读模式)", fg="#1a7f37")
            self.log("[安全锁] 只读模式")

    # ================= UI =================
    def _build_root(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def _build_widgets(self):
        r = self.root
        r.title("MR Console · 机械革命电竞控制台 (自制全功能版)")
        r.geometry("1120x760")

        # ---- ★顶部常驻工具条(所有标签页之上, 始终可见) ----
        top = ttk.Frame(r); top.pack(fill="x", padx=12, pady=(8, 2))
        ttk.Label(top, text="MR Console", font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        self.conn_lbl = tk.Label(top, text="● 连接中...", fg="#c08000",
                                 font=("Microsoft YaHei UI", 9))
        self.conn_lbl.pack(side="left", padx=16)
        self.write_chk = tk.Checkbutton(top, text="✍ 启用写入(只读模式)", variable=self.write_enabled,
                                        font=("Microsoft YaHei UI", 10, "bold"),
                                        fg="#1a7f37", activeforeground="#d00000",
                                        selectcolor="#f0f0f0")
        self.write_chk.pack(side="right")
        ttk.Checkbutton(top, text="自动刷新5s", variable=self.auto).pack(side="right", padx=12)
        self.write_enabled.trace_add("write", self._write_state_changed)

        self.nb = nb = ttk.Notebook(r)
        nb.pack(fill="both", expand=True, padx=6, pady=4)

        self._tab_status(nb)
        self._tab_perf(nb)
        self._tab_oc(nb)
        self._tab_fan(nb)
        self._tab_kb(nb)
        self._tab_display(nb)
        self._tab_battery(nb)
        self._tab_learn(nb)
        self._tab_research(nb)      # ★ 全部⛔项集中于此

    # ---------- 通用行 ----------
    def _toggle_row(self, parent, label, topic, field, on_val, off_val,
                    sup="✅", status_key=None):
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        color = "#b00020" if sup.startswith("⛔") else "#1a1a1a"
        ttk.Label(fr, text=label, width=32, foreground=color).pack(side="left")

        def apply(v):
            if not self._gate(sup):
                return
            self.app.set_field(topic, field, v)
        ttk.Button(fr, text="开", width=4, command=lambda: apply(on_val)).pack(side="left", padx=2)
        ttk.Button(fr, text="关", width=4, command=lambda: apply(off_val)).pack(side="left", padx=2)
        if status_key:
            lb = ttk.Label(fr, text="-", width=28, foreground="#555")
            lb.pack(side="left", padx=8)
            self.toggles[status_key] = (lb, {str(on_val): "当前: 开", str(off_val): "当前: 关"})

    def _slider_row(self, parent, label, topic, field, mn, mx, sup="✅", unit=""):
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        color = "#b00020" if sup.startswith("⛔") else "#1a1a1a"
        ttk.Label(fr, text=f"{sup} {label}", width=32, foreground=color).pack(side="left")
        var = tk.IntVar(value=mn)
        ttk.Scale(fr, from_=mn, to=mx, orient="horizontal", variable=var, length=290).pack(side="left", padx=6)
        lb = ttk.Label(fr, text=f"{mn}{unit}", width=9)
        lb.pack(side="left")
        var.trace_add("write", lambda *a, v=var, l=lb, u=unit: l.config(text=f"{v.get()}{u}"))
        cur = ttk.Label(fr, text="-", width=10, foreground="#555"); cur.pack(side="left", padx=4)
        key = f"{topic}|{field}"
        self.sliders[key] = (var, cur)

        def apply():
            if not self._gate(sup):
                return
            self.app.set_field(topic, field, var.get())
            self.log(f"[SLIDER] {field}={var.get()} 已发送, 观察状态回读")
        ttk.Button(fr, text="发送", width=6, command=apply).pack(side="left", padx=4)

    def _radio_row(self, parent, label, topic, field, options, sup="✅"):
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        color = "#b00020" if sup.startswith("⛔") else "#1a1a1a"
        ttk.Label(fr, text=f"{sup} {label}", width=32, foreground=color).pack(side="left")
        var = tk.StringVar(value=options[0])
        inner = ttk.Frame(fr); inner.pack(side="left")
        for opt in options:
            ttk.Radiobutton(inner, text=opt.replace("DISPLAY_", "").replace("_MODE", ""),
                            value=opt, variable=var).pack(side="left", padx=4)

        def apply():
            if not self._gate(sup):
                return
            self.app.set_field(topic, field, var.get())
        ttk.Button(fr, text="发送", width=6, command=apply).pack(side="left", padx=6)

    def _action_row(self, parent, label, topic, payload, sup="⚠️", note="",
                    danger=False):
        fr = ttk.Frame(parent); fr.pack(fill="x", padx=8, pady=2)
        if danger:
            color = "#d00000"
        elif sup == "✅":
            color = "#1a1a1a"
        elif sup.startswith("⛔"):
            color = "#b00020"
        else:
            color = "#b26a00"
        txt = f"{sup} {label}" + (f"   ({note})" if note else "")
        ttk.Label(fr, text=txt, width=54, foreground=color).pack(side="left")

        def apply():
            if danger:
                if not messagebox.askyesno("危险操作", "即将发送 System_OFF 关机指令!\n确认所有工作已保存?"):
                    return
            if not self._gate(sup):
                return
            self.mqtt_pub(topic, json.dumps(payload))
        ttk.Button(fr, text="发送", width=6, command=apply).pack(side="left", padx=6)

    def _gate(self, sup):
        if sup.startswith("⛔"):
            if not self.research.get():
                if messagebox.askyesno("研究模式",
                        "该项为本机⛔不支持项(位于研究模式页)。\n\n是否开启[允许研究发送]并继续?"):
                    self.research.set(True)
                else:
                    return False
            if not self.write_enabled.get():
                if messagebox.askyesno("安全锁", "写入未启用。是否启用[✍ 启用写入]并继续?"):
                    self.write_enabled.set(True)
                else:
                    return False
            return True
        if not self.write_enabled.get():
            if messagebox.askyesno("安全锁", "写入未启用(顶部工具栏)。\n\n是否现在启用并执行本次操作?"):
                self.write_enabled.set(True)
            else:
                return False
        return True

    def mqtt_pub(self, topic, payload):
        self.app.mqtt.publish(topic, payload)
        self.log(f"[SEND] {topic} <- {payload}")

    def servcmd(self, cmd, topic):
        """真实ServCMD指令(双键), 仅需全局写入锁"""
        if not self.write_enabled.get():
            messagebox.showwarning("安全锁", "请先勾选底部[启用写入]")
            return
        self.app.write_servcmd(cmd, topic)

    # ================= Tabs =================
    def _tab_status(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 状态总览 ")
        bar = ttk.Frame(f); bar.pack(fill="x", padx=8, pady=4)
        ttk.Button(bar, text="⟳ 全部刷新", command=self.refresh_all).pack(side="left")
        ttk.Button(bar, text="🗑 清空显示", command=lambda: self.status_text.delete("1.0", "end")
                   ).pack(side="left", padx=4)
        ttk.Label(bar, text="单项深度查询:").pack(side="left", padx=12)
        # 按钮: (名称, 控制topic, 载荷, 应答主题前缀列表)
        qcfg = [
            ("风扇/OC",   mc.TOPIC_FAN_CTRL, {"Action": "GETSTATUS"}, ("Fan/",)),
            ("设置",      mc.TOPIC_SET_CTRL, {"Action": "GETSTATUS"}, ("Setting/",)),
            ("电池",      mc.TOPIC_BAT_CTRL, {"Report": "GET"}, ("System/BatteryProtection", "Battery")),
            ("键盘",      mc.TOPIC_KB_CTRL, {"Action": "GETSTATUS"}, ("Keyboard",)),
            ("显卡信息",  mc.TOPIC_SYS_CTRL, {"Action": "GetGraphicInfo"}, ("System/HardwareInfo", "GPUDevice")),
            ("OEM支持",  "Customize/Control", {"Action": "GETSUPPORT"}, ("Customize/Support",)),
        ]
        for name, t, p, pre in qcfg:
            ttk.Button(bar, text=name,
                       command=lambda t=t, p=p, pre=pre, n=name: self.dump_query(t, p, pre, n)
                       ).pack(side="left", padx=3)
        self.status_text = scrolledtext.ScrolledText(f, font=("Consolas", 10))
        self.status_text.pack(fill="both", expand=True, padx=8, pady=4)

    def dump_query(self, ctrl_topic, payload, prefixes, title):
        """发送查询 → 定向收集匹配前缀的全部应答(含新出现与已更新) → 即时渲染"""
        st = self.status_text
        st.delete("1.0", "end")
        st.insert("end", f"[{title}] 已发布 {ctrl_topic} {json.dumps(payload)} , 等待应答...\n")
        try:
            self.app.mqtt.publish(ctrl_topic, json.dumps(payload))
        except Exception as e:
            st.insert("end", f"发送失败: {e}\n")
            return
        snap = json.dumps(self.app.status, sort_keys=True)   # 用于检测已有topic内容更新

        def collect(rounds_left):
            hits = {k: v for k, v in self.app.status.items()
                    if k != ctrl_topic                                  # 排除自身发布回声
                    and any(k.startswith(p) for p in prefixes)}
            if hits:
                out = [f"═══ [{title}] 收到 {len(hits)} 个应答 (带注释: 是什么|参考值|增减含义) ═══"]
                for k in sorted(hits):
                    v = hits[k]
                    if isinstance(v, dict):
                        out.append(f"── {k} ──")
                        for kk, vv in v.items():
                            out.append(doc_line(kk, vv))
                    else:
                        out.append(f"{k} = {str(v)[:200]}")
                st.delete("1.0", "end")
                st.insert("end", "\n".join(out))
            elif rounds_left > 0:
                st.delete("1.0", "end")
                st.insert("end", f"[{title}] 等待应答... ({rounds_left * 0.4:.1f}s)\n"
                                 f"提示: 无响应 = 本机无该硬件通道或官方前端未挂载该处理分支")
                self.root.after(400, lambda: collect(rounds_left - 1))
            else:
                st.delete("1.0", "end")
                st.insert("end",
                          f"[{title}] ⛔ 3秒内无应答。\n"
                          f"可能原因: 本机无此硬件通道 / 官方前端未运行导致服务未挂载该处理分支。\n"
                          f"(可到[协议学习]页手动发不同载荷试探)")
        collect(8)

    def _tab_perf(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 性能模式 ")
        lf = ttk.LabelFrame(f, text="四档性能模式 (OperatingMode)")
        lf.pack(fill="x", padx=8, pady=8)
        self.mode_var.set("2")
        for lab, val in [("办公 Office=0", "0"), ("均衡 Gaming=1", "1"),
                         ("狂暴 Turbo=2", "2"), ("自定义 Custom=3", "3")]:
            ttk.Radiobutton(lf, text=lab, value=val, variable=self.mode_var).pack(side="left", padx=12)
        ttk.Button(lf, text="应用(标准格式)", command=self.apply_mode).pack(side="left", padx=12)
        ttk.Button(lf, text="应用(自动探测)", command=self.apply_mode_probe).pack(side="left")

        lf2 = ttk.LabelFrame(f, text="性能开关")
        lf2.pack(fill="x", padx=8, pady=8)
        self._toggle_row(lf2, "超频总开关 OverClockingSwitch", F, "OverClockingSwitch", 1, 0)
        self._toggle_row(lf2, "Whisper低功耗模式(GPU侧)", F, "GPU_WhisperModeSwitch", 1, 0)
        self._toggle_row(lf2, "Dynamic Boost", F, "GPU_DynamicBoostSwitch", 1, 0)

        lf4 = ttk.LabelFrame(f, text="风扇强冷/Boost —— 全部实测生效(FanBoostEnable回读验证✓)")
        lf4.pack(fill="x", padx=8, pady=8)
        fb = ttk.Frame(lf4); fb.pack(fill="x")
        col = 0
        for name, (cmd, topic) in mc.MrConsole.SERVCMD_FAN.items():
            ttk.Button(fb, text=name, width=16,
                       command=lambda c=cmd, t=topic: self.servcmd(c, t)
                       ).grid(row=col // 4, column=col % 4, padx=3, pady=3, sticky="we")
            col += 1

        lf3 = ttk.LabelFrame(f, text="配置档索引")
        lf3.pack(fill="x", padx=8, pady=8)
        for fname, flabel in [("GamingProfileIndex", "均衡档"), ("OfficeProfileIndex", "办公档"),
                              ("TurboProfileIndex", "狂暴档"), ("CustomProfileIndex", "自定义档")]:
            self._slider_row(lf3, flabel, F, fname, 0, 4)

    def _tab_oc(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 超频参数 ")
        lf = ttk.LabelFrame(f, text="CPU (边界来自服务端实时上报: PL≤80/80/100)")
        lf.pack(fill="x", padx=8, pady=6)
        self._slider_row(lf, "PL1 (W)", F, "CPU_PL1", 10, 80)
        self._slider_row(lf, "PL2 (W)", F, "CPU_PL2", 10, 80)
        self._slider_row(lf, "PL4 (W)", F, "CPU_PL4", 10, 100)
        self._slider_row(lf, "温度墙偏移 TccOffset (°C)", F, "CPU_TccOffset", 80, 100)
        lf2 = ttk.LabelFrame(f, text="GPU")
        lf2.pack(fill="x", padx=8, pady=6)
        self._slider_row(lf2, "核心频率偏移 (MHz)", F, "GPU_CoreClockOffsetOC", 0, 250)
        self._slider_row(lf2, "显存频率偏移 (MHz)", F, "GPU_MemoryClockOffsetOC", -1000, 1000)
        self._slider_row(lf2, "目标温度 (°C)", F, "GPU_TargetTemperature", 75, 87)
        self._slider_row(lf2, "Dynamic Boost (W)", F, "GPU_DynamicBoost", 5, 25)
        ttk.Label(f, text="提示: CPU降压/TGP解锁/内存OC等⛔项已移至[🔴研究模式]页",
                  foreground="#888").pack(anchor="w", padx=12, pady=6)

    def _tab_fan(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 风扇 ")
        lf = ttk.LabelFrame(f, text="风扇策略 (一律走MQTT, 直改JSON会触发UI保护性隐藏)")
        lf.pack(fill="x", padx=8, pady=6)
        self._toggle_row(lf, "切换转速启用 FanSwitchSpeedEnabled", F, "FAN_FanSwitchSpeedEnabled", 1, 0)
        self._slider_row(lf, "切换转速 (RPM, 原厂=300勿越界)", F, "FAN_FanSwitchSpeed", 0, 1500)
        lf2 = ttk.LabelFrame(f, text="智能风扇表 (RamFan1p5: CPU 0xF00/F10 · GPU 0xF30/F40)")
        lf2.pack(fill="both", expand=True, padx=8, pady=6)
        ttk.Button(lf2, text="读取曲线设定 GET_FAN_SPEED_CURVE_SETTING(已实证)",
                   command=self.read_curve).pack(anchor="w", padx=8, pady=4)
        self.curve_text = scrolledtext.ScrolledText(lf2, height=10, font=("Consolas", 9))
        self.curve_text.pack(fill="both", expand=True, padx=8, pady=4)

    def _tab_kb(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 灯光键盘 ")
        lf = ttk.LabelFrame(f, text="键盘背光 (SingleZone · 0x769-76B Level制+0x767触发)")
        lf.pack(fill="x", padx=8, pady=6)
        self._toggle_row(lf, "键盘灯电源 SingleColorKBBL", S, "SingleColorKBBL",
                         "SINGLE_COLOR_KBBL_STATUS_ON", "SINGLE_COLOR_KBBL_STATUS_OFF")
        br = ttk.Frame(lf); br.pack(fill="x", padx=8, pady=2)
        ttk.Label(br, text="亮度5档:", width=14).pack(side="left")
        for i in range(5):
            ttk.Button(br, text=str(i), width=3,
                       command=lambda v=i: self._kb_candidate("brightness", v)).pack(side="left", padx=3)
        ef = ttk.LabelFrame(f, text="灯效库 (点击生成候选载荷 → 协议学习页发送; 官方设一次+抓包最可靠)")
        ef.pack(fill="both", expand=True, padx=8, pady=6)
        grid = ttk.Frame(ef); grid.pack(fill="both", expand=True)
        cols = 4
        for i, (name, key, tag) in enumerate(RGB_EFFECTS):
            ttk.Button(grid, text=f"{tag}{name}",
                       command=lambda n=key: self._kb_effect(n)).grid(
                row=i // cols, column=i % cols, sticky="we", padx=3, pady=2)
        lf2 = ttk.LabelFrame(f, text="外设开关(字段式)")
        lf2.pack(fill="x", padx=8, pady=6)
        self._toggle_row(lf2, "Win键锁", S, "WinKey",
                         "WINKEY_STATUS_LOCK", "WINKEY_STATUS_UNLOCK")
        self._toggle_row(lf2, "Fn键交换", S, "FnKey", "FNKEY_LOCK", "FNKEY_UNLOCK")
        self._toggle_row(lf2, "小键盘 NumPad", S, "NumPad", "NUMPAD_LOCK", "NUMPAD_UNLOCK")
        self._toggle_row(lf2, "触控板", S, "TouchpadToggle",
                         "TOUCHPAD_TOGGLE_ON", "TOUCHPAD_TOGGLE_OFF")
        lf3 = ttk.LabelFrame(f, text="🔥 硬件外设 —— 服务端真实ServCMD指令(无需学习)")
        lf3.pack(fill="x", padx=8, pady=6)
        pb = ttk.Frame(lf3); pb.pack(fill="x")
        col = 0
        for name, (cmd, topic) in mc.MrConsole.SERVCMD_PERIPH.items():
            ttk.Button(pb, text=name, width=10,
                       command=lambda c=cmd, t=topic: self.servcmd(c, t)
                       ).grid(row=col // 8, column=col % 8, padx=2, pady=2, sticky="we")
            col += 1

    def _tab_display(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 显示器 ")
        lf = ttk.LabelFrame(f, text="显示模式")
        lf.pack(fill="x", padx=8, pady=6)
        self._radio_row(lf, "显示模式", S, "DisplayMode", DISPLAY_MODES)
        self._toggle_row(lf, "显示功能总开关", S, "DisplayFeatureStatus",
                         "DISPLAY_FEATURE_STATUS_ON", "DISPLAY_FEATURE_STATUS_OFF")
        lf2 = ttk.LabelFrame(f, text="游戏模式画面参数")
        lf2.pack(fill="x", padx=8, pady=6)
        self._slider_row(lf2, "亮度 GamingBrightness", S, "GamingBrightness", 0, 100)
        self._slider_row(lf2, "色温 GamingColorTemp", S, "GamingColorTemp", 0, 100)
        self._slider_row(lf2, "对比 GamingContrast", S, "GamingContrast", 0, 100)
        self._slider_row(lf2, "红 GamingRed", S, "GamingRed", 0, 128)
        self._slider_row(lf2, "绿 GamingGreen", S, "GamingGreen", 0, 128)
        self._slider_row(lf2, "蓝 GamingBlue", S, "GamingBlue", 0, 128)
        lf3 = ttk.Frame(f); lf3.pack(fill="x", padx=8, pady=6)
        lfa = ttk.LabelFrame(lf3, text="OSD/校准/定时"); lfa.pack(side="left", fill="both", expand=True)
        self._toggle_row(lfa, "OSD悬浮显示", S, "OSD", "OSD_HIDDEN_OFF", "OSD_HIDDEN_ON")
        self._action_row(lfa, "色彩校准 ColorCalibration", S,
                         {"Action": "COLOR_CALIBRATION_ON", "ServCMD": "COLOR_CALIBRATION_ON"}, sup="✅")
        self._slider_row(lfa, "自动关屏定时 CloseTimer(分)", S, "CloseTimer", 0, 120)
        lfb = ttk.LabelFrame(lf3, text="🔥 显示模式 ServCMD直发"); lfb.pack(side="left", fill="both", expand=True, padx=6)
        db = ttk.Frame(lfb); db.pack(fill="x")
        col = 0
        for name, (cmd, topic) in mc.MrConsole.SERVCMD_DISPLAY.items():
            ttk.Button(db, text=name, width=12,
                       command=lambda c=cmd, t=topic: self.servcmd(c, t)
                       ).grid(row=col // 3, column=col % 3, padx=2, pady=2, sticky="we")
            col += 1

    def _tab_battery(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 电池电源 ")
        lf = ttk.LabelFrame(f, text="电池保护 (HEALTHYMODE / Report:GET 已实证)")
        lf.pack(fill="x", padx=8, pady=6)
        for name, payload in BATTERY_ACTIONS:
            self._action_row(lf, name, mc.TOPIC_BAT_CTRL, payload)
        self._action_row(lf, "查询电池状态 Report:GET", mc.TOPIC_BAT_CTRL,
                         {"Report": "GET"}, sup="✅")
        lf2 = ttk.LabelFrame(f, text="充电上限")
        lf2.pack(fill="x", padx=8, pady=6)
        self._slider_row(lf2, "充电上限 ChargeMaximumLimit(%)", mc.TOPIC_BAT_CTRL,
                         "ChargeMaximumLimit", 60, 100)
        self._slider_row(lf2, "充电下限 ChargeMinimumLimit(%)", mc.TOPIC_BAT_CTRL,
                         "ChargeMinimumLimit", 0, 50)
        lf3 = ttk.LabelFrame(f, text="🔥 电源计划/恢复 —— ServCMD真实指令")
        lf3.pack(fill="x", padx=8, pady=6)
        eb = ttk.Frame(lf3); eb.pack(fill="x")
        col = 0
        for name, (cmd, topic) in mc.MrConsole.SERVCMD_BATTERY.items():
            ttk.Button(eb, text=name, width=14,
                       command=lambda c=cmd, t=topic: self.servcmd(c, t)
                       ).grid(row=col // 4, column=col % 4, padx=2, pady=2, sticky="we")
            col += 1
        self._toggle_row(lf3, "AC断电恢复(字段式⚠️)", S, "AcRecoverySwitch_Status",
                         "ACRECOVERY_TOGGLE_ON", "ACRECOVERY_TOGGLE_OFF", sup="⚠️")

    def _tab_learn(self, nb):
        f = ttk.Frame(nb); nb.add(f, text=" 协议学习·手动 ")
        top = ttk.Frame(f); top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="● 开始抓包20s(去操作官方UI)", command=self.learn).pack(side="left", padx=4)
        ttk.Button(top, text="命令库", command=self.show_lib).pack(side="left", padx=4)
        ttk.Label(top, text="回放:").pack(side="left", padx=(16, 2))
        ttk.Entry(top, textvariable=self.replay_name, width=22).pack(side="left")
        ttk.Button(top, text="回放", command=self.replay).pack(side="left", padx=4)
        bar2 = ttk.Frame(f); bar2.pack(fill="x", padx=8, pady=2)
        ttk.Label(bar2, text="Topic:").pack(side="left")
        ttk.Entry(bar2, textvariable=self.manual_topic, width=24).pack(side="left", padx=3)
        ttk.Label(bar2, text="Payload(JSON):").pack(side="left", padx=6)
        ttk.Entry(bar2, textvariable=self.manual_payload, width=52).pack(side="left", padx=3)
        ttk.Button(bar2, text="发布", command=self.manual_send).pack(side="left", padx=6)
        ttk.Button(bar2, text="存入库", command=self.save_manual).pack(side="left")
        self.capture_text = scrolledtext.ScrolledText(f, font=("Consolas", 9))
        self.capture_text.pack(fill="both", expand=True, padx=8, pady=6)

    def _tab_research(self, nb):
        """★ 全部⛔不支持项集中地 —— 供后续调研突破"""
        f = ttk.Frame(nb); nb.add(f, text=" 🔴研究模式 ")
        head = ttk.Frame(f); head.pack(fill="x", padx=8, pady=6)
        ttk.Label(head, text="本页收录本机硬件不支持的全部功能通道。",
                  foreground="#b00020",
                  font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        ttk.Checkbutton(head, text="允许研究发送", variable=self.research).pack(side="right")
        ttk.Label(f, text="依据: ItemSupport注册表 / EC支持位0x765-766 / 服务端Min-Max。"
                          "发送后观察[状态总览]回读变化——若EC固件更新解锁支持位可立即复测。",
                  foreground="#666", wraplength=1050, justify="left").pack(anchor="w", padx=12)

        # --- 组1: 功耗突破 ---
        g1 = ttk.LabelFrame(f, text="功耗突破 (7435H SMU锁死 · 与Linux ryzenadj实测互证)")
        g1.pack(fill="x", padx=8, pady=4)
        self._toggle_row(g1, "内存超频 MemoryOverClock(Support=0)", F, "MEM_MemoryOverClockSwitch", 1, 0, sup="⛔")
        self._slider_row(g1, "Intel降压通道 OffsetVoltage(AMD区间0~0)",
                         F, "CPU_OffsetCoreVoltage", -300, 0, sup="⛔")
        self._slider_row(g1, "TGP解锁尝试(现固定115,驱动上限140)",
                         F, "GPU_ConfigurableTGPTarget", 116, 175, sup="⛔")
        self._slider_row(g1, "cTGP-GN21自定义值(官方隐藏特性)",
                         F, "CustomTGPinGCUforGN21_Value", 60, 175, sup="⛔")

        # --- 组2: 风扇安全 ---
        g2 = ttk.LabelFrame(f, text="风扇突破 (曾致UI保护性隐藏——慎用)")
        g2.pack(fill="x", padx=8, pady=4)
        self._toggle_row(g2, "跳过安全异常保护 SkipSafetyAbnormalProtection",
                         F, "FAN_SafetyProtect", 1, 0, sup="⛔")

        # --- 组3: MUX/GPU输出 ---
        g3 = ttk.LabelFrame(f, text="MUX独显直连 (DGpuDirectConnectionSupport=0 · 本机无MUX硬件)")
        g3.pack(fill="x", padx=8, pady=4)
        self._radio_row(g3, "NVIDIA输出模式(Auto/HyperPerf)", S, "DGpu",
                        ["NV_CTRL_PANEL_AUTOSELECT", "NV_CTRL_PANEL_HIGHPERFORMANCE"], sup="⛔")
        self._toggle_row(g3, "独显直连开关 DGPU_DIRECT_CONNECT",
                         S, "DiscreteGpuDirectConnectionSwitch_Status",
                         "DGPU_DIRECT_CONNECT_TOGGLE_ON", "DGPU_DIRECT_CONNECT_TOGGLE_OFF", sup="⛔")
        self._action_row(g3, "GPU P-State 直控(新版字段)", F,
                         {"Action": "SET", "GPUPState": 0}, sup="⛔")
        self._action_row(g3, "GPU dstate 电源态(新版字段)", F,
                         {"Action": "SET", "GPUdstate": 0}, sup="⛔")

        # --- 组4: 供电 ---
        g4 = ttk.LabelFrame(f, text="供电扩展 (TypeCSupport=0 · USB充电无支持位)")
        g4.pack(fill="x", padx=8, pady=4)
        self._toggle_row(g4, "TypeC适配器供电优先", S, "TypeCAdaptorPrioritySwitch", 1, 0, sup="⛔")
        self._toggle_row(g4, "USB关机充电(0x767 bit4)", S, "UsbCharger",
                         "USB_CHARGER_STATUS_ON", "USB_CHARGER_STATUS_OFF", sup="⛔")

        # --- 组5: 新版5.56特性 ---
        g5 = ttk.LabelFrame(f, text="新版5.56特性 (CCU.WinUI字段名逆向 · EC路径未知 · 待抓包验证)")
        g5.pack(fill="x", padx=8, pady=4)
        self._action_row(g5, "游戏白名单 GameWhiteList", F,
                         {"Action": "SET", "GameWhitelistSwitch": 1}, sup="⛔")
        self._action_row(g5, "iGPU ECO节能 igpuEcoEnable", F,
                         {"Action": "SET", "igpuEcoEnable": 1}, sup="⛔")
        self._action_row(g5, "静音性能模式 SilentPerformance", F,
                         {"Action": "SET", "SilentPerformanceMode": 1}, sup="⛔")
        self._action_row(g5, "自动刷新率 AutoRefreshRate", S,
                         {"Action": "SET", "AutoRefreshRate": 1}, sup="⛔")
        self._action_row(g5, "LCD Overdrive 屏幕响应加速", S,
                         {"Action": "SET", "LCDOverdrive": 1}, sup="⛔")
        self._action_row(g5, "Aurora极光灯效(28效之一)", KB,
                         {"Action": "SET", "KBEffect": "Aurora"}, sup="⛔")

        # --- 组6: 宏与重映射 ---
        g6 = ttk.LabelFrame(f, text="宏/键位重映射 (0x765 无MACRO/SHORTCUT支持位)")
        g6.pack(fill="x", padx=8, pady=4)
        self._toggle_row(g6, "键位重映射 KeyRemapping", S, "KeyRemappingEnable", 1, 0, sup="⛔")
        self._action_row(g6, "宏录制 MacroRecord", S,
                         {"Action": "SET", "MacroRecord": 1}, sup="⛔")
        self._action_row(g6, "BIOS级AC断电恢复(AcRecoverySwitchBiosSupport=0)",
                         S, {"Action": "SET", "AcRecoveryBios": 1}, sup="⛔")
        g7 = ttk.LabelFrame(f, text="系统 (危险区)")
        g7.pack(fill="x", padx=8, pady=4)
        self._action_row(g7, "⚠️危险: System_OFF 关机(已实证指令)", mc.TOPIC_SYS_CTRL,
                         {"Action": "System_OFF"}, sup="⚠️",
                         note="发送前确认所有工作已保存", danger=True)

    # ================= 运行时 =================
    def _poll(self):
        while True:
            try:
                kind, msg = self.q.get_nowait()
                if kind == "log":
                    self.log_text.insert("end", msg); self.log_text.see("end")
                elif kind == "capture":
                    self.capture_text.insert("end", msg); self.capture_text.see("end")
                elif kind == "conn":
                    ok, text = msg
                    self.conn_lbl.config(text=f"● {text}",
                                         fg="#1a7f37" if ok else "#d00000")
            except queue.Empty:
                break
        self._update_status_labels()
        if self.auto.get():
            self.root.after(REFRESH_MS, self.refresh_all_silent)
        self.root.after(400, self._poll)

    def _update_status_labels(self):
        fan = self.app.status.get(mc.TOPIC_FAN_STA, {})
        st = self.app.status.get(mc.TOPIC_SET_STA, {})
        merged = {**fan, **st}
        for k, (lb, mapping) in self.toggles.items():
            v = str(merged.get(k, "-"))
            lb.config(text=mapping.get(v, v[:26]))
        for key, (var, curlb) in self.sliders.items():
            topic, field = key.split("|", 1)
            src = self.app.status.get(topic.replace("/Ctrl", "/Status").replace("/Control", "/Status"), {})
            if field in src:
                curlb.config(text=f"当前:{src[field]}")

    def refresh_all(self): self.refresh_worker(); self.root.after(1200, self._render_status)
    def refresh_all_silent(self): self.refresh_worker()

    def refresh_worker(self):
        def worker():
            try:
                self.app.get_fan(); self.app.get_setting()
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _render_status(self, verbose=True):
        """全部刷新: 渲染所有已知状态Topic(动态), 每行带注释"""
        lines = ["提示: 每字段附「是什么 | 参考值 | 增减含义」; 未收录字段显示原样。"]
        for tname in sorted(self.app.status.keys()):
            d = self.app.status[tname]
            if isinstance(d, dict):
                lines.append(f"═══ {tname} ═══")
                for k, v in d.items():
                    lines.append(doc_line(k, v))
        self.status_text.delete("1.0", "end")
        if len(lines) > 1:
            self.status_text.insert("end", "\n".join(lines))
        else:
            self.status_text.insert("end", "暂无数据 — 点击单项查询按钮或等待自动刷新...")

    MODE_KEY = {"0": "office", "1": "gaming", "2": "turbo", "3": "custom"}

    def apply_mode(self):
        if not self._gate("✅"):
            return
        key = self.MODE_KEY[self.mode_var.get()]
        threading.Thread(target=lambda: self.app.set_mode(key), daemon=True).start()

    def apply_mode_probe(self):
        if not self._gate("✅"):
            return
        target = int(self.mode_var.get())   # 主线程取值, 避免后台读tk变量崩溃
        threading.Thread(target=lambda: self.app.probe_mode(target),
                         daemon=True).start()

    def _verify_mode(self, val):
        for _ in range(6):
            time.sleep(0.5)
            cur = self.app.get_fan().get("OperatingMode")
            if str(cur) == str(val):
                self.log(f"[✅] 模式切换成功 OperatingMode={cur}")
                return
        self.log("[..] 标准格式未生效, 转入全候选探测...")
        self.app.probe_mode(int(val))

    def read_curve(self):
        self.app.mqtt.publish(mc.TOPIC_FAN_CTRL, '{"Action":"GET_FAN_SPEED_CURVE_SETTING"}')
        self.log("[READ] 曲线请求已发送, 结果见状态总览页")

    def _kb_candidate(self, kind, value):
        """真实协议(DefaultTool IL提取): {"function":"SetLightingLevel","level":N}"""
        payload = json.dumps({"MqttID": None, "function": "SetLightingLevel", "level": value})
        self.manual_topic.set(mc.TOPIC_KB_CTRL)
        self.manual_payload.set(payload)
        self.nb.select(8)
        self.cap(f"[亮度={value}] 已填入手动发布框(function协议) → 勾选写入后点[发布]")
        self.log(f"生成键盘亮度指令: {payload}")

    @staticmethod
    def _kb_seteffect(effect="Wave", light="4", speed="2", direction="None",
                      nv_save="0", rgb=(0, 255, 0)):
        """官方抓包实证的 SetEffectALL 真实载荷"""
        rainbow = [(255,0,0),(255,165,0),(255,255,0),(0,255,0),(0,0,255),(0,255,255),(139,0,255)]
        buf = [{"ID": i, "R": r, "G": g, "B": b} for i, (r, g, b) in enumerate(rainbow)]
        if rgb:
            buf = [{"ID": 0, "R": rgb[0], "G": rgb[1], "B": rgb[2]}] * 7
        return {
            "MqttID": None, "function": "SetEffectALL", "mode": "Lighting",
            "effect": effect, "light": str(light), "speed": str(speed),
            "direction": direction, "nv_save": nv_save,
            "color": {"isCircular": True, "ColorBlocks": 7, "ColorBuffer": buf}
        }

    def _kb_effect(self, effect):
        payload = json.dumps(self._kb_seteffect(effect=effect))
        self.manual_topic.set(mc.TOPIC_KB_CTRL)
        self.manual_payload.set(payload)
        self.nb.select(8)
        self.cap(f"[灯效{effect}] 官方真实SetEffectALL载荷已填入 → 勾选写入后点[发布]")
        self.log(f"生成灯效指令({effect}): 载荷{len(payload)}字节(官方格式)")


    def learn(self):
        def worker():
            self.app.start_capture()
            self.cap(f"─── 抓包开始 {time.strftime('%H:%M:%S')} , 20秒内去操作官方UI ───")
            time.sleep(20)
            cap = self.app.stop_capture_save()
            for topic, payload in cap:
                self.cap(f"[{topic}] {payload[:160]}")
            self.cap(f"─── 已保存 {len(cap)} 条到 learned_commands.json ───")
        threading.Thread(target=worker, daemon=True).start()

    def show_lib(self):
        lib = self.app.load_lib()
        self.capture_text.delete("1.0", "end")
        self.capture_text.insert("end", f"=== 命令库 共{len(lib)}条 ===\n")
        for k, v in lib.items():
            self.capture_text.insert("end", f"{k:<26} {v['topic']:<36} {v['payload'][:110]}\n")

    def replay(self):
        name = self.replay_name.get().strip()
        if not name:
            messagebox.showinfo("提示", "输入命令库中的名称"); return
        if not self.write_enabled.get():
            messagebox.showwarning("安全锁", "先勾选底部[启用写入]"); return
        try:
            self.app.replay(name)
        except KeyError as e:
            messagebox.showerror("错误", str(e))

    def manual_send(self):
        if not self.write_enabled.get():
            messagebox.showwarning("安全锁", "先勾选底部[启用写入]"); return
        t, p = self.manual_topic.get(), self.manual_payload.get()
        try:
            json.loads(p)
        except Exception:
            messagebox.showerror("错误", "Payload 不是合法JSON"); return
        self.mqtt_pub(t, p)

    def save_manual(self):
        lib = self.app.load_lib()
        name = f"manual_{int(time.time())%100000}"
        lib[name] = {"topic": self.manual_topic.get(), "payload": self.manual_payload.get()}
        with open(mc.LIB_PATH, "w", encoding="utf-8") as fp:
            json.dump(lib, fp, ensure_ascii=False, indent=2)
        self.cap(f"已存入库: {name}")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.deiconify()
        self.root.mainloop()

    def _close(self):
        try:
            self.app.stop()
        finally:
            self.root.destroy()


# ---------- 辅助 ----------
def run(app_factory):
    app = app_factory()
    g = GuiApp(app)
    g.run()


if __name__ == "__main__":
    run(lambda: mc.MrConsole())
