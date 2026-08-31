# -*- coding: utf-8 -*-
import socket, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(10)
s.sendto(b"getmode", ("127.0.0.1", 13690))
print("daemon reply:", s.recvfrom(512)[0].decode())
