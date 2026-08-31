import ctypes, os, time
libc = ctypes.CDLL(None)
libc.iopl(3)
p = os.open('/dev/port', os.O_RDWR)
def rd(port):
    os.lseek(p, port, 0); return os.read(p, 1)[0]
def wr(port, v):
    os.lseek(p, port, 0); os.write(p, bytes([v]))
while rd(0x64) & 1: rd(0x60)
wr(0x60, 0xFF)
time.sleep(0.8)
while rd(0x64) & 1: rd(0x60)
print('矩阵已复位, 请按内置键盘 3 个键 (10秒)')
t0 = time.time(); n = 0
while time.time() - t0 < 10:
    if rd(0x64) & 1:
        n += 1; d = rd(0x60)
        if n <= 12: print(f'  0x{d:02X}')
print(f'共 {n} 字节')
