# -*- coding: utf-8 -*-
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_console as mc

m = mc.MiniMQTT(mc.BROKER_HOST, mc.BROKER_PORT,
                "PluginClient_13", "PluginClient_User_13", "PluginClient_Pwd<REDACTED_PWD_SALT>_13")
captured = []
def on_msg(topic, payload):
    try:
        txt = payload.decode("utf-8", "replace")
        if "Control" in topic or "Setting" in topic:
            captured.append((time.time(), topic, txt[:500]))
    except Exception:
        pass
m.on_message = on_msg
m.connect()
m.subscribe("#")
print("[CAPTURE] 240s. >>> OPEN 官方控制台 -> 充电限制滑条 -> 拖到70/80/90 <<<", flush=True)
t0 = time.time()
while time.time() - t0 < 240:
    time.sleep(0.4)
m.close()
print("[CAPTURE] done, %d messages:" % len(captured))
for t, topic, txt in captured:
    print("  [%s] %s : %s" % (time.strftime("%H:%M:%S", time.localtime(t)), topic, txt))