import os, time
# 0x72/0x73 索引端口测试
# 需要 iopl(0)
os.system('python3 -c "import ctypes; libc=ctypes.CDLL(None); libc.iopl(3)"')
def wr(port, v): os.write(open(f'/dev/port','r+b',buffering=0).fileno(), b'')  # placeholder
