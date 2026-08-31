import ctypes, os, fcntl, struct, time

UI_DEV_SETUP = 0x405c5503
UI_SET_EVBIT = 0x40045564   # _IOW('U',100,int)
UI_SET_KEYBIT = 0x40045565  # _IOW('U',101,int)
UI_DEV_CREATE = 0x5501

class UInputSetup(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint16 * 4),
        ("name", ctypes.c_char * 80),
        ("ff_effects_max", ctypes.c_uint32),
    ]

fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
setup = UInputSetup()
setup.id[0] = 0x11
setup.id[1] = 0x4D43
setup.id[2] = 0x4B42
setup.id[3] = 1
setup.name = b"Test Bridge Keyboard"
setup.ff_effects_max = 0

fcntl.ioctl(fd, UI_DEV_SETUP, setup)
fcntl.ioctl(fd, UI_SET_EVBIT, 0x01)
fcntl.ioctl(fd, UI_SET_EVBIT, 0x04)
fcntl.ioctl(fd, UI_SET_KEYBIT, 30)
fcntl.ioctl(fd, UI_SET_KEYBIT, 57)
fcntl.ioctl(fd, UI_DEV_CREATE, 0)
print("设备创建 OK")
time.sleep(1)
os.system("ls /dev/input/ | grep -i test")

class InputEvent(ctypes.Structure):
    _fields_ = [("time", ctypes.c_long * 2), ("type", ctypes.c_ushort), ("code", ctypes.c_ushort), ("value", ctypes.c_int)]
def emit(t, c, v):
    os.write(fd, bytes(InputEvent((0,0), t, c, v)))
emit(0x01, 30, 1); emit(0x00, 0, 0)   # A down
emit(0x01, 30, 0); emit(0x00, 0, 0)   # A up
print("A 键事件已注入")
time.sleep(1)
os.close(fd)
