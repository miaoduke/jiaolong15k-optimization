#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mr_gui_v6qt.py — MR Control Center v6.0 Qt版 (G-Helper 观感还原)
暗色圆角卡片 · 大按钮模式条 · 双风扇面板 · 曲线画布 · 底部状态栏
通道: MQTT官方桥 + UWACPIDriver (全部实验验证过的写路径)
"""
import sys, os, json, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QFrame, QLineEdit, QMessageBox, QComboBox,
    QTextEdit, QSizePolicy)

BG      = "#1a1b1e"
CARD    = "#242629"
BTN     = "#33363b"
BTN_H   = "#3d4046"
ACCENT  = "#4fc3f7"
GREEN   = "#9ece6a"
FG      = "#e8e8e8"
DIM     = "#8a8d93"

QSS = f"""
QWidget {{ background:{BG}; color:{FG}; font-family:'Segoe UI'; font-size:13px; }}
QCard   {{ background:{CARD}; border-radius:10px; }}
QHead  {{ color:{ACCENT}; font-weight:600; font-size:13px; background:transparent; }}
QDim   {{ color:{DIM}; font-size:12px; background:transparent; }}
QValue {{ font-size:20px; font-weight:700; background:transparent; }}
QPushButton {{
    background:{BTN}; color:{FG}; border:none; border-radius:8px;
    padding:9px 16px; font-size:13px;
}}
QPushButton:hover {{ background:{BTN_H}; }}
QPushButton:pressed {{ background:#2a2c30; }}
QPushButton[modeBtn="true"] {{
    font-size:14px; font-weight:700; padding:12px 26px; border:2px solid transparent;
}}
QPushButton[active="true"] {{ border:2px solid {ACCENT}; color:{ACCENT}; background:#2a3038; }}
QLineEdit {{
    background:#141517; border:1px solid #3a3d42; border-radius:6px;
    padding:6px 8px; color:{FG}; font-size:12px;
}}
QTextEdit {{
    background:#141517; border:none; border-radius:8px;
    color:{GREEN}; font-family:'Consolas'; font-size:11px;
}}
QComboBox {{
    background:{BTN}; border-radius:6px; padding:5px 10px; color:{FG};
}}
"""

class Card(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(f"#card {{ background:{CARD}; border-radius:10px; }}")
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(14, 12, 14, 12)
        self.v.setSpacing(8)
        t = QLabel(title); t.setProperty("class", "head")
        t.setStyleSheet("color:%s; font-weight:600; font-size:13px; background:transparent;" % ACCENT)
        self.v.addWidget(t)

class CurveWidget(QWidget):
    """16点曲线可视化画布 (只读展示 + 预设高亮)"""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(110)
        self.points = [30]*16
        self.temp = None

    def set_points(self, pts):
        self.points = list(pts) + [pts[-1]]*(16-len(pts)) if len(pts) < 16 else list(pts[:16])
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#1b1c1f"))
        p.setPen(QPen(QColor("#2e3136"), 1))
        for i in range(1, 4):
            p.drawLine(0, h*i//4, w, h*i//4)
        for i in range(1, 8):
            p.drawLine(w*i//8, 0, w*i//8, h)
        if self.temp is not None:
            x = min(max(self.temp - 30, 0), 70) / 70 * w
            p.setPen(QPen(QColor("#e06c75"), 1))
            p.drawLine(int(x), 0, int(x), h)
        p.setPen(QPen(QColor(ACCENT), 2))
        n = len(self.points)
        for i in range(n-1):
            x1, y1 = w*i/(n-1), h - h*self.points[i]/100*0.92 - 4
            x2, y2 = w*(i+1)/(n-1), h - h*self.points[i+1]/100*0.92 - 4
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
        for i in range(n):
            cx, cy = int(w*i/(n-1)), int(h - h*self.points[i]/100*0.92 - 4)
            p.setBrush(QBrush(QColor(ACCENT)))
            p.drawEllipse(cx-3, cy-3, 6, 6)
        p.end()

class App(QMainWindow):
    MODES = [("🤫 办公", 0), ("⚖ 均衡", 1), ("🚀 狂暴", 2), ("⚙ 自定义", 3)]

    def __init__(self):
        super().__init__()
        import mr_console as mc
        import mr_ec_hw as ec
        self.mc_mod, self.ec = mc, ec
        self.mc = None
        self.setWindowTitle("MR Control Center v6.0 — Jiaolong15K")
        self.resize(1020, 660)
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(16, 12, 16, 10); root.setSpacing(10)

        # ── 性能模式条
        mode_row = QHBoxLayout()
        lbl = QLabel("性能模式"); lbl.setStyleSheet("color:%s;font-weight:600;" % FG)
        mode_row.addWidget(lbl); mode_row.addSpacing(8)
        self.mode_btns = []
        for text, tgt in self.MODES:
            b = QPushButton(text)
            b.setProperty("modeBtn", True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, t=tgt: self.set_mode(t))
            self.mode_btns.append((b, tgt))
            mode_row.addWidget(b)
        mode_row.addStretch()
        self.mq = QLabel("MQTT 连接中…"); self.mq.setStyleSheet("color:%s;" % DIM)
        mode_row.addWidget(self.mq)
        root.addLayout(mode_row)

        grid = QGridLayout(); grid.setSpacing(10)
        root.addLayout(grid, 1)

        # ── CPU 风扇卡
        ccpu = Card("🌀 CPU 风扇")
        g1 = QGridLayout(); g1.setHorizontalSpacing(18)
        self.cpu_t, self.cpu_d, self.cpu_r = QLabel("-- °C"), QLabel("-- %"), QLabel("---- RPM")
        for i, (w, _) in enumerate([("温度", self.cpu_t), ("Duty", self.cpu_d), ("RPM", self.cpu_r)]):
            col = QVBoxLayout()
            cap = QLabel(w); cap.setStyleSheet("color:%s;font-size:11px;background:transparent;" % DIM)
            w_.setStyleSheet("font-size:19px;font-weight:700;background:transparent;")
            col.addWidget(cap); col.addWidget(w_)
            g1.addLayout(col, 0, i)
        self.cpu_curve = CurveWidget()
        g1.addWidget(self.cpu_curve, 1, 0, 1, 3)
        row = QHBoxLayout()
        b1 = QPushButton("🔥 强冷 开"); b1.clicked.connect(lambda: self.boost(True))
        b2 = QPushButton("强冷 关"); b2.clicked.connect(lambda: self.boost(False))
        b3 = QPushButton("恢复官方默认曲线"); b3.clicked.connect(self.curve_restore)
        for b in (b1, b2, b3): row.addWidget(b)
        row.addStretch()
        g1.addLayout(row, 2, 0, 1, 3)
        ccpu.v.addLayout(g1)
        grid.addWidget(ccpu, 0, 0)

        # ── GPU 卡
        cgpu = Card("❄ GPU 风扇 / 高级")
        g2 = QGridLayout(); g2.setHorizontalSpacing(18)
        self.gpu_t, self.gpu_d, self.gpu_r = QLabel("-- °C"), QLabel("-- %"), QLabel("---- RPM")
        for i, (_, w_) in enumerate([("温度", self.gpu_t), ("Duty", self.gpu_d), ("RPM", self.gpu_r)]):
            col = QVBoxLayout()
            cap = QLabel(_); cap.setStyleSheet("color:%s;font-size:11px;background:transparent;" % DIM)
            w_.setStyleSheet("font-size:19px;font-weight:700;background:transparent;")
            col.addWidget(cap); col.addWidget(w_)
            g2.addLayout(col, 0, i)
        self.gpu_curve = CurveWidget()
        g2.addWidget(self.gpu_curve, 1, 0, 1, 3)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("PL1 (W):"))
        self.pl_ent = QLineEdit(); self.pl_ent.setFixedWidth(64)
        prow.addWidget(self.pl_ent)
        pb = QPushButton("写入 PL1"); pb.clicked.connect(self.pl_apply)
        prow.addWidget(pb); prow.addStretch()
        self.lbl_pl = QLabel("PL 墙: --/--/-- W")
        prow.addWidget(self.lbl_pl)
        g2.addLayout(prow, 2, 0, 1, 3)
        cgpu.v.addLayout(g2)
        grid.addWidget(cgpu, 0, 1)

        # ── 电源卡
        cpow = Card("🔋 电源 / 电池")
        self.lbl_chg = QLabel("充电限制: 本机EC固件不支持软件限充")
        self.lbl_bat = QLabel("电池: --%")
        cpow.v.addWidget(self.lbl_chg); cpow.v.addWidget(self.lbl_bat)
        grid.addWidget(cpow, 1, 0)

        # ── 设备卡
        cdev = Card("⌨ 设备")
        krow = QHBoxLayout()
        krow.addWidget(QLabel("键盘背光:"))
        self.bkl_btns = []
        for lv in (0, 1, 2):
            b = QPushButton(["熄灭", "微亮", "全亮"][lv]); b.setFixedWidth(72)
            b.clicked.connect(lambda _, l=lv: self.backlight(l))
            krow.addWidget(b); self.bkl_btns.append(b)
        krow.addSpacing(18)
        krow.addWidget(QLabel("关机USB充电:"))
        uon = QPushButton("开"); uon.setFixedWidth(56); uon.clicked.connect(lambda: self.usbchg(True))
        uoff = QPushButton("关"); uoff.setFixedWidth(56); uoff.clicked.connect(lambda: self.usbchg(False))
        krow.addWidget(uon); krow.addWidget(uoff); krow.addStretch()
        cdev.v.addLayout(krow)
        trow = QHBoxLayout()
        trow.addWidget(QLabel("触摸板:"))
        td = QPushButton("禁用"); td.setFixedWidth(64); td.clicked.connect(lambda: self.touchpad(1))
        te = QPushButton("启用"); te.setFixedWidth(64); te.clicked.connect(lambda: self.touchpad(0))
        trow.addWidget(td); trow.addWidget(te); trow.addStretch()
        cdev.v.addLayout(trow)
        self.lbl_dev = QLabel("背光档: - · 触摸板: --")
        cdev.v.addWidget(self.lbl_dev)
        grid.addWidget(cdev, 1, 1)

        # ── 日志
        self.logbox = QTextEdit(); self.logbox.setReadOnly(True); self.logbox.setFixedHeight(96)
        root.addWidget(self.logbox)

        # MQTT 异步连接
        QTimer.singleShot(200, self.connect_mc)
        self.timer = QTimer(); self.timer.timeout.connect(self.poll)
        self.timer.start(2500)

    # ---------- helpers ----------
    def log(self, m): self.logbox.append(m)

    def connect_mc(self):
        try:
            self.mc = self.mc_mod.MrConsole(log_fn=lambda _: None)
            ok = self.mc.start()
            self.mq.setText("MQTT ✅" if ok else "MQTT ❌")
            self.mq.setStyleSheet("color:%s;" % (GREEN if ok else "#e06c75"))
        except Exception as e:
            self.mq.setText("MQTT ❌ %s" % e)

    def need_mc(self):
        if not self.mc:
            QMessageBox.information(self, "提示", "MQTT 未连接")
            return True
        return False

    def set_mode(self, target):
        if self.need_mc(): return
        for b, t in self.mode_btns:
            b.setProperty("active", t == target)
            b.style().unpolish(b); b.style().polish(b)
        key = {0: "office", 1: "gaming", 2: "turbo", 3: "custom"}.get(target)
        self.log("[MODE] → %s" % key)
        threading.Thread(target=lambda: self.mc.set_mode(key), daemon=True).start()

    def boost(self, on):
        if self.need_mc(): return
        threading.Thread(target=lambda: self.mc.set_fan_boost(on), daemon=True).start()
        self.log("[FAN_BOOST] %s" % ("ON" if on else "OFF"))

    def curve_restore(self):
        if self.need_mc(): return
        threading.Thread(target=lambda: self.mc.restore_fan_curve(""), daemon=True).start()
        self.log("[CURVE] 恢复官方默认")

    def pl_apply(self):
        try: w = int(self.pl_ent.text())
        except Exception: return
        ok = self.ec.set_pl1(w)
        self.log("[PL1] %dW -> %s" % (w, "✅" if ok else "❌"))
        self.poll()

    def backlight(self, level):
        ok = self.ec.set_kb_backlight(level)
        self.log("[BACKLIGHT] 档%d -> %s" % (level, "✅" if ok else "❌"))

    def usbchg(self, on):
        if self.need_mc(): return
        act = "USB_CHARGER_ON" if on else "USB_CHARGER_OFF"
        payload = json.dumps({"Action": act, "ServCMD": act})
        threading.Thread(target=lambda: self.mc.mqtt.publish("Setting/Control", payload), daemon=True).start()
        self.log("[USB_CHG] %s 下发 (EC 0x767 bit4)" % act)

    def touchpad(self, disable):
        v = self.ec.ec_read(0x7A6)
        if v is None: return
        if disable and QMessageBox.question(self, "确认",
                "将禁用内置触摸板!\n确认已连接外接鼠标?") != QMessageBox.Yes:
            return
        nv = (v | 64) if disable else (v & ~64 & 0xFF)
        self.ec.ec_write(0x7A6, nv)
        time.sleep(0.3)
        self.log("[TP] bit6=%d 读回=%s" % (disable, self.ec.ec_read(0x7A6)))

    def poll(self):
        try:
            e = self.ec
            ct, cd, cr = e.get_cpu_temp(), e.get_fan_duty(), e.get_fan_rpm()
            gt, gd, gr = e.get_gpu_temp(), e.get_gpu_duty(), e.get_gpu_rpm()
            self.cpu_t.setText("%s °C" % ct); self.cpu_d.setText("%s %%" % cd); self.cpu_r.setText("%s RPM" % cr)
            self.gpu_t.setText("%s °C" % gt); self.gpu_d.setText("%s %%" % gd); self.gpu_r.setText("%s RPM" % gr)
            self.cpu_curve.set_points([cd or 30]*16); self.cpu_curve.temp = ct
            self.gpu_curve.set_points([gd or 30]*16); self.gpu_curve.temp = gt
            pl = e.get_pl_walls()
            if pl:
                self.lbl_pl.setText("PL 墙: %s/%s/%s W" % (pl["pl1"], pl["pl2"], pl["pl4"]))
                if not self.pl_ent.text() or self.pl_ent.text() == "--":
                    self.pl_ent.setText(str(pl["pl1"]))
            bkl = e.get_kb_backlight(); tp = e.ec_read(0x7A6)
            self.lbl_dev.setText("背光档: %s · 触摸板: %s" %
                (bkl, "禁用" if tp is not None and tp & 64 else ("启用" if tp is not None else "--")))
            bat = {}
            if self.mc:
                try: bat = self.mc.get_battery() or {}
                except Exception: pass
            self.lbl_bat.setText("电池: %s%%" % bat.get("BatteryPercent", "--"))
        except Exception as ex:
            self.log("[poll] %r" % ex)

def run():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = App()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run()
