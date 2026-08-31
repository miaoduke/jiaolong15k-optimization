# -*- coding: utf-8 -*-
import sys, time, json, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
sys.path.insert(0, r'D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0')
import mr_console as mc
def cur():
    r = subprocess.run(['powershell','-NoProfile','-Command',
        "$b=Get-CimInstance -Namespace root\\wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object -First 1; $w=Get-CimInstance Win32_Battery; Write-Host (($b.ChargeRate).ToString() + ';' + ($b.RemainingCapacity).ToString() + ';' + ($w.EstimatedChargeRemaining).ToString() + ';' + ($b.Charging).ToString())"],
        capture_output=True, text=True).stdout.strip()
    return r
app = mc.MrConsole()
app.start(); time.sleep(2)
print('t0 (current mode):', cur())
app.mqtt.publish(mc.TOPIC_BAT_CTRL, json.dumps({'Action':'PERFORMANCEDMODE'}))
print('>>> sent PERFORMANCEDMODE (工作站)')
for i in range(14):
    time.sleep(10)
    print('t+%ds:' % ((i+1)*10), cur())
app.stop()