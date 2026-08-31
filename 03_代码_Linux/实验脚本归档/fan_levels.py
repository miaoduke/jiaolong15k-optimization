import os, time
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
BASE = 0xFED50000
def rd(off): return os.pread(fd, 1, BASE+off)[0]
def wr(off, v): os.pwrite(fd, bytes([v&0xFF]), BASE+off)

print('=== 分级 PWM 测试 (每档 4 秒, 连续写) ===')
for pwm in [60, 100, 150, 200, 255, 60]:
    t0 = time.time()
    while time.time() - t0 < 4:
        wr(0x461, pwm); wr(0x469, pwm)
        time.sleep(0.05)
    r = rd(0x461)
    print(f'PWM={pwm:3d} 保持结束 回读={r}  → 请听这档声音!')
    time.sleep(1)
print('=== 完成, 已回 60 ===')
