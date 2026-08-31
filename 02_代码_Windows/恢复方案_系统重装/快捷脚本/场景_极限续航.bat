@echo off
python -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(3);s.sendto(b'eco',('127.0.0.1',13690));print(s.recvfrom(4096)[0].decode())"
pause

