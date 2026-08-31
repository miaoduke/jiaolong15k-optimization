
import json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_console as mc
app = mc.MrConsole()
try:
    app.start(); time.sleep(1.2)
    F = mc.TOPIC_FAN_CTRL
    print("救援前 CPU_PL1 =", (app.get_fan() or {}).get("CPU_PL1"))
    for key in ("PL1", "CpuPL1", "cpu_pl1"):
        app.mqtt.publish(F, json.dumps({"Action":"SET_OPERATING_MODE_DETAIL", key: 80}))
        time.sleep(2.0)
        v = (app.get_fan() or {}).get("CPU_PL1")
        print(f"尝试 wire键={key} → CPU_PL1={v}")
        if str(v) == "80":
            print("RESCUED with", key); break
    # 终态三采样
    fin = [(app.get_fan() or {}).get("CPU_PL1") for _ in range(3)]
    print("终态:", fin)
finally:
    try: app.stop()
    except Exception: pass
