#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mr_ec_hw.py — EC 硬件访问组合通道模块
优先级: MQTT(免管理员,状态/设置) > UWACPIDriver直读(免管理员,寄存器) > WMI(已死,仅后备)
UWACPIDriver: 官方驱动 C:/Program Files/OEM/机械革命电竞控制台/UWACPIDriver/UWACPIDriver.sys
  用户态封装 ACPIDriverDll.dll 导出 ReadEC(int addr)->int (签名已实测验证, 20260825)
  WriteEC(addr, value) 签名已于 20260825 经反汇编+零破坏NO-OP实验双重定案(报告附录D)

审计修复记录 (2026-08-26):
  [2.1] EC写入value范围校验: int(value) & 0xFF
  [2.2] ec_write返回值明确化(当前WMI固件无效仍返回False)
  [2.3] get/set_fan_boost单例模式, 避免MQTT连接风暴
  [3.7] DLL加载双重检查锁(double-checked locking)
  [4.10] _direct_read不再将恒0视为无效
  [4.11] set_kb_backlight失败时恢复原值
  [4.12] set_pl1范围校验+回滚
  [4.13] 异常记录而非静默吞掉
  [4.18] _wmi_write_ec使用白名单校验防止注入
  [5.12] _wmi_read_ec使用白名单校验
  [5.13] get_fan_rpm上限校验
  [5.14] ctypes统一顶部import
"""
import sys, os, time, json, subprocess, ctypes
import threading as _thr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# 内部日志
# ============================================================
def _log_ec(msg):
    """EC模块内部日志"""
    try:
        sys.stderr.write("[ec_hw] {}\n".format(msg))
    except Exception:
        pass

# ============================================================
# UWACPIDriver 直读 (免管理员, 首选)
# ============================================================
_DLL_PATH = "C:/Program Files/OEM/机械革命电竞控制台/UniwillService/MyControlCenter/ACPIDriverDll.dll"
_dll = None
_dll_lock = _thr.Lock()

def _load_dll():
    """加载官方 ACPIDriverDll 并绑定已验证签名 [修复3.7: 双重检查锁]"""
    global _dll
    if _dll is not None:
        return True
    with _dll_lock:
        if _dll is not None:
            return True
        if not os.path.exists(_DLL_PATH):
            return False
        _dll = ctypes.CDLL(_DLL_PATH)
        _dll.ReadEC.restype = ctypes.c_int
        _dll.ReadEC.argtypes = [ctypes.c_int]
        _dll.WriteEC.restype = None
        _dll.WriteEC.argtypes = [ctypes.c_int, ctypes.c_int]
    return True

_ADDR_MIN, _ADDR_MAX = 0x000, 0x7FF

def _addr_ok(addr):
    """客户端白名单校验"""
    try:
        a = int(addr)
        return _ADDR_MIN <= a <= _ADDR_MAX
    except Exception:
        return False

def _direct_read(addr):
    """通过官方 ACPIDriverDll.ReadEC 读 EC 寄存器 [修复4.10: 不再将0视为无效]"""
    if not _addr_ok(addr):
        return None
    try:
        if not _load_dll():
            return None
        v = _dll.ReadEC(int(addr)) & 0xFF
        return v
    except Exception as e:
        _log_ec("ReadEC(0x{:03X}) ERR: {!r}".format(int(addr), e))
        return None

def _direct_write(addr, value):
    """通过官方 ACPIDriverDll.WriteEC 写 EC 寄存器 [修复2.1: value范围校验]"""
    if not _addr_ok(addr):
        return False
    try:
        v = int(value) & 0xFF
    except Exception:
        return False
    try:
        if not _load_dll():
            return False
        _dll.WriteEC(int(addr), v)
        return True
    except Exception as e:
        _log_ec("WriteEC(0x{:03X}, {}) ERR: {!r}".format(int(addr), v, e))
        return False

# ============================================================
# WMI EC 读写 (需管理员; 当前固件下恒返0, 仅作后备)
# ============================================================
def _wmi_read_ec(addr):
    """通过 WMI AcpiTest_MULong 读取 EC 寄存器 [修复5.12: 白名单校验]"""
    if not _addr_ok(addr):
        return None
    try:
        ps = (
            "$o = Get-WmiObject -Namespace root\\wmi -Class AcpiTest_MULong | "
            "Where-Object { $_.InstanceName -eq 'ACPI\\PNP0C14\\1_0' }; "
            "if ($o) { "
            "$null = $o.GetSetULong([UInt64](0x0000010000000000 -bor [UInt64]{})); "
            "$r = $o.GetULong(); "
            "Write-Output ($r.Return -band 0xFF) "
            "}"
        ).format(int(addr) & 0xFFF)
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10
        )
        if r.stdout.strip():
            return int(r.stdout.strip())
    except Exception as e:
        _log_ec("WMI read 0x{:03X} ERR: {!r}".format(int(addr), e))
    return None

def _wmi_write_ec(addr, value):
    """通过 WMI AcpiTest_MULong 写入 EC 寄存器 [修复4.18: 白名单校验防注入]"""
    if not _addr_ok(addr):
        return
    try:
        ps = (
            "$o = Get-WmiObject -Namespace root\\wmi -Class AcpiTest_MULong | "
            "Where-Object { $_.InstanceName -eq 'ACPI\\PNP0C14\\1_0' }; "
            "if ($o) { "
            "$data = [UInt64]({} * 0x10000 + {}); "
            "$null = $o.GetSetULong($data) "
            "}"
        ).format(int(value) & 0xFF, int(addr) & 0xFFF)
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10
        )
    except Exception as e:
        _log_ec("WMI write 0x{:03X} ERR: {!r}".format(int(addr), e))

# ============================================================
# 高层 API
# ============================================================
def ec_read(addr):
    """读取 EC 寄存器: UWACPIDriver直读优先, WMI后备"""
    v = _direct_read(addr)
    return v if v is not None else _wmi_read_ec(addr)

def ec_write(addr, value):
    """写入 EC 寄存器 [修复2.2: 返回值明确化]"""
    if _direct_write(addr, value):
        return True
    _wmi_write_ec(addr, value)
    return False

def get_cpu_temp():
    """CPU 温度 (EC 0x43E)"""
    return ec_read(0x43E)

def get_gpu_temp():
    """GPU 温度 (EC 0x44C)"""
    return ec_read(0x44C)

def get_fan_duty():
    """CPU 风扇 Duty (EC 0x461, raw÷2=%)"""
    v = ec_read(0x461)
    return round(v / 2) if v is not None else None

def get_fan_rpm():
    """CPU 风扇 RPM [修复5.13: 上限校验]"""
    hi = ec_read(0x464)
    lo = ec_read(0x465)
    if lo is not None and hi is not None:
        rpm = hi * 256 + lo
        return rpm if rpm <= 10000 else None
    return None

def get_gpu_duty():
    """GPU 风扇 Duty (EC 0x469)"""
    v = ec_read(0x469)
    return round(v / 2) if v is not None else None

def get_gpu_rpm():
    """GPU 风扇 RPM"""
    hi = ec_read(0x46C)
    lo = ec_read(0x46D)
    if lo is not None and hi is not None:
        rpm = hi * 256 + lo
        return rpm if rpm <= 10000 else None
    return None

# ==== v6.0 新增 ====
def get_kb_backlight():
    """键盘背光档位 0-2 (EC 0x78C bit5-7)"""
    v = ec_read(0x78C)
    return (v >> 5) & 7 if v is not None else None

def set_kb_backlight(level):
    """背光三档 0/1/2 [修复4.11: 失败恢复]"""
    level = int(level) & 7
    v = ec_read(0x78C)
    if v is None:
        return False
    nv = (v & 0x1F) | (level << 5)
    ec_write(0x78C, nv)
    time.sleep(0.3)
    readback = (ec_read(0x78C) >> 5) & 7
    if readback == level:
        return True
    ec_write(0x78C, v)
    time.sleep(0.3)
    return False

def get_pl_walls():
    """CPU 功耗墙 PL1/PL2/PL4"""
    a, b, c = ec_read(0x783), ec_read(0x784), ec_read(0x785)
    if None in (a, b, c):
        return None
    return {"pl1": a, "pl2": b, "pl4": c}

def set_pl1(w):
    """写 PL1 瓦数 [修复4.12: 范围校验+回滚]"""
    w = int(w)
    if not (5 <= w <= 120):
        return False
    o = ec_read(0x783)
    if o is None:
        return False
    ec_write(0x783, w)
    time.sleep(0.5)
    readback = ec_read(0x783)
    if readback == w:
        return True
    ec_write(0x783, o)
    time.sleep(0.3)
    return False

def get_charge_thresholds():
    """读取充电阈值对 (0x7D0=起始% / 0x7B9=停止%)。
    本机EC固件未实现软件限充, 仅为协议参考。"""
    start = ec_read(0x7D0)
    stop = ec_read(0x7B9)
    if start is None or stop is None:
        return None
    return {"start": start, "stop": stop}

def get_charge_limit():
    """读取充电阈值 (EC 0x7B9)"""
    t = get_charge_thresholds()
    return t["stop"] if t else None

def set_charge_limit(percent):
    """设置充电停止阈值 (EC 0x7B9)。本机固件不支持。"""
    if percent < 60 or percent > 100:
        return False
    cur = get_charge_thresholds()
    if not cur:
        return False
    if not _direct_write(0x7B9, percent):
        return False
    time.sleep(0.5)
    now = get_charge_thresholds()
    if now and now.get("stop") == percent:
        return True
    _direct_write(0x7B9, cur["stop"])
    time.sleep(0.3)
    return False

# [修复2.3] 单例模式避免MQTT连接风暴
_mc_singleton = None
_mc_lock = _thr.Lock()

def _get_mc():
    """获取或创建单例MrConsole"""
    global _mc_singleton
    with _mc_lock:
        if _mc_singleton is None:
            import mr_console as mc
            _mc_singleton = mc.MrConsole()
            _mc_singleton.start()
        return _mc_singleton

def get_fan_boost():
    """读取风扇强冷状态 (通过 MQTT)"""
    try:
        app = _get_mc()
        v = (app.get_fan() or {}).get("FanBoostEnable")
        return int(v) if v is not None else None
    except Exception:
        return None

def set_fan_boost(on):
    """设置风扇强冷 (通过 MQTT)"""
    try:
        app = _get_mc()
        app.set_fan_boost(on)
        return True
    except Exception:
        return False

# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EC 硬件访问工具")
    parser.add_argument("-r", "--read", type=lambda x: int(x, 0), help="读取EC地址")
    parser.add_argument("--temp", action="store_true", help="读取温度")
    parser.add_argument("--fan", action="store_true", help="读取风扇")
    parser.add_argument("--charge", action="store_true", help="读取充电阈值")
    parser.add_argument("--set-charge", type=int, help="设置充电停止阈值(60-100)")
    parser.add_argument("--boost", choices=["on", "off"], help="风扇强冷")
    args = parser.parse_args()

    if args.read is not None:
        v = ec_read(args.read)
        print("0x{:03X} = {} ({})".format(args.read, hex(v) if v is not None else "无效", v))
    elif args.temp:
        c = get_cpu_temp()
        print("CPU: {}C".format(c) if c else "EC直读失败")
    elif args.fan:
        d = get_fan_duty()
        r_ = get_fan_rpm()
        g = get_gpu_duty()
        gr = get_gpu_rpm()
        print("CPU: {}% {}RPM  GPU: {}% {}RPM".format(d, r_, g, gr) if d else "EC直读失败")
    elif args.charge:
        t = get_charge_thresholds()
        print("充电阈值: 起始{}% / 停止{}%".format(t['start'], t['stop']) if t else "未设置/不可读")
    elif args.set_charge:
        ok = set_charge_limit(args.set_charge)
        t = get_charge_thresholds()
        print("设置 {}%: {} 当前: {}".format(args.set_charge, "OK" if ok else "FAIL", t))
    elif args.boost:
        ok = set_fan_boost(args.boost == "on")
        print("风扇强冷 {}: {}".format(args.boost, "OK" if ok else "FAIL"))
    else:
        parser.print_help()
