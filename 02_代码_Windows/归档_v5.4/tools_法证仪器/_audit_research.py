# -*- coding: utf-8 -*-
"""audit: verify decimal->hex conversions claimed in reports + asset existence"""
import sys, os, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
base = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4"

passed = failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print("PASS", name, detail)
    else: failed += 1; print("FAIL", name, detail)

# A. 十六进制换算全表复核 (roj234 十进制 -> 我方报告十六进制)
conv = [(1883,0x75B),(1884,0x75C),(1923,0x783),(1924,0x784),(1925,0x785),(1926,0x786),
        (1927,0x787),(1977,0x7B9),(1873,0x751),(1859,0x743),(1862,0x746),(1830,0x726),
        (1183,0x49F),(1124,0x464),(1125,0x465),(1131,0x46B),(1132,0x46C),
        (3840,0xF00),(3856,0xF10),(3872,0xF20),(3888,0xF30),(3904,0xF40),(3920,0xF50)]
for dec, hexv in conv:
    check("conv %d=0x%X" % (dec, hexv), dec == hexv)

# B. 资产存在性 (总集索引所列)
assets = [
    "调研成果总集_20260826.md",
    "FanControl解锁探索报告_20260825.md",
    "FanControl源码穷尽调研_20260825.md",
    "穷尽调研第二轮重大发现_20260825.md",
    "v6.0方案评审与GHelper照搬UI方案_20260825.md",
    "自制控制台v6.0设计方案_20260825.md",
    "data_原始数据/roj234_ec_api.py",
    "data_原始数据/lhm_src/EmbeddedController.cs",
    "data_原始数据/lhm_src/WindowsEmbeddedControllerIO.cs",
    "data_原始数据/nbfc_MECHREVO_Jiaolong_GK5NR0O.json",
    "data_原始数据/nbfc_Tongfang_X6RP57TW.json",
    "tools_法证仪器/_fc_lhm_source.py",
    "tools_法证仪器/_lhm_ec_pull.py",
    "tools_法证仪器/_ecapi_fetch.py",
    "tools_法证仪器/_xvalidate_roj234.py",
    "tools_法证仪器/_xvalidate2.py",
]
for a in assets:
    p = os.path.join(base, a.replace("/", os.sep))
    ok = os.path.isfile(p) and os.path.getsize(p) > 0
    check("asset " + a.split("/")[-1], ok, "" if ok else "(missing/empty)")

# C. 总集内部声明抽查
doc = open(os.path.join(base, "调研成果总集_20260826.md"), encoding="utf-8").read()
check("claim 双镜像", "0x461 ≡ 0x75B" in doc or "0x461≡0x75B" in doc)
check("claim duty÷2", "raw÷2" in doc or "÷2" in doc)
check("claim PL值", "65/65/100" in doc)
check("claim 曲线表缺失", "本模具缺失" in doc or "本模具无此区" in doc or "曲线表区本模具不存在" in doc)
check("claim 零写入", "零写入" in doc)

# D. 报告间一致性: roj234源码里的实际十进制常量 vs 我方引用
src = open(os.path.join(base, "data_原始数据", "roj234_ec_api.py"), encoding="utf-8").read()
for const, val in [("REG_FAN1_DUTY", 1883), ("REG_FAN2_DUTY", 1884), ("REG_CPU_PL1", 1923),
                   ("REG_BATTERY_CHARGE_LIMIT", 1977), ("FAN_CPU_UPT", 3840)]:
    m = re.search(const + r"\s*=\s*(\d+)", src)
    check("src " + const, m is not None and int(m.group(1)) == val, m.group(1) if m else "(absent)")

# E. duty÷2 证据链: 源码确有 /2
check("src /2 evidence", "/ 2" in src or ("/2" in src))

print("\nRESULT: %d passed, %d failed" % (passed, failed))
