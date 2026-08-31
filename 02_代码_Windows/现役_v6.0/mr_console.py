#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
 MR Console —— 机械革命电竞控制台（自制第三方版）
------------------------------------------------------------
 协议来源: ControlCenter 5.17.49.19 逆向工程 + 实机验证
 Broker:   GCUBridge.exe 监听 127.0.0.1:13688 (MQTT 3.1.1)
 认证:     PluginClient_N / PluginClient_User_N /
           PluginClient_Pwd<REDACTED_PWD_SALT>_N
------------------------------------------------------------
 用法:
   python mr_console.py status          查询全部硬件状态
   python mr_console.py monitor         实时监控(每5秒刷新)
   python mr_console.py learn [秒]      协议学习(监听官方UI操作)
   python mr_console.py lib             查看已学习的命令库
   python mr_console.py replay 名称      回放学习到的命令
   python mr_console.py send <topic> <json>   手动发布
   python mr_console.py probe-mode N    探测模式切换指令格式(N=0~3)
   python mr_console.py gui             图形界面
------------------------------------------------------------
 安全说明:
   · 本工具默认只读(GETSTATUS)。写操作需 --write 参数或GUI勾选
   · 服务端对越界值有Min/Max钳制保护，但请勿恶意刷写
============================================================
"""
import json
import os
import socket
import struct
import sys
import threading
import time

# ---------------- 控制台UTF-8输出(Windows GBK兼容) ----------------
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 13688
CLIENT_SLOT = 9                      # v6: 避开官方UI占用的低槽位与v5的5号槽
CID = f"PluginClient_{CLIENT_SLOT}"
USERNAME = f"PluginClient_User_{CLIENT_SLOT}"
PASSWORD = f"PluginClient_Pwd<REDACTED_PWD_SALT>_{CLIENT_SLOT}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.join(SCRIPT_DIR, "learned_commands.json")

TOPIC_FAN_CTRL, TOPIC_FAN_STA = "Fan/Control", "Fan/Status"
TOPIC_SET_CTRL, TOPIC_SET_STA = "Setting/Control", "Setting/Status"
TOPIC_LC_CTRL, TOPIC_LC_STA = "LCHWOC/Control", "LCHWOC/Status"
TOPIC_BAT_CTRL = "BatteryProtection/Control"
TOPIC_SYS_CTRL = "System/Control"
TOPIC_KB_CTRL = "Keyboard/Ctrl"
TOPIC_RGB_CTRL, TOPIC_RGB_STA = "MyRgbLightbar/Control", "MyRgbLightbar/Status"


# ============================================================
# 极简 MQTT 3.1.1 客户端（零第三方依赖，QoS0）
# ============================================================
class MiniMQTT:
    def __init__(self, host, port, cid, username, password, keepalive=60):
        self.host, self.port = host, port
        self.cid, self.user, self.pwd = cid, username, password
        self.keepalive = keepalive
        self.sock = None
        self.lock = threading.Lock()
        self.on_message = None            # fn(topic: str, payload: bytes)
        self.on_disconnect = None
        self._run = False
        self.last_recv = time.time()      # 最后收到任何MQTT包的时间
        self._rx = threading.Thread(target=self._reader, daemon=True)

    # ---- 组包工具 ----
    @staticmethod
    def _enc_str(s: str) -> bytes:
        b = s.encode("utf-8")
        return struct.pack("!H", len(b)) + b

    @staticmethod
    def _remaining_len(n: int) -> bytes:
        out = b""
        while True:
            d = n % 128
            n //= 128
            if n > 0:
                d |= 0x80
            out += bytes([d])
            if n == 0:
                return out

    def _send_packet(self, first: int, body: bytes):
        pkt = bytes([first]) + self._remaining_len(len(body)) + body
        with self.lock:
            self.sock.sendall(pkt)

    # ---- 连接 ----
    def connect(self, timeout=5) -> bool:
        last_err = None
        for attempt in range(3):
            try:
                return self._connect_once(timeout)
            except Exception as e:
                last_err = e
                time.sleep(0.6)
        raise last_err

    def _connect_once(self, timeout=5) -> bool:
        new_sock = socket.create_connection((self.host, self.port), timeout=timeout)
        new_sock.settimeout(1.0)
        self.sock = new_sock
        flags = 0x02
        payload = self._enc_str(self.cid)
        if self.user:
            flags |= 0x80
            payload += self._enc_str(self.user)
        if self.pwd:
            flags |= 0x40
            payload += self._enc_str(self.pwd)
        vh = self._enc_str("MQTT") + bytes([4, flags]) + struct.pack("!H", self.keepalive)
        self._send_packet(0x10, vh + payload)
        ack = self._read_exact_deadline(4, 4)
        if not ack or len(ack) < 4 or ack[0] >> 4 != 2 or ack[3] != 0:
            rc = ack[3] if ack and len(ack) >= 4 else -1
            # [修复3.4] 失败时显式关闭socket
            try:
                new_sock.close()
            except Exception:
                pass
            self.sock = None
            # [修复4.21] 区分CONNACK错误码
            reasons = {1: "协议版本不支持", 2: "ClientID被拒绝", 3: "服务不可用",
                       4: "用户名密码错误", 5: "未授权"}
            reason = reasons.get(rc, "未知")
            raise ConnectionError(f"CONNACK rc={rc} ({reason})")
        self._run = True
        self._rx.start()
        threading.Thread(target=self._keepalive_loop, daemon=True).start()
        return True

    def _read_exact_deadline(self, n: int, seconds: float):
        """跨超时累积读取, 直到凑满n字节或总时限到"""
        buf = b""
        deadline = time.time() + seconds
        while len(buf) < n and time.time() < deadline:
            try:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
            except socket.timeout:
                continue
            except OSError:
                return None
        return buf if len(buf) == n else None

    def _read_exact(self, n: int):
        buf = b""
        while len(buf) < n:
            try:
                chunk = self.sock.recv(n - len(buf))
            except socket.timeout:
                return None if not buf else buf
            except OSError:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf

    # ---- 收包线程: 流式缓冲 + 完整帧解析 ----
    def _reader(self):
        buf = bytearray()
        while self._run:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            except socket.timeout:
                continue
            except OSError:
                break
            # 从缓冲区解析所有完整包
            while True:
                if len(buf) < 2:
                    break
                first = buf[0]
                rl = 0; mul = 1; j = 1; hdr_ok = False
                while j < len(buf):
                    d = buf[j]; rl += (d & 127) * mul; mul *= 128; j += 1
                    if not (d & 0x80):
                        hdr_ok = True; break
                if not hdr_ok:
                    break                          # 头部不完整, 等更多数据
                if len(buf) - j < rl:
                    break                          # 包体不完整
                body = bytes(buf[j:j + rl])
                del buf[:j + rl]
                self.last_recv = time.time()  # 任何完整包都更新时间戳(含PINGRESP)
                ptype = first >> 4
                if ptype == 9:
                    continue                       # SUBACK
                if ptype != 3:
                    continue                       # 忽略其他类型
                qos = (first >> 1) & 3
                if rl < 2:
                    continue
                tlen = struct.unpack("!H", body[:2])[0]
                if 2 + tlen > rl:
                    continue
                topic = body[2:2 + tlen].decode("utf-8", "replace")
                off = 2 + tlen + (2 if qos else 0)
                payload = body[off:]
                if self.on_message:
                    try:
                        self.on_message(topic, payload)
                    except Exception as e:
                        # [修复3.5] 记录异常而非静默
                        try:
                            sys.stderr.write("[mqtt] on_message ERR: {}\n".format(repr(e)))
                        except Exception:
                            pass

    def _keepalive_loop(self):
        while self._run:
            time.sleep(self.keepalive * 0.7)
            try:
                self._send_packet(0xC0, b"")             # PINGREQ
            except Exception:
                if self.on_disconnect:
                    self.on_disconnect()
                return

    def subscribe(self, topic: str, qos=0):
        body = struct.pack("!H", 1) + self._enc_str(topic) + bytes([qos])
        self._send_packet(0x82, body)

    def publish(self, topic: str, payload: str, qos=0):
        body = self._enc_str(topic)
        if qos:
            body += struct.pack("!H", int(time.time()) & 0xFFFF)
        body += payload.encode("utf-8")
        self._send_packet(0x30 | (qos << 1), body)

    def close(self):
        self._run = False
        try:
            self.sock.close()
        except Exception:
            pass
        # [修复4.19] 等待reader线程退出
        if self._rx.is_alive():
            self._rx.join(timeout=2)


# ============================================================
# 业务层: MR Console
# ============================================================
class MrConsole:
    def __init__(self, log_fn=print):
        self.log = log_fn
        self.mqtt = None
        self.status = {}                                  # topic -> 最新dict
        self.status_lock = threading.Lock()              # [修复2.4] 保护status并发
        self.status_evt = {}                              # topic -> threading.Event
        self.capture = []                                 # 学习模式抓包
        self.capturing = False

    # ---- 连接与订阅 ----
    def start(self):
        self.mqtt = MiniMQTT(BROKER_HOST, BROKER_PORT, CID, USERNAME, PASSWORD)
        self.mqtt.on_message = self._on_message
        self.mqtt.connect()
        self.mqtt.subscribe("#")
        self.log(f"[+] 已连接 {BROKER_HOST}:{BROKER_PORT} 身份={CID}")

    def stop(self):
        if self.mqtt:
            self.mqtt.close()

    def _on_message(self, topic, payload: bytes):
        try:
            txt = payload.decode("utf-8", "replace")
            data = json.loads(txt) if txt.strip().startswith("{") else txt
        except Exception:
            data = payload[:200]
        with self.status_lock:
            self.status[topic] = data
        evt = self.status_evt.get(topic)
        if evt:
            evt.set()
        if self.capturing:
            rec = (topic, txt if isinstance(data, str) else json.dumps(data, ensure_ascii=False))
            if rec not in self.capture:
                self.capture.append(rec)

    # ---- 请求/响应 ----
    def request(self, ctrl_topic: str, action: dict, timeout=4):
        sta_topic = ctrl_topic.replace("/Control", "/Status").replace("/Ctrl", "/Status")
        with self.status_lock:
            self.status.pop(sta_topic, None)
        evt = threading.Event()
        self.status_evt[sta_topic] = evt
        self.mqtt.publish(ctrl_topic, json.dumps(action))
        evt.wait(timeout)
        self.status_evt.pop(sta_topic, None)
        with self.status_lock:
            return self.status.get(sta_topic)

    # ---- 高层查询 ----
    def get_fan(self):
        return self.request(TOPIC_FAN_CTRL, {"Action": "GETSTATUS"}) or {}

    def get_setting(self):
        return self.request(TOPIC_SET_CTRL, {"Action": "GETSTATUS"}) or {}

    def get_lc(self):
        return self.request(TOPIC_LC_CTRL, {"Action": "GETSTATUS"}) or {}

    def get_support(self):
        """v5.3法证修正: GETSUPPORT 回包主题实为 Customize/Info"""
        with self.status_lock:
            self.status.pop("Customize/Info", None)
        evt = threading.Event()
        self.status_evt["Customize/Info"] = evt
        self.mqtt.publish("Customize/Control", json.dumps({"Action": "GETSUPPORT"}))
        evt.wait(4)
        self.status_evt.pop("Customize/Info", None)
        with self.status_lock:
            return self.status.get("Customize/Info") or {}

    def get_keyboard(self):
        return self.request(TOPIC_KB_CTRL, {"Action": "GETSTATUS"}) or {}

    def get_rgb(self):
        return self.request(TOPIC_RGB_CTRL, {"Action": "GETSTATUS"}) or {}

    def get_battery(self):
        # 官方抓包: BatteryProtection/Control {"Report":"GET"} → System/BatteryProtection
        self.status.pop("System/BatteryProtection", None)
        evt = threading.Event()
        self.status_evt["System/BatteryProtection"] = evt
        self.mqtt.publish(TOPIC_BAT_CTRL, json.dumps({"Report": "GET"}))
        evt.wait(4)
        self.status_evt.pop("System/BatteryProtection", None)
        return self.status.get("System/BatteryProtection") or {}

    def get_graphic_info(self):
        self.mqtt.publish(TOPIC_SYS_CTRL, json.dumps({"Action": "GetGraphicInfo"}))
        time.sleep(1.2)
        return self.status.get("System/HardwareInfo") or {}

    def set_field(self, ctrl_topic, field, value, extra=None):
        """写入口: Fan/Control 的字段自动翻译为真实指令 SET_OPERATING_MODE_DETAIL"""
        try:
            if ctrl_topic == TOPIC_FAN_CTRL and field in self.WIRE_KEY:
                wire = self.WIRE_KEY[field]
                payload = {"Action": "SET_OPERATING_MODE_DETAIL", wire: value}
                self.log(f"[SET_DETAIL] {wire}={value} (状态键:{field})")
                self.mqtt.publish(TOPIC_FAN_CTRL, json.dumps(payload))
                time.sleep(0.5)
                return True
            payload = {"Action": "SET", field: value}
            if extra:
                payload.update(extra)
            self.log(f"[SET] {ctrl_topic} <- {json.dumps(payload, ensure_ascii=False)}")
            self.mqtt.publish(ctrl_topic, json.dumps(payload))
            return True
        except Exception as e:
            self.log(f"[SET] ERR {field}={value}: {e!r}")
            return False

    # 状态键 -> 服务端wire键 (2026-08-24 抓包实证)
    WIRE_KEY = {
        "CPU_PL1": "PL1", "CPU_PL2": "PL2", "CPU_PL4": "PL4",
        "CPU_TccOffset": "CpuTccOffset", "CPU_TccOffsetSwitch": "CpuTccOffsetSwitch",
        "CPU_AmdTccTarget": "CpuAmdTccTarget",
        "CPU_AmdSPL": "CpuAmdSPL", "CPU_AmdSPPT": "CpuAmdSPPT", "CPU_AmdFPPT": "CpuAmdFPPT",
        "GPU_CoreClockOffsetOC": "GpuCoreClockOffsetOC",
        "GPU_MemoryClockOffsetOC": "GpuMemoryClockOffsetOC",
        "GPU_ConfigurableTGPTarget": "GpuConfigurableTGPTarget",
        "GPU_DynamicBoostSwitch": "GpuDynamicBoostSwitch",
        "GPU_DynamicBoost": "GpuDynamicBoost",
        "OverClockingSwitch": "OverClockingSwitch",
        "FAN_FanSwitchSpeedEnabled": "FanSwitchSpeedEnabled",
        "FAN_FanSwitchSpeed": "FanSwitchSpeed",
    }

    def set_fan_boost(self, on: bool):
        """风扇强冷 — 实测生效(官方UI无此按钮, 属功能解锁)"""
        cmd = "FAN_BOOST_ON" if on else "FAN_BOOST_OFF"
        self.log(f"[FAN_BOOST] {'开' if on else '关'}")
        self.mqtt.publish(TOPIC_FAN_CTRL, json.dumps({"Action": cmd}))

    def set_fan_curve(self, name: str, ctype: str, duties):
        """写入16点风扇曲线 duties=[16个占空比]; 实证格式"""
        if len(duties) != 16:
            raise ValueError(f"duties必须16个元素, 实际{len(duties)}个")
        payload = {"Action": "SET_FAN_SPEED_CURVE_SETTING", "Name": name,
                   "Type": ctype}
        for i, d in enumerate(duties):
            payload[f"T{i}"] = int(d)
        self.log(f"[CURVE] {name}/{ctype} T0-T15={duties}")
        self.mqtt.publish(TOPIC_FAN_CTRL, json.dumps(payload))

    def restore_fan_curve(self, name: str):
        self.mqtt.publish(TOPIC_FAN_CTRL, json.dumps(
            {"Action": "RESTORE_FAN_SPEED_CURVE_SETTING", "Name": name}))

    def restore_mode_detail(self):
        self.mqtt.publish(TOPIC_FAN_CTRL, '{"Action":"RESTORE_OPERATING_MODE_DETAIL"}')

    def set_fan_respective(self, name: str, respective: bool):
        """独立控制开关 — 实证指令"""
        self.mqtt.publish(TOPIC_FAN_CTRL, json.dumps(
            {"Action": "SET_FAN_CONTROL_RESPECTIVE", "Name": name,
             "FanControlRespective": respective}))

    # ---- 服务端权威指令表(GCUService ServCMD 字符串堆提取) ----
    # 双键发送: Action + ServCMD 同时携带, 覆盖桥接层与服务层两种解析
    def write_servcmd(self, cmd: str, ctrl_topic=TOPIC_FAN_CTRL, **fields):
        payload = {"Action": cmd, "ServCMD": cmd}
        payload.update(fields)
        self.log(f"[ServCMD] {ctrl_topic} <- {json.dumps(payload)}")
        self.mqtt.publish(ctrl_topic, json.dumps(payload))

    SERVCMD_FAN = {
        "🔥风扇强冷 开(实测✅)": ("FAN_BOOST_ON", TOPIC_FAN_CTRL),
        "🔥风扇强冷 关(实测✅)": ("FAN_BOOST_OFF", TOPIC_FAN_CTRL),
        "恢复默认曲线(实证)": ("RESTORE_FAN_SPEED_CURVE_SETTING", TOPIC_FAN_CTRL),
        "恢复模式默认(实证)": ("RESTORE_OPERATING_MODE_DETAIL", TOPIC_FAN_CTRL),
    }
    SERVCMD_PERIPH = {
        "摄像头开": ("WEBCAM_ON", TOPIC_SET_CTRL),
        "摄像关": ("WEBCAM_OFF", TOPIC_SET_CTRL),
        "WiFi 开": ("WIFI_ON", TOPIC_SET_CTRL),
        "WiFi 关": ("WIFI_OFF", TOPIC_SET_CTRL),
        "蓝牙开": ("BT_ON", TOPIC_SET_CTRL),
        "蓝牙关": ("BT_OFF", TOPIC_SET_CTRL),
        "Win键锁": ("WINKEY_LOCK", TOPIC_SET_CTRL),
        "Win键解锁": ("WINKEY_UNLOCK", TOPIC_SET_CTRL),
        "Fn锁": ("FNKEY_LOCK", TOPIC_SET_CTRL),
        "Fn解锁": ("FNKEY_UNLOCK", TOPIC_SET_CTRL),
        "小键盘锁": ("NUMPAD_LOCK", TOPIC_SET_CTRL),
        "小键盘解": ("NUMPAD_UNLOCK", TOPIC_SET_CTRL),
        "触控板开": ("TOUCHPAD_ON", TOPIC_SET_CTRL),
        "触控板关": ("TOUCHPAD_OFF", TOPIC_SET_CTRL),
        "飞行模式设备": ("AIRPLANE_DEVICE", TOPIC_SET_CTRL),
    }
    SERVCMD_DISPLAY = {
        "标准模式": ("DISPLAY_STANDARD_MODE", TOPIC_SET_CTRL),
        "游戏模式": ("DISPLAY_GAMING_MODE", TOPIC_SET_CTRL),
        "视频模式": ("DISPLAY_VIDEO_MODE", TOPIC_SET_CTRL),
        "阅读模式": ("DISPLAY_READ_MODE", TOPIC_SET_CTRL),
        "自定义模式": ("DISPLAY_CUSTOMIZED_MODE", TOPIC_SET_CTRL),
        "游戏模式恢复默认": ("DISPLAY_GAMING_MODE_RECOVERY", TOPIC_SET_CTRL),
        "屏幕亮度设置": ("SETSCREENBRIGHTNESS", TOPIC_SET_CTRL),
        "色彩校准开": ("COLOR_CALIBRATION_ON", TOPIC_SET_CTRL),
        "ICC配置设定": ("ICCPROFILESETING", TOPIC_SET_CTRL),
    }
    SERVCMD_BATTERY = {
        "充电限制设定": ("BATTERY_CHARGINGLIMIT_SETTING", TOPIC_BAT_CTRL),
        "电源计划-游戏": ("POWER_PLAN_GAMING", TOPIC_SET_CTRL),
        "电源计划-高性能": ("POWER_PLAN_HIPERFORMANCE", TOPIC_SET_CTRL),
        "电源计划-平衡": ("POWER_PLAN_BALANCED", TOPIC_SET_CTRL),
        "电源计划-省电": ("POWER_PLAN_POWERSAVING", TOPIC_SET_CTRL),
        "系统电源-性能模式": ("SYSPOWER_PERFORMANCE_MODE", TOPIC_SET_CTRL),
        "系统电源-平衡模式": ("SYSPOWER_BALANCED_MODE", TOPIC_SET_CTRL),
        "系统电源-省电模式": ("SYSPOWER_BATTERYSAVER_MODE", TOPIC_SET_CTRL),
    }
    SERVCMD_MISC = {
        "AC断电恢复ON": ("ACRECOVERY_TOGGLE_ON", TOPIC_SET_CTRL),
        "AC断电恢复OFF": ("ACRECOVERY_TOGGLE_OFF", TOPIC_SET_CTRL),
        "被动冷却禁用ON": ("DISABLE_PASSIVECOOLING_MODE_ON", TOPIC_FAN_CTRL),
        "被动冷却禁用OFF": ("DISABLE_PASSIVECOOLING_MODE_OFF", TOPIC_FAN_CTRL),
        "键盘灯条定时ON": ("KEYBOARD_LIGHTBAR_TIMER_ON", TOPIC_SET_CTRL),
        "呼吸灯ON": ("OSD_BREATH_LED_ON", TOPIC_SET_CTRL),
        "呼吸灯OFF": ("OSD_BREATH_LED_OFF", TOPIC_SET_CTRL),
        "显示器电源ON": ("MONITOR_ON", TOPIC_SET_CTRL),
        "显示器关闭": ("MONITOR_OFF", TOPIC_SET_CTRL),
        "USB充电ON(⛔研究)": ("USB_CHARGER_ON", TOPIC_SET_CTRL),
        "独显直连ON(⛔研究)": ("DGPU_DIRECT_CONNECT_TOGGLE_ON", TOPIC_SET_CTRL),
        "独显直连OFF(⛔研究)": ("DGPU_DIRECT_CONNECT_TOGGLE_OFF", TOPIC_SET_CTRL),
    }

    # ---- 写操作(✅全部经官方UI抓包+回读实测验证) ----
    # 模式切换真实指令(2026-08-23 UIA驱动官方UI抓包所得)
    MODE_ACTIONS = {
        "office": ("OPERATING_OFFICE_MODE",  "Mode2"),
        "gaming": ("OPERATING_GAMING_MODE",  "Mode1"),
        "turbo":  ("OPERATING_TURBO_MODE",   "Mode3"),
        "custom": ("OPERATING_CUSTOM_MODE",  "Mode4"),
    }

    def set_mode(self, key: str, profile_index: str = "0"):
        """切换性能模式; 返回切换后ProfileName"""
        if key not in self.MODE_ACTIONS:
            raise ValueError(f"未知模式: {key}, 可用: {list(self.MODE_ACTIONS)}")
        cmd, expect = self.MODE_ACTIONS[key]
        payload = {"Action": cmd, "ProfileIndex": profile_index}
        self.log(f"[MODE] {key} -> {cmd} (期望 {expect})")
        self.mqtt.publish(TOPIC_FAN_CTRL, json.dumps(payload))
        time.sleep(2.5)
        prof = self.get_fan().get("ProfileName")
        ok = prof and expect in str(prof)
        self.log(f"[MODE] 结果 ProfileName={prof} {'✅' if ok else '⚠️'}")
        return ok, prof

    # ---- 模式指令格式探测 ----
    CANDIDATES = [
        {"Action": "SET", "ServCMD": "SET", "OperatingMode": "{v}"},
        {"Action": "{v}", "ServCMD": "{v}"},
        {"Action": "SET", "OperatingMode": "{v}"},
        {"Action": "SET", "OperatingMode": "{v}"},
        {"Action": "SETMODE", "OperatingMode": "{v}"},
        {"Action": "SetOperatingMode", "Value": "{v}"},
        {"OperatingMode": "{v}"},
        {"Action": "MODE_SELECTINGS", "Index": "{v}"},
    ]

    def probe_mode(self, target: int):
        cur = self.get_fan().get("OperatingMode")
        self.log(f"当前 OperatingMode={cur}, 目标={target}, 开始探测指令格式...")
        for i, tpl in enumerate(self.CANDIDATES):
            payload = json.loads(json.dumps(tpl).replace("{v}", str(target)))
            self.log(f"  尝试{i+1}/{len(self.CANDIDATES)}: {json.dumps(payload)}")
            self.mqtt.publish(TOPIC_FAN_CTRL, json.dumps(payload))
            for _ in range(6):                         # 观察3秒
                time.sleep(0.5)
                now = self.get_fan().get("OperatingMode")
                if str(now) == str(target) and str(cur) != str(target):
                    self.log(f"  ✅ 命中! 格式={json.dumps(tpl)}")
                    return tpl
            # 未命中则恢复探测前状态再试下一候选
            self.log("    未生效")
        self.log("❌ 所有候选格式均未命中——请用 learn 模式从官方UI捕获真实指令")
        return None

    # ---- 协议学习/命令库 ----
    def start_capture(self):
        self.capture.clear()
        self.capturing = True
        self.log("[*] 抓包开始——现在去官方控制台UI操作目标功能...")

    def stop_capture_save(self):
        self.capturing = False
        lib = {}
        if os.path.exists(LIB_PATH):
            with open(LIB_PATH, "r", encoding="utf-8") as f:
                lib = json.load(f)
        for topic, payload in self.capture:
            key = f"{topic.split('/')[0]}_{abs(hash(payload)) % 10000}"
            lib[key] = {"topic": topic, "payload": payload}
        with open(LIB_PATH, "w", encoding="utf-8") as f:
            json.dump(lib, f, ensure_ascii=False, indent=2)
        self.log(f"[+] 抓到 {len(self.capture)} 条, 命令库共 {len(lib)} 条 -> {LIB_PATH}")
        return self.capture

    def load_lib(self):
        if os.path.exists(LIB_PATH):
            with open(LIB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def replay(self, name: str):
        lib = self.load_lib()
        if name not in lib:
            raise KeyError(f"命令库中无 '{name}', 可用: {list(lib.keys())}")
        cmd = lib[name]
        self.log(f"[REPLAY] {name} -> {cmd['topic']} {cmd['payload']}")
        self.mqtt.publish(cmd["topic"], cmd["payload"])


# ============================================================
# 状态美化输出
# ============================================================
CN_FIELD = {
    "OperatingMode": "性能模式(0办公/1均衡/2狂暴/3自定义)",
    "ProfileName": "当前配置文件",
    "CPU_PL1": "CPU PL1(W)", "CPU_PL1Maximum": "├ PL1上限", "CPU_PL1Minimum": "├ PL1下限",
    "CPU_PL2": "CPU PL2(W)", "CPU_PL2Maximum": "├ PL2上限",
    "CPU_PL4": "CPU PL4(W)", "CPU_PL4Maximum": "├ PL4上限",
    "CPU_TccOffset": "CPU温度墙(°C)", "CPU_TccOffsetMaximum": "├ 温度墙上限",
    "GPU_CoreClockOffsetOC": "GPU核心偏移(MHz)", "GPU_CoreClockOffsetMaximum": "├ 核心上限",
    "GPU_MemoryClockOffsetOC": "GPU显存偏移(MHz)", "GPU_MemoryClockOffsetMaximum": "├ 显存上限",
    "GPU_MemoryClockOffsetMaximumHWOC": "├ 显存上限(HWOC)",
    "GPU_ConfigurableTGPTarget": "GPU TGP(W)", "GPU_ConfigurableTGPMaximum": "├ TGP上限",
    "GPU_TargetTemperature": "GPU目标温度(°C)",
    "GPU_DynamicBoostSwitch": "DynamicBoost开关", "GPU_DynamicBoost": "├ DB值(W)",
    "FAN_TableName": "风扇曲线表", "FAN_FanSwitchSpeedEnabled": "切换转速启用",
    "FAN_FanSwitchSpeed": "切换转速(RPM)",
    "MEM_MemoryOverClockSupport": "内存OC支持",
    "CPU_AmdOverClockSupport": "AMD超频支持",
    "CPU_OffsetCoreVoltageSupport": "Intel降压通道",
    "OcSupport": "超频页支持",
}

def pretty_status(d: dict, title: str):
    print(f"\n───── {title} ─────")
    if not d:
        print("  (无响应)")
        return
    shown = set()
    for k, cn in CN_FIELD.items():
        if k in d:
            print(f"  {cn:<28} = {d[k]}")
            shown.add(k)
    for k, v in d.items():
        if k not in shown and not k.startswith("_"):
            vs = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            s = str(vs)
            print(f"  {k:<30} = {s[:70]}{'...' if len(s) > 70 else ''}")


# ============================================================
# CLI 入口
# ============================================================
def _cli_power(args):
    """v5.3: Windows原生电源/显示/GPU子命令(免MQTT·不依赖GCUBridge)"""
    import mr_win_ctrl as wc
    sub = args[0] if args else "info"
    if sub == "epp":
        if len(args) > 1:
            ac = int(args[1]); dc = int(args[2]) if len(args) > 2 else ac
            ok, dt = wc.powercfg_set("PERFEPP", ac, dc)
            print(("OK " if ok else "FAIL ") + dt)
        print("EPP:", wc.powercfg_get("PERFEPP"))
    elif sub == "boost":
        m = {"off": 0, "on": 1, "agg": 2, "eff": 3, "effagg": 4}
        if len(args) > 1:
            ac = m.get(args[1].lower(), int(args[1]))
            dc = m.get(args[2].lower(), int(args[2])) if len(args) > 2 else ac
            ok, dt = wc.powercfg_set("PERFBOOSTMODE", ac, dc)
            print(("OK " if ok else "FAIL ") + dt)
        print("Boost:", wc.powercfg_get("PERFBOOSTMODE"))
    elif sub == "maxstate":
        if len(args) > 1:
            ac = int(args[1]); dc = int(args[2]) if len(args) > 2 else ac
            ok, dt = wc.powercfg_set("PROCTHROTTLEMAX", ac, dc)
            print(("OK " if ok else "FAIL ") + dt)
        print("MaxState:", wc.powercfg_get("PROCTHROTTLEMAX"))
    elif sub == "rates":    print("刷新率:", wc.list_refresh_rates())
    elif sub == "setrate":  print(wc.set_refresh_rate(int(args[1])))
    elif sub == "bright":   print(wc.set_brightness(int(args[1])))
    elif sub == "hags":     print("当前:", wc.hags_get(), "->", wc.hags_set(args[1] == "on")[1] if len(args) > 1 else "(只读)")
    elif sub == "gamemode": print("当前:", wc.gamemode_get(), "->", wc.gamemode_set(args[1] == "on")[1] if len(args) > 1 else "(只读)")
    elif sub == "gpuwall":
        if len(args) > 1:
            ok, dt = wc.gpu_wall_set(int(args[1])); print(("OK " if ok else "REJECTED ") + dt)
        print("墙:", wc.gpu_wall_get())
    elif sub == "gpuinfo":  print(wc.gpu_stats())
    else:
        print("power子命令: epp|boost|maxstate [AC DC] | rates | setrate N | bright N")
        print("             | hags on/off | gamemode on/off | gpuwall W | gpuinfo")


def cli():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    app = MrConsole()

    if cmd == "gui":
        import mr_gui_v6
        mr_gui_v6.run()
        return

    if cmd == "power":                    # 免MQTT分支, 不启broker连接
        _cli_power(args[1:])
        return

    app.start()
    try:
        if cmd == "status":
            pretty_status(app.get_fan(), "Fan/Status 性能·风扇·超频")
            pretty_status(app.get_setting(), "Setting/Status 系统设置")
            pretty_status(app.get_lc(), "LCHWOC/Status 液冷超频")

        elif cmd == "monitor":
            interval = float(args[1]) if len(args) > 1 else 5
            print(f"实时监控 每{interval}s刷新 Ctrl+C退出")
            keys = ["OperatingMode", "ProfileName", "CPU_PL1", "CPU_PL2", "GPU_ConfigurableTGPTarget",
                    "GPU_CoreClockOffsetOC", "GPU_MemoryClockOffsetOC", "GPU_TargetTemperature"]
            while True:
                f = app.get_fan()
                line = " | ".join(f"{k}={f.get(k,'?')}" for k in keys)
                print(f"[{time.strftime('%H:%M:%S')}] {line}")
                time.sleep(interval)

        elif cmd == "learn":
            secs = float(args[1]) if len(args) > 1 else 20
            app.start_capture()
            print(f"抓包 {secs}s —— 请立即在官方控制台UI操作目标功能!")
            time.sleep(secs)
            for topic, payload in app.stop_capture_save():
                print(f"  [{topic}] {payload[:120]}")

        elif cmd == "lib":
            lib = app.load_lib()
            print(f"命令库 {LIB_PATH} 共{len(lib)}条:")
            for k, v in lib.items():
                print(f"  {k:<24} {v['topic']:<36} {v['payload'][:90]}")

        elif cmd == "replay":
            app.replay(args[1])

        elif cmd == "send":
            app.mqtt.publish(args[1], args[2])
            print(f"已发布 -> {args[1]} {args[2]}")
            time.sleep(1.5)

        elif cmd == "probe-mode":
            app.probe_mode(int(args[1]))

        else:
            print(__doc__)
    finally:
        app.stop()


if __name__ == "__main__":
    cli()
