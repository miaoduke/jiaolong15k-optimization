#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mr_gui_v6.py — MR Control Center v6.0 (G-Helper 照搬式一屏流)
日期: 2026-08-26
通道: MQTT官方桥(模式/风扇曲线/强冷) · UWACPIDriver(EC温度/duty/背光/PL墙)
安全: 全部写通道经实验验证; 触摸板真写需勾选已接外接鼠标
"""
import sys, os, json, threading, tkinter as tk
from tkinter import ttk, messagebox

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mr_console as mc
import mr_ec_hw as ec

BG, FG = "#1e1f22", "#e6e6e6"
ACCENT, CARD = "#4fc3f7", "#2b2d31"
BTN = "#38393f"

class App:
    def __init__(self):
        self.mc = None
        self.root = tk.Tk()
        self.root.title("MR Control Center v6.0 — Jiaolong15K (GM5BG0E)")
        self.root.configure(bg=BG)
        self.root.geometry("980x620")
        self._build_style()
        self._build_ui()
        self._connect_async()

    def _build_style(self):
        st = ttk.Style()
        try: st.theme_use("clam")
        except Exception: pass
        st.configure(".", background=BG, foreground=FG, fieldbackground=CARD)
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=CARD)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Card.TLabel", background=CARD, foreground=FG)
        st.configure("Head.TLabel", background=BG, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        st.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 10))
        st.configure("TButton", background=BTN, foreground=FG, padding=(8, 5))

    def card(self, parent, title, r, c):
        f = ttk.Frame(parent, style="Card.TFrame", padding=10)
        f.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
        ttk.Label(f, text=title, style="Head.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        return f

    def _build_ui(self):
        top = ttk.Frame(self.root, style="TFrame")
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text="性能模式", style="Head.TLabel").pack(side="left", padx=(0, 12))
        self.mode_var = tk.StringVar(value="—")
        for label, tgt in [("🤫 办公", 0), ("⚖ 均衡", 1), ("🚀 狂暴", 2), ("⚙ 自定义", 3)]:
            ttk.Button(top, text=label, style="Big.TButton", width=10,
                       command=lambda t=tgt: self._set_mode(t)).pack(side="left", padx=4)
        self.mq_lbl = ttk.Label(top, text="MQTT: 连接中…")
        self.mq_lbl.pack(side="right")

        grid = ttk.Frame(self.root, style="TFrame")
        grid.pack(fill="both", expand=True, padx=10, pady=4)
        grid.columnconfigure((0, 1), weight=1)
        grid.rowconfigure(0, weight=3)
        grid.rowconfigure(1, weight=2)

        # CPU 风扇卡
        cf = self.card(grid, "🌀 CPU 风扇", 0, 0)
        self.lbl_cpu_t = ttk.Label(cf, text="温度 -- °C", style="Card.TLabel"); self.lbl_cpu_t.grid(row=1, column=0, sticky="w")
        self.lbl_cpu_d = ttk.Label(cf, text="Duty -- %", style="Card.TLabel"); self.lbl_cpu_d.grid(row=2, column=0, sticky="w")
        self.lbl_cpu_r = ttk.Label(cf, text="RPM ----", style="Card.TLabel"); self.lbl_cpu_r.grid(row=3, column=0, sticky="w")
        bf = ttk.Frame(cf, style="Card.TFrame"); bf.grid(row=4, column=0, pady=6, sticky="w")
        ttk.Button(bf, text="🔥 强冷 开", command=lambda: self._boost(True)).pack(side="left", padx=2)
        ttk.Button(bf, text="强冷 关", command=lambda: self._boost(False)).pack(side="left", padx=2)
        ttk.Button(bf, text="恢复默认曲线", command=self._curve_restore).pack(side="left", padx=2)
        cf2 = ttk.Frame(cf, style="Card.TFrame"); cf2.grid(row=5, column=0, sticky="we", pady=4)
        ttk.Label(cf2, text="自定义16点(T0-T15):", style="Card.TLabel").pack(side="top", anchor="w")
        self.curve_ent = tk.Entry(cf2, bg="#111", fg=FG, insertbackground=FG, width=52)
        self.curve_ent.insert(0, "40,40,42,45,50,55,60,65,70,75,80,85,90,95,100,100")
        self.curve_ent.pack(side="top", fill="x", pady=2)
        ttk.Button(cf2, text="下发官方曲线(固件执行)", command=self._curve_apply).pack(side="left", pady=2)

        # GPU 风扇卡
        gf = self.card(grid, "❄ GPU 风扇 / 高级", 0, 1)
        self.lbl_gpu_t = ttk.Label(gf, text="温度 -- °C", style="Card.TLabel"); self.lbl_gpu_t.grid(row=1, column=0, sticky="w")
        self.lbl_gpu_d = ttk.Label(gf, text="Duty -- %", style="Card.TLabel"); self.lbl_gpu_d.grid(row=2, column=0, sticky="w")
        self.lbl_gpu_r = ttk.Label(gf, text="RPM ----", style="Card.TLabel"); self.lbl_gpu_r.grid(row=3, column=0, sticky="w")
        pf = ttk.Frame(gf, style="Card.TFrame"); pf.grid(row=4, column=0, pady=6, sticky="w")
        ttk.Label(pf, text="PL1(W):", style="Card.TLabel").pack(side="left")
        self.pl_ent = tk.Entry(pf, bg="#111", fg=FG, width=6); self.pl_ent.insert(0, "--")
        self.pl_ent.pack(side="left", padx=3)
        ttk.Button(pf, text="写入PL1(Custom)", command=self._pl_apply).pack(side="left", padx=3)
        self.lbl_pl = ttk.Label(gf, text="PL墙: --/--/-- W", style="Card.TLabel"); self.lbl_pl.grid(row=5, column=0, sticky="w")

        # 电源卡
        bt = self.card(grid, "🔋 电源 / 电池", 1, 0)
        self.lbl_chg = ttk.Label(bt, text="充电限制: 本机EC固件不支持软件限充", style="Card.TLabel"); self.lbl_chg.grid(row=1, column=0, sticky="w")
        self.lbl_bat = ttk.Label(bt, text="电池: --%", style="Card.TLabel"); self.lbl_bat.grid(row=2, column=0, sticky="w")

        # 设备卡
        dv = self.card(grid, "⌨ 设备 (背光/触摸板)", 1, 1)
        kb = ttk.Frame(dv, style="Card.TFrame"); kb.grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(kb, text="键盘背光:", style="Card.TLabel").pack(side="left")
        for lv in (0, 1, 2):
            ttk.Button(kb, text=str(lv), width=4, command=lambda l=lv: self._backlight(l)).pack(side="left", padx=3)
        self.lbl_bkl = ttk.Label(dv, text="当前档: -", style="Card.TLabel"); self.lbl_bkl.grid(row=2, column=0, sticky="w")
        tp = ttk.Frame(dv, style="Card.TFrame"); tp.grid(row=3, column=0, sticky="w", pady=4)
        ttk.Label(tp, text="触摸板:", style="Card.TLabel").pack(side="left")
        ttk.Button(tp, text="禁用(bit6)", command=lambda: self._touchpad(1)).pack(side="left", padx=3)
        ttk.Button(tp, text="启用(bit6=0)", command=lambda: self._touchpad(0)).pack(side="left", padx=3)
        self.lbl_tp = ttk.Label(dv, text="状态: --", style="Card.TLabel"); self.lbl_tp.grid(row=4, column=0, sticky="w")
        uc = ttk.Frame(dv, style="Card.TFrame"); uc.grid(row=5, column=0, sticky="w", pady=4)
        ttk.Label(uc, text="关机USB充电:", style="Card.TLabel").pack(side="left")
        ttk.Button(uc, text="开", width=4, command=lambda: self._usbchg(True)).pack(side="left", padx=3)
        # 底部日志
        self.log_box = tk.Text(self.root, height=6, bg="#141517", fg="#9ece6a",
                               insertbackground=FG, relief="flat")
        self.log_box.pack(fill="x", padx=10, pady=(2, 8))

    def _usbchg(self, on):
        if self._need_mc(): return
        act = "USB_CHARGER_ON" if on else "USB_CHARGER_OFF"
        payload = json.dumps({"Action": act, "ServCMD": act})
        threading.Thread(target=lambda: [self.mc.mqtt.publish("Setting/Control", payload),
                                          self.log("[USB_CHG] %s 已下发(EC 0x767 bit4)" % act)],
                         daemon=True).start()

    def log(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")

    def _connect_async(self):
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        def lf(m): pass
        try:
            self.mc = mc.MrConsole(log_fn=lf)
            ok = self.mc.start()
            self.mq_lbl.config(text="MQTT: ✅ 已连接" if ok else "MQTT: ❌ 失败")
            self.poll()
        except Exception as e:
            self.mq_lbl.config(text="MQTT: ❌ %s" % e)

    def _need_mc(self):
        if not self.mc:
            messagebox.showinfo("提示", "MQTT 未连接")
            return True
        return False

    def _set_mode(self, target):
        if self._need_mc(): return
        key = {0: "office", 1: "gaming", 2: "turbo", 3: "custom"}.get(target)
        self.log("[MODE] 切换到 %s ..." % target)
        threading.Thread(target=lambda: self.mc.set_mode(key), daemon=True).start()

    def _boost(self, on):
        if self._need_mc(): return
        threading.Thread(target=lambda: self.mc.set_fan_boost(on), daemon=True).start()
        self.log("[FAN_BOOST] %s" % ("ON" if on else "OFF"))

    def _curve_restore(self):
        if self._need_mc(): return
        threading.Thread(target=lambda: self.mc.restore_fan_curve(""), daemon=True).start()
        self.log("[CURVE] 恢复默认")

    def _curve_apply(self):
        if self._need_mc(): return
        raw = self.curve_ent.get().strip()
        try:
            duties = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except Exception:
            messagebox.showerror("格式错误", "应为逗号分隔的16个整数"); return
        if len(duties) != 16:
            messagebox.showerror("数量错误", "需要正好16个点, 当前%d个" % len(duties)); return
        name = "Custom"
        self.log("[CURVE] 下发 16 点...")
        threading.Thread(target=lambda: self.mc.set_fan_curve(name, "CPU", duties), daemon=True).start()

    def _pl_apply(self):
        try:
            w = int(self.pl_ent.get())
        except Exception:
            messagebox.showerror("错误", "PL1 需为整数瓦数"); return
        ok = ec.set_pl1(w)
        self.log("[PL1] 写 %dW -> %s" % (w, "✅ 读回一致" if ok else "❌ 不一致"))
        self._refresh_static()

    def _backlight(self, level):
        ok = ec.set_kb_backlight(level)
        self.log("[BACKLIGHT] 档%d -> %s" % (level, "✅" if ok else "❌"))
        self.lbl_bkl.config(text="当前档: %s" % ec.get_kb_backlight())

    def _touchpad(self, disable):
        v = ec.ec_read(0x7A6)
        if v is None:
            self.log("[TP] 地址不可用"); return
        if disable and not messagebox.askyesno(
                "确认", "将禁用内置触摸板!\n请确认已连接外接鼠标, 否则可能操作困难。\n\n继续?"):
            return
        nv = (v | 64) if disable else (v & ~64 & 0xFF)
        ec.ec_write(0x7A6, nv)
        import time as _t; _t.sleep(0.3)
        rb = ec.ec_read(0x7A6)
        self.log("[TP] 写bit6=%d -> 读回%s" % (disable, rb))
        self.lbl_tp.config(text="状态: %s" % ("禁用" if (rb or 0) & 64 else "启用"))

    def poll(self):
        try:
            ct = ec.get_cpu_temp(); gt = ec.get_gpu_temp()
            cd = ec.get_fan_duty(); cr = ec.get_fan_rpm()
            gd = ec.get_gpu_duty(); gr = ec.get_gpu_rpm()
            bkl = ec.get_kb_backlight(); pl = ec.get_pl_walls()
            tp = ec.ec_read(0x7A6)
            self.lbl_cpu_t.config(text="温度 %s °C" % ct)
            self.lbl_cpu_d.config(text="Duty %s %%" % cd)
            self.lbl_cpu_r.config(text="RPM %s" % cr)
            self.lbl_gpu_t.config(text="温度 %s °C" % gt)
            self.lbl_gpu_d.config(text="Duty %s %%" % gd)
            self.lbl_gpu_r.config(text="RPM %s" % gr)
            self.lbl_bkl.config(text="当前档: %s" % bkl)
            self.lbl_tp.config(text="状态: %s" % ("禁用" if tp is not None and tp & 64 else ("启用" if tp is not None else "--")))
            if pl:
                self.lbl_pl.config(text="PL墙: %s/%s/%s W" % (pl["pl1"], pl["pl2"], pl["pl4"]))
                if self.pl_ent.get() in ("--", ""):
                    self.pl_ent.delete(0, "end"); self.pl_ent.insert(0, str(pl["pl1"]))
            bat = {}
            if self.mc:
                try: bat = self.mc.get_battery() or {}
                except Exception: pass
            self.lbl_bat.config(text="电池: %s%%" % bat.get("BatteryPercent", bat.get("battery_pct", "--")))
        except Exception as e:
            self.log("[poll err] %r" % e)
        self.root.after(2500, self.poll)

def run():
    app = App()
    app.root.mainloop()

if __name__ == "__main__":
    run()
