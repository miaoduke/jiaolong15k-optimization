# -*- coding: utf-8 -*-
import socket, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(10)
s.sendto(b"charge 80", ("127.0.0.1", 13690))
print("reply:", s.recvfrom(512)[0].decode())
time.sleep(1)
import mr_ec_hw as ec
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0")
print("regs: 7A9=%s 7B9=%s 7A8=%s" % (ec.ec_read(0x7A9), ec.ec_read(0x7B9), ec.ec_read(0x7A8)))
