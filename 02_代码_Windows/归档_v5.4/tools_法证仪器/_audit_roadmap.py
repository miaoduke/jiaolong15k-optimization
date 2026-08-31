# -*- coding: utf-8 -*-
"""audit roadmap doc vs roj234 source - bit-level verification"""
import re, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
base = r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4"
src = open(os.path.join(base, "data_原始数据", "roj234_ec_api.py"), encoding="utf-8").read()
doc = open(os.path.join(base, "待解锁与B类科学实现路线图_20260826.md"), encoding="utf-8").read()

passed = failed = warn = 0
def check(name, cond, detail="", iswarn=False):
    global passed, failed, warn
    if cond: passed += 1; print("PASS", name, detail)
    elif iswarn: warn += 1; print("WARN", name, detail)
    else: failed += 1; print("FAIL", name, detail)

# A. 十进制->十六进制换算
for dec, hx, name in [(1932,0x78C,"backlight"),(1958,0x7A6,"touchpad"),(1870,0x74E,"fnkey"),(1895,0x767,"trigger")]:
    check("conv %s %d=0x%X" % (name,dec,hx), dec==hx)

# B. 换算声明在文档中的呈现
for s in ["0x78C","0x7A6","0x767"]:
    check("doc has " + s, s in doc)

# C. 背光写法位运算仿真(roj234原码语义)
def set_backlight(val, status):
    val |= 16
    val &= 31
    val |= (status & 7) << 5
    return val
# 验证: 只动bit5-7? bit4恒置1?
ok_range = all(((set_backlight(v,s)>>5)&7)==s for v in range(256) for s in range(3))
check("backlight bit5-7 sets档位", ok_range)
low_preserved = all((set_backlight(v,s)&0x0F)==(v&0x0F) for v in range(256) for s in range(3))
check("backlight low nibble preserved", low_preserved)
bit4_always1 = all((set_backlight(v,s)>>4)&1==1 for v in range(256) for s in range(3))
check("backlight bit4 forced 1", bit4_always1)
# 文档是否披露 bit4 恒置1 这个副作用?
check("doc discloses bit4 side-effect", "bit4" in doc and ("强制置" in doc or "恒置" in doc), "")

# D. 触发器语义: 先清bit1再+2 => 制造上升沿
def trigger(bval):
    b = bval & 0xFD
    return 2 + b
ok_edge = all((trigger(v)&2)==2 for v in range(256))
check("trigger always ends bit1=1", ok_edge)
check("doc describes edge semantics", ("清bit1" in doc and ("触发" in doc or "沿" in doc)), "")

# E. 触摸板位段: 0xC7 属 set_battery_mode 残缺代码(审计修正), 文档须声明不采信
m_bat = re.search(r"def set_battery_mode.*?0xC7.*?write_ec\(REG_TOUCHPAD, mode\)", src, re.S)
check("0xC7 in battery_mode with val-unused bug", m_bat is not None)
check("doc rejects 0xC7 as touchpad evidence", "不采信" in doc)
m_led = re.search(r"def set_touchpad_led_status.*?(?=def )", src, re.S)
check("src led func exists(bit3)", m_led is not None and "bit3" in (m_led.group(0)[:400] if m_led else ""))
m_on = re.search(r"def set_touchpad_on.*?(?=def )", src, re.S)
check("src touchpad_on func exists(bit6)", m_on is not None and "bit6" in (m_on.group(0)[:400] if m_on else ""))

# F. Fn地址: 本机实测None的记录在场
check("doc notes 0x74E None on our machine", ("0x74E" in doc and "None" in doc))

# G. U5新发现来源可追溯: REG_TRIGGER 在源码中
check("src REG_TRIGGER exists", re.search(r"REG_TRIGGER\s*=\s*1895", src) is not None)

print("\nRESULT: %d passed, %d failed, %d warnings" % (passed, failed, warn))
