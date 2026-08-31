# -*- coding: utf-8 -*-
"""MR-GHelper 联调体检: 三项功能实效验证"""
import socket, sys, time, subprocess, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec

def ask(cmd, tmo=20):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(tmo)
    s.sendto(cmd.encode(), ("127.0.0.1", 13690))
    try:
        return s.recvfrom(512)[0].decode()
    except Exception as e:
        return "FAIL %r" % e

print("=== 1. GPU温度三方对比 (EC vs nvidia-smi) ===")
for i in range(3):
    ecT = ec.get_gpu_temp()
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as e:
        out = "ERR"
    print("  t+%ds: EC 0x44C=%s  |  nvidia-smi=%s" % (i*3, ecT, out))
    time.sleep(3)

print("\n=== 2. 风扇转速 EC 实时采样 (对照GHelper显示) ===")
for i in range(3):
    r1 = ec.get_fan_rpm(); d1 = ec.get_fan_duty(); ct = ec.get_cpu_temp()
    print("  t+%ds: CPU %s°C duty %s%% rpm %s" % (i*2, ct, d1, r1))
    time.sleep(2)

print("\n=== 3. 模式切换实效: EC功耗墙实证 ===")
def pl(): return ec.get_pl_walls()
print("  切办公(0)...", ask("mode 0"))
time.sleep(12)
p0 = pl(); print("  办公档 PL:", p0)
print("  切狂暴(2)...", ask("mode 2"))
time.sleep(12)
p2 = pl(); print("  狂暴档 PL:", p2)

print("\n=== 4. 充电阈值读回 ===")
print("  阈值(start/stop):", ec.get_charge_thresholds())
