import os, time, sys
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
BASE = 0xFED50000
def rd(off): return os.pread(fd, 1, BASE+off)[0]
def wr(off, v): os.pwrite(fd, bytes([v&0xFF]), BASE+off)

cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
if cmd == 'status':
    print('=== 当前状态 ===')
    for off in [0x43E, 0x44F, 0x460, 0x461, 0x462, 0x463, 0x464, 0x465, 0x469, 0x46A, 0x46C, 0x46D]:
        print(f'  0x{off:03X} = 0x{rd(off):02X} ({rd(off)})')
elif cmd == 'write':
    off = int(sys.argv[2], 16)
    val = int(sys.argv[3])
    old = rd(off)
    wr(off, val)
    time.sleep(1.5)
    r = rd(off)
    keep = "✓ 保持" if r == val else f"✗ 被修正为 {r}"
    print(f'写 0x{off:03X} = {val} (原值 {old}) → 回读 {r} {keep}')
elif cmd == 'restore':
    off = int(sys.argv[2], 16)
    val = int(sys.argv[3])
    wr(off, val)
    print(f'恢复 0x{off:03X} = {val} → 回读 {rd(off)}')
