import os, time
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
BASE = 0xFED50000
def rd(off): return os.pread(fd, 1, BASE+off)[0]
def wr(off, v): os.pwrite(fd, bytes([v&0xFF]), BASE+off)

print('=== 满载 + 手动写 255 (超越 EC 的 200) 60 秒 ===')
print('时间  CPTM  PWM1  PWM2')
t0 = time.time()
while time.time() - t0 < 60:
    wr(0x461, 255); wr(0x469, 255)
    print(f'{time.time()-t0:5.0f}s  {rd(0x43E):3d}  {rd(0x461):3d}  {rd(0x469):3d}')
    time.sleep(4)
print('=== 停止写 ===')
