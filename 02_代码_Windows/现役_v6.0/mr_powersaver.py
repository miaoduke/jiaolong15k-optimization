# -*- coding: utf-8 -*-
"""
mr_powersaver.py - 独立AC/DC电源+刷新率自动切换器 v1.0 (2026-08-28)
不依赖控制台/MQTT，纯本地运行。

功能:
  - 监测AC/DC供电状态
  - 离电(DC): 刷新率60Hz + 切到MR-超级省电
  - 插电(AC): 刷新率165Hz + 切到MR-均衡模式
  - 自动重建丢失的MR-极限性能计划（仅启动时一次）

用法:
  python mr_powersaver.py         前台运行
  pythonw mr_powersaver.py        后台无窗口运行(推荐)
"""
import ctypes, sys, os, json, time, subprocess, re

CREATE_NO_WINDOW = 0x08000000

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if sys.stdout is not None:  # pythonw 下 stdout=None, reconfigure/print 都会崩
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import mr_win_ctrl as wc

# 固定GUID
BAL_GUID = "19ff782b-5b3b-48a2-aaa3-b9b63ce751bc"  # MR-均衡模式
ECO_GUID = "3a99624d-672a-43d3-93d6-9f78114bb9ae"   # MR-超级省电

# 场景定义: AC->165Hz+均衡, DC->60Hz+省电
SCENARIOS = {
    "AC": {"hz": 165, "plan": "MR-均衡模式", "guid": BAL_GUID},
    "DC": {"hz": 60,  "plan": "MR-超级省电", "guid": ECO_GUID},
}

_GUID_CACHE = os.path.join(HERE, "plan_guids.json")


def log(m):
    line = "[{}][{}] {}".format(time.strftime("%H:%M:%S"), os.getpid(), m)
    try:
        print(line)
    except Exception:
        pass  # pythonw 无控制台
    try:
        with open(os.path.join(HERE, "powersaver.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


class POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte), ("Reserved1", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_uint32), ("BatteryFullLifeTime", ctypes.c_uint32)]


def on_ac():
    ps = POWER_STATUS()
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)):
        return ps.ACLineStatus == 1
    return True


def active_plan_guid():
    try:
        r = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
        m = re.search(rb"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", r.stdout)
        return m.group(1).decode("ascii").lower() if m else ""
    except Exception:
        return ""


def plan_guid_by_name(name):
    """通过名称查找电源计划GUID"""
    try:
        r = subprocess.run(["powercfg", "/list"], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
        name_bytes = name.encode("gbk", errors="replace")
        for line in r.stdout.splitlines():
            if name_bytes in line:
                m = re.search(rb"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", line)
                if m:
                    return m.group(1).decode("ascii").lower()
    except Exception:
        pass
    return None


def ensure_max_perf_plan():
    """确保MR-极限性能存在，缺失则重建"""
    # 加载缓存的GUID
    cached = ""
    try:
        if os.path.exists(_GUID_CACHE):
            with open(_GUID_CACHE, "r") as f:
                cached = json.load(f).get("MR-极限性能", "")
    except Exception:
        pass

    # 检查缓存GUID是否仍存在
    if cached:
        r = subprocess.run(["powercfg", "/list"], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
        if cached.encode("ascii") in r.stdout:
            return  # 存在，无需重建

    # 缓存GUID失效，重建
    log("MR-极限性能丢失, 重建中...")
    try:
        r = subprocess.run(["powercfg", "/duplicatescheme", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
                           capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
        out = r.stdout.decode("gbk", errors="ignore") + r.stderr.decode("gbk", errors="ignore")
        m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", out)
        if m:
            g = m.group(1).lower()
            subprocess.run(["powercfg", "/changename", g, "MR-极限性能", "极限性能"], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            subprocess.run(["powercfg", "/setacvalueindex", g, "SUB_PROCESSOR", "PROCTHROTTLEMAX", "100"], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            with open(_GUID_CACHE, "w") as f:
                json.dump({"MR-极限性能": g}, f)
            log("MR-极限性能重建完成: {}".format(g))
        else:
            log("MR-极限性能重建失败: 无法提取GUID")
    except Exception as e:
        log("MR-极限性能重建失败: {!r}".format(e))


def apply(src, reason):
    sc = SCENARIOS[src]
    # 1) 刷新率
    try:
        dev = wc.find_internal_display()
        if dev:
            cur = wc.current_refresh_rate()
            if cur != sc["hz"]:
                ok, msg = wc.set_refresh_rate_on(sc["hz"], dev)
                log("refresh: {}->{} {}".format(cur, sc["hz"], msg))
    except Exception as e:
        log("refresh ERR {!r}".format(e))
    # 2) 电源计划
    try:
        g = plan_guid_by_name(sc["plan"])
        if g:
            subprocess.run(["powercfg", "/setactive", g], capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            log("plan -> {} ({})".format(sc["plan"], reason))
        else:
            log("plan '{}' GUID未找到".format(sc["plan"]))
    except Exception as e:
        log("plan ERR {!r}".format(e))


def main():
    # 启动时确保MR-极限性能存在
    ensure_max_perf_plan()

    last_src = None
    log("powersaver started (refresh+plan auto-switch, no MQTT)")
    while True:
        try:
            src = "AC" if on_ac() else "DC"
            if src != last_src:
                last_src = src
                log("power -> {} : apply".format(src))
                apply(src, "source-" + src)
        except Exception as e:
            log("ERR {!r}".format(e))
        time.sleep(3)


if __name__ == "__main__":
    main()