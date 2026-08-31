# -*- coding: utf-8 -*-
import socket, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
import mr_ec_hw as ec
def ask(cmd, tmo=20):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(tmo)
    s.sendto(cmd.encode(), ("127.0.0.1", 13690))
    try: return s.recvfrom(512)[0].decode()
    except Exception as e: return "FAIL %r" % e
print("switch OFFICE...", ask("mode 0"))
time.sleep(10)
print("  PL:", ec.get_pl_walls(), " (expect pl1=65)")
print("switch TURBO...", ask("mode 2"))
time.sleep(10)
print("  PL:", ec.get_pl_walls(), " (expect pl1=80)")
print("restore TURBO state:", ec.get_pl_walls())
