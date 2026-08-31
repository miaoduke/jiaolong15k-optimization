import os, time
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
BASE = 0xFED50000
def rd(off): return os.pread(fd, 1, BASE+off)[0]

print('=== 满载 90 秒观察 (EC 自控, 不写 PWM) ===')
print('时间  CPTM  VGAT  PWM1  PWM2  状态0x460  档位0x464')
t0 = time.time()
while time.time() - t0 < 90:
    print(f'{time.time()-t0:5.0f}s  {rd(0x43E):3d}  {rd(0x44F):3d}  {rd(0x461):3d}  {rd(0x469):3d}  0x{rd(0x460):02X}    {rd(0x464):3d}')
    time.sleep(5)
