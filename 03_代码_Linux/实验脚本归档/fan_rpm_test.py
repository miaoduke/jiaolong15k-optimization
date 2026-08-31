import os, time
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
BASE = 0xFED50000
def rd(off): return os.pread(fd, 1, BASE+off)[0]
def wr(off, v): os.pwrite(fd, bytes([v&0xFF]), BASE+off)

print('=== 基线采样 (PWM=60, 5秒) ===')
base = []
for i in range(5):
    base.append((rd(0x465), rd(0x46D), rd(0x464), rd(0x46C), rd(0x461)))
    time.sleep(1)
print('  0x465/0x46D/0x464/0x46C 序列:', base)

print('=== 写 PWM=200, 密集采样 10 秒 ===')
t0 = time.time()
while time.time() - t0 < 10:
    wr(0x461, 200); wr(0x469, 200)
    print(f'  t={time.time()-t0:.1f}s  0x465={rd(0x465):3d} 0x46D={rd(0x46D):3d} 0x464={rd(0x464):3d} 0x46C={rd(0x46C):3d}')
    time.sleep(1)

print('=== 停止写, 恢复 60, 采样 5 秒 ===')
for i in range(5):
    print(f'  0x465={rd(0x465):3d} 0x46D={rd(0x46D):3d} 0x464={rd(0x464):3d} 0x46C={rd(0x46C):3d}')
    time.sleep(1)
