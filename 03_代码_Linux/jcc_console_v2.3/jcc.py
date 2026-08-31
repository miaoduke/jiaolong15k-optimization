#!/usr/bin/env python3
# jcc.py — 蛟龙15K 控制中心 v2.3 (Jiaolong Control Center)
# 单文件 PyGObject/Gtk3 控制台，复用已有脚本 + uniwill sysfs
import os
import re
import json
import random
import subprocess
import sys
import threading
import time
import fcntl
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, Gio

# ---------- 常量 ----------
HW = "/sys/class/hwmon"
PLATFORM_PROFILE = "/sys/firmware/acpi/platform_profile"
BIN = os.path.dirname(os.path.abspath(__file__))  # 脚本同目录，便于自包含部署
INOU = "/sys/devices/platform/INOU0000:00"
BAT = "/sys/class/power_supply/BAT0"
PRESETS = {
    "红": (255, 0, 0), "绿": (0, 255, 0), "蓝": (0, 0, 255),
    "黄": (255, 255, 0), "青": (0, 255, 255), "紫": (255, 0, 255),
    "白": (255, 255, 255), "橙": (255, 165, 0),
}
PROFILES = {"quiet": "安静", "balanced": "平衡", "performance": "性能"}
EPP_MODES = {
    "performance": "最高性能",
    "balance_performance": "偏性能",
    "balance_power": "偏省电",
    "power": "最省电",
}
CPU_FREQ_MIN = 1100000  # 1.1 GHz
CPU_FREQ_MAX = 3100000  # 3.1 GHz (BIOS 锁定上限)
CONFIG_DIR = os.path.expanduser("~/.config/jcc")
CONFIG_FILE = os.path.join(CONFIG_DIR, "profiles.json")

# ---------- 内部缓存 ----------
_hwmon_path = None
_last_gpu_power = ("N/A", 0.0)
_last_refresh_rate = ("-", 0.0)

# ---------- 批量读取 ----------
def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return ""

def _read_multi(paths):
    res = {}
    for p in paths:
        res[p] = _read(p)
    return res

# ---------- 监控数据缓冲 ----------
class RingBuffer:
    def __init__(self, size=360):
        self.size = size
        self.data = [None] * size
        self.idx = 0
        self.count = 0

    def push(self, value):
        self.data[self.idx] = value
        self.idx = (self.idx + 1) % self.size
        self.count = min(self.count + 1, self.size)

    def series(self):
        if self.count < self.size:
            return [v for v in self.data[:self.idx] if v is not None]
        return [v for v in (self.data[self.idx:] + self.data[:self.idx]) if v is not None]

_monitor_buffers = {
    "cpu_temp": RingBuffer(),
    "gpu_temp": RingBuffer(),
    "fan1_rpm": RingBuffer(),
    "fan2_rpm": RingBuffer(),
    "gpu_power": RingBuffer(),
}

def get_uniwill_hwmon():
    global _hwmon_path
    if not _hwmon_path:
        try:
            for h in sorted(os.listdir(HW)):
                hd = os.path.join(HW, h)
                if _read(os.path.join(hd, "name")) == "uniwill":
                    _hwmon_path = hd
                    break
        except Exception:
            pass
    if not _hwmon_path:
        return None
    paths = [os.path.join(_hwmon_path, f) for f in
             ["temp1_input", "temp2_input", "fan1_input", "fan2_input", "pwm1", "pwm2"]]
    vals = _read_multi(paths)
    return tuple(int(vals.get(p, "0") or 0) for p in paths)

def _update_monitor_buffers():
    h = get_uniwill_hwmon()
    if h:
        _monitor_buffers["cpu_temp"].push(h[0] // 1000)
        _monitor_buffers["gpu_temp"].push(h[1] // 1000)
        _monitor_buffers["fan1_rpm"].push(h[2])
        _monitor_buffers["fan2_rpm"].push(h[3])
    gp = get_gpu_power()
    if gp != "N/A":
        try:
            _monitor_buffers["gpu_power"].push(float(gp))
        except ValueError:
            pass

# ---------- 读状态 ----------
def get_profile():
    return _read(PLATFORM_PROFILE)

def get_battery():
    vals = _read_multi([f"{BAT}/capacity", "/sys/class/power_supply/AC0/online"])
    ac = vals.get("/sys/class/power_supply/AC0/online", "0")
    return vals.get(f"{BAT}/capacity", "0"), "AC" if ac == "1" else "电池"

def get_battery_health():
    full = int(_read(f"{BAT}/charge_full") or 0)
    design = int(_read(f"{BAT}/charge_full_design") or 0)
    health = f"{full * 100 // design}" if full and design else "-"
    return health, get_cycle_count()

_cycles_cache = (None, 0.0)

def get_cycle_count():
    """EC 直读循环次数(0x4A6/4A7 小端)，60s 缓存；sysfs cycle_count 本机恒 0 不可信"""
    global _cycles_cache
    now = time.time()
    val, ts = _cycles_cache
    if val is not None and now - ts < 60.0:
        return str(val)
    try:
        r = subprocess.run(["sudo", "-n", os.path.join(BIN, "jcc-sudo-wrapper"), "get-cycles"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            val = r.stdout.strip()
            _cycles_cache = (val, now)
            return val
    except Exception:
        pass
    fb = _read(f"{BAT}/cycle_count")
    return fb if fb else "-"

def get_cpu_freq():
    total = n = 0
    for i in range(16):
        v = _read(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq")
        if v:
            total += int(v)
            n += 1
    return f"{total / n / 1e6:.2f}" if n else "-"

def get_nvme_temp():
    try:
        for h in sorted(os.listdir(HW)):
            hd = os.path.join(HW, h)
            if _read(os.path.join(hd, "name")) == "nvme":
                return str(int(_read(os.path.join(hd, "temp1_input")) or 0) // 1000)
    except Exception:
        pass
    return "-"

def get_mem_usage():
    total = avail = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
                    break
        if total:
            return f"{(total - avail) * 100 // total}"
    except Exception:
        pass
    return "-"

_last_gpu_info = ("N/A", "-", 0.0)  # (power, clocks, timestamp)

def get_gpu_info():
    """GPU 功耗+频率合并查询，5s 缓存"""
    global _last_gpu_info
    now = time.time()
    pw, clk, ts = _last_gpu_info
    if now - ts < 5.0 and pw != "N/A":
        return pw, clk
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=power.draw,clocks.sm",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=2)
        parts = [p.strip() for p in r.stdout.strip().split(",")]
        pw = parts[0] if parts and parts[0] else "N/A"
        clk = parts[1] if len(parts) > 1 and parts[1] else "-"
        _last_gpu_info = (pw, clk, time.time())
        return pw, clk
    except Exception:
        _last_gpu_info = ("N/A", "-", time.time())
        return "N/A", "-"

def get_gpu_power():
    return get_gpu_info()[0]

_rapl_prev = None  # (energy_uj, timestamp)
_cpu_power_w = 0.0

def get_cpu_power():
    """CPU 功耗 W (RAPL package 差分)，经 wrapper 读 root-only 计数器"""
    global _rapl_prev, _cpu_power_w
    try:
        r = subprocess.run(["sudo", "-n", os.path.join(BIN, "jcc-sudo-wrapper"), "get-cpurap"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return _cpu_power_w
        e = int(r.stdout.strip())
        now = time.time()
        prev = _rapl_prev
        _rapl_prev = (e, now)
        if prev and now > prev[1]:
            d = e - prev[0]
            if d < 0:
                d += 65533000000  # 计数器回绕 (max_energy_range ≈65533J)
            w = d / 1e6 / (now - prev[1])
            if 0 <= w < 200:  # 合理范围过滤
                _cpu_power_w = w
    except Exception:
        pass
    return _cpu_power_w

_cpu_stat_prev = None
_cpu_usage_cache = (0, 0.0)

def get_cpu_usage():
    """CPU 占用率 %（/proc/stat 差分），1s 节流"""
    global _cpu_stat_prev, _cpu_usage_cache
    now = time.time()
    if now - _cpu_usage_cache[1] < 0.9:
        return _cpu_usage_cache[0]
    try:
        with open("/proc/stat") as f:
            line = f.readline().split()[1:]
        vals = list(map(int, line))
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        prev = _cpu_stat_prev
        _cpu_stat_prev = (idle, total)
        if prev:
            d_idle = idle - prev[0]
            d_total = total - prev[1]
            usage = max(0, min(100, int((d_total - d_idle) * 100 / d_total))) if d_total else 0
            _cpu_usage_cache = (usage, now)
            return usage
    except Exception:
        pass
    return 0

_BAT_STATUS_MAP = {
    "Charging": "⚡充电中", "Discharging": "🔋放电中", "Not charging": "未充电",
    "Full": "已充满", "Unknown": "未知",
}

def get_battery_status():
    raw = _read(f"{BAT}/status")
    return _BAT_STATUS_MAP.get(raw, raw or "-")

def get_battery_power():
    """电池充/放电功率 W（AC 下接近 0）"""
    c = int(_read(f"{BAT}/current_now") or 0)
    v = int(_read(f"{BAT}/voltage_now") or 0)
    return abs(c * v) / 1e12

def get_uptime():
    try:
        secs = float(open("/proc/uptime").read().split()[0])
        h, m = int(secs // 3600), int(secs % 3600 // 60)
        return f"{h}h{m:02d}m" if h else f"{m}m"
    except Exception:
        return "-"

# ---------- 电池续航会话统计 ----------
BATTERY_SESSION_FILE = os.path.join(CONFIG_DIR, "battery_session.json")

def _bs_load():
    try:
        with open(BATTERY_SESSION_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _bs_save(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(BATTERY_SESSION_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception:
        pass

def bs_on_ac_change(ac_online):
    """AC 状态变化时记录: 掉电记起点, 恢复电算结果"""
    data = _bs_load()
    if not ac_online:
        # 开始离电: 已有 ac_off_ts 则保留(跨关机持续统计), 否则补记现在
        if not data.get("ac_off_ts"):
            data["ac_off_ts"] = time.time()
            data["ac_off_cap"] = int(_read(f"{BAT}/capacity") or 0)
            data["ac_off_profile"] = get_profile()
            _bs_save(data)
    else:
        # 恢复供电: 结算本次离电会话
        ts = data.pop("ac_off_ts", None)
        start_cap = data.pop("ac_off_cap", None)
        start_profile = data.pop("ac_off_profile", None)
        if ts and start_cap is not None:
            dur_s = max(1, time.time() - ts)
            end_cap = int(_read(f"{BAT}/capacity") or start_cap)
            used = max(0, start_cap - end_cap)
            entry = {
                "date": time.strftime("%m-%d %H:%M"),
                "duration_s": int(dur_s),
                "cap_start": start_cap, "cap_end": end_cap, "used": used,
                "rate_per_h": round(used * 3600 / dur_s, 1),
                "profile": start_profile or "-",
            }
            data["last"] = entry
            hist = data.setdefault("history", [])
            hist.append(entry)
            del hist[:-50]  # 保留最近 50 条
        _bs_save(data)

def bs_stats():
    """科学统计: 按电源模式分组平均速率 + 趋势 + 续航估算"""
    data = _bs_load()
    hist = [h for h in data.get("history", []) if h.get("duration_s", 0) >= 300]  # ≥5分钟才计入
    groups = {}
    for h in hist:
        groups.setdefault(h.get("profile", "-"), []).append(h)
    stats = []
    for prof, items in sorted(groups.items()):
        rates = [i["rate_per_h"] for i in items]
        durs = [i["duration_s"] for i in items]
        n = len(rates)
        avg = sum(rates) / n
        # 趋势: 最近一半 vs 之前一半 (样本≥4 才有意义)
        trend = None
        if n >= 4:
            half = n // 2
            older = rates[:-half] if half else rates
            newer = rates[-half:]
            old_avg = sum(older) / len(older)
            new_avg = sum(newer) / len(newer)
            if old_avg > 0:
                trend = (old_avg - new_avg) / old_avg * 100  # 正=改善(变慢放电)
        stats.append({
            "profile": prof, "count": n,
            "avg_rate": avg,
            "best_rate": min(rates), "worst_rate": max(rates),
            "total_h": sum(durs) / 3600,
            "trend_pct": trend,
            "reliable": n >= 3,                      # 样本量可靠性
            "est_hours_to_20": (100 - 20) / avg if avg > 0 else None,  # 100%→20% 预计可用时长
        })
    stats.sort(key=lambda s: s["avg_rate"])
    return stats, hist[-8:]

def bs_display():
    """返回 (离电时长文本, 放电速率文本)"""
    data = _bs_load()
    now_ac = _read("/sys/class/power_supply/AC0/online") == "1"
    if not now_ac and data.get("ac_off_ts"):
        # 离电中: 实时时长与速率
        dur_s = time.time() - data["ac_off_ts"]
        start = data.get("ac_off_cap", 0)
        cur = int(_read(f"{BAT}/capacity") or start)
        used = max(0, start - cur)
        rate = used * 3600 / max(dur_s, 60) if dur_s > 60 else None
        h, m = int(dur_s // 3600), int(dur_s % 3600 // 60)
        dur_txt = f"{h}h{m:02d}m" if h else f"{m}m"
        rate_txt = f"{rate:.1f}%/h" if rate is not None else "计算中…"
        return dur_txt, rate_txt
    # 插电: 显示上次离电会话
    last = data.get("last")
    if last:
        d = last["duration_s"]
        h, m = int(d // 3600), int(d % 3600 // 60)
        dur_txt = (f"{h}h{m:02d}m" if h else f"{m}m") + "(上次)"
        rate_txt = f"{last['rate_per_h']}%/h(上次)"
        return dur_txt, rate_txt
    return "-", "-"

def get_refresh_rate():
    global _last_refresh_rate
    now = time.time()
    val, ts = _last_refresh_rate
    if now - ts < 5.0 and val != "-":
        return val
    try:
        env = {**os.environ, "DISPLAY": ":0"}
        r = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=2, env=env)
        m = re.search(r"(\d+\.\d+)\*", r.stdout)
        val = m.group(1) if m else "-"
        _last_refresh_rate = (val, time.time())
        return val
    except Exception:
        return "-"

def get_all_switches():
    names = ["rainbow_animation", "breathing_in_suspend",
             "fn_lock_toggle_enable", "super_key_toggle_enable",
             "touchpad_toggle_enable"]
    paths = [os.path.join(INOU, n) for n in names]
    vals = _read_multi(paths)
    return {n: vals.get(os.path.join(INOU, n), "0") for n in names}

_rfkill_cache = {}
_lsmod_cache = ("", 0.0)

def get_rfkill_state(device):
    """返回 True=未阻断(开)，5s 缓存"""
    now = time.time()
    cached = _rfkill_cache.get(device)
    if cached and now - cached[1] < 5.0:
        return cached[0]
    try:
        r = subprocess.run(["rfkill", "list", device], capture_output=True, text=True, timeout=3)
        state = "Soft blocked: yes" not in r.stdout and "Hard blocked: yes" not in r.stdout
        _rfkill_cache[device] = (state, now)
        return state
    except Exception:
        return False

def get_camera_state():
    """摄像头开 = uvcvideo 已加载，5s 缓存"""
    global _lsmod_cache
    now = time.time()
    val, ts = _lsmod_cache
    if now - ts < 5.0:
        return "uvcvideo" in val
    try:
        r = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=3)
        _lsmod_cache = (r.stdout, now)
        return "uvcvideo" in r.stdout
    except Exception:
        return False

# ---------- 写操作（root，经 jcc-sudo-wrapper / 免密脚本） ----------
def sudo_cmd(args, timeout=10):
    try:
        r = subprocess.run(["sudo", "-n"] + args, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return True, r.stdout.strip()
        # 透传真实错误(如 EC 写入异常), 而非笼统报"没权限"
        err = (r.stderr or "").strip().splitlines()
        real = err[-1] if err else ""
        if "password" in real.lower() or "no new privileges" in real.lower():
            return False, "需要权限：请点击'授权'按钮刷新权限"
        return False, real or f"命令失败(exit {r.returncode})"
    except Exception as e:
        return False, str(e)

def _jcc_sudo(action, value):
    return sudo_cmd([os.path.join(BIN, "jcc-sudo-wrapper"), action, str(value)])

def set_profile(mode):
    return _jcc_sudo("set-profile", mode)

def set_charge_limit(percent):
    return sudo_cmd([os.path.join(BIN, "charge_limit.sh"), "set", str(percent)])

def set_rgb(r, g, b):
    # 直接调用脚本本体（有 shebang 且已 chmod+x；sudoers 免密匹配此路径）
    return sudo_cmd([os.path.join(BIN, "kbd_rgb.py"), str(r), str(g), str(b)])

def set_rainbow(on):
    return _jcc_sudo("set-rainbow", 1 if on else 0)

def set_breathing(on):
    return _jcc_sudo("set-breathing", 1 if on else 0)

def set_touchpad(on):
    return _jcc_sudo("set-touchpad", 1 if on else 0)

def set_super_key(on):
    return _jcc_sudo("set-super", 1 if on else 0)

def set_fn_lock(on):
    return _jcc_sudo("set-fnlock", 1 if on else 0)

# ---------- 性能控制 ----------
def get_epp():
    return _read("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")

def set_epp(mode):
    return _jcc_sudo("set-epp", mode)

def get_max_freq():
    v = int(_read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq") or 0)
    return v if v else CPU_FREQ_MAX

def set_max_freq(khz):
    return _jcc_sudo("set-maxfreq", str(int(khz)))

def get_boost():
    return _read("/sys/devices/system/cpu/cpufreq/boost") == "1"

def set_boost(on):
    return _jcc_sudo("set-boost", 1 if on else 0)

# ---------- 风扇强冷 (EC 0x751 FanBoost 位, 实测双风扇全速 4382RPM) ----------
def set_fan_boost_ec(on):
    return _jcc_sudo("set-fanboost-ec", 1 if on else 0)

def get_fan_boost_ec():
    try:
        r = subprocess.run(["sudo", "-n", os.path.join(BIN, "jcc-sudo-wrapper"), "get-fanboost-ec"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() == "1"
    except Exception:
        return False

def set_fan_dual(on):
    """双风扇常开: EC 0x751=0x80 User模式(实测副风扇不再温控停转)"""
    # 注意: ec_tool CLI 按16进制解析, 必须传 hex 字符串而非 str(int)
    return _jcc_sudo("set-fandual", "80" if on else "10")

def get_fan_dual():
    try:
        r = subprocess.run(["sudo", "-n", os.path.join(BIN, "ec_tool.py"), "r", "751"],
                           capture_output=True, text=True, timeout=10)
        # 输出形如 "0x0751 = 0x80"
        return "0x80" in r.stdout
    except Exception:
        return False

def set_bluetooth(on):
    action = "unblock" if on else "block"
    return sudo_cmd(["rfkill", action, "bluetooth"])

def set_camera(on):
    if on:
        return sudo_cmd(["modprobe", "uvcvideo"])
    return sudo_cmd(["modprobe", "-r", "uvcvideo"])

def set_battery_light(on):
    kb_battery = os.path.join(BIN, "kbd-battery.sh")
    if on:
        cmd = ["bash", "-c",
               "if [ -f /var/run/kbd-battery.pid ]; then kill $(cat /var/run/kbd-battery.pid) 2>/dev/null; fi; "
               f"nohup {kb_battery} >/dev/null 2>&1 &"]
        return sudo_cmd(cmd)
    return sudo_cmd(["bash", "-c",
                     "if [ -f /var/run/kbd-battery.pid ]; then kill $(cat /var/run/kbd-battery.pid) 2>/dev/null; "
                     "rm -f /var/run/kbd-battery.pid; fi"])

# ---------- 配置档案 ----------
def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {"profiles": {}, "power_binding": {"ac": "", "bat": ""}, "active": ""}

def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def snapshot_current():
    """抓取当前全套设置"""
    switches = get_all_switches()
    return {
        "profile": get_profile(),
        "rainbow": switches.get("rainbow_animation") == "1",
        "breathing": switches.get("breathing_in_suspend") == "1",
        "touchpad": switches.get("touchpad_toggle_enable") == "1",
        "super_key": switches.get("super_key_toggle_enable") == "1",
        "fn_lock": switches.get("fn_lock_toggle_enable") == "1",
    }

def apply_snapshot(snap):
    """应用档案快照，返回失败项列表"""
    fails = []
    ops = [
        ("profile", lambda: set_profile(snap.get("profile", "balanced"))),
        ("rainbow", lambda: set_rainbow(snap.get("rainbow", False))),
        ("breathing", lambda: set_breathing(snap.get("breathing", False))),
        ("touchpad", lambda: set_touchpad(snap.get("touchpad", True))),
        ("super_key", lambda: set_super_key(snap.get("super_key", True))),
        ("fn_lock", lambda: set_fn_lock(snap.get("fn_lock", False))),
    ]
    for name, fn in ops:
        ok, _ = fn()
        if not ok:
            fails.append(name)
    return fails

# ---------- 监控图表 ----------
class MonitorChart(Gtk.DrawingArea):
    """60秒滚动监控图：双系列，cairo 绘制"""
    def __init__(self, title, buf1_key, label1, color1, buf2_key=None, label2=None, color2=None):
        super().__init__()
        self.set_size_request(-1, 150)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.title = title
        self.buf1_key, self.label1, self.color1 = buf1_key, label1, color1
        self.buf2_key, self.label2, self.color2 = buf2_key, label2, color2
        self.connect("draw", self._on_draw)

    @staticmethod
    def _range(data):
        if not data:
            return 0.0, 1.0
        lo, hi = min(data), max(data)
        if hi == lo:
            hi = lo + 1
        pad = (hi - lo) * 0.15
        return lo - pad, hi + pad

    def _plot(self, cr, data, x0, y0, w0, h0, lo, hi, color, fill=False):
        if len(data) < 2:
            return
        cr.set_source_rgba(*color)
        cr.set_line_width(1.8)
        pts = []
        n = len(data)
        for i, v in enumerate(data):
            x = x0 + i * w0 / (n - 1)
            y = y0 + h0 * (1 - (v - lo) / (hi - lo))
            pts.append((x, y))
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.stroke()
        if fill:
            cr.line_to(pts[-1][0], y0 + h0)
            cr.line_to(pts[0][0], y0 + h0)
            cr.close_path()
            cr.set_source_rgba(color[0], color[1], color[2], 0.18)
            cr.fill()

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        if w < 40 or h < 40:
            return False
        # 背景
        cr.set_source_rgb(0.10, 0.10, 0.12)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        pad_l, pad_r, pad_t, pad_b = 44, 44, 22, 14
        x0, y0 = pad_l, pad_t
        w0, h0 = w - pad_l - pad_r, h - pad_t - pad_b

        d1 = list(_monitor_buffers[self.buf1_key].series())
        d2 = list(_monitor_buffers[self.buf2_key].series()) if self.buf2_key else []

        if not d1 and not d2:
            cr.set_source_rgb(0.55, 0.55, 0.55)
            cr.move_to(w / 2 - 36, h / 2)
            cr.show_text("等待数据…")
            return False

        # 网格
        cr.set_line_width(0.6)
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.25)
        for i in range(1, 4):
            y = y0 + i * h0 / 4
            cr.move_to(x0, y)
            cr.line_to(x0 + w0, y)
        cr.stroke()

        lo1, hi1 = self._range(d1)
        self._plot(cr, d1, x0, y0, w0, h0, lo1, hi1, self.color1)

        if d2:
            lo2, hi2 = self._range(d2)
            self._plot(cr, d2, x0, y0, w0, h0, lo2, hi2, self.color2, fill=True)

        # 左轴刻度
        cr.set_source_rgb(0.75, 0.75, 0.78)
        cr.set_font_size(9)
        for i in range(5):
            v = hi1 - i * (hi1 - lo1) / 4
            y = y0 + i * h0 / 4 + 9
            cr.move_to(2, y)
            cr.show_text(f"{v:.0f}")
        # 右轴刻度
        if d2:
            for i in range(5):
                v = hi2 - i * (hi2 - lo2) / 4
                y = y0 + i * h0 / 4 + 9
                cr.move_to(w - pad_r + 2, y)
                cr.show_text(f"{v:.0f}")

        # 标题与图例
        cr.set_font_size(10)
        cr.set_source_rgb(0.85, 0.85, 0.88)
        cr.move_to(x0, 13)
        cr.show_text(self.title)
        lx = x0 + 90
        cr.set_source_rgb(*self.color1[:3])
        cr.rectangle(lx, 6, 10, 3)
        cr.fill()
        cr.move_to(lx + 14, 13)
        cr.show_text(self.label1)
        if self.label2:
            cr.set_source_rgb(*self.color2[:3])
            cr.rectangle(lx + 14 + len(self.label1) * 7 + 12, 6, 10, 3)
            cr.fill()
            cr.move_to(lx + 14 + len(self.label1) * 7 + 26, 13)
            cr.show_text(self.label2)
        return False

# ---------- Toast ----------
class ToastManager:
    def __init__(self, container):
        self.container = container
        self.queue = []
        self.showing = False

    def show(self, message, mtype="info", duration=2600):
        colors = {"info": "#3584e4", "success": "#2ec27e",
                  "warning": "#e5a50a", "error": "#e01b24"}
        bg = colors.get(mtype, colors["info"])
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl = Gtk.Label()
        lbl.set_markup(f"<span foreground='white'><b>{message}</b></span>")
        lbl.set_margin_top(8)
        lbl.set_margin_bottom(8)
        lbl.set_margin_start(20)
        lbl.set_margin_end(20)
        frame = Gtk.Frame()
        ev = Gtk.EventBox()
        css = Gtk.CssProvider()
        css.load_from_data(f"* {{ background: {bg}; border-radius: 8px; }}".encode())
        ev.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        lbl.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        ev.add(lbl)
        frame.add(ev)
        self.queue.append((frame, duration))
        if not self.showing:
            self._next()

    def _next(self):
        if not self.queue:
            self.showing = False
            return
        self.showing = True
        widget, duration = self.queue.pop(0)
        self.container.pack_start(widget, False, False, 4)
        widget.show_all()
        GLib.timeout_add(duration, self._hide, widget)

    def _hide(self, widget):
        widget.destroy()
        self._next()
        return False

# ---------- 主应用 ----------
class JCC(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.jcc.controlcenter")
        self.cfg = load_config()
        self.dynamic_timer_id = None
        self.dynamic_interval = 3
        self.dynamic_mode = None  # None/'random'
        self._syncing = False     # 防止 set_active 触发回调

    def do_activate(self):
        # 单实例: 二次启动把已有窗口带到前台而非静默
        if getattr(self, 'win', None) is not None:
            self.win.present()
            return

        win = Gtk.ApplicationWindow(application=self)
        win.set_title("蛟龙15K 控制中心 v2.3")
        win.set_default_size(680, 640)
        win.set_resizable(True)

        self.toast_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_container.set_halign(Gtk.Align.CENTER)
        self.toast_container.set_valign(Gtk.Align.END)
        self.toast_container.set_margin_bottom(16)

        nb = Gtk.Notebook()
        nb.append_page(self._wrap_scroll(self._build_perf_page()), Gtk.Label(label="电源模式"))
        nb.append_page(self._wrap_scroll(self._build_rgb_page()), Gtk.Label(label="键盘灯效"))
        nb.append_page(self._wrap_scroll(self._build_hw_page()), Gtk.Label(label="硬件开关"))
        nb.append_page(self._wrap_scroll(self._build_tune_page()), Gtk.Label(label="性能调校"))
        nb.append_page(self._wrap_scroll(self._build_profile_page()), Gtk.Label(label="配置档案"))

        overlay = Gtk.Overlay()
        overlay.add(nb)
        overlay.add_overlay(self.toast_container)
        win.add(overlay)
        win.show_all()

        self.toast = ToastManager(self.toast_container)
        self.win = win

        GLib.idle_add(self._check_auth_status)
        GLib.timeout_add(1000, self._refresh)

        # 续航会话: 初始化 AC 状态, 启动时已离电则补记起点
        self._last_ac = _read("/sys/class/power_supply/AC0/online") == "1"
        if not self._last_ac:
            bs_on_ac_change(False)

    def _wrap_scroll(self, page):
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sc.add(page)
        return sc

    # ---- 性能页 ----
    def _build_perf_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        frame = Gtk.Frame(label="电源模式")
        vb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vb.set_margin_start(12)
        vb.set_margin_end(12)
        vb.set_margin_top(8)
        vb.set_margin_bottom(8)
        self.profile_btns = {}
        grp = None
        for key, label in PROFILES.items():
            rb = Gtk.RadioButton.new_with_label_from_widget(grp, label)
            rb.connect("toggled", self._on_profile, key)
            grp = rb
            vb.pack_start(rb, False, False, 0)
            self.profile_btns[key] = rb
        frame.add(vb)
        box.pack_start(frame, False, False, 0)

        frame2 = Gtk.Frame(label="实时状态")
        grid = Gtk.Grid(column_spacing=14, row_spacing=6)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.set_margin_top(8)
        grid.set_margin_bottom(8)

        # 科学分组: (组名, [(标签, key), ...]) — 每组一行, 组内4列
        groups = [
            ("处理器", [("温度", "cpu"), ("占用", "cpuusage"), ("频率", "cpufreq"), ("功耗", "cpupower")]),
            ("图形", [("温度", "gpu"), ("功耗", "gpupw"), ("频率", "gpuclock"), ("", None)]),
            ("散热", [("主风扇", "fan1"), ("副风扇", "fan2"), ("", None), ("", None)]),
            ("电池", [("电量", "bat"), ("状态", "batstatus"), ("功率", "batpower"), ("健康", "bathealth")]),
            ("续航", [("离电时长", "batsession"), ("放电速率", "disrate"), ("", None), ("", None)]),
            ("系统", [("内存", "mem"), ("NVMe 温度", "nvme"), ("刷新率", "refresh"), ("", None)]),
        ]
        self.val_labels = {}
        row_i = 0
        for gname, items in groups:
            # 组标题行
            gl = Gtk.Label()
            gl.set_markup(f"<span size='small' foreground='gray' weight='bold'>{gname}</span>")
            gl.set_xalign(0)
            grid.attach(gl, 0, row_i, 8, 1)
            row_i += 1
            # 数据行
            for ci, (label, key) in enumerate(items):
                if not key:
                    continue
                grid.attach(Gtk.Label(label=label, xalign=1), ci * 2, row_i, 1, 1)
                v = Gtk.Label(label="-")
                v.set_markup("<b>-</b>")
                v.set_halign(Gtk.Align.START)
                grid.attach(v, ci * 2 + 1, row_i, 1, 1)
                self.val_labels[key] = v
            row_i += 1
        frame2.add(grid)
        box.pack_start(frame2, False, False, 0)

        frame5 = Gtk.Frame(label="实时监控 (60 秒滚动)")
        hb5 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hb5.set_margin_start(8)
        hb5.set_margin_end(8)
        hb5.set_margin_top(8)
        hb5.set_margin_bottom(8)
        # 关键修复: 直接传缓冲 key, 不再从中文标签生成
        self.chart_temp = MonitorChart("温度 °C", "cpu_temp", "CPU", (0.30, 0.69, 1.0),
                                       "gpu_temp", "GPU", (1.0, 0.55, 0.20))
        self.chart_fan = MonitorChart("风扇 RPM / GPU 功耗 W", "fan1_rpm", "风扇", (0.55, 0.80, 0.40),
                                      "gpu_power", "功耗", (0.80, 0.45, 0.95))
        hb5.pack_start(self.chart_temp, True, True, 0)
        hb5.pack_start(self.chart_fan, True, True, 0)
        frame5.add(hb5)
        box.pack_start(frame5, True, True, 0)

        frame3 = Gtk.Frame(label="充电阈值")
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hb.set_margin_start(12)
        hb.set_margin_end(12)
        hb.set_margin_top(8)
        hb.set_margin_bottom(8)
        adj = Gtk.Adjustment(value=80, lower=40, upper=100, step_increment=1, page_increment=5, page_size=0)
        self.charge_scale = Gtk.Scale(adjustment=adj)
        self.charge_scale.set_digits(0)
        self.charge_scale.set_hexpand(True)
        btn = Gtk.Button(label="应用")
        btn.connect("clicked", self._on_charge)
        hb.pack_start(self.charge_scale, True, True, 0)
        hb.pack_start(btn, False, False, 0)
        frame3.add(hb)
        box.pack_start(frame3, False, False, 0)

        frame4 = Gtk.Frame(label="权限")
        hb4 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hb4.set_margin_start(12)
        hb4.set_margin_end(12)
        hb4.set_margin_top(8)
        hb4.set_margin_bottom(8)
        auth_btn = Gtk.Button(label="授权")
        auth_btn.connect("clicked", self._on_auth)
        self.auth_status = Gtk.Label(label="检查中…")
        hb4.pack_start(auth_btn, False, False, 0)
        hb4.pack_start(self.auth_status, False, False, 0)
        frame4.add(hb4)
        box.pack_start(frame4, False, False, 0)

        return box

    # ---- RGB 页 ----
    def _build_rgb_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        frame = Gtk.Frame(label="静态颜色")
        hb = Gtk.Box(spacing=8)
        hb.set_margin_start(12)
        hb.set_margin_end(12)
        hb.set_margin_top(8)
        hb.set_margin_bottom(8)
        for name, (r, g, b) in PRESETS.items():
            b2 = Gtk.Button(label=name)
            b2.connect("clicked", self._on_rgb, r, g, b)
            hb.pack_start(b2, False, False, 0)
        frame.add(hb)
        box.pack_start(frame, False, False, 0)

        frame_c = Gtk.Frame(label="自定义颜色")
        hb_c = Gtk.Box(spacing=8)
        hb_c.set_margin_start(12)
        hb_c.set_margin_end(12)
        hb_c.set_margin_top(8)
        hb_c.set_margin_bottom(8)
        self.color_btn = Gtk.ColorButton()
        rgba = Gdk.RGBA(1.0, 0, 0, 1.0)
        self.color_btn.set_rgba(rgba)
        self.color_btn.connect("color-set", self._on_custom_color)
        hb_c.pack_start(Gtk.Label(label="选择颜色:"), False, False, 0)
        hb_c.pack_start(self.color_btn, False, False, 0)
        frame_c.add(hb_c)
        box.pack_start(frame_c, False, False, 0)

        frame_d = Gtk.Frame(label="动态灯效")
        hb_d = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hb_d.set_margin_start(12)
        hb_d.set_margin_end(12)
        hb_d.set_margin_top(8)
        hb_d.set_margin_bottom(8)

        hb_dm = Gtk.Box(spacing=8)
        self.rb_dyn_off = Gtk.RadioButton.new_with_label_from_widget(None, "关闭")
        self.rb_dyn_off.connect("toggled", self._on_dynamic, "off")
        self.rb_dyn_random = Gtk.RadioButton.new_with_label_from_widget(self.rb_dyn_off, "随机换色")
        self.rb_dyn_random.connect("toggled", self._on_dynamic, "random")
        hb_dm.pack_start(self.rb_dyn_random, False, False, 0)
        hb_dm.pack_start(self.rb_dyn_off, False, False, 0)
        hb_d.pack_start(hb_dm, False, False, 0)

        hb_di = Gtk.Box(spacing=8)
        hb_di.pack_start(Gtk.Label(label="换色间隔:"), False, False, 0)
        adj_dyn = Gtk.Adjustment(value=3, lower=1, upper=60, step_increment=1, page_increment=5, page_size=0)
        self.spin_dyn_interval = Gtk.SpinButton(adjustment=adj_dyn)
        self.spin_dyn_interval.connect("value-changed", self._on_dynamic_interval)
        hb_di.pack_start(self.spin_dyn_interval, False, False, 0)
        hb_di.pack_start(Gtk.Label(label="秒"), False, False, 0)
        hb_d.pack_start(hb_di, False, False, 0)

        frame_d.add(hb_d)
        box.pack_start(frame_d, False, False, 0)

        frame2 = Gtk.Frame(label="键盘亮度")
        hb2 = Gtk.Box(spacing=8)
        hb2.set_margin_start(12)
        hb2.set_margin_end(12)
        hb2.set_margin_top(8)
        hb2.set_margin_bottom(8)
        for i in range(1, 6):
            b3 = Gtk.Button(label=f"{i}")
            b3.connect("clicked", self._on_brightness, i)
            hb2.pack_start(b3, False, False, 0)
        frame2.add(hb2)
        box.pack_start(frame2, False, False, 0)

        frame3 = Gtk.Frame(label="动画")
        hb3 = Gtk.Box(spacing=16)
        hb3.set_margin_start(12)
        hb3.set_margin_end(12)
        hb3.set_margin_top(8)
        hb3.set_margin_bottom(8)
        self.cb_rainbow = Gtk.CheckButton(label="彩虹")
        self.cb_rainbow.connect("toggled", self._on_rainbow)
        self.cb_breathing = Gtk.CheckButton(label="呼吸")
        self.cb_breathing.connect("toggled", self._on_breathing)
        hb3.pack_start(self.cb_rainbow, False, False, 0)
        hb3.pack_start(self.cb_breathing, False, False, 0)
        frame3.add(hb3)
        box.pack_start(frame3, False, False, 0)

        frame4 = Gtk.Frame(label="电量灯（拔电显示电量颜色）")
        hb4 = Gtk.Box(spacing=12)
        hb4.set_margin_start(12)
        hb4.set_margin_end(12)
        hb4.set_margin_top(8)
        hb4.set_margin_bottom(8)
        self.sw_battlight = Gtk.Switch()
        self.sw_battlight.connect("state-set", self._on_battlight)
        hb4.pack_start(Gtk.Label(label="启用"), False, False, 0)
        hb4.pack_start(self.sw_battlight, False, False, 0)
        frame4.add(hb4)
        box.pack_start(frame4, False, False, 0)

        return box

    # ---- 硬件页 ----
    def _build_hw_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        def row(label, cb, key):
            r = Gtk.Box(spacing=12)
            lbl = Gtk.Label(label=label, xalign=0)
            lbl.set_width_chars(16)
            r.pack_start(lbl, False, False, 0)
            r.pack_start(cb, False, False, 0)
            setattr(self, key, cb)
            box.pack_start(r, False, False, 0)

        sw_tp = Gtk.Switch()
        sw_tp.connect("state-set", self._on_touchpad)
        row("触摸板", sw_tp, "sw_touchpad")

        sw_super = Gtk.Switch()
        sw_super.connect("state-set", self._on_super)
        row("Win 键", sw_super, "sw_super")

        sw_fnlock = Gtk.Switch()
        sw_fnlock.connect("state-set", self._on_fnlock)
        row("Fn 锁", sw_fnlock, "sw_fnlock")

        sw_br = Gtk.Switch()
        sw_br.connect("state-set", self._on_breathing_hw)
        row("呼吸灯(挂起)", sw_br, "sw_breathing")

        sw_bl = Gtk.Switch()
        sw_bl.connect("state-set", self._on_battlight)
        row("电量灯(拔电)", sw_bl, "sw_battlight")

        sep = Gtk.Separator()
        box.pack_start(sep, False, False, 4)

        sw_bt = Gtk.Switch()
        sw_bt.connect("state-set", self._on_bluetooth)
        row("蓝牙", sw_bt, "sw_bluetooth")

        sw_cam = Gtk.Switch()
        sw_cam.connect("state-set", self._on_camera)
        row("摄像头", sw_cam, "sw_camera")

        return box

    # ---- 性能调校页 ----
    def _build_tune_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        # EPP 能效偏好
        frame1 = Gtk.Frame(label="CPU 能效偏好 (EPP)")
        vb1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vb1.set_margin_start(12)
        vb1.set_margin_end(12)
        vb1.set_margin_top(8)
        vb1.set_margin_bottom(8)
        self.epp_btns = {}
        grp = None
        for key, label in EPP_MODES.items():
            rb = Gtk.RadioButton.new_with_label_from_widget(grp, label)
            rb.connect("toggled", self._on_epp, key)
            grp = rb
            vb1.pack_start(rb, False, False, 0)
            self.epp_btns[key] = rb
        frame1.add(vb1)
        box.pack_start(frame1, False, False, 0)

        # CPU 频率上限
        frame2 = Gtk.Frame(label="CPU 最大频率限制")
        hb2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hb2.set_margin_start(12)
        hb2.set_margin_end(12)
        hb2.set_margin_top(8)
        hb2.set_margin_bottom(8)
        self.adj_maxfreq = Gtk.Adjustment(value=CPU_FREQ_MAX // 1000,
                                          lower=CPU_FREQ_MIN // 1000,
                                          upper=CPU_FREQ_MAX // 1000,
                                          step_increment=100, page_increment=500, page_size=0)
        self.scale_maxfreq = Gtk.Scale(adjustment=self.adj_maxfreq)
        self.scale_maxfreq.set_digits(0)
        self.scale_maxfreq.set_hexpand(True)
        self.scale_maxfreq.set_draw_value(False)
        self.scale_maxfreq.add_mark(CPU_FREQ_MIN // 1000, Gtk.PositionType.BOTTOM, "1.1G")
        self.scale_maxfreq.add_mark(2000000 // 1000, Gtk.PositionType.BOTTOM, "2.0G")
        self.scale_maxfreq.add_mark(2500000 // 1000, Gtk.PositionType.BOTTOM, "2.5G")
        self.scale_maxfreq.add_mark(CPU_FREQ_MAX // 1000, Gtk.PositionType.BOTTOM, "3.1G")
        btn_freq = Gtk.Button(label="应用")
        btn_freq.connect("clicked", self._on_maxfreq)
        btn_freq_reset = Gtk.Button(label="恢复全速")
        btn_freq_reset.connect("clicked", self._on_maxfreq_reset)
        hb2.pack_start(Gtk.Label(label="MHz:"), False, False, 0)
        hb2.pack_start(self.scale_maxfreq, True, True, 0)
        hb2.pack_start(btn_freq, False, False, 0)
        hb2.pack_start(btn_freq_reset, False, False, 0)
        frame2.add(hb2)
        box.pack_start(frame2, False, False, 0)

        # CPU Boost
        frame3 = Gtk.Frame(label="CPU Boost 睿频开关")
        hb3 = Gtk.Box(spacing=12)
        hb3.set_margin_start(12)
        hb3.set_margin_end(12)
        hb3.set_margin_top(8)
        hb3.set_margin_bottom(8)
        self.sw_boost = Gtk.Switch()
        self.sw_boost.connect("state-set", self._on_boost)
        boost_note = Gtk.Label()
        boost_note.set_markup("<span size='small' foreground='gray'>注: 本机 BIOS 锁定 3.1GHz，此开关实际影响有限</span>")
        hb3.pack_start(self.sw_boost, False, False, 0)
        hb3.pack_start(boost_note, False, False, 0)
        frame3.add(hb3)
        box.pack_start(frame3, False, False, 0)

        # 风扇控制
        frame_fan = Gtk.Frame(label="风扇控制")
        hb_fan = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hb_fan.set_margin_start(12)
        hb_fan.set_margin_end(12)
        hb_fan.set_margin_top(8)
        hb_fan.set_margin_bottom(8)

        row1 = Gtk.Box(spacing=16)
        self.sw_cool = Gtk.Switch()
        self.sw_cool.connect("state-set", self._on_cool_boost)
        row1.pack_start(Gtk.Label(label="一键强冷 (双风扇全速):"), False, False, 0)
        row1.pack_start(self.sw_cool, False, False, 0)

        btn_silent = Gtk.Button(label="一键静音")
        btn_silent.connect("clicked", self._on_silent)
        row1.pack_start(btn_silent, False, False, 0)
        hb_fan.pack_start(row1, False, False, 0)

        row2 = Gtk.Box(spacing=12)
        btn_deep = Gtk.Button(label="深度静音 (离电办公)")
        btn_deep.connect("clicked", self._on_deep_silent)
        row2.pack_start(btn_deep, False, False, 0)
        deep_note = Gtk.Label()
        deep_note.set_markup("<span size='small' foreground='gray'>= 一键静音 + EPP最省电 + 限频2.0G + Boost关 (整套低功耗预设)</span>")
        row2.pack_start(deep_note, False, False, 0)
        hb_fan.pack_start(row2, False, False, 0)

        fan_note = Gtk.Label()
        fan_note.set_markup(
            "<span size='small'>▎功能关系说明</span>\n"
            "<span size='small' foreground='gray'>"
            "• <b>一键静音</b>: 只切「安静模式」风扇表 → 风扇低速转（日常安静）\n"
            "• <b>深度静音</b>: 静音 + CPU 限频降耗 → 发热更低 → 风扇<b>自然停转</b>（离电续航办公用）\n"
            "• <b>一键强冷</b>: 双风扇全速散热（与静音互斥，开一个自动关另一个）\n"
            "• 风扇转速由 EC 温控闭环管理: 单独调速/强制常开均不可行(EC 秒级覆盖, 实测)</span>")
        fan_note.set_justify(Gtk.Justification.LEFT)
        hb_fan.pack_start(fan_note, False, False, 0)
        hb_fan.pack_start(fan_note, False, False, 0)
        hb_fan.pack_start(fan_note, False, False, 0)
        frame_fan.add(hb_fan)
        box.pack_start(frame_fan, False, False, 0)

        # 当前值显示
        frame4 = Gtk.Frame(label="当前生效值")
        grid4 = Gtk.Grid(column_spacing=16, row_spacing=6)
        grid4.set_margin_start(12)
        grid4.set_margin_end(12)
        grid4.set_margin_top(8)
        grid4.set_margin_bottom(8)
        self.tune_labels = {}
        tune_rows = [("EPP", "epp"), ("频率上限", "maxfreq"), ("Boost", "boost")]
        for i, (label, key) in enumerate(tune_rows):
            grid4.attach(Gtk.Label(label=label, xalign=1), 0, i, 1, 1)
            v = Gtk.Label(label="-")
            v.set_markup("<b>-</b>")
            v.set_halign(Gtk.Align.START)
            grid4.attach(v, 1, i, 1, 1)
            self.tune_labels[key] = v
        frame4.add(grid4)
        box.pack_start(frame4, False, False, 0)

        return box

    # ---- 性能调校事件 ----
    def _on_epp(self, rb, key):
        if rb.get_active() and not self._syncing:
            ok, out = set_epp(key)
            if ok:
                self._toast(f"EPP: {EPP_MODES[key]}", "success")
            else:
                self._err(out)

    def _on_maxfreq(self, btn):
        mhz = int(self.scale_maxfreq.get_value())
        ok, out = set_max_freq(mhz * 1000)
        if ok:
            self._toast(f"CPU 频率上限 {mhz} MHz", "success")
        else:
            self._err(out)

    def _on_maxfreq_reset(self, btn):
        ok, out = set_max_freq(CPU_FREQ_MAX)
        if ok:
            self.scale_maxfreq.set_value(CPU_FREQ_MAX // 1000)
            self._toast("已恢复全速 3.1 GHz", "success")
        else:
            self._err(out)

    def _on_boost(self, sw, state):
        if self._syncing:
            return
        ok, out = set_boost(state)
        if ok:
            self._toast(f"Boost 已{'开启' if state else '关闭'}", "success")
        else:
            self._err(out)

    def _on_cool_boost(self, sw, state):
        if self._syncing:
            return
        # 互斥: 开强冷时若处于安静模式则先回平衡(全速与静音意图冲突)
        if state and get_profile() == "quiet":
            set_profile("balanced")
            self._toast("已退出安静模式", "info")
        ok, out = set_fan_boost_ec(state)
        if ok:
            self._toast("强冷已开启 (双风扇全速)" if state else "强冷已关闭", "success")
        else:
            self._err(out)

    def _on_fan_dual(self, sw, state):
        if self._syncing:
            return
        ok, out = set_fan_dual(state)
        if ok:
            self._toast("双风扇常开已开启" if state else "已恢复自动温控", "success")
        else:
            self._err(out)

    def _on_deep_silent(self, btn):
        """深度静音预设: quiet + EPP power + 限频2.0G + boost关 — 低发热使风扇自然停转"""
        fails = []
        if get_fan_boost_ec():
            set_fan_boost_ec(False)
        for fn, args in [
            (set_profile, ("quiet",)),
            (set_epp, ("power",)),
            (set_max_freq, (2000000,)),
            (set_boost, (False,)),
        ]:
            ok, _ = fn(*args)
            if not ok:
                fails.append(fn.__name__)
        # 同步 UI
        self.scale_maxfreq.set_value(2000)
        if fails:
            self._err(f"部分失败: {','.join(fails)}")
        else:
            self._toast("深度静音已启用 — 风扇将自然停转", "success")

    def _on_silent(self, btn):
        # 互斥: 静音前先关强冷
        if get_fan_boost_ec():
            set_fan_boost_ec(False)
        ok, out = set_profile("quiet")
        if ok:
            self._toast("已切换安静模式 (风扇低速)", "success")
        else:
            self._err(out)

    def _sync_tune_ui(self):
        """同步性能调校页 UI（在 _refresh 中调用）"""
        if not hasattr(self, 'tune_labels'):
            return
        epp = get_epp()
        if epp in self.epp_btns and not self.epp_btns[epp].get_active():
            self.epp_btns[epp].set_active(True)
        self.tune_labels["epp"].set_markup(f"<b>{EPP_MODES.get(epp, epp)}</b>")
        mf = get_max_freq()
        self.tune_labels["maxfreq"].set_markup(f"<b>{mf // 1000} MHz</b>")
        boost = get_boost()
        self.tune_labels["boost"].set_markup("<b>开</b>" if boost else "<b>关</b>")
        self.sw_boost.set_active(boost)
        # 强冷状态(EC 0x751)——10s 缓存避免频繁 sudo
        now = time.time()
        if now - getattr(self, '_cool_ts', 0) > 10:
            self._cool_ts = now
            self.sw_cool.set_active(get_fan_boost_ec())

    # ---- 配置档案页 ----
    def _build_profile_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        frame = Gtk.Frame(label="配置档案（保存当前全套设置，一键恢复）")
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vb.set_margin_start(12)
        vb.set_margin_end(12)
        vb.set_margin_top(8)
        vb.set_margin_bottom(8)

        hb_name = Gtk.Box(spacing=8)
        hb_name.pack_start(Gtk.Label(label="档案名:"), False, False, 0)
        self.entry_profile_name = Gtk.Entry()
        self.entry_profile_name.set_placeholder_text("例如: 办公 / 游戏")
        self.entry_profile_name.set_hexpand(True)
        hb_name.pack_start(self.entry_profile_name, True, True, 0)
        btn_save = Gtk.Button(label="保存当前设置")
        btn_save.connect("clicked", self._on_profile_save)
        hb_name.pack_start(btn_save, False, False, 0)
        vb.pack_start(hb_name, False, False, 0)

        self.listbox_profiles = Gtk.ListBox()
        self.listbox_profiles.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(200)
        scroll.add(self.listbox_profiles)
        vb.pack_start(scroll, True, True, 0)

        hb_ops = Gtk.Box(spacing=8)
        btn_apply = Gtk.Button(label="应用选中档案")
        btn_apply.connect("clicked", self._on_profile_apply)
        hb_ops.pack_start(btn_apply, False, False, 0)
        btn_del = Gtk.Button(label="删除选中")
        btn_del.connect("clicked", self._on_profile_delete)
        hb_ops.pack_start(btn_del, False, False, 0)
        vb.pack_start(hb_ops, False, False, 0)

        frame.add(vb)
        box.pack_start(frame, True, True, 0)

        frame_pb = Gtk.Frame(label="电源联动（拔插电自动应用档案）")
        vb_pb = Gtk.Box(spacing=8)
        vb_pb.set_margin_start(12)
        vb_pb.set_margin_end(12)
        vb_pb.set_margin_top(8)
        vb_pb.set_margin_bottom(8)
        grid_pb = Gtk.Grid(column_spacing=8, row_spacing=6)
        grid_pb.attach(Gtk.Label(label="插电 (AC):", xalign=1), 0, 0, 1, 1)
        self.combo_ac = Gtk.ComboBoxText()
        self.combo_ac.append("", "不切换")
        grid_pb.attach(self.combo_ac, 1, 0, 1, 1)
        grid_pb.attach(Gtk.Label(label="电池 (BAT):", xalign=1), 0, 1, 1, 1)
        self.combo_bat = Gtk.ComboBoxText()
        self.combo_bat.append("", "不切换")
        grid_pb.attach(self.combo_bat, 1, 1, 1, 1)
        btn_pb = Gtk.Button(label="保存绑定")
        btn_pb.connect("clicked", self._on_binding_save)
        grid_pb.attach(btn_pb, 1, 2, 1, 1)
        vb_pb.pack_start(grid_pb, False, False, 0)
        frame_pb.add(vb_pb)
        box.pack_start(frame_pb, False, False, 0)

        # 续航统计分析
        frame_bs = Gtk.Frame(label="续航统计分析（按电源模式对比放电速率）")
        vb_bs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vb_bs.set_margin_start(12)
        vb_bs.set_margin_end(12)
        vb_bs.set_margin_top(8)
        vb_bs.set_margin_bottom(8)

        self.bs_stats_label = Gtk.Label()
        self.bs_stats_label.set_xalign(0)
        self.bs_stats_label.set_markup("<span foreground='gray'>暂无统计数据 — 离电使用并插电后自动记录</span>")
        scroll_bs = Gtk.ScrolledWindow()
        scroll_bs.set_min_content_height(180)
        scroll_bs.add(self.bs_stats_label)
        vb_bs.pack_start(scroll_bs, True, True, 0)

        btn_bs_refresh = Gtk.Button(label="刷新统计")
        btn_bs_refresh.connect("clicked", lambda b: self._update_bs_stats())
        vb_bs.pack_start(btn_bs_refresh, False, False, 0)

        frame_bs.add(vb_bs)
        box.pack_start(frame_bs, False, False, 0)

        self._update_bs_stats()
        self._reload_profile_ui()
        return box

    def _update_bs_stats(self):
        stats, recent = bs_stats()
        if not stats:
            self.bs_stats_label.set_markup("<span foreground='gray'>暂无统计数据 — 离电使用并插电后自动记录</span>")
            return
        lines = ["<b>▎模式对比 (平均放电速率, 越低越省电)</b>"]
        for s in stats:
            rel = "" if s["reliable"] else " <span foreground='orange'>(样本不足,n≥3才可靠)</span>"
            trend = ""
            if s["trend_pct"] is not None:
                arrow = "↓改善" if s["trend_pct"] > 0 else "↑变差"
                trend = f" | 近期{arrow} {abs(s['trend_pct']):.0f}%"
            est = f" | 满电预计可用 ~{s['est_hours_to_20']:.1f}h (至20%)" if s["est_hours_to_20"] else ""
            lines.append(f"  {PROFILES.get(s['profile'], s['profile'])}: "
                         f"<b>{s['avg_rate']}%/h</b> | 最佳 {s['best_rate']} 最差 {s['worst_rate']}"
                         f"{trend}{est}{rel}\n    ({s['count']} 次 / 累计 {s['total_h']:.1f}h)")
        if len(stats) >= 2:
            best, worst = stats[0], stats[-1]
            if worst["avg_rate"] > 0:
                gain = (1 - best["avg_rate"] / worst["avg_rate"]) * 100
                lines.append(f"\n<b>▎结论: 「{PROFILES.get(best['profile'], best['profile'])}」比 "
                             f"「{PROFILES.get(worst['profile'], worst['profile'])}」省电 {gain:.0f}%</b>")
                lines.append("<span foreground='gray'>随数据积累, 对比将更精确; 建议每种模式至少积累 3 次离电会话</span>")
        lines.append("\n<b>▎最近记录</b>")
        for r in recent:
            d = r["duration_s"]
            h, mi = int(d // 3600), int(d % 3600 // 60)
            dur = f"{h}h{mi:02d}m" if h else f"{mi}m"
            lines.append(f"  {r['date']} | {PROFILES.get(r['profile'], r['profile'])} | "
                         f"{dur} | {r['cap_start']}%→{r['cap_end']}% | {r['rate_per_h']}%/h")
        self.bs_stats_label.set_markup("\n".join(lines))

    def _reload_profile_ui(self):
        for child in self.listbox_profiles.get_children():
            self.listbox_profiles.remove(child)
        for combo in (self.combo_ac, self.combo_bat):
            for _ in range(len(combo.get_model()) - 1):
                combo.remove(1)
        for name in self.cfg.get("profiles", {}):
            row = Gtk.ListBoxRow()
            row.add(Gtk.Label(label=name, xalign=0))
            row.name = name
            self.listbox_profiles.add(row)
            self.combo_ac.append_text(name)
            self.combo_bat.append_text(name)
        binding = self.cfg.get("power_binding", {})
        self.listbox_profiles.show_all()

    def _selected_profile(self):
        sel = self.listbox_profiles.get_selected_row()
        return sel.name if sel else None

    # ---- 事件处理 ----
    def _on_profile(self, rb, key):
        if rb.get_active() and not self._syncing:
            # 互斥: 切安静模式时自动关强冷
            if key == "quiet" and get_fan_boost_ec():
                set_fan_boost_ec(False)
                self._toast("强冷已自动关闭", "info")
            ok, out = set_profile(key)
            if ok:
                self._toast(f"已切换到{PROFILES[key]}模式", "success")
            else:
                self._err(out)

    def _on_charge(self, btn):
        v = int(self.charge_scale.get_value())
        ok, out = set_charge_limit(v)
        if ok:
            self._toast(f"充电阈值已设为 {v}%", "success")
        else:
            self._err(out)

    def _on_rgb(self, btn, r, g, b):
        self._stop_dynamic()
        # 颜色写入与彩虹/呼吸互斥: 先关掉动画避免 EC 覆盖
        if self.cb_rainbow.get_active() or self.cb_breathing.get_active():
            self._syncing = True
            set_rainbow(False)
            set_breathing(False)
            self.cb_rainbow.set_active(False)
            self.cb_breathing.set_active(False)
            self._syncing = False
        ok, out = set_rgb(r, g, b)
        name = PRESETS_NAMES.get((r, g, b), "")
        if ok:
            self._toast(f"颜色已设置 {name} ({r},{g},{b})".replace(" ()", ""), "success")
        else:
            self._err(out)

    def _on_custom_color(self, btn):
        self._stop_dynamic()
        if self.cb_rainbow.get_active() or self.cb_breathing.get_active():
            self._syncing = True
            set_rainbow(False)
            set_breathing(False)
            self.cb_rainbow.set_active(False)
            self.cb_breathing.set_active(False)
            self._syncing = False
        rgba = btn.get_rgba()
        r, g, b = int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
        ok, out = set_rgb(r, g, b)
        if ok:
            self._toast(f"自定义颜色 RGB({r},{g},{b})", "success")
        else:
            self._err(out)

    def _on_brightness(self, btn, lv):
        level = lv * 51  # 5档 → RGB 51/102/153/204/255 (EC 内部 /5 = Level 10/20/30/40/50 满档)
        ok, out = set_rgb(level, level, level)
        if ok:
            self._toast(f"亮度 {lv}/5", "success")
        else:
            self._err(out)

    def _on_rainbow(self, chk):
        if self._syncing:
            return
        self._stop_dynamic()
        ok, out = set_rainbow(chk.get_active())
        if ok:
            self._toast("彩虹已开启" if chk.get_active() else "彩虹已关闭", "success")
        else:
            self._err(out)

    def _on_breathing(self, chk):
        if self._syncing:
            return
        self._stop_dynamic()
        ok, out = set_breathing(chk.get_active())
        if ok:
            self._toast("呼吸已开启" if chk.get_active() else "呼吸已关闭", "success")
        else:
            self._err(out)

    def _on_battlight(self, sw, state):
        if self._syncing:
            return
        ok, out = set_battery_light(state)
        if ok:
            self._toast("电量灯已开启" if state else "电量灯已关闭", "success")
        else:
            self._err(out)

    def _on_touchpad(self, sw, state):
        if self._syncing:
            return
        ok, out = set_touchpad(state)
        if ok:
            self._toast(f"触摸板已{'开启' if state else '关闭'}", "success")
        else:
            self._err(out)

    def _on_super(self, sw, state):
        if self._syncing:
            return
        ok, out = set_super_key(state)
        if ok:
            self._toast(f"Win 键已{'开启' if state else '禁用'}", "success")
        else:
            self._err(out)

    def _on_fnlock(self, sw, state):
        if self._syncing:
            return
        ok, out = set_fn_lock(state)
        if ok:
            self._toast(f"Fn 锁已{'开启' if state else '关闭'}", "success")
        else:
            self._err(out)

    def _on_breathing_hw(self, sw, state):
        if self._syncing:
            return
        ok, out = set_breathing(state)
        if not ok:
            self._err(out)

    def _on_bluetooth(self, sw, state):
        if self._syncing:
            return
        ok, out = set_bluetooth(state)
        if ok:
            self._toast(f"蓝牙已{'开启' if state else '关闭'}", "success")
        else:
            self._err(out)

    def _on_camera(self, sw, state):
        if self._syncing:
            return
        ok, out = set_camera(state)
        if ok:
            self._toast(f"摄像头已{'开启' if state else '关闭'}", "success")
        else:
            self._err(out)

    # ---- 动态灯效 ----
    def _on_dynamic(self, rb, mode):
        if not rb.get_active() or self._syncing:
            return
        if mode == "off":
            self._stop_dynamic()
            self._toast("动态灯效已停止", "info")
        elif mode == "random":
            self._start_dynamic_random()

    def _start_dynamic_random(self):
        self._stop_dynamic()
        self.dynamic_mode = "random"
        self._dynamic_tick()
        self._toast(f"随机换色已启动 ({self.dynamic_interval}s)", "success")

    def _dynamic_tick(self):
        if self.dynamic_mode != "random":
            return False
        r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
        set_rgb(r, g, b)
        self.dynamic_timer_id = GLib.timeout_add_seconds(self.dynamic_interval, self._dynamic_tick)
        return False

    def _stop_dynamic(self):
        if self.dynamic_timer_id:
            GLib.source_remove(self.dynamic_timer_id)
            self.dynamic_timer_id = None
        self.dynamic_mode = None

    def _on_dynamic_interval(self, spin):
        self.dynamic_interval = int(spin.get_value())

    # ---- 档案事件 ----
    def _on_profile_save(self, btn):
        name = self.entry_profile_name.get_text().strip()
        if not name:
            self._toast("请输入档案名", "warning")
            return
        self.cfg.setdefault("profiles", {})[name] = snapshot_current()
        if save_config(self.cfg):
            self._reload_profile_ui()
            self._toast(f"档案「{name}」已保存", "success")
        else:
            self._err("保存失败")

    def _on_profile_apply(self, btn):
        name = self._selected_profile()
        if not name:
            self._toast("请先选中一个档案", "warning")
            return
        snap = self.cfg["profiles"].get(name)
        if not snap:
            self._err("档案不存在")
            return
        fails = apply_snapshot(snap)
        self.cfg["active"] = name
        save_config(self.cfg)
        if fails:
            self._toast(f"部分失败: {','.join(fails)}", "warning", 4000)
        else:
            self._toast(f"档案「{name}」已应用", "success")

    def _on_profile_delete(self, btn):
        name = self._selected_profile()
        if not name:
            self._toast("请先选中一个档案", "warning")
            return
        self.cfg.get("profiles", {}).pop(name, None)
        save_config(self.cfg)
        self._reload_profile_ui()
        self._toast(f"档案「{name}」已删除", "info")

    def _on_binding_save(self, btn):
        ac = self.combo_ac.get_active_text() or ""
        bat = self.combo_bat.get_active_text() or ""
        self.cfg["power_binding"] = {"ac": ac, "bat": bat}
        if save_config(self.cfg):
            self._toast("电源绑定已保存", "success")
        else:
            self._err("保存失败")

    # ---- 权限 ----
    def _on_auth(self, btn):
        """zenity 密码框获取密码 → sudo -S 刷新缓存"""
        try:
            r = subprocess.run(["zenity", "--password", "--title=蛟龙15K 控制中心 - 输入 sudo 密码"],
                               capture_output=True, text=True, timeout=120)
            pwd = r.stdout.strip()
            if not pwd:
                self.auth_status.set_markup("<b><span color='orange'>已取消</span></b>")
                return
            r2 = subprocess.run(["sudo", "-S", "-v"], input=pwd + "\n",
                                capture_output=True, text=True, timeout=15)
            if r2.returncode == 0:
                self.auth_status.set_markup("<b><span color='green'>已授权 ✓</span></b>")
                self._toast("权限已刷新 (15分钟内免密)", "success")
            else:
                self.auth_status.set_markup("<b><span color='red'>密码错误</span></b>")
        except FileNotFoundError:
            self.auth_status.set_markup("<b><span color='red'>需安装 zenity</span></b>")
        except Exception as e:
            self.auth_status.set_markup(f"<b><span color='red'>异常：{e}</span></b>")

    def _check_auth_status(self):
        try:
            r = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5)
            if r.returncode == 0:
                self.auth_status.set_markup("<b><span color='green'>已授权 ✓</span></b>")
            else:
                self.auth_status.set_markup("<b><span color='orange'>需授权</span></b>")
        except Exception:
            self.auth_status.set_markup("<b><span color='red'>检查失败</span></b>")
        return False

    def _err(self, msg):
        self._toast(str(msg)[:80], "error", 4000)

    def _toast(self, message, mtype="info", duration=2600):
        if hasattr(self, 'toast'):
            self.toast.show(message, mtype, duration)

    # ---- 状态刷新 ----
    def _refresh(self):
        try:
            self._refresh_impl()
        except Exception:
            pass  # 单次刷新失败不致命
        finally:
            self._syncing = False  # 无论异常与否必须复位, 否则全部按钮失效
        return True

    def _refresh_impl(self):
        _update_monitor_buffers()
        if hasattr(self, 'chart_temp'):
            self.chart_temp.queue_draw()
        if hasattr(self, 'chart_fan'):
            self.chart_fan.queue_draw()

        h = get_uniwill_hwmon()
        if h:
            self.val_labels["cpu"].set_markup(f"<b>{h[0]//1000}°C</b>")
            self.val_labels["gpu"].set_markup(f"<b>{h[1]//1000}°C</b>")
            # 风扇 0 RPM = 停转（低温停转策略，真实硬件状态）
            self.val_labels["fan1"].set_markup(f"<b>{h[2]} RPM</b>" if h[2] else "<b>停转</b>")
            self.val_labels["fan2"].set_markup(f"<b>{h[3]} RPM</b>" if h[3] else "<b>停转</b>")
        pw, clk = get_gpu_info()
        self.val_labels["gpupw"].set_markup(f"<b>{pw} W</b>")
        self.val_labels["gpuclock"].set_markup(f"<b>{clk} MHz</b>")
        cap, ac = get_battery()
        self.val_labels["bat"].set_markup(f"<b>{cap}% {ac}</b>")
        self.val_labels["batstatus"].set_markup(f"<b>{get_battery_status()}</b>")
        self.val_labels["batpower"].set_markup(f"<b>{get_battery_power():.1f} W</b>")
        health, cycles = get_battery_health()
        self.val_labels["bathealth"].set_markup(f"<b>{health}% (循环{cycles})</b>")
        self.val_labels["cpufreq"].set_markup(f"<b>{get_cpu_freq()} GHz</b>")
        self.val_labels["cpuusage"].set_markup(f"<b>{get_cpu_usage()}%</b>")
        self.val_labels["nvme"].set_markup(f"<b>{get_nvme_temp()}°C</b>")
        self.val_labels["mem"].set_markup(f"<b>{get_mem_usage()}%</b>")
        self.val_labels["refresh"].set_markup(f"<b>{get_refresh_rate()} Hz</b>")
        self.val_labels["cpupower"].set_markup(f"<b>{get_cpu_power():.1f} W</b>")
        # 续航会话: 检测 AC 变化并更新显示
        ac_now = _read("/sys/class/power_supply/AC0/online") == "1"
        if getattr(self, '_last_ac', None) is not None and ac_now != self._last_ac:
            bs_on_ac_change(ac_now)
            if not ac_now:
                prof = PROFILES.get(get_profile(), get_profile())
                self._toast(f"已离电 (当前: {prof}) — 开始统计续航", "info", 3500)
            else:
                d = _bs_load().get("last")
                if d:
                    h, mi = int(d["duration_s"] // 3600), int(d["duration_s"] % 3600 // 60)
                    dur = f"{h}h{mi:02d}m" if h else f"{mi}m"
                    self._toast(f"已插电 | 上次离电 {dur} 耗电 {d['used']}% ({d['rate_per_h']}%/h)", "success", 5000)
        self._last_ac = ac_now
        dur_txt, rate_txt = bs_display()
        self.val_labels["batsession"].set_markup(f"<b>{dur_txt}</b>")
        self.val_labels["disrate"].set_markup(f"<b>{rate_txt}</b>")

        # 同步 UI 状态（阻断信号防止回调风暴）
        self._syncing = True
        p = get_profile()
        if p in self.profile_btns and not self.profile_btns[p].get_active():
            self.profile_btns[p].set_active(True)
        switches = get_all_switches()
        self.cb_rainbow.set_active(switches.get("rainbow_animation") == "1")
        self.cb_breathing.set_active(switches.get("breathing_in_suspend") == "1")
        self.sw_touchpad.set_active(switches.get("touchpad_toggle_enable") == "1")
        self.sw_super.set_active(switches.get("super_key_toggle_enable") == "1")
        self.sw_fnlock.set_active(switches.get("fn_lock_toggle_enable") == "1")
        self.sw_breathing.set_active(switches.get("breathing_in_suspend") == "1")
        # 电量灯真实状态 = 轮询进程存活
        batt_on = False
        try:
            with open("/var/run/kbd-battery.pid") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # 不发信号, 仅探测进程存在
            batt_on = True
        except Exception:
            pass
        self.sw_battlight.set_active(batt_on)
        self.sw_bluetooth.set_active(get_rfkill_state("bluetooth"))
        self.sw_camera.set_active(get_camera_state())
        self._sync_tune_ui()

PRESETS_NAMES = {(r, g, b): n for n, (r, g, b) in PRESETS.items()}

# ---------- 单实例 ----------
def _single_instance_lock():
    """flock 单实例锁: 进程退出自动释放, 无陈旧 PID 残留(覆盖无 D-Bus 会话场景)"""
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "jcc.lock")
    f = open(path, "a+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        return f
    except OSError:
        f.close()
        return None


def _present_existing():
    """唤起已运行实例的窗口(经 D-Bus application_id 机制); 无会话总线时静默失败"""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "com.jcc.controlcenter", "/com/jcc/controlcenter",
            "org.freedesktop.Application", "Activate",
            GLib.Variant("(a{sv})", ({},)),
            None,
            Gio.DBusCallFlags.NONE, 3000, None,
        )
    except Exception:
        pass


if __name__ == "__main__":
    lock = _single_instance_lock()
    if lock is None:
        _present_existing()
        sys.exit(0)
    app = JCC()
    sys.exit(app.run(sys.argv))