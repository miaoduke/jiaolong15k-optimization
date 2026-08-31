# -*- coding: utf-8 -*-
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_console as mc
import mr_ec_hw as ec

app = mc.MrConsole()
app.start()
time.sleep(2)
st0 = app.get_battery()
print("BEFORE:", json.dumps(st0, ensure_ascii=False))
print("EC before: 7B9=%s 7D0=%s" % (ec.ec_read(0x7B9), ec.ec_read(0x7D0)))

# hex字符串格式 (HexStringJsonConverter)
variants = [
    {"Action": "BATTERY_CHARGINGLIMIT_SETTING", "ServCMD": "BATTERY_CHARGINGLIMIT_SETTING",
     "BatteryLimitation": "0x01", "ChargeMaximumLimit": "0x50", "ChargeMinimumLimit": "0x28"},
    {"Action": "BATTERY_CHARGINGLIMIT_SETTING", "ServCMD": "BATTERY_CHARGINGLIMIT_SETTING",
     "PowerMode": "0x02", "BatteryLimitation": "0x01", "ChargeMaximumLimit": "0x50", "ChargeMinimumLimit": "0x28"},
]
for v in variants:
    app.mqtt.publish(mc.TOPIC_BAT_CTRL, json.dumps(v))
    time.sleep(4)
    st = app.get_battery()
    print("sent:", {k: x for k, x in v.items() if k not in ("Action", "ServCMD")})
    print("  -> HP =", st.get("HealthProtectionStatus"), "| EC: 7B9=%s 7D0=%s" % (ec.ec_read(0x7B9), ec.ec_read(0x7D0)))
app.stop()
