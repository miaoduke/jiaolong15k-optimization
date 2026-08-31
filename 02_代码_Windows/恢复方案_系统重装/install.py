# -*- coding: utf-8 -*-
"""
蛟龙15K 系统重装一键恢复脚本 v2.2
以管理员权限运行: Start-Process python -Verb RunAs -ArgumentList "install.py"
"""
import subprocess
import os
import sys
import json
import time
import re
import shutil

# ==================== 配置 ====================
WORK_DIR = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 电源计划基础GUID
HIGH_PERF_BASE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"  # 高性能
BALANCED_BASE = "381b4222-f694-41f0-9685-ff5bb260df2e"    # 平衡

# 固定GUID
BAL_GUID = "19ff782b-5b3b-48a2-aaa3-b9b63ce751bc"
ECO_GUID = "3a99624d-672a-43d3-93d6-9f78114bb9ae"

# MQTT配置
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 13688
UDP_PORT = 13690

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def run(cmd, check=True):
    """执行命令"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if check and r.returncode != 0:
            log(f"  WARN: {cmd[0]} 返回 {r.returncode}")
        return r
    except Exception as e:
        log(f"  ERR: {cmd[0]} - {e}")
        return None

def check_admin():
    """检查管理员权限"""
    import ctypes
    return ctypes.windll.shell32.IsUserAnAdmin()

def check_python():
    """检查Python"""
    log("检查Python...")
    py = sys.executable
    r = run([py, "--version"])
    if r:
        log(f"  Python: {py}")
        log(f"  版本: {r.stdout.strip()}")
    return py

def install_deps(py):
    """安装依赖"""
    log("安装Python依赖...")
    run([py, "-m", "pip", "install", "paho-mqtt"], check=False)
    run([py, "-m", "pip", "install", "PyQt5"], check=False)
    log("  依赖安装完成")

def check_gcubridge():
    """检查GCUBridge"""
    log("检查GCUBridge...")
    r = run(["tasklist"], check=False)
    if r and "GCUBridge" in r.stdout:
        log("  GCUBridge: 运行中")
        return True
    else:
        log("  GCUBridge: 未运行")
        return False

def get_existing_plans():
    """获取现有电源计划"""
    plans = {}
    r = run(["powercfg", "/list"], check=False)
    if r:
        for line in r.stdout.splitlines():
            m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\s+\((.+?)\)", line)
            if m:
                plans[m.group(2)] = m.group(1)
    return plans

def create_plan(name, base_guid):
    """创建电源计划"""
    log(f"  创建{name}...")
    r = run(["powercfg", "/duplicatescheme", base_guid])
    if not r:
        return None
    
    m = re.search(r"([0-9a-fA-F-]{36})", r.stdout)
    if not m:
        return None
    
    guid = m.group(1)
    run(["powercfg", "/changename", guid, name])
    time.sleep(0.3)
    return guid

def setup_plans():
    """创建电源计划"""
    log("创建电源计划...")
    plans = get_existing_plans()
    
    # MR-均衡模式
    if "MR-均衡模式" not in plans:
        guid = create_plan("MR-均衡模式", BALANCED_BASE)
        if guid:
            log(f"  MR-均衡模式: {guid}")
    else:
        log(f"  MR-均衡模式: 已存在 ({plans['MR-均衡模式']})")
    
    # MR-超级省电
    if "MR-超级省电" not in plans:
        guid = create_plan("MR-超级省电", BALANCED_BASE)
        if guid:
            log(f"  MR-超级省电: {guid}")
    else:
        log(f"  MR-超级省电: 已存在 ({plans['MR-超级省电']})")
    
    # MR-极限性能
    if "MR-极限性能" not in plans:
        log("  创建MR-极限性能...")
        guid = create_plan("MR-极限性能", HIGH_PERF_BASE)
        if guid:
            run(["powercfg", "/setacvalueindex", guid, "SUB_PROCESSOR", "PROCTHROTTLEMAX", "100"])
            run(["powercfg", "/setactive", guid])
            # 保存GUID到缓存
            cache_path = os.path.join(SCRIPT_DIR, "配置文件", "plan_guids.json")
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump({"MR-极限性能": guid}, f, indent=2)
            log(f"  MR-极限性能: {guid}")
    else:
        log(f"  MR-极限性能: 已存在 ({plans['MR-极限性能']})")
    
    # 验证
    log("  电源计划列表:")
    plans = get_existing_plans()
    for name in ["MR-极限性能", "MR-均衡模式", "MR-超级省电"]:
        if name in plans:
            log(f"    {name}: {plans[name]}")

def copy_files():
    """复制文件到工作目录"""
    log("复制文件到工作目录...")
    os.makedirs(WORK_DIR, exist_ok=True)
    
    # 核心模块
    core_dir = os.path.join(SCRIPT_DIR, "核心模块")
    if os.path.exists(core_dir):
        for f in os.listdir(core_dir):
            src = os.path.join(core_dir, f)
            dst = os.path.join(WORK_DIR, f)
            shutil.copy2(src, dst)
            log(f"  复制: {f}")
    
    # 配置文件
    config_dir = os.path.join(SCRIPT_DIR, "配置文件")
    if os.path.exists(config_dir):
        for f in os.listdir(config_dir):
            src = os.path.join(config_dir, f)
            dst = os.path.join(WORK_DIR, f)
            shutil.copy2(src, dst)
            log(f"  复制: {f}")
    
    # 快捷脚本
    script_dir = os.path.join(SCRIPT_DIR, "快捷脚本")
    if os.path.exists(script_dir):
        for f in os.listdir(script_dir):
            src = os.path.join(script_dir, f)
            dst = os.path.join(WORK_DIR, f)
            shutil.copy2(src, dst)
            log(f"  复制: {f}")

def start_powersaver():
    """启动mr_powersaver(轻量AC/DC切换, 替代daemon的电源管理) 并注册开机自启"""
    log("启动mr_powersaver...")

    # 只杀我们的进程(按命令行匹配), 不能 /im python.exe 全杀
    run(["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
         "Where-Object { $_.CommandLine -match 'mr_powersaver|mr_daemon' } | "
         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], check=False)
    time.sleep(1)

    ps_path = os.path.join(WORK_DIR, "mr_powersaver.py")
    if not os.path.exists(ps_path):
        log("  [警告] mr_powersaver.py 不存在, 跳过")
        return
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    subprocess.Popen([exe, ps_path], cwd=WORK_DIR,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    log("  mr_powersaver已启动")

    # 注册开机自启vbs(必须ANSI/GBK编码, 否则cscript中文路径乱码)
    startup = os.path.join(os.environ["APPDATA"],
                           r"Microsoft\Windows\Start Menu\Programs\Startup")
    vbs = os.path.join(startup, "mr_powersaver.vbs")
    content = (
        'Set WShell = CreateObject("WScript.Shell")\r\n'
        'WShell.CurrentDirectory = "%s"\r\n'
        'WShell.Run """%s"" ""%s""", 0, False\r\n' % (WORK_DIR, exe, ps_path)
    )
    with open(vbs, "wb") as f:
        f.write(content.encode("gbk"))
    log(f"  开机自启已注册: {vbs}")

def verify():
    """验证安装"""
    log("验证安装...")
    
    # 检查daemon
    try:
        s = __import__("socket").socket(__import__("socket").AF_INET, __import__("socket").SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(b"status", ("127.0.0.1", UDP_PORT))
        resp = s.recvfrom(4096)[0].decode()
        data = json.loads(resp)
        log(f"  daemon: 场景={data['scenario']}, auto={data['auto']}")
        s.close()
    except Exception as e:
        log(f"  daemon: 连接失败 - {e}")
    
    # 检查电源计划
    plans = get_existing_plans()
    for name in ["MR-极限性能", "MR-均衡模式", "MR-超级省电"]:
        if name in plans:
            log(f"  {name}: OK")
        else:
            log(f"  {name}: 缺失!")

def main():
    print("=" * 60)
    print(" 蛟龙15K 系统重装恢复脚本 v2.2")
    print("=" * 60)
    
    # 检查管理员权限
    if not check_admin():
        print("\n[ERROR] 请以管理员权限运行!")
        print("\n执行以下命令:")
        print(f'  Start-Process python -Verb RunAs -ArgumentList "{os.path.abspath(__file__)}"')
        return
    
    # 执行恢复步骤
    py = check_python()
    install_deps(py)
    check_gcubridge()
    setup_plans()
    copy_files()
    start_powersaver()
    verify()
    
    print("\n" + "=" * 60)
    print(" 恢复完成!")
    print("=" * 60)
    print(f"\n工作目录: {WORK_DIR}")
    print(f"\n验证命令:")
    print(f'  python -c "import socket,json;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(3);s.sendto(b\'status\',(\'127.0.0.1\',{UDP_PORT}));print(json.loads(s.recvfrom(4096)[0]))"')
    print(f"\n  powercfg /list | findstr MR-")

if __name__ == "__main__":
    main()
