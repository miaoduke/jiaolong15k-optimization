# -*- coding: utf-8 -*-
"""复刻官方三档切换, 监控 EC 充电位变化"""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_console as mc
import mr_ec_hw as ec

def snap(tag):
    keys = [0x742, 0x7A6, 0x7A7, 0x7A8, 0x7A9, 0x7AA, 0x7AB, 0x7B9, 0x7D0, 0x7D1, 0x7C3]
    return {hex(k): ec.ec_read(k) for k in keys}

app = mc.MrConsole()
app.start()
time.sleep(2)
print("BASELINE:", snap("base"))
st = app.get_battery()
print("HP status:", st.get("HealthProtectionStatus"))

for mode in ("HEALTHYMODE", "BALANCEDMODE", "PERFORMANCEDMODE"):
    app.mqtt.publish(mc.TOPIC_BAT_CTRL, json.dumps({"Action": mode}))
    print("\n>>> sent", mode)
    for i in range(4):
        time.sleep(5)
        s = snap(mode[:5] + str(i))
        print("  t+%ds:" % ((i+1)*5), s)
app.stop()
