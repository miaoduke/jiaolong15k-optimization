# -*- coding: utf-8 -*-
import socket, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, "D:/出厂自带/蛟龙15K_7435H_优化方案_20260825/02_代码_Windows/现役_v6.0")
import mr_ec_hw as ec

def ask(msg):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(10)
    s.sendto(msg.encode(), ("127.0.0.1", 13690))
    try:
        return s.recvfrom(512)[0].decode()
    finally:
        s.close()

print("set charge 75:", ask("charge 75"))
time.sleep(1)
print("readback: 7A9=%s 7B9=%s 7A8=%s" % (ec.ec_read(0x7A9), ec.ec_read(0x7B9), ec.ec_read(0x7A8)))
print("wait 35s for guard cycle...")
time.sleep(35)
print("after guard: 7A9=%s 7B9=%s" % (ec.ec_read(0x7A9), ec.ec_read(0x7B9)))
# 恢复80
print("restore charge 80:", ask("charge 80"))
time.sleep(1)
print("final: 7A9=%s 7B9=%s" % (ec.ec_read(0x7A9), ec.ec_read(0x7B9)))
