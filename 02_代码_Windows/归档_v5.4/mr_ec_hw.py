#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mr_ec_hw.py — EC 硬件访问组合通道模块
优先级: MQTT(免管理员,状态/设置) > UWACPIDriver直读(免管理员,寄存器) > WMI(已死,仅后备)
UWACPIDriver: 官方驱动 C:/Program Files/OEM/机械革命电竞控制台/UWACPIDriver/UWACPIDriver.sys
  用户态封装 ACPIDriverDll.dll 导出 ReadEC(int addr)->int (签名已实测验证, 20260825)
  WriteEC(addr, value) 签名已于 20260825 经反汇编+零破坏NO-OP实验双重定案(报告附录D)
"""
import sys, os, time, json, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# UWACPIDriver 直读 (免管理员, 首选)
# ============================================================
_DLL_PATH = "C:/Program Files/OEM/机械革命电竞控制台/UniwillService/MyControlCenter/ACPIDriverDll.dll"
_dll = None

def _load_dll():
    """加载官方 ACPIDriverDll 并绑定已验证签名"""
    global _dll
    if _dll is None:
        if not os.path.exists(_DLL_PATH):
            return False
        import ctypes
        _dll = ctypes.CDLL(_DLL_PATH)
        _dll.ReadEC.restype = ctypes.c_int
        _dll.ReadEC.argtypes = [ctypes.c_int]
        _dll.WriteEC.restype = None
        _dll.WriteEC.argtypes = [ctypes.c_int, ctypes.c_int]
    return True

_ADDR_MIN, _ADDR_MAX = 0x000, 0x7FF   # 全域扫描验证过的合法窗口; 越界参数禁止进入驱动

def _addr_ok(addr):
    """客户端白名单校验 — 20260825第二次内核事故教训: 非法地址读同样会击穿内核"""
    try:
        a = int(addr)
        return _ADDR_MIN <= a <= _ADDR_MAX
    except Exception:
        return False

def _direct_read(addr):
    """通过官方 ACPIDriverDll.ReadEC 读 EC 寄存器; 死地址(恒0)/异常返回 None"""
    if not _addr_ok(addr):
        return None
    try:
        if not _load_dll():
            return None
        import ctypes
        v = _dll.ReadEC(int(addr)) & 0xFF
        return v if v != 0 else None   # 死地址恒0, 视为无效
    except Exception:
        return None

def _direct_write(addr, value):
    """通过官方 ACPIDriverDll.WriteEC 写 EC 寄存器。
    签名 WriteEC(addr, value) 已于 20260825 经零破坏NO-OP实验定案(见报告附录D)"""
    if not _addr_ok(addr):
        return False
    try:
        if not _load_dll():
            return False
        _dll.WriteEC(int(addr), int(value))
        return True
    except Exception:
        return False

# ============================================================
# WMI EC 读写 (需管理员; 当前固件下恒返0, 仅作后备)
# ============================================================
def _wmi_read_ec(addr):
    """通过 WMI AcpiTest_MULong 读取 EC 寄存器 (返回 byte 或 None)"""
    try:
        ps = (
            "$o = Get-WmiObject -Namespace root\\wmi -Class AcpiTest_MULong | "
            "Where-Object { $_.InstanceName -eq 'ACPI\\PNP0C14\\1_0' }; "
            "if ($o) { "
            "$null = $o.GetSetULong([UInt64](0x0000010000000000 -bor [UInt64]{})); "
            "$r = $o.GetULong(); "
            "Write-Output ($r.Return -band 0xFF) "
            "}"
        ).format(addr)
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10
        )
        if r.stdout.strip():
            return int(r.stdout.strip())
    except Exception:
        pass
    return None

def _wmi_write_ec(addr, value):
    """通过 WMI AcpiTest_MULong 写入 EC 寄存器"""
    try:
        ps = (
            "$o = Get-WmiObject -Namespace root\\wmi -Class AcpiTest_MULong | "
            "Where-Object { $_.InstanceName -eq 'ACPI\\PNP0C14\\1_0' }; "
            "if ($o) { "
            "$data = [UInt64]({} * 0x10000 + {}); "
            "$null = $o.GetSetULong($data) "
            "}"
        ).format(value, addr)
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass

# ============================================================
# 高层 API — 所有读取统一经 ec_read
# ============================================================
def ec_read(addr):
    """读取 EC 寄存器: UWACPIDriver直读优先, WMI后备"""
    v = _direct_read(addr)
    return v if v is not None else _wmi_read_ec(addr)

def ec_write(addr, value):
    """写入 EC 寄存器: UWACPIDriver WriteEC(addr,value) 已验证(20260825 NO-OP实验), WMI后备(当前固件无效)"""
    if _direct_write(addr, value):
        return True
    _wmi_write_ec(addr, value)
    return False

def get_cpu_temp():
    """CPU 温度 (EC 0x43E)"""
    return ec_read(0x43E)

def get_gpu_temp():
    """GPU 温度 (EC 0x44C, 20260825全域扫描+nvidia-smi交叉验证±2°C; 旧地址0x44F已死)"""
    return ec_read(0x44C)

def get_fan_duty():
    """CPU 风扇 Duty (EC 0x461)"""
    return ec_read(0x461)

def get_fan_rpm():
    """CPU 风扇 RPM (EC 0x464=高字节 / 0x465=低字节)"""
    hi = ec_read(0x464)
    lo = ec_read(0x465)
    if lo is not None and hi is not None:
        return hi * 256 + lo
    return None

def get_gpu_duty():
    """GPU 风扇 Duty (EC 0x469, 0~200 映射 %)"""
    v = ec_read(0x469)
    return round(v * 100 / 200) if v is not None else None

def get_gpu_rpm():
    """GPU 风扇 RPM (EC 0x46C=高 / 0x46D=低)"""
    hi = ec_read(0x46C)
    lo = ec_read(0x46D)
    if lo is not None and hi is not None:
        return hi * 256 + lo
    return None

def get_charge_thresholds():
    """读取充电阈值对 (EC 0x7A8=起始% / 0x7A9=停止%; 20260825全域扫描定位, 默认80/100)"""
    start = ec_read(0x7A8)
    stop = ec_read(0x7A9)
    if start is None or stop is None:
        return None
    return {"start": start, "stop": stop}

def get_charge_limit():
    """读取充电阈值 (EC 0x7A9 停止值)"""
    t = get_charge_thresholds()
    return t["stop"] if t else None

def set_charge_limit(percent):
    """设置充电停止阈值 (EC 0x7A9, 起始值0x7A8保持不变)
    科学流程: 读原值 -> 写 -> 延时 -> 回读验证 -> 失败则恢复原值"""
    if percent < 60 or percent > 100:
        return False
    cur = get_charge_thresholds()
    if not cur:
        return False
    if not _direct_write(0x7A9, percent):
        return False
    time.sleep(0.5)
    now = get_charge_thresholds()
    if now and now.get("stop") == percent:
        return True
    # 回读不符 -> 恢复原值
    _direct_write(0x7A9, cur["stop"])
    time.sleep(0.3)
    return False

def get_fan_boost():
    """读取风扇强冷状态 (通过 MQTT)"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mr_console as mc
        app = mc.MrConsole(); app.start()
        time.sleep(1)
        v = app.get_fan().get("FanBoostEnable")
        app.stop()
        return int(v) if v is not None else None
    except:
        return None

def set_fan_boost(on):
    """设置风扇强冷 (通过 MQTT)"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mr_console as mc
        app = mc.MrConsole(); app.start()
        app.set_fan_boost(on)
        time.sleep(1)
        app.stop()
        return True
    except:
        return False

# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EC 硬件访问工具")
    parser.add_argument("-r", "--read", type=lambda x: int(x, 0), help="读取EC地址 (支持0x格式)")
    parser.add_argument("--temp", action="store_true", help="读取温度")
    parser.add_argument("--fan", action="store_true", help="读取风扇")
    parser.add_argument("--charge", action="store_true", help="读取充电阈值")
    parser.add_argument("--set-charge", type=int, help="设置充电停止阈值(60-100)")
    parser.add_argument("--boost", choices=["on", "off"], help="风扇强冷")
    args = parser.parse_args()

    if args.read is not None:
        v = ec_read(args.read)
        print(f"0x{args.read:03X} = 0x{v:02X} ({v})" if v is not None else f"0x{args.read:03X} = (无效)")
    elif args.temp:
        c = get_cpu_temp()
        print(f"CPU: {c}°C" if c else "EC直读失败")
    elif args.fan:
        d = get_fan_duty()
        r_ = get_fan_rpm()
        g = get_gpu_duty()
        gr = get_gpu_rpm()
        print(f"CPU风扇: {d}% {r_}RPM   GPU风扇: {g}% {gr}RPM" if d else "EC直读失败")
    elif args.charge:
        t = get_charge_thresholds()
        print(f"充电阈值: 起始{t['start']}% / 停止{t['stop']}%" if t else "充电阈值: 未设置/不可读")
    elif args.set_charge:
        ok = set_charge_limit(args.set_charge)
        t = get_charge_thresholds()
        print(f"设置 {args.set_charge}%: {'✅' if ok else '❌'}  当前阈值: {t}")
    elif args.boost:
        ok = set_fan_boost(args.boost == "on")
        print(f"风扇强冷 {args.boost}: {'✅' if ok else '❌'}")
    else:
        parser.print_help()
