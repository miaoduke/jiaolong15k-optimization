# -*- coding: utf-8 -*-
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_console as mc

m = mc.MiniMQTT(mc.BROKER_HOST, mc.BROKER_PORT,
                "PluginClient_11", "PluginClient_User_11", "PluginClient_Pwd<REDACTED_PWD_SALT>_11")
captured = []
def on_msg(topic, payload):
    try:
        txt = payload.decode("utf-8", "replace")
        captured.append((time.time(), topic, txt[:400]))
    except Exception:
        pass
m.on_message = on_msg
m.connect()
m.subscribe("#")
print("[CAPTURE] 180s window. >>> OPEN 官方控制台 and CLICK a performance mode NOW <<<", flush=True)
t0 = time.time()
last_control = 0
while time.time() - t0 < 180:
    time.sleep(0.4)
    for t, tp, _ in captured:
        if "Control" in tp and t > last_control:
            last_control = t
    if last_control > 0 and time.time() - last_control > 10:
        break
print("[CAPTURE] done, %d messages:" % len(captured))
for t, topic, txt in captured:
    print("  [%s] %s : %s" % (time.strftime("%H:%M:%S", time.localtime(t)), topic, txt))
m.close()
