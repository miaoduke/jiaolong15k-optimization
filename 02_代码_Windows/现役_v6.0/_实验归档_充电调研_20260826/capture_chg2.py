# -*- coding: utf-8 -*-
import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
sys.path.insert(0, r'D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0')
import mr_console as mc

f = open(r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0\\cap_result.txt", "w", encoding="utf-8")
m = mc.MiniMQTT(mc.BROKER_HOST, mc.BROKER_PORT,
                "PluginClient_16", "PluginClient_User_16", "PluginClient_Pwd<REDACTED_PWD_SALT>_16")
def on_msg(topic, payload):
    try:
        txt = payload.decode("utf-8", "replace")
        line = "[%s] %s : %s" % (time.strftime("%H:%M:%S"), topic, txt[:400])
        f.write(line + "\n"); f.flush()
    except Exception as e:
        pass
m.on_message = on_msg
m.connect()
m.subscribe("#")
f.write("[CAPTURE START]\n"); f.flush()
t0 = time.time()
while time.time() - t0 < 300:
    time.sleep(0.3)
m.close()
f.write("[DONE]\n"); f.close()