import os, time
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
BASE = 0xFED50000
def rd(off): return os.pread(fd, 1, BASE+off)[0]
def wr(off, v): os.pwrite(fd, bytes([v&0xFF]), BASE+off)

print('=== 声音对比: 200 → 255 → 200 (各 8 秒) ===')
for pwm in [200, 255, 200]:
    t0 = time.time()
    while time.time() - t0 < 8:
        wr(0x461, pwm); wr(0x469, pwm)
        time.sleep(0.05)
    print(f'>>> PWM={pwm} 结束')
    time.sleep(1)
print('完成')
