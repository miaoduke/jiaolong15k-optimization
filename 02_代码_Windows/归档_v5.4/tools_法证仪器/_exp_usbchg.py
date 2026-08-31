# -*- coding: utf-8 -*-
"""USB charger probe v2: use spare client slot 9"""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_console as mc
import mr_ec_hw as ec

WATCH = [0x767, 0x768, 0x741, 0x727, 0x7A6]
def snap(tag):
    vals = {("0x%X" % a): ec.ec_read(a) for a in WATCH}
    print("  [%s] %s" % (tag, vals))
    return vals

m = mc.MiniMQTT(mc.BROKER_HOST, mc.BROKER_PORT,
                "PluginClient_9", "PluginClient_User_9", "PluginClient_Pwd<REDACTED_PWD_SALT>_9")
m.connect()
print("mqtt connected (slot 9)")
m.subscribe("#")

base = snap("baseline")
topics = ["Setting/Control", "System/Control", "BatteryProtection/Control"]
try:
    for t in topics:
        m.publish(t, json.dumps({"Action": "USB_CHARGER_ON", "ServCMD": "USB_CHARGER_ON"}))
        print("fired ->", t)
        time.sleep(2.0)
        after = snap("after " + t)
        changed = {k: (base[k], after[k]) for k in base if base[k] != after[k]}
        if changed:
            print("   *** CHANGED:", changed)
            break
    for t in topics:
        m.publish(t, json.dumps({"Action": "USB_CHARGER_OFF", "ServCMD": "USB_CHARGER_OFF"}))
    time.sleep(1.5)
    snap("after OFF restore")
finally:
    m.close()
    print("done")
