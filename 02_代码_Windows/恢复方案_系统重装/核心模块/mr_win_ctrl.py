#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mr_win_ctrl.py — Windows 原生电源/显示/系统控制层（纯标准库，零第三方依赖）
覆盖主文档待实现项: W4 EPP / W5 Boost / W6 MaxState / W7 刷新率(完整DEVMODE) /
W8 亮度 / W12 GPU监控(nvidia-smi解析, 免pynvml) / W15 HAGS / W19 游戏模式·GameDVR /
W18 WiFi频段优先 / 节电计划创建 / E1 GPU功耗墙(带回读验证) / AC-DC状态(W9底座)
设计: 读操作失败返回 None；写操作返回 (ok: bool, detail: str)，不弹窗不打印——展示归调用方。
"""
import ctypes
import re
import subprocess
import winreg

# ---------------- 基础 ----------------
def _run(args, timeout=12, admin=False):
    """执行命令; admin=True 时经 UAC 提权"""
    try:
        if admin:
            inner = " ".join('"{0}"'.format(a) if " " in a else a for a in args)
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Start-Process cmd -ArgumentList '/c {0} & exit' -Verb RunAs -Wait".format(inner)],
                capture_output=True, text=True, timeout=30)
            # [修复3.8] 检查实际执行结果
            if r.returncode != 0:
                return False, "UAC rejected or failed: " + (r.stderr or "")[:100]
            return True, "elevated"
        r = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, str(e)

# ---------------- powercfg 三件套: EPP / Boost / MaxState (W4/W5/W6) ----------------
POWER_PARAMS = {
    "PERFEPP":          {"cn": "EPP能效偏好",      "mn": 0,  "mx": 100},  # 0性能~100效率
    "PERFBOOSTMODE":    {"cn": "Boost加速模式",    "mn": 0,  "mx": 4},    # 0关1开2激进3高效4高效激进
    "PROCTHROTTLEMAX":  {"cn": "最大处理器状态%",  "mn": 5,  "mx": 100},
}

def powercfg_get(param):
    """读当前 AC/DC 值 → {"ac": int|None, "dc": int|None}。
    注①: EPP/BOOST 属隐藏设置, 必须 /qh 才可见(普通 /q 只回方案头)；
    注②: 输出可能是 GBK, 中文关键词会乱码 → 用编码无关法:
         块内十六进制依次为 Min/Max/Increment/AcIdx/DcIdx, 取末两位即 AC/DC"""
    ok, out = _run(["powercfg", "/qh", "SCHEME_CURRENT", "SUB_PROCESSOR", param])
    if not ok:
        return None
    hexes = re.findall(r"0x[0-9a-fA-F]+", out)
    if len(hexes) < 2:
        return None
    return {"ac": int(hexes[-2], 16), "dc": int(hexes[-1], 16)}

def powercfg_set(param, ac=None, dc=None):
    """写 AC/DC 值; 返回 (全部成功?, 明细)"""
    if param not in POWER_PARAMS:
        return False, "未知参数"
    details, okall = [], True
    for tag, val in (("setacvalueindex", ac), ("setdcvalueindex", dc)):
        if val is None:
            continue
        ok, out = _run(["powercfg", "/" + tag, "SCHEME_CURRENT",
                        "SUB_PROCESSOR", param, str(int(val))])
        okall &= ok
        details.append("{0}={1}:{2}".format(tag.replace("set", "").replace("valueindex", ""), val, "OK" if ok else "FAIL"))
    if okall:
        _run(["powercfg", "/setactive", "SCHEME_CURRENT"])  # 生效刷新
    return okall, " ".join(details)

# ---------------- 屏幕亮度 (W8, 免管理员) ----------------
def set_brightness(pct):
    ok, out = _run(["powershell", "-NoProfile", "-Command",
                    "(Get-WmiObject -Namespace root/wmi -Class "
                    "WmiMonitorBrightnessMethods).WmiSetBrightness(1,{0})".format(int(pct))])
    return ok, "亮度{0}%".format(pct)

# ---------------- 刷新率 (W7, 完整规范 DEVMODEW) ----------------
class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_ushort), ("dmDriverVersion", ctypes.c_ushort),
        ("dmSize", ctypes.c_ushort), ("dmDriverExtra", ctypes.c_ushort),
        ("dmFields", ctypes.c_uint),
        ("dmPositionX", ctypes.c_int), ("dmPositionY", ctypes.c_int),
        ("dmDisplayOrientation", ctypes.c_uint), ("dmDisplayFixedOutput", ctypes.c_uint),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_ushort), ("dmBitsPerPel", ctypes.c_uint),
        ("dmPelsWidth", ctypes.c_uint), ("dmPelsHeight", ctypes.c_uint),
        ("dmDisplayFlags", ctypes.c_uint), ("dmDisplayFrequency", ctypes.c_uint),
        ("dmICMMethod", ctypes.c_uint), ("dmICMIntent", ctypes.c_uint),
        ("dmMediaType", ctypes.c_uint), ("dmDitherType", ctypes.c_uint),
        ("dmReserved1", ctypes.c_uint), ("dmReserved2", ctypes.c_uint),
        ("dmPanningWidth", ctypes.c_uint), ("dmPanningHeight", ctypes.c_uint),
    ]

# [修复4.17] 验证DEVMODEW结构体大小
assert ctypes.sizeof(DEVMODEW) >= 156, "DEVMODEW size mismatch: {}".format(ctypes.sizeof(DEVMODEW))

DM_DISPLAYFREQUENCY = 0x00800000
ENUM_CURRENT_SETTINGS = -1
ENUM_REGISTRY_SETTINGS = -2

def _user32():
    u = ctypes.windll.user32
    u.EnumDisplaySettingsW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.POINTER(DEVMODEW)]
    u.EnumDisplaySettingsW.restype = ctypes.c_int
    u.ChangeDisplaySettingsW.argtypes = [ctypes.POINTER(DEVMODEW), ctypes.c_uint]
    u.ChangeDisplaySettingsW.restype = ctypes.c_long
    return u

def list_refresh_rates():
    """枚举【当前分辨率/色深】下全部可用刷新率(Hz), 升序去重"""
    u = _user32()
    cur = DEVMODEW(); cur.dmSize = ctypes.sizeof(DEVMODEW)
    if not u.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(cur)):
        return []
    key = (cur.dmPelsWidth, cur.dmPelsHeight, cur.dmBitsPerPel)
    rates, i = set(), 0
    while True:
        dm = DEVMODEW(); dm.dmSize = ctypes.sizeof(DEVMODEW)
        if not u.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
            break
        i += 1
        if (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmBitsPerPel) == key and dm.dmDisplayFrequency >= 40:
            rates.add(int(dm.dmDisplayFrequency))
    return sorted(rates)

def set_refresh_rate(hz):
    """以当前完整模式为基只改刷新率 → 不碰分辨率/色深(吸取 jcc.ps1 半截结构教训)"""
    u, dm = _user32(), DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    if not u.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return False, "EnumDisplaySettings 失败"
    cur = int(dm.dmDisplayFrequency)
    dm.dmFields |= DM_DISPLAYFREQUENCY
    dm.dmDisplayFrequency = int(hz)
    ret = u.ChangeDisplaySettingsW(ctypes.byref(dm), 0)   # 0=立即生效
    return ret == 0, "{0}Hz(ret={1}, 原{2}Hz)".format(hz, ret, cur)

# ---------------- 注册表开关: HAGS / 游戏模式 / GameDVR / WiFi频段 (W15/W19/W18) ----------------
def _reg_get(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return v
    except Exception:
        return None

def _reg_set(root, path, name, value, vtype=4):
    """vtype: 4=REG_DWORD。先直写；权限不足时经 UAC 提权重试(弹一次窗口)"""
    rootps = "HKLM" if root is winreg.HKEY_LOCAL_MACHINE else "HKCU"
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, vtype, int(value))
        return True, "OK"
    except PermissionError:
        full = "Registry::{0}\\{1}".format(rootps, path).replace("'", "''")
        cmd = ("New-ItemProperty -Path '{0}' -Name '{1}' -PropertyType DWord "
               "-Value {2} -Force".format(full, name, int(value)))
        ok, _ = _run(["powershell", "-NoProfile", "-Command",
                      "Start-Process powershell -Verb RunAs -Wait -ArgumentList "
                      "'-NoProfile -Command {0}'".format(cmd)])
        return ok, "elevated"
    except Exception as e:
        return False, str(e)

def hags_get():
    """硬件加速GPU计划: 2=开 1=关 None=未设置(默认关)"""
    v = _reg_get(winreg.HKEY_LOCAL_MACHINE,
                 r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode")
    return v

def hags_set(on):
    return _reg_set(winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                    "HwSchMode", 2 if on else 1)

def gamemode_get():
    return _reg_get(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AutoGameModeEnabled")

def gamemode_set(on):
    return _reg_set(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar",
                    "AutoGameModeEnabled", 1 if on else 0)

def gamedvr_set(on):
    """GameDVR 后台录制: 关闭可减少游戏后台开销"""
    return _reg_set(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore",
                    "GameDVR_Enabled", 1 if on else 0)

def wifi_adapters():
    """枚举无线网卡注册表节点 [{index, desc, band}]"""
    out, base = [], r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as bk:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(bk, i); i += 1
                except OSError:
                    break
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + "\\" + sub) as k:
                        desc, _ = winreg.QueryValueEx(k, "DriverDesc")
                        # 排除微软虚拟/诊断适配器(Wi-Fi Direct Virtual, Wi-Fi Diagnostics等)
                        if re.search(r"(microsoft|virtual|direct|diagnos|wfp)", desc, re.I) \
                                or not re.search(r"(wi-?fi|wireless|ax\d{3}| wireless)", desc, re.I):
                            continue
                        try:
                            band, _ = winreg.QueryValueEx(k, "RoamingPreferredBandType")
                        except Exception:
                            band = 0
                        out.append({"index": sub, "desc": desc, "band": int(band)})
                except Exception:
                    continue
    except Exception:
        pass
    return out

def wifi_band_prefer(index, band):
    """band: 0默认 1偏2.4G 2偏5G; 需管理员"""
    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\\" + index
    return _reg_set(winreg.HKEY_LOCAL_MACHINE, base, "RoamingPreferredBandType", band)

def power_plan_create_saver():
    """创建节电计划(幂等: 已存在则直接启用) — W17"""
    GUID_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"
    ok1, out = _run(["powercfg", "/duplicatescheme", GUID_SAVER])
    ok2, _ = _run(["powercfg", "/setactive", GUID_SAVER])
    return ok1 and ok2, out.strip()[:120]

# ---------------- nvidia-smi: 监控(W12) 与 功耗墙(E1) ----------------
def gpu_stats():
    """免pynvml的GPU监控 → dict 或 None(驱动不可用)"""
    q = ("temperature.gpu,power.draw,utilization.gpu,clocks.sm,"
         "clocks.max.sm,fan.speed,memory.used,power.limit")
    ok, out = _run(["nvidia-smi", "--query-gpu=" + q, "--format=csv,noheader,nounits"])
    if not ok or "," not in out:
        return None
    def num(x):
        try:
            return float(x.strip())
        except Exception:
            return None                      # 笔记本驱动常见 [N/A]
    vals = [num(x) for x in out.strip().splitlines()[0].split(",")]
    keys = ["temp", "power_w", "util_pct", "sm_mhz", "sm_max_mhz",
            "fan_pct", "mem_mb", "power_limit_w"]
    d = dict(zip(keys, vals))
    wall = gpu_wall_get()
    if wall:
        d.update(wall)
    return d if any(v is not None for v in vals) else None

def gpu_wall_get():
    """/q -d POWER 解析: {current, default, min, max}(W); 多卡时取第一块"""
    ok, out = _run(["nvidia-smi", "-q", "-d", "POWER"])
    if not ok:
        return None
    res = {}
    for line in out.splitlines():
        m = re.match(r"\s*(Current|Default|Min|Max) Power Limit\s*:\s*([0-9.]+)", line)
        if m and m.group(1).lower() + "_w" not in res:
            res[m.group(1).lower() + "_w"] = float(m.group(2))
    return res or None

def gpu_wall_set(watt):
    """设 GPU 功耗墙并回读验证(E1); 笔记本驱动可能拒绝 → 返回实测结果"""
    ok, out = _run(["nvidia-smi", "-pl", str(int(watt))])
    if not ok and "administrator" in (out or "").lower():
        ok, _ = _run(["nvidia-smi", "-pl", str(int(watt))], admin=True)
    w = gpu_wall_get() or {}
    cur = w.get("current_w")
    detail = "请求={0}W 回读current={1} max={2} (驱动拒绝则current不变)".format(
        watt, cur, w.get("max_w"))
    return bool(cur is not None and abs(cur - float(watt)) < 1.0), detail

# ---------------- AC/DC 电源状态 (W9 底座, 替代GUI里残缺实现) ----------------
def power_status():
    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte), ("Reserved1", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_uint), ("BatteryFullLifeTime", ctypes.c_uint)]
    sp = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sp)):
        return None
    return {"ac_online": bool(sp.ACLineStatus), "battery_pct": sp.BatteryLifePercent}

if __name__ == "__main__":
    print("list_refresh_rates:", list_refresh_rates())
    print("power_status:", power_status())
    print("gpu_stats:", gpu_stats())
    print("hags:", hags_get(), "| gamemode:", gamemode_get())
    for p in POWER_PARAMS:
        print(p, powercfg_get(p))


# ---------------- 场景引擎扩展(20260826): 内置屏识别 + 定向刷新率 ----------------
def find_internal_display():
    """活动显示器中支持>100Hz者视为内置屏; 找不到返回None"""
    import ctypes
    u = _user32()

    class DD(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_uint), ("DeviceName", ctypes.c_wchar * 32),
                    ("DeviceString", ctypes.c_wchar * 128), ("StateFlags", ctypes.c_uint),
                    ("DeviceID", ctypes.c_wchar * 128), ("DeviceKey", ctypes.c_wchar * 128)]

    active = []
    i = 0
    # [修复4.14] 安全上限防止无限循环
    while i < 32:
        d = DD(); d.cb = ctypes.sizeof(DD)
        if not u.EnumDisplayDevicesW(None, i, ctypes.byref(d), 0):
            break
        if d.StateFlags & 1:  # DISPLAY_DEVICE_ACTIVE
            active.append(d.DeviceName)
        i += 1
    for name in active:
        dm = DEVMODEW(); dm.dmSize = ctypes.sizeof(DEVMODEW)
        rates = set()
        k = 0
        while u.EnumDisplaySettingsW(name, k, ctypes.byref(dm)):
            rates.add(int(dm.dmDisplayFrequency))
            k += 1
        if any(r > 100 for r in rates):
            return name
    return None


def set_refresh_rate_on(hz, devname=None):
    """定向设备改刷新率; devname=None时退化为原主屏行为"""
    u = _user32()
    dm = DEVMODEW(); dm.dmSize = ctypes.sizeof(DEVMODEW)
    if not u.EnumDisplaySettingsW(devname, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return False, "EnumDisplaySettings failed"
    cur = int(dm.dmDisplayFrequency)
    if cur == int(hz):
        return True, "already {0}Hz".format(hz)
    dm.dmFields |= DM_DISPLAYFREQUENCY
    dm.dmDisplayFrequency = int(hz)
    ret = u.ChangeDisplaySettingsExW(devname, ctypes.byref(dm), None, 0, None)
    return ret == 0, "{0}Hz(ret={1})".format(hz, ret)


def current_refresh_rate(devname=None):
    u = _user32()
    dm = DEVMODEW(); dm.dmSize = ctypes.sizeof(DEVMODEW)
    if not u.EnumDisplaySettingsW(devname if devname else None, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return None
    return int(dm.dmDisplayFrequency)
