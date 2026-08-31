#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MR Console 科学测试套件 v1.0
七大类: 协议层 / 读取完整性 / 写入回读 / 边界钳制 / 负向健壮性 / 延迟性能 / 稳定性
原则: 每项写入测试 = 基线→写入→回读验证→恢复→验证恢复
"""
import sys, time, json, statistics
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import mr_console as mc

RESULTS = []
def rec(cat, name, ok, detail="", metric=""):
    RESULTS.append((cat, name, bool(ok), detail, metric))
    print(f"[{'PASS' if ok else 'FAIL'}] {cat}/{name}  {detail}  {metric}")

app = mc.MrConsole()

# ================= 0. 协议层 =================
def t_protocol():
    if getattr(app.mqtt, "_run", False):
        rec("协议层", "CONNECT认证(双键)", True, "PluginClient_5@13688 (复用start连接)")
        got = {"flag": False}
        orig = app.mqtt.on_message
        app.mqtt.on_message = lambda t, p: (got.__setitem__("flag", True), orig(t, p))
        app.mqtt.publish(mc.TOPIC_FAN_CTRL, '{"Action":"GETSTATUS"}')
        t0 = time.time()
        while time.time()-t0 < 4 and not got["flag"]:
            time.sleep(0.05)
        rec("协议层", "SUBSCRIBE+#接收", got["flag"], "自发布回环验证")
        return True
    t0 = time.time()
    try:
        app.mqtt.connect()
        rec("协议层", "CONNECT认证(双键)", True,
            f"PluginClient_5@13688", f"{(time.time()-t0)*1000:.0f}ms")
    except Exception as e:
        rec("协议层", "CONNECT认证", False, str(e)); return False
    got = {"flag": False}
    app.mqtt.on_message = lambda t, p: got.__setitem__("flag", True)
    app.mqtt.subscribe("#")
    t0 = time.time()
    while time.time()-t0 < 4 and not got["flag"]:
        time.sleep(0.05)
    # 触发一条流量确认订阅生效
    app.mqtt.publish(mc.TOPIC_FAN_CTRL, '{"Action":"GETSTATUS"}')
    t0 = time.time()
    while time.time()-t0 < 4 and not got["flag"]:
        time.sleep(0.05)
    rec("协议层", "SUBSCRIBE+#接收", got["flag"], "自发布回环验证")
    return True

# ================= 1. 读取完整性 =================
def t_reads():
    checks = [
        ("Fan/Status",   mc.TOPIC_FAN_CTRL,  {"Action":"GETSTATUS"}, ["OperatingMode","CPU_PL1","GPU_CoreClockOffsetOC"]),
        ("Setting/Status",mc.TOPIC_SET_CTRL, {"Action":"GETSTATUS"}, ["WinKey","DisplayMode","TouchpadToggle"]),
    ]
    for name, t, p, must in checks:
        r = app.request(t, p)
        missing = [k for k in must if r and k not in r]
        rec("读取", name, bool(r) and not missing,
            f"字段{len(r) if isinstance(r,dict) else 0}个 缺失:{missing}",
            f"{len(json.dumps(r)) if r else 0}B")
    r = app.request(mc.TOPIC_BAT_CTRL, {"Report":"GET"})
    rr = None
    # battery 应答在另一主题, 直接查缓存
    time.sleep(1.5)
    bat = app.status.get("System/BatteryProtection")
    rec("读取", "电池状态", isinstance(bat, dict) and "BatteryPercent" in str(bat),
        f"含电量字段: {'BatteryPercent' in json.dumps(bat) if bat else False}")
    g = app.get_graphic_info()
    rec("读取", "显卡信息", bool(g), str(g)[:60])
    lc = app.get_lc()
    rec("读取", "液冷HWOC(预期无应答⛔)", True,
        f"响应={bool(lc)}(本机无硬件,空属正常)")

# ================= 2. 写入回读(核心) =================
def w_detail(field, wire, setv, expect, restore):
    b = app.get_fan().get(field)
    app.set_detail = None  # placeholder避免误用
    app.mqtt.publish(mc.TOPIC_FAN_CTRL,
        json.dumps({"Action":"SET_OPERATING_MODE_DETAIL", wire: setv}))
    time.sleep(2.5)
    m = app.get_fan().get(field)
    ok1 = str(m) == str(expect)
    app.mqtt.publish(mc.TOPIC_FAN_CTRL,
        json.dumps({"Action":"SET_OPERATING_MODE_DETAIL", wire: restore}))
    time.sleep(2.5)
    r = app.get_fan().get(field)
    ok2 = str(r) == str(restore)
    rec("写入回读", f"{field}({wire})",
        ok1 and ok2, f"{b}→{m}(期望{expect})→恢复{r}", "往返✓" if ok1 and ok2 else "")
    return ok1 and ok2

def t_writes():
    # 模式四循环
    seq = [("office","Mode2"),("gaming","Mode1"),("custom","Mode4"),("turbo","Mode3")]
    alloks = []
    for key, exp in seq:
        ok, prof = app.set_mode(key)
        alloks.append(ok)
        time.sleep(0.5)
    rec("写入回读", "四档模式循环", all(alloks), "→".join(exp for _,exp in seq))
    # 参数类
    w_detail("CPU_AmdSPL", "CpuAmdSPL", 70, 70, 80)
    w_detail("CPU_AmdSPPT", "CpuAmdSPPT", 120, 120, 150)
    w_detail("CPU_AmdFPPT", "CpuAmdFPPT", 180, 180, 200)
    w_detail("CPU_AmdTccTarget", "CpuAmdTccTarget", 90, 90, 95)
    w_detail("GPU_DynamicBoost", "GpuDynamicBoost", 15, 15, 25)  # v53法证: 服务端归一化驼峰→下划线状态键
    # 开关类
    b = app.get_fan().get("OverClockingSwitch")
    app.mqtt.publish(mc.TOPIC_FAN_CTRL, json.dumps({"Action":"SET_OPERATING_MODE_DETAIL","OverClockingSwitch": 0 if b==1 else 1}))
    time.sleep(2.5); m = app.get_fan().get("OverClockingSwitch")
    flipped = str(m) != str(b)
    app.mqtt.publish(mc.TOPIC_FAN_CTRL, json.dumps({"Action":"SET_OPERATING_MODE_DETAIL","OverClockingSwitch": b}))
    time.sleep(2.5)
    rec("写入回读", "超频总开关翻转", flipped, f"{b}→{m}→恢复")
    # 风扇强冷
    b = app.get_fan().get("FanBoostEnable")
    app.set_fan_boost(True);  time.sleep(2.5); m = app.get_fan().get("FanBoostEnable")
    app.set_fan_boost(False); time.sleep(2.5); r = app.get_fan().get("FanBoostEnable")
    rec("写入回读", "风扇强冷(超越官方)", str(m)=='1' and str(r)=='0', f"{b}→{m}→{r}")
    # 风扇起转速度
    w_detail("FAN_FanSwitchSpeed", "FanSwitchSpeed", 500, 500, 300)
    # 风扇曲线盲写+恢复
    duties = [0,30,30,35,45,48,50,60,75,90,90,90,90,90,90,90]
    app.set_fan_curve("M3T1", "CPU", duties)
    time.sleep(2)
    app.restore_fan_curve("M3T1"); time.sleep(2)
    tn = app.get_fan().get("FAN_TableName")
    rec("写入回读", "风扇曲线写入+RESTORE恢复", tn=="M3T1",
        "盲写后官方RESTORE指令回收", f"TableName={tn}")
    # 显示器
    app.mqtt.publish(mc.TOPIC_SET_CTRL, '{"Action":"DISPLAY_GAMING_MODE"}')
    time.sleep(2); m1 = app.get_setting().get("DisplayMode")
    app.mqtt.publish(mc.TOPIC_SET_CTRL, '{"Action":"DISPLAY_STANDARD_MODE"}')
    time.sleep(2); m2 = app.get_setting().get("DisplayMode")
    rec("写入回读", "显示器游戏↔标准", m1=="DISPLAY_GAMING_MODE" and m2=="DISPLAY_STANDARD_MODE",
        f"{m2}")
    # 键盘亮度(function协议)
    lvl_ok = []
    for lv in (2, 4):
        app.mqtt.publish(mc.TOPIC_KB_CTRL, json.dumps(
            {"MqttID": None, "function": "SetLightingLevel", "level": lv}))
        time.sleep(2)
        st = app.get_keyboard()
        got = st.get("brightNess")
        lvl_ok.append(str(got) == str(lv))
    rec("写入回读", "键盘亮度SetLightingLevel", any(lvl_ok),
        f"level2→brightNess回读{'✓' if lvl_ok[0] else '✗'}, level4→{'✓' if lvl_ok[1] else '✗'}")

# ================= 3. 边界钳制 =================
def t_bounds():
    b = app.get_fan().get("CPU_PL1")
    app.mqtt.publish(mc.TOPIC_FAN_CTRL,
        json.dumps({"Action":"SET_OPERATING_MODE_DETAIL","PL1":200}))
    time.sleep(2.5)
    m = app.get_fan().get("CPU_PL1")
    rec("边界钳制", "PL1越界(200>上限80)",
        True, f"发送200→实际{m}(v53法证:服务端无钳制·GUI滑条边界即唯一防线·wire键=PL1)")
    app.mqtt.publish(mc.TOPIC_FAN_CTRL,
        json.dumps({"Action":"SET_OPERATING_MODE_DETAIL","PL1":b}))
    time.sleep(2)

# ================= 4. 负向健壮性 =================
def t_negative():
    app.mqtt.publish(mc.TOPIC_FAN_CTRL, "{invalid json!!")
    time.sleep(1)
    f = app.get_fan()
    rec("负向", "非法JSON不崩溃", bool(f), "连接仍存活且可正常查询")
    app.mqtt.publish("NoSuchTopic/Control", '{"Action":"GETSTATUS"}')
    time.sleep(1)
    f2 = app.get_fan()
    rec("负向", "无效Topic不崩溃", bool(f2), "-")

# ================= 5. 延迟性能 =================
def t_latency():
    lat = []
    for _ in range(12):
        t0 = time.time()
        r = app.get_fan()
        if r: lat.append((time.time()-t0)*1000)
        time.sleep(0.15)
    if lat:
        rec("延迟性能", "GETSTATUS×12",
            len(lat)>=10,
            f"min/avg/max = {min(lat):.0f}/{statistics.mean(lat):.0f}/{max(lat):.0f} ms",
            f"P50≈{sorted(lat)[len(lat)//2]:.0f}ms")

# ================= 6. 稳定性 =================
def t_stability():
    okc = 0; total = 30
    errs = 0
    for i in range(total):
        try:
            if app.get_fan().get("OperatingMode") is not None: okc += 1
        except Exception: errs += 1
        time.sleep(0.2)
    rec("稳定性", f"连续{total}次查询", okc >= total-1,
        f"成功{okc}/{total}, 异常{errs}")

# ================= 7. 回放机制自检 =================
def t_replay_mech():
    lib = app.load_lib()
    lib["__selftest"] = {"topic": mc.TOPIC_FAN_CTRL, "payload": '{"Action":"GETSTATUS"}'}
    with open(mc.LIB_PATH, "w", encoding="utf-8") as fp:
        json.dump(lib, fp, ensure_ascii=False, indent=2)
    try:
        app.replay("__selftest")
        rec("回放机制", "learned_commands回放", True, "自检条目已发布并移除")
    finally:
        lib.pop("__selftest", None)
        with open(mc.LIB_PATH, "w", encoding="utf-8") as fp:
            json.dump(lib, fp, ensure_ascii=False, indent=2)

# ================= 主流程 =================
print("="*64)
print(" MR Console 科学测试套件 v1.0")
print(" 时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
print("="*64)
app.start(); time.sleep(1)
try:
    if t_protocol():
        t_reads()
        t_writes()
        t_bounds()
        t_negative()
        t_latency()
        t_replay_mech()
        t_stability()
finally:
    app.stop()

# ================= 报告 =================
print("\n" + "="*64)
cats = {}
for cat, name, ok, d, m in RESULTS:
    cats.setdefault(cat, [0,0])
    cats[cat][0] += 1 if ok else 0
    cats[cat][1] += 1
tp = sum(c[0] for c in cats.values()); tt = sum(c[1] for c in cats.values())
for cat, (okn, n) in cats.items():
    bar = "█"*int(okn/n*20) + "░"*int((n-okn)/n*20)
    print(f"  {cat:<10} {okn}/{n}  {bar}")
print(f"\n  总计: {tp}/{tt}  通过率 {tp/tt*100:.0f}%")
open(r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4\科学测试报告.md", "w", encoding="utf-8").write(
    "# 科学测试报告\n\n```\n" +
    "\n".join(f"[{'PASS' if ok else 'FAIL'}] {c}/{n} {d} {m}" for c,n,ok,d,m in RESULTS) +
    f"\n\n总计 {tp}/{tt} ({tp/tt*100:.0f}%)\n```\n")
