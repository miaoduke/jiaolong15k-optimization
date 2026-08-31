# -*- coding: utf-8 -*-
"""mr_daemon.py v2.2 - 三场景电源引擎 + MQTT断线自愈 (2026-08-27)
UDP(127.0.0.1:13690):
  perf / bal / eco      强制场景(S1带电极限/S2离电均衡/S3极限续航) + 禁用auto
  select <max|bal|eco>  切换场景但保留auto=True(供电变化时仍自动切换)
  auto                  恢复供电自动跟随
  status                JSON状态
  chgmode <0|1|2>       充电电压档(长效-50mV/标准-100mV/工作站-200mV, RMW安全实现)
  mode <0..3> / curve / boost / usb / getmode   兼容旧协议
v2.2修复:
  - plan_watcher: 检测控制面板手动切换, 自动同步daemon场景
  - watchdog: auto=False时跳过模式检查, 尊重用户手动选择
  - MR-极限性能GUID文件缓存, 避免重复创建
  - active_plan_guid/plan_guid_by_name 修复GBK编码
"""
import socket, sys, os, json, threading, time, subprocess, ctypes, random, signal, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import mr_console as mc
import mr_ec_hw as hw
import mr_win_ctrl as wc

# ---- ClientId槽位(合法域1-10实测; 守护专用7, 被踢则轮换) ----
CANDIDATE_SLOTS = [7, 3, 4, 2, 6, 8]
SLOT_IDX = 0
SLOT = CANDIDATE_SLOTS[0]


def _apply_slot(slot):
    mc.CLIENT_SLOT = slot
    mc.CID = "PluginClient_{}".format(slot)
    mc.USERNAME = "PluginClient_User_{}".format(slot)
    mc.PASSWORD = "PluginClient_Pwd<REDACTED_PWD_SALT>_{}".format(slot)


_apply_slot(SLOT)

SCENARIOS = {
    "max": {"mode": "turbo",  "plan": "MR-极限性能",  "hz": 165, "pl": (80, 80, 100)},
    "bal": {"mode": "gaming", "plan": "MR-均衡模式", "hz": 165, "pl": (65, 65, 100)},
    "eco": {"mode": "office", "plan": "MR-超级省电",  "hz": 60,  "pl": (35, 35, 100)},
}
MODE_VALUE = {"office": 0, "gaming": 1, "turbo": 2, "custom": 3}

state = {"scenario": None, "auto": True, "last_source": None,
         "gen": 0, "last_apply": 0.0}
lock = threading.Lock()
LAST_MSG = time.time()


LOGF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daemon_v21.log")


def log(m):
    line = "[{}][{}] {}".format(time.strftime("%H:%M:%S"), os.getpid(), m)
    print(line)
    try:
        # [修复4.5] 日志轮转: >1MB时备份
        if os.path.exists(LOGF) and os.path.getsize(LOGF) > 1_000_000:
            bak = LOGF + ".bak"
            try:
                if os.path.exists(bak):
                    os.remove(bak)
                os.rename(LOGF, bak)
            except OSError:
                pass
        with open(LOGF, "a", encoding="utf-8") as f:
            f.write(line + chr(10))
    except OSError:
        pass


# ---------------- MQTT ----------------
mcc = None


def _new_console():
    c = mc.MrConsole(log_fn=lambda m: None)
    c.start()
    return c


def _connect():
    """轮换候选槽位直到CONNACK通过"""
    global mcc, SLOT, SLOT_IDX
    tries = 0
    while tries < len(CANDIDATE_SLOTS):
        s = CANDIDATE_SLOTS[SLOT_IDX % len(CANDIDATE_SLOTS)]
        _apply_slot(s)
        try:
            mcc = _new_console()
            global LAST_MSG
            LAST_MSG = time.time()
            orig = mcc._on_message

            def wrapped(topic, payload):
                global LAST_MSG
                LAST_MSG = time.time()
                orig(topic, payload)
            mcc._on_message = wrapped
            SLOT = s
            log("mqtt ready (slot {})".format(s))
            return True
        except Exception as e:
            log("mqtt FAIL slot {} {!r}".format(s, e))
            SLOT_IDX += 1
            tries += 1
            time.sleep(1)
    return False


def _reconnect(reason):
    global SLOT_IDX
    log("mqtt reconnect ({})".format(reason))
    try:
        mcc.stop()
    except Exception:
        pass
    SLOT_IDX = (SLOT_IDX + 1) % len(CANDIDATE_SLOTS)
    time.sleep(2)
    _connect()
    time.sleep(2)
    # [修复5.6] 重连后立即重申当前场景
    if state.get("scenario"):
        try:
            apply_scenario(state["scenario"], "reconnect")
        except Exception:
            pass


threading.Thread(target=_connect, daemon=True).start()


# ---------------- 工具 ----------------
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
        r = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, timeout=10)
        m = re.search(rb"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", r.stdout)
        return m.group(1).decode("ascii").lower() if m else ""
    except Exception:
        return ""


PLAN_GUIDS = {
    # 硬编码基础GUID (MR-均衡模式/MR-超级省电固定)
    "MR-均衡模式": "19ff782b-5b3b-48a2-aaa3-b9b63ce751bc",
    "MR-超级省电": "3a99624d-672a-43d3-93d6-9f78114bb9ae",
}
# MR-极限性能GUID从文件缓存加载 (每次duplicatescheme生成不同GUID)
_GUID_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan_guids.json")
try:
    if os.path.exists(_GUID_CACHE):
        with open(_GUID_CACHE, "r") as f:
            _cached = json.load(f)
        if "MR-极限性能" in _cached:
            PLAN_GUIDS["MR-极限性能"] = _cached["MR-极限性能"]
except Exception:
    pass
if "MR-极限性能" not in PLAN_GUIDS:
    PLAN_GUIDS["MR-极限性能"] = ""  # 启动时动态创建


def plan_guid_by_name(name):
    key = name.lower()
    if key in PLAN_GUIDS:
        return PLAN_GUIDS[key]
    if name in PLAN_GUIDS:
        return PLAN_GUIDS[name]
    try:
        r = subprocess.run(["powercfg", "/list"], capture_output=True, timeout=10)
        name_bytes = name.encode("gbk", errors="replace")
        for line in r.stdout.splitlines():
            if name_bytes in line:
                m = re.search(rb"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", line)
                if m:
                    PLAN_GUIDS[name] = m.group(1).decode("ascii").lower()
                    return PLAN_GUIDS[name]
    except Exception:
        pass
    return None


def set_refresh_safe(hz):
    try:
        dev = wc.find_internal_display()
        if not dev:
            log("refresh: 内置屏不在活动列表, 跳过")
            return
        ok, msg = wc.set_refresh_rate_on(hz, dev)
        log("refresh: {} -> {}".format(dev, msg))
    except Exception as e:
        log("refresh ERR {!r}".format(e))


def _mqtt_alive():
    try:
        return (time.time() - mcc.mqtt.last_recv) < 150
    except Exception:
        return (time.time() - LAST_MSG) < 150


# ---------------- 场景应用(带回验重试) ----------------
def apply_scenario(key, reason=""):
    sc = SCENARIOS.get(key)
    if not sc:
        return False
    with lock:
        want = MODE_VALUE[sc["mode"]]
        # 1) MQTT档位(带验证重试)
        for attempt in (1, 2):
            if not _mqtt_alive():
                _reconnect("dead-before-mode")
            try:
                mcc.set_mode(sc["mode"])
            except Exception as e:
                log("set_mode ERR {!r}".format(e))
                _reconnect("exception")
                continue
            time.sleep(3)
            try:
                got = (mcc.get_fan() or {}).get("OperatingMode")
            except Exception:
                got = None
            try:
                got_i = int(str(got))
            except Exception:
                got_i = None
            if got_i == want:
                log("mqtt mode -> {} (verified)".format(sc["mode"]))
                try:
                    for f, v in (("CPU_PL1", sc["pl"][0]), ("CPU_PL2", sc["pl"][1]), ("CPU_PL4", sc["pl"][2])):
                        mcc.set_field("Fan/Control", f, v)
                    time.sleep(1)
                    st2 = mcc.get_fan() or {}
                    log("PL -> want {}/{}/{} srv {}/{}/{}".format(
                        sc["pl"][0], sc["pl"][1], sc["pl"][2],
                        st2.get("CPU_PL1"), st2.get("CPU_PL2"), st2.get("CPU_PL4")))
                except Exception as e:
                    log("PL ERR {!r}".format(e))
                break
            log("mode verify fail (got={}, want={}) attempt{}".format(got, want, attempt))
            if not _mqtt_alive():
                _reconnect("dead-after-verify")
        else:
            log("WARN: mode 未收敛到 {}, 保持监控".format(want))
        # 2) Windows计划 (watchdog不动, 允许用户在控制面板手动选)
        if reason != "watchdog":
            g = plan_guid_by_name(sc["plan"])
            if g:
                subprocess.run(["powercfg", "/setactive", g], capture_output=True, timeout=10)
                log("plan -> {}".format(sc["plan"]))
            else:
                log("plan '{}' GUID未找到".format(sc["plan"]))
        # 3) 刷新率
        threading.Thread(target=set_refresh_safe, args=(sc["hz"],), daemon=True).start()
        state["scenario"] = key
        state["gen"] = state.get("gen", 0) + 1
        state["last_apply"] = time.time()
        log("scenario APPLIED [{}] ({}) gen={}".format(key, reason, state["gen"]))
    return True


# ---------------- 看门狗 ----------------
# 反向映射: 计划名 -> 场景名
PLAN_TO_SCENARIO = {v["plan"]: k for k, v in SCENARIOS.items()}

def plan_watcher():
    """检测用户在控制面板手动切换电源计划, 自动同步daemon状态"""
    time.sleep(5)
    last_plan = None
    while True:
        try:
            ag = active_plan_guid()
            if ag:
                # 通过GUID查计划名
                r = subprocess.run(["powercfg", "/list"], capture_output=True, timeout=10)
                plan_name = None
                for line in r.stdout.splitlines():
                    if ag.encode("ascii") in line:
                        m = re.search(rb"\((.+?)\)", line)
                        if m:
                            plan_name = m.group(1).decode("gbk", errors="replace")
                            break
                if plan_name and plan_name != last_plan:
                    last_plan = plan_name
                    # 如果是我们的MR计划, 同步daemon场景
                    if plan_name in PLAN_TO_SCENARIO:
                        target = PLAN_TO_SCENARIO[plan_name]
                        if state["scenario"] != target:
                            log("plan_watcher: {} -> {}".format(plan_name, target))
                            state["scenario"] = target
                            state["auto"] = False  # 手动切换 = 禁用自动
                            # 同步EC功耗墙 (通过MQTT, 同apply_scenario)
                            sc = SCENARIOS[target]
                            try:
                                for f, v in (("CPU_PL1", sc["pl"][0]), ("CPU_PL2", sc["pl"][1]), ("CPU_PL4", sc["pl"][2])):
                                    mcc.set_field("Fan/Control", f, v)
                                log("plan_watcher: PL -> {}/{}/{}W".format(*sc["pl"]))
                            except Exception as e:
                                log("plan_watcher PL ERR {!r}".format(e))
        except Exception as e:
            log("plan_watcher ERR {!r}".format(e))
        time.sleep(3)


# ---------------- 看门狗 ----------------
def watchdog():
    time.sleep(15)
    while True:
        try:
            # 手动模式(auto=False): 用户通过控制面板/UDP选择, watchdog不干预
            if not state["auto"]:
                time.sleep(10)
                continue
            # 冷却期: 距上次apply不足30s -> 跳过
            if time.time() - state.get("last_apply", 0) < 30:
                time.sleep(5)
                continue
            key = state.get("scenario")
            if not key:
                time.sleep(5)
                continue
            sc = SCENARIOS[key]
            want = MODE_VALUE[sc["mode"]]
            gen0 = state.get("gen", 0)
            if not _mqtt_alive():
                _reconnect("watchdog-dead")
                time.sleep(3)
            got = None
            try:
                got = (mcc.get_fan() or {}).get("OperatingMode")
            except Exception:
                pass
            # get_fan()可能耗时10-20s, 期间可能发生新的apply
            # 必须重新检查: 代数变了? 场景变了? 任一变化都放弃本轮
            if state.get("gen", 0) != gen0 or state["scenario"] != key:
                log("watchdog: 场景在get_fan期间变更, 放弃")
                continue
            # 双重冷却: 再次确认距apply足够久
            if time.time() - state.get("last_apply", 0) < 30:
                log("watchdog: get_fan后距apply仍近, 放弃")
                continue
            # [修复] watchdog只检查MQTT模式,不检查Windows电源计划
            # 允许用户在控制面板手动切换电源计划
            try:
                mode_bad = (got is not None and int(str(got)) != want)
            except Exception:
                mode_bad = False
            if mode_bad:
                log("watchdog: mode({}/{}) -> 重申".format(got, want))
                apply_scenario(key, "watchdog")
            # 即使不需要重申, 也记录当前状态(便于诊断)
            # log("watchdog: mode({}) plan({}) ok".format(got, ag[:8] if ag else "?"))
        except Exception as e:
            log("watchdog ERR {!r}".format(e))
        time.sleep(30)
# ---------------- 供电跟随 ----------------
def power_source_loop():
    time.sleep(3)
    while True:
        try:
            src = "AC" if on_ac() else "DC"
            if src != state["last_source"]:
                state["last_source"] = src
                if state["auto"]:
                    target = "max" if src == "AC" else "bal"
                    log("power -> {} : auto {}".format(src, target))
                    apply_scenario(target, "source-" + src)
                else:
                    log("power -> {} (手动模式保持{})".format(src, state["scenario"]))
        except Exception as e:
            log("psrc ERR {!r}".format(e))
        time.sleep(3)


# ---------------- 指令 ----------------
def handle(data):
    try:
        parts = data.decode().strip().split()
        cmd = parts[0].lower()
        if cmd == "perf":
            state["auto"] = False
            apply_scenario("max", "manual"); return "OK S1"
        if cmd == "bal":
            state["auto"] = False
            apply_scenario("bal", "manual"); return "OK S2"
        if cmd == "eco":
            state["auto"] = False
            apply_scenario("eco", "manual"); return "OK S3"
        if cmd == "select":
            # select: 切场景但保留auto=True (供电变化时仍会自动切换)
            if len(parts) < 2:
                return "ERR need: select <max|bal|eco>"
            target = parts[1].lower()
            if target not in SCENARIOS:
                return "ERR bad target (need max/bal/eco)"
            apply_scenario(target, "select")
            return "OK select({})".format(target)
        if cmd == "auto":
            state["auto"] = True
            src = "AC" if on_ac() else "DC"
            apply_scenario("max" if src == "AC" else "bal", "auto-resume")
            return "OK auto({})".format(src)
        if cmd == "status":
            return json.dumps({"scenario": state["scenario"], "auto": state["auto"],
                               "on_ac": on_ac(), "slot": SLOT,
                               "mqtt_age_s": int(time.time() - LAST_MSG)})
        if cmd == "chgmode":
            mv = int(parts[1])
            if mv not in (0, 1, 2):
                return "ERR bad mv (need 0/1/2)"
            cur = hw.ec_read(0x7A6)
            val = (cur & 0xC7) | 0x08 | (mv << 4)
            hw.ec_write(0x7A6, val)
            back = hw.ec_read(0x7A6)
            ok = ((back >> 4) & 0b11) == mv
            log("chgmode {} -> {:#04x} back {:#04x}".format(mv, val, back))
            return "OK" if ok else "WARN"
        if cmd == "mode":
            t = int(parts[1])
            key = {0: "office", 1: "gaming", 2: "turbo", 3: "custom"}.get(t)
            if key is None:
                return "ERR bad mode"
            threading.Thread(target=lambda: _safe_mode(key), daemon=True).start()
            return "OK(mode {})".format(key)
        if cmd == "getmode":
            try:
                return str((mcc.get_fan() or {}).get("OperatingMode", "-"))
            except Exception:
                return "-"
        if cmd == "curve":
            mcc.set_fan_curve(parts[1].upper(), [int(x) for x in parts[2].split(",")])
            return "OK"
        if cmd == "boost":
            mcc.set_fan_boost(parts[1].lower() == "on"); return "OK"
        if cmd == "usb":
            act = "USB_CHARGER_ON" if parts[1].lower() == "on" else "USB_CHARGER_OFF"
            mcc.mqtt.publish("Setting/Control", json.dumps({"Action": act, "ServCMD": act}))
            return "OK"
        return "ERR unknown"
    except Exception as e:
        return "ERR %r" % e


def _safe_mode(key):
    try:
        mcc.set_mode(key)
    except Exception as e:
        log("safe_mode ERR {!r}".format(e))


# [修复5.2] graceful shutdown
_shutdown = False

def _on_signal(sig, frame):
    global _shutdown
    log("shutdown signal received")
    _shutdown = True
    try:
        mcc.stop()
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)

# ---------------- 启动 ----------------
print("[daemon] v2.1 scenario engine")
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SIO_UDP_CONNRESET = 0x9800000C
_b = ctypes.c_uint32(0); _n = ctypes.c_uint32()
ctypes.windll.ws2_32.WSAIoctl(s.fileno(), SIO_UDP_CONNRESET,
                              ctypes.byref(_b), 4, None, 0, ctypes.byref(_n), None, None)
s.bind(("127.0.0.1", 13690))
log("udp 13690 listening")

# 启动时检查并重建丢失的MR-极限性能计划
try:
    r = subprocess.run(["powercfg", "/list"], capture_output=True, timeout=10)
    if PLAN_GUIDS["MR-极限性能"].encode() not in r.stdout:
        log("MR-极限性能丢失, 重建中...")
        r2 = subprocess.run(["powercfg", "/duplicatescheme", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
                           capture_output=True, timeout=10)
        m = re.search(rb"([0-9a-fA-F-]{36})", r2.stdout)
        if m:
            g = m.group(1).decode()
            subprocess.run(["powercfg", "/changename", g, "MR-极限性能"], timeout=10)
            subprocess.run(["powercfg", "/setacvalueindex", g, "SUB_PROCESSOR", "PROCTHROTTLEMAX", "100"], timeout=10)
            subprocess.run(["powercfg", "/setactive", g], timeout=10)
            PLAN_GUIDS["MR-极限性能"] = g
            # 保存到缓存文件
            try:
                with open(_GUID_CACHE, "w") as f:
                    json.dump({"MR-极限性能": g}, f)
            except Exception:
                pass
            log("MR-极限性能重建完成: {}".format(g))
except Exception as e:
    log("MR-极限性能重建失败: {!r}".format(e))

time.sleep(4)  # 等MQTT首连
if state["scenario"] is None:
    src = "AC" if on_ac() else "DC"
    state["last_source"] = src
    apply_scenario("max" if src == "AC" else "bal", "boot")

threading.Thread(target=watchdog, daemon=True).start()
threading.Thread(target=power_source_loop, daemon=True).start()
threading.Thread(target=plan_watcher, daemon=True).start()

while True:
    try:
        data, addr = s.recvfrom(4096)
    except OSError as e:
        print("[daemon] recv err:", e)
        continue
    resp = handle(data).encode()
    try:
        s.sendto(resp, addr)
    except OSError as e:
        print("[daemon] send err:", e)
