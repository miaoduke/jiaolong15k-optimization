import os, time, sys
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
BASE = 0xFED50000
def rd(off): return os.pread(fd, 1, BASE+off)[0]
def wr(off, v): os.pwrite(fd, bytes([v&0xFF]), BASE+off)

# 连续快速写 0x461/0x469 = 200 持续 5 秒
print('连续写 0x461=200, 0x469=200 持续 5 秒... 请听风扇!')
t0 = time.time()
while time.time() - t0 < 5:
    wr(0x461, 200)
    wr(0x469, 200)
print(f'最终回读: 0x461={rd(0x461)} 0x469={rd(0x469)}')
time.sleep(2)
print(f'停止写 2 秒后: 0x461={rd(0x461)} 0x469={rd(0x469)}')
