# ControlCenter Windows 侧穷尽反编译 × EC逆向分析 交叉对照（2026-08-23）

> 本次工作：Windows 侧穷尽扫描 `C:\Program Files\OEM\机械革命电竞控制台` + 反编译 UWP MSIX 包 + GCUService/GCUBridge 字符串分析，与既有 `EC逆向分析` 目录交叉验证。
> 背景：蛟龙15K (7435H+4060) / Uniwill GM5BG0E / Linux Mint 22.3 + Windows 双系统
> 主分析：`EC逆向分析\ControlCenter逆向报告_20260820.md`（DefaultTool 反编译 + Linux 实测）已非常完整

---

## 一、Windows 侧新确认/补充的寄存器定义（此前文档未完整列出）

### 1.1 RGB 键盘 — 新增寄存器（GCUService.exe 符号全量）
| 符号 | 功能 | 状态 |
|------|------|------|
| `ADDR_RGBKB_LEVEL_DEFAULT_R/G/B` | **默认色寄存器（0x76C-76E）** | 既有文档已确认（只读存储） |
| `ADDR_RGBKB_MUSIC_NO` | **音乐律动号（0x76F）** | 既有文档已确认（0xFE 开/0 关） |
| `ADDR_SINGLEKBL_SUPPORTPOWER` | 单键背光电源支持位 | 既有 0x78E 已覆盖 |
| `ADDR_AP_OEM_BYTE10_CUSTOM_LIGHT_TEST` | 灯光测试（0x727） | 既有文档已确认 |
| `ADDR_BLUEBAR/GREENBAR/REDBAR_CONTROL_BYTE` | RGB 三色条控制字节 | 既有文档未列（本机无灯条，低价值） |

### 1.2 风扇系统 — 新确认（此前未完整）
| 符号 | 功能 | 既有文档 |
|------|------|---------|
| `ADDR_MYFANI_EXTRA_SPEED / MIN_SPEED / MIN_TEMP` | 用户风扇 3 参数（0x79E-7A0） | ✅ 已确认 |
| `ADDR_MYFAN2_L1-L5_PWM` | 用户风扇 5 档 PWM（0x743-747） | ✅ 已确认 |
| `ADDR_MYFAN3_CPU_TAU / GPU_SETTING` | 风扇 TAU/GPU 设置 | 新补充（0x78E 相关） |
| `ADDR_MyFanCCI_Mode_Index / Profile1-3` | CCI 风扇模式表 | 新补充（MyFan3 子模式） |
| `ADDR_MAFAN_CONTROL_BYTE` | 主风扇控制 | 与 0x751 对应 |
| `ADDR_LC_FAN_VALUE / LC_PUMP_VALUE` | 液冷风扇/水泵值（0x7E6-7E7） | ✅ 既有 0x7E6-7E7 已确认 |

### 1.3 功耗/温度 — 新确认
| 符号 | 功能 | 既有文档 |
|------|------|---------|
| `ADDR_GAMING/OFFICE/BATTERYSAVER_PL1/PL2/PL4_D` | 三档 PL 默认值表（0x730-737/0x7A7-7AA） | ✅ 已确认 |
| `ADDR_GAMING/OFFICE/TURBO_TCC_OFFSET_DEFAULT` | 各档 TCC 默认（0x7D8-7DA） | ✅ 已确认 |
| `ADDR_TIMAP_TccOffset_Setting` | **TCC 温度墙偏移（0x786）** | ✅ 已确认（P2 可实测项） |
| `ADDR_CPU_VRM_CURRENT_LIMIT / MAXI` | VRM 电流限制（0x753-754） | ✅ 已确认 |
| `ADDR_ConfigurableTGP_DynamicBoost_CTRL` | cTGP/DynamicBoost 控制（0x743-746） | ✅ 已确认 |

### 1.4 电池 — 新确认
| 符号 | 功能 | 既有文档 |
|------|------|---------|
| `ADDR_BATTERY_CHARGE_LIMIT_UP` | 充电阈值上限（0x7B9） | ✅ 已确认 |
| `ADDR_BATTERY_CHARGE_LIMIT_DOWN` | 充电阈值下限（0x7D0） | ✅ 已确认 |
| `ADDR_BATTERY_ALERT_BYTE` | 电池警报（0x494） | ✅ 已确认 |
| `ADDR_EC_BT1CycleCount_BYTE1/2` | 电池循环次数（0x4A6-4A7） | ✅ 已确认 |

---

## 二、关键新发现（既有文档未覆盖的隐藏功能）

### 2.1 风扇控制字节完整标志（既有文档部分缺失）
GCUService 符号确认（与 Linux 实测 0x751 一致）：
```
MyFanCTLByteFlag:
  Normal_Mode   = 0x00   # 正常
  Turbo_Mode    = 0x10   # 狂暴
  FanBoost_Mode = 0x40   # 风扇强冷（新增确认，既有文档有）
  User_Fan_Mode = 0x80   # 用户风扇
  User_Fan_Level1-5 = 0x81-0x85
  User_Fan_HiMode  = 0xA0  # 高级用户模式
```

### 2.2 风扇智能表结构（GCUService 反编译全量）
```
RamFan1p5 定义: CPU 表1=0xF00 + 表2=0xF10, GPU 表1=0xF30 + 表2=0xF40
F1/F2/F3 三套表: 0xF00/0xF50/0xFA0 起 (RamFan2)
表状态/控制: 0xF5D-5F
```
与既有 Linux 实测完全一致 ✅

### 2.3 TURBO 4 档（既有文档已确认）
GCUService: `TURBO_MODE 1-4`（默认 2）
- Fn+X 实测仅切到 0x78C bits2-3（TURBO=2）
- 官方 4 档 TURBO_MODE 寄存器未解位

### 2.4 OSD 事件码（与既有文档 uniwill-wmi.h 一致）
GCUService 反编译确认（十六进制）：
```
亮度 0x14/0x15、音量 0x36/0x37、静音 0x35、键盘灯 LEVEL0-4=0x3B-3F、
触控板 0x04/05、静音模式 0x06/07、WLAN 0x08/09、蓝牙 0x0C/0D、
摄像头 0x12/13/0x90/91、电源保存 0x31/32、Super锁 0x40/41、
FAN_BOOST 状态 0xA7、灯条状态 0xA6、适配器变化 0xAB、
风扇过热 0xAA、风扇降温 0xAD、RFKILL 0xA4
```

---

## 三、Windows 侧确认的功能清单（UI 可见 vs 隐藏）

### 3.1 本机确认支持（0x765=0xA1 / 0x766=0xB4 实测）
✅ RGB键盘 / 飞行模式 / 风扇增压(FAN_BOOST) / Super键锁 / 中国模式 / 我的电池 / 充电配置文件 / 通用风扇控制 / 风扇表模式

### 3.2 本机不支持（0x765/0x766 无支持位）
⛔ 灯条(LIGHTBAR) / 静音模式(SILENT) / USB充电 / 超频(OVERCLOCK) / 宏键 / 快捷键

### 3.3 Windows 侧 UI 隐藏但代码存在的功能（本机硬件不支持）
| 功能 | 符号 | 本机状态 |
|------|------|---------|
| 灯条 | `ADDR_LIGHTBAR_CONTROL_BYTE` | ⛔ 0x765 无支持位 |
| 静音模式 | `ADDR_SILENTMODE_STATUS_BYTE` | ⛔ 0x766 无支持位 |
| 液冷 | `ADDR_LC_FAN_VALUE/PUMP_VALUE` | ⛔ 无液冷硬件 |
| USB 充电 | `ADDR_767 bit4` | ⛔ 无支持位 |
| 第二GPU功耗 | `_S2` 系列参数 | ⛔ 无第二独显 |

---

## 四、交叉验证结论

### 4.1 双方一致（已互相印证）
- RGB 键盘协议：0x769-76B + 0x767 bit5/bit7 + 0x7C5 ✅
- 风扇表结构：0xF00-0xF5F 六块 ✅
- 风扇控制：0x751 全标志 ✅
- 充电阈值：0x7B9 UP / 0x7D0 DOWN ✅
- TCC 温度墙：0x786 ✅
- PL1/2/4：0x783-785 + 各档默认表 ✅

### 4.2 新补充（本报告）
- `ADDR_MYFAN3_CPU_TAU/GPU_SETTING`、`ADDR_MyFanCCI_*`（MyFan3/CCI 子模式）
- RGB 三色条控制字节（本机无灯条，低价值）
- GCUService 反编译符号全集（供后续寄存器对照）

### 4.3 既有生态项结论（引用，不重复）
- 已做：RGB/灯效/风扇表/平台模式/温度墙/充电阈值/硬件开关——官方 90%+ 覆盖
- 已否定：CPU 超频（SMU 锁死）、用户风扇（驱动覆盖）、单键背光（0x78C 风险）、独显直连（BIOS 级）、灯条/静音（无支持位）
- 唯一可实测新项：**TCC 温度墙 0x786**（写偏移只降温不升温）

---

## 五、对既有结论的更新

1. **确认** `0x786` TCC 温度墙是官方唯一未利用的可实测项（GCUService `ADDR_TIMAP_TccOffset_Setting` 确认）
2. **确认** 摄像头 Fn 开关（OSD 0x12/13）低风险可加（acpid）
3. **无新增硬件可测项**——本机硬件限制（灯条/静音/超频）与既有结论一致
4. **本机最值项仍是**：键盘灯电量显示、GPU 风扇表扩展、平台模式切换 UI

## 六、保留的可执行清单（本机）
| 优先级 | 项 | 依据 |
|--------|----|------|
| 高 | TCC 温度墙 0x786 实测（写 5 读回→恢复） | 官方唯一未利用项 |
| 高 | 摄像头 Fn 开关（acpid） | 低风险补充 |
| 中 | GPU 风扇表 0xF50 扩展 | 驱动未覆盖的扩展点 |
| 中 | 键盘灯电量显示 | 官方 BatteryPercent 效果 |

---

*本报告由 Compose-Max 于 2026-08-23 生成，整合 Windows 侧 GCUService 反编译 + 既有 EC 逆向分析*