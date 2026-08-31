# -*- coding: utf-8 -*-
"""pull LHM master EC implementation files"""
import subprocess, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
dst = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\data_原始数据\lhm_src"
os.makedirs(dst, exist_ok=True)
files = [
    "LibreHardwareMonitorLib/Hardware/Motherboard/Lpc/EC/WindowsEmbeddedControllerIO.cs",
    "LibreHardwareMonitorLib/Hardware/Motherboard/Lpc/EC/WindowsEmbeddedController.cs",
    "LibreHardwareMonitorLib/Hardware/Motherboard/Lpc/EC/EmbeddedController.cs",
    "LibreHardwareMonitorLib/PawnIo/LpcACPIEC.cs",
]
base = "https://raw.githubusercontent.com/LibreHardwareMonitor/LibreHardwareMonitor/master/"
for f in files:
    p = subprocess.run(["curl.exe", "-sL", "--max-time", "30", base + f], capture_output=True)
    txt = p.stdout.decode("utf-8", errors="replace")
    name = f.split("/")[-1]
    open(os.path.join(dst, name), "w", encoding="utf-8").write(txt)
    print("%-40s %6d chars" % (name, len(txt)))
