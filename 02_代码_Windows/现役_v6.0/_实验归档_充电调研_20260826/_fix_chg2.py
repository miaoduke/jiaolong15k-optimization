# -*- coding: utf-8 -*-
"""双管齐下: A) MQTT官方充电限制命令试射 B) blog workaround EC序列
每次动作后观察 0x742 bit2 是否被置位"""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_console as mc
import mr_ec_hw as ec

def gate():
    v = ec.ec_read(0x742)
    return bool(v & 0x04)

m = mc.MiniMQTT(mc.BROKER_HOST, mc.BROKER_PORT,
                "PluginClient_12", "PluginClient_User_12", "PluginClient_Pwd<REDACTED_PWD_SALT>_12")
m.connect()
print("mqtt ok. gate before:", gate())

# --- A: 官方命令试射 (BATTERY_CHARGINGLIMIT_SETTING / BatteryProtection topic)
tries = [
    ("BatteryProtection/Control", {"Action": "BATTERY_CHARGINGLIMIT_SETTING", "ServCMD": "BATTERY_CHARGINGLIMIT_SETTING", "Value": 80}),
    ("Setting/Control",           {"Action": "BATTERY_CHARGINGLIMIT_SETTING", "ServCMD": "BATTERY_CHARGINGLIMIT_SETTING", "Value": 80}),
    ("Fan/Control",               {"Action": "BATTERY_CHARGINGLIMIT_SETTING", "ServCMD": "BATTERY_CHARGINGLIMIT_SETTING", "Value": 80}),
]
for topic, payload in tries:
    m.publish(topic, json.dumps(payload))
    time.sleep(2.5)
    g = gate()
    print("fired %s -> gate=%s" % (topic, g))
    if g:
        print("*** GATE ENABLED by:", topic)
        break

if not gate():
    print("\n--- B: roj234 blog workaround (EC 序列) ---")
    val1 = ec.ec_read(0x07C3); print("0x7C3 =", val1)
    if val1 not in (4, 5):
        val2 = ec.ec_read(0x0770); print("0x770 =", val2)
        if val2 not in (4, 5):
            ec.ec_write(0x7C3, 4)
            time.sleep(2)
            ec.ec_write(0x7C3, val1 if val1 is not None else 0)
            time.sleep(2)
            print("after workaround: gate =", gate())
            print("0x7B9 limit =", ec.ec_read(0x7B9))
m.close()
