# 蛟龙15K (GM5BG0E) Windows 生态 · 科学总览
**版本**: v5.4 快照 | **日期**: 2026-08-26 | **机器**: MECHREVO 蛟龙15K (Ryzen 7 7435H + RTX 4060 Laptop, Uniwill EC)
**性质**: 本文档是当前 Windows 生态的权威事实快照。每条结论标注证据等级与出处。

---

## 0. 方法论

### 证据分级
| 等级 | 含义 | 示例 |
|------|------|------|
| **[A]** | 双源交叉验证或破坏性排除后的定案 | GPU温度地址(nvidia-smi±2°C对照) |
| **[B]** | 单源实测, 脚本可复现 | EC直读温度采样 |
| **[C]** | 合理推断(有部分证据) | WriteEC参数顺序的API对称性论证(后被实验升级为A) |
| **[D]** | 未验证假设 | 满充截止的长期物理行为 |

### 强制规范
1. 一切写操作五步法: **记原始值 → 写 → 延时 → 回读 → 失败自动恢复**
2. 内核驱动封装函数**禁止猜测签名**(20260825内核崩溃事故教训, 见§6.R1)
3. 单次任务一次性提权(用户铁律); 批处理纯ASCII; ps1避免裸UTF-8中文注释
4. 自动化测试安全排除项: System_OFF / MONITOR_OFF / AIRPLANE / 摄像头·WiFi·BT开关 / 所有⛔研究项

---

## 1. 硬件访问通道全景(分层架构)

```
┌─ L3 产品层 ────────────────────────────────────────────────┐
│ mr_ec_hw.py(ctypes直调)  mr_win_ctrl.py  mr_console.py(MQTT)│
├─ L2 用户态封装 ────────────────────────────────────────────┤
│ ACPIDriverDll.dll (官方, 导出19函数)                        │
│   ReadEC(addr)->int │ WriteEC(addr,val) │ Read/WriteIO     │
│   Read/WritePCI │ Read/WriteCMOS │ Read/WriteMEMB          │
│   TempRead1/2/3 │ SMAPCTable                               │
├─ L1 内核驱动 ──────────────────────────────────────────────┤
│ UWACPIDriver.sys (Running, 46KB) ← 设备对象 \.ACPIDriver   │
│   IOCTL 0x9C40A488=读 / 0x9C40A48C=写                       │
│   ACPI请求包: 魔术字 ECRW/AeiC, 操作码 1=读 2=写            │
└────────────────────────────────────────────────────────────┘
并行通道: MQTT桥(GCUBridge 127.0.0.1:13688) │ nvidia-smi │ powercfg │ WMI(死口)
```

**关键事实**: 官方 UWP 控制台(ControlCenter3 5.17.49.19)走的是**已死的 AcpiTest_WMI 口**;
UWACPIDriver 是其配套新通道但老 UI 未使用 —— 这就是"官方温度显示可能也坏了"而自制控制台能读的原因。[B]

---

## 2. 通道能力矩阵

| # | 通道 | 管理员 | 延迟 | 读 | 写 | 状态 | 证据 |
|---|------|--------|------|----|----|------|------|
| C1 | **UWACPIDriver 直调**(ctypes) | ❌免管 | ~µs | ✅ | ✅ | ✅主力 | 附录C改判/D |
| C2 | MQTT 桥(官方服务) | ❌ | ms级 | ✅状态 | ✅设置 | ✅ | 法证附录A |
| C3 | nvidia-smi | 部分 | ~100ms | ✅温/功/频率 | ✅锁频/TGP | ✅ | hw_test S1 |
| C4 | powercfg/注册表/DEVMODEW | 视操作 | ms | ✅ | ✅ | ✅ | S1 win-native |
| C5 | WMI AcpiTest_MULong | 曾需 | - | ❌恒零 | ❌无效 | ☠️**弃用铁案** | 附录B/C |

**C5 死亡定案三重证据**: 重启后10实例(1_0~1_9)×多编码×管理员全零; PS/CIM双客户端一致; wmic已被系统移除。[A]

---

## 3. EC 地址映射基线(全域只读扫描 0x000-0x7FF ×2采样)

| 功能 | 地址 | 验证方式 | 等级 |
|------|------|---------|------|
| CPU 温度 | **0x43E** | 多次活体采样 | [A] |
| GPU 温度 | **0x44C** | nvidia-smi 对照 ±2°C | [A] |
| CPU 风扇 Duty/RPM | 0x461 / 0x464(hi)·0x465(lo) | 采样持续变化 | [A] |
| GPU 风扇 Duty/RPM | 0x469 / 0x46C(hi)·0x46D(lo) | 同上 | [A] |
| 充电阈值 起/停 | **0x7A8 / 0x7A9** | 默认80/100 + 写读环 | [A] |
| ~~旧 GPU温 0x44F~~ | 恒0 | 死地址 | [A] |
| 0x7B9(旧阈值位) | 条件性镜像 | 通电+写操作后=起始阈值80; 离电期恒0 | [B]审计修正 |

扫描器 `_ec_sweep.py` 可重复执行; 原始数据 `_ec_sweep.json`(非零739/变化90)。
⚠️ RPM 字节序: hi 在前(0x464×256+0x465), JCC 校准基准 0x071D→1821RPM。[B]

---

## 4. MQTT 协议要点(C2 通道)

- Broker `127.0.0.1:13688`(GCUBridge 服务), MQTT 3.1.1 JSON, ClientId=`PluginClient_{N}` 槽位5
- 订阅 `#` 后全部话题缓存在 `app.status[topic]` → 支持**全量差分法证**
- Wire键 ≠ Status键(如写 `PL1` 回显 `CPU_PL1`; `GpuDynamicBoost` 规范化为 `GPU_DynamicBoost`)
- `get_support()` 真实回显 topic 为 `Customize/Info`(法证修复)
- 模式切换会重载 OC profile(曾把卡死的 PL1=200 冲回 65)[B]
- 已知现象: 大量 SET_DETAIL 突发后 GETSTATUS 偶发 >4s 无回包(~17%), 干净连接 30/30·0-2ms
  → 分类: 桥侧节流, GUI 5s 刷新天然容忍 [B]

---

## 5. 已证结论清单

| # | 结论 | 等级 | 出处 |
|---|------|------|------|
| K1 | EC 双向通路经 UWACPIDriver 打通, 免管理员 | [A] | 报告附录C/D |
| K2 | AcpiTest_WMI 口已弃用(恒零), 与 EC 解绑 | [A] | 附录B/C |
| K3 | ReadEC(int addr)->int / WriteEC(int addr,int value) | [A] | 附录D(NO-OP实验) |
| K4 | 服务端(MQTT)**无钳制**: PL1=200 照单全收, GUI滑条是唯一防线 | [A] | 法证2.x |
| K5 | GPU vBIOS 锁 115W: nvidia-smi -pl 对140/100均拒绝(提权后亦然) | [A] | E1仲裁 |
| K6 | GPU TargetTemperature=87 钉死不可下调(OC开关开亦然) | [B] | FIELD_DOC注 |
| K7 | EPP/Boost/MaxState 为**每电源计划**独立值; "漂移"实为计划切换(离电自动切节能) | [A] | 法证2.6 |
| K8 | 模式切换重载OC profile(冲掉卡死值) | [B] | _pl1_rescue |
| K9 | 键盘亮度 AC/DC 双路径存在(状态包新键 ACBrightness/DCBrightness) | [C] | 法证2.8 |
| K10 | CloseTimer 为盲写(无任何回声) | [B] | 法证2.8 |
| K11 | 官方栈构成: UWP ControlCenter3 + UniwillService/GCUBridge + UWACPIDriver | [B] | §1 |
| K12 | 系统装有火绒(HipsTray/sysdiag/hrwfpdrv 运行中); powershell带脚本提权被拦, python/cmd载体可行 | [B] | 进程清单+提权史 |

---

## 6. 风险登记簿 & 事故复盘

| # | 风险/事故 | 处置 | 教训(已入铁律) |
|---|----------|------|----------------|
| R1 | **20260825 内核崩溃重启一次**: 两参指针签名猜测致驱动野指针写入 | 事故定位到行; WriteEC 解禁前先静态证明无解引用 | 禁止猜测内核封装签名; 只读单参起步; NO-OP实验定型 |
| R5 | **20260825 第二次内核崩溃重启**: 审计边界测试将非法地址(-1/0x7FFFFFFF)直喂 ReadEC → 内核故障(23:24)。与插拔电源无关, 时序与非法注入吻合 | `_addr_ok()` 白名单[0x000-0x7FF]读写双向守卫落地; 边界测试重定义为客户端拦截验证(10/10) | **任何进入内核路径的参数必须客户端白名单校验——无论读写**; 测试不得成为危害源 |
| R6 | 0x7B9"死地址"误判: 实为条件性镜像(离电恒0, 通电+写后=起始阈值80) | 总览表降级[B]; 测试期望改为稳定性断言 | 死地址判定需注明观测条件(电源态/初始化态) |
| R2 | 提权干扰: 火绒静默拦截 powershell 提权; UAC 弹窗超时 | python/cmd 载体 + bat自提权 + 手动管理员终端三路径 | 一次性提权打包; 结果落盘不依赖窗口存活 |
| R3 | UTF-8 中文批处理在 GBK 代码页乱码执行 | bat 纯 ASCII 化 | 中文输出仅允许 PS 侧或日志文件 |
| R4 | 并发写 JSON 竞争导致结果文件清空一次 | 数据从日志完整抢救 | 关键产物增量落盘(v5载荷已内置) |

---

## 7. 测试与质量基线(当前)

| 套件 | 结果 | 备注 |
|------|------|------|
| 科学测试 mr_science_test | **23/25 (92%)** | 边界钳制✅如实记录无钳制; 稳定性25/30=桥侧节流已定性 |
| 功能回归 func_test | **26/26** | 重启后全绿 |
| 硬件套件 hw_test | 34/39 | 5个失败全部转化为发现(WMI死亡→EC复活路线) |
| GUI 穷举 | 1562 按钮 0 异常 100% | 含新增电源·系统页 |
| CLI 自检 | --temp/--fan/--charge/--set-charge 全绿 | 免管理员 |

---

## 8. 资产清单与一键复现

### 核心产品(根目录, 桌面快捷方式依赖以下精确文件名)
| 文件 | 说明 |
|------|------|
| `mr_gui_v5.py` (v5.4) | 主控台 GUI; EC实时卡+充电滑条走 UWACPIDriver 直写(免管理员) |
| `mr_console.py` | MQTT CLI 客户端(`python mr_console.py gui`=启动GUI) |
| `mr_win_ctrl.py` | Windows原生层(EPP/Boost/rates/HAGS/wifi_band/gpu_wall...) |
| `mr_ec_hw.py` | EC 读写双向 + `_addr_ok()` 白名单守卫(R5教训) |
| `启动MR控制台.bat` | 双击启动(v5.4免提权版); 另有 GPU降压/恢复·一键优化 三个bat |

### 目录结构
- `tools_法证仪器/` — 全部一次性逆向/诊断脚本(35件, 含NO-OP实验、反汇编器、扫描器)
- `data_原始数据/` — 法证JSON/日志/CSV(8件)
- `旧版归档_20260825/` — 旧版测试脚本与历史调研文档(17件)
- `custom_scenarios.json` — GUI场景配置(运行时读写, 必须留根目录)

### 可复现仪器(全部可重复执行)
```bash
python mr_ec_hw.py --temp          # CPU/GPU温度
python mr_ec_hw.py --fan           # 双风扇 duty+RPM
python mr_ec_hw.py --charge        # 充电阈值对
python mr_ec_hw.py --set-charge 90 # 设置停止阈值(带回读保护)
python _ec_sweep.py                # EC全域只读扫描(两采样)
python mr_science_test.py          # 科学测试 25项
python mr_v53_func_test.py         # 功能回归 26项
python _writeec_test.py            # WriteEC NO-OP 定性实验(无害)
```
法证仪器: `_forensic.py/_forensic2.py/_pl1_rescue.py/_ecadmin_full.ps1/_disasm_ec.py/_drv_disasm.py`
数据存档: `_forensic_out.json/_forensic2_out.json/_ecadmin.json/_ec_sweep.json/_uwacpi.sys副本`

---

## 9. 开放问题(下一步候选, 按 ROI 排序)

| # | 问题 | 类型 | 建议 |
|---|------|------|------|
| Q1 | 满充截止物理效果(设90后是否真停在90) | [D]观察 | 日常插电使用中记录电量曲线 |
| Q2 | HEALTHYMODE 三级健康模式的 MQTT 载荷 | 逆向 | 官方电池页点击抓包(协议学习器) |
| Q3 | GPU 温度调节(87钉死)与功耗墙解锁 | 研究 | 经 WriteEC 试探相关寄存器(需先全域比对官方各模式下的差异) |
| Q4 | MQTT BatteryProtection 状态话题无回包原因 | 小 bug | 检查订阅时机/主题名大小写 |
| Q5 | TempRead1/2/3 与 IO/PCI 等其余16导出函数的应用价值 | 探索 | 低优先级, 有需求再逆 |

---

*本快照生成于 EC 逆向收官日。此前历史(法证十案/重启复测/EC终审与复活)详见同目录:
`审计报告_20260825.md` · `实机验证报告_20260825.md`(附录A/B/C/D)。*
