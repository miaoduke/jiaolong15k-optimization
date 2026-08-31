# -*- coding: utf-8 -*-
"""fetch ec_api.py core - the fan curve + EC write logic"""
import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
url = "https://raw.githubusercontent.com/roj234/mechrevo_ec_api/master/ec_api.py"
p = subprocess.run(["curl.exe", "-sL", "--max-time", "30", url], capture_output=True)
txt = p.stdout.decode("utf-8", errors="replace")
dst = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\data_原始数据\roj234_ec_api.py"
open(dst, "w", encoding="utf-8").write(txt)
print("saved:", len(txt), "chars -> data_原始数据/roj234_ec_api.py")
# 打印关键段: 寄存器定义与写函数
import re
for m in re.finditer(r"(?m)^(FAN|REG|ADDR|EC_|DUTY|CPU|GPU|TEMP|CHARGE)[A-Z0-9_]*\s*=.*$", txt):
    print(m.group(0))
