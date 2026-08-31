# ControlCenter 5.17.49.19 官方控制台反编译报告 — 蛟龙15K (GM5BG0E)

> 日期: 2026-08-20 | 来源: 出厂自带/ControlCenter_5.17.49.19_Mechrevo.zip + Windows 系统分区(Program Files/OEM/机械革命电竞控制台)
> 方法: msixbundle 解包 + ilspycmd 8.2 反编译(.NET) + strings(原生/AOT)

## 一、软件架构（三层 + 原生驱动）

```
GamingCenter3_Cross.exe (UWP 主程序, .NET Native AOT — 不可 IL 反编译)
        ↓ MQTT (M2Mqtt.Net.dll, topic: Fan/Control, Fan/Status...)
SystrayComponent.exe (托盘, .NET — 已反编译, 31 文件 3452 行)
        ↓ WMI/服务调用
GCUService.exe (核心服务, .NET 12MB — 方法体被混淆剥离, 签名完整, 421 文件 7.5MB)
        ↓ DeviceIoControl (IOCTL_GPD_ACPI_ECREAD/ECWRITE 等)
ACPIDriverDll.dll (原生 C++ 4.1MB — GPD ACPI 驱动接口, SMRW: READ=0xBB/WRITE=0xAA)
        ↓
EC/WMI 硬件
```

- 身份接口: GetProjectIdFromEC/GetSystemId/GetModuleId/GetROMId/GetAdapterWatt(适配器功率)
- IOCTL 全集: 端口读写/ACPI CM/EC READ/WRITE/MMIO/PCI/温度 TMP1-3/SmartApcTable(智能风扇表)/CustomRW

## 二、RGB 键盘灯协议 — 官方确认（与我们逆向完全一致）

| 常量 | 地址 | 说明 |
|------|------|------|
| EC_RGBKB_LEVEL_R/G/B | 0x769/76A/76B | Level 值(0-50) — **与我们的协议一致 ✓** |
| EC_RGBKB_LEVEL_DEFAULT_R/G/B | **0x76C/76D/76E** | **默认色寄存器(新发现, 未实测)** |
| EC_TRIGGER_BYTE | 0x767 | 触发器 — **bit5(32)=颜色触发 ✓ bit7(128)=Welcome/彩虹 ✓** |
| EC_SUPPORT_BYTE2 | 0x766 | 支持标志 — bit2(4)=RGB 键盘支持位 |
| EC_PROJECT_ID_BYTE | 0x740 | 项目 ID — GM5 系列=17 (GM5MU1Y) |
| EC_SINGLEKBL_LEVEL_CHG | HID cmd 0xB4 | 单键键盘灯 Level 变化(HID 通道, 高级机型) |

- **RGBKB_Effect 28 种效果**: Single/Breathing/Wave/Reactive/Rainbow/Ripple/Raindrop/Neon/Marquee/Stack/Impact/Spark/Aurora/Music/UserMode/Gaming/Flash/Mix/RippleO/Alphabet/StarHitting/StarSpark/Thinking/Manual/BatteryPercent/ColorfulWave/Dawn
- **RGBKB_Type 分区**: MEZone_1st/2nd_101/2nd_102/2p1nd_85-88/2p2nd/Lighbar/3nd/... **本机=MEZone_2nd_101**(101 键 2 分区)
- 注册表(MEZone_2nd_101): save_light=36(Level 制证实)、save_effect=3/5(效果编号)、ColorBlocks=7(7 段彩虹: 红橙黄绿蓝青紫)、save_speed/direction
- 灯效接口: SetEffectALL(mode, effect, light, speed, direction, color, save, backgroundcolor, alphabet)

## 三、风扇/性能模式 — 官方标志位(对照我们逆向)

| 常量 | 值 | 说明 |
|------|-----|------|
| MyFanCTLByteFlag.Normal_Mode | 0x00 | 正常模式 |
| MyFanCTLByteFlag.Turbo_Mode | 0x10 | 涡轮模式 |
| MyFanCTLByteFlag.FanBoost_Mode | **0x40** | **风扇增压(新发现, 可实测)** |
| MyFanCTLByteFlag.User_Fan_Mode | **0x80** | **用户风扇模式位(我们的曲线注入对应此位)** |
| User_Fan_Level1-5 | 0x81-0x85 | 用户风扇 5 级 |
| User_Fan_HiMode | 0xA0 | 高级用户模式 |
| TURBO_MODE 1-4 | 1-4 | **4 档涡轮(新发现: 我们 Fn+X 实测三档, 官方定义 4 档)** |
| MyFan2SpeedByteFlag | 0-0x8C | 2 速风扇 PWM 值(60-140 十进) |
| FAN_MODE | 0/1/2 | NORMAL/BOOST/CUSTOMIZE |
| FAN_GAMING/OFFICE/TURBO/CUSTOM | 0-3 | 4 种风扇场景 |

## 四、官方 EC 寄存器地图(ECSpec.cs — 十进制→hex)

| 地址 | 用途 |
|------|------|
| 0x402-0x40A | 电池设计容量/电压(BIF) |
| 0x434-0x438 | 电池充放电率/剩余容量/电压(BST) |
| 0x456 | SystemID |
| 0x464/0x46B-46C | 主风扇 RPM / 第二风扇 RPM |
| 0x730-0x737 | Gaming/Office 档 PL1/PL2/PL4/D 默认值 |
| 0x740 | ProjectID |
| 0x743-0x746 | **cTGP 控制/值/TotalPowerTarget/最大 TGP(官方地址)** |
| 0x751 | 主风扇控制字节 |
| 0x753-0x754 | CPU VRM 电流限制/最大电流限制 |
| 0x75B-0x75C | 主风扇左/右占空比 |
| 0x765-0x766 | 支持字节 |
| 0x771-0x772 | ROMID |
| 0x783-0x785 | PL1/PL2/PL4 设置值 |
| **0x78C** | **SINGLEKBL_ENABLE(单键键盘灯使能 — 与我们逆向的 0x78C 亮度/TURBO/POWER 复用)** |
| 0x7D0 | 电池充电下限 |
| 0x7D8-0x7DA | Gaming/Office/Turbo 档 TCC 偏移默认值 |
| 0x7E6-0x7E7 | 水冷风扇/水泵(高级机型) |

## 五、OSD 事件编号(WMI 事件值 — 对照驱动 notifier)

KB_LED_LEVEL0-4=59-63、BREATH_LED_ON/OFF=57/58、SILENT=6/7、BRIGHTNESS=20/21、WINKEY_LOCK=64/65、VOLUME=54/55、MUTE=53、TPON/OFF=4/5、WLAN=8/9、BT=12/13、RADIO=26/27、POWERSAVE=49/50、MENU=52/56/66、CAMERA=18/19/144/145、AIRPLANE=164

## 六、其他能力发现

- GPU 超频 UI: GpuCoreClockOffset/HWOCGpuMemoryClockOffset(官方支持 — NVIDIA 驱动锁 OC, Linux 不可用)
- IsCommercial_HAVE_20DB: 20dB 静音模式标识
- WhisperMode_Define: 静音档定义(需验证本机 EC 支持)
- GetTouchPadLedStatusFromEC: 触控板 LED 状态(本机触控板有 LED?)
- KeyboardManager: PowerToys 键盘管理器(重映射/宏 — Linux 可用 keyd/系统快捷键替代)
- SmartApcTableCtrl: 智能风扇表控制(对应我们的 0x0F00 六表)
- MQTT 通信架构(Windows 内部架构 — Linux 无需)

## 七、可借鉴/可实现清单(Ponytail 评估)

| 项 | 价值 | 成本 | 说明 |
|----|------|------|------|
| **0x76C-76E 默认色寄存器实测** | 高 | 低 | 若生效: 开机颜色恢复变 EC 硬件级(替代 save/restore 服务) |
| **FanBoost 0x40 实测** | 中 | 低 | 风扇增压模式位 |
| **WhisperMode 静音档验证** | 中 | 低 | 官方定义存在, 验证本机 EC 是否支持 |
| **BatteryPercent 灯效** | 中 | 低 | 电池电量→键盘灯颜色(实用) |
| User_Fan_Level1-5 | 低 | 低 | 5 级用户风扇(我们的曲线注入已覆盖) |
| TURBO_MODE 4 档 | 低 | 低 | Fn+X 三档 vs 官方 4 档(寄存器未定位) |
| GPU 超频 | — | — | NVIDIA 锁 OC, 不可行 |
| 键盘宏/重映射 | 低 | 中 | PowerToys 思路, Linux 用 keyd 替代 |

## 八、反编译工具链备忘

- ilspycmd 8.2.0.7535 (dotnet tool global, DOTNET_ROLL_FORWARD=LatestMajor)
- monodis 对 .NET Native AOT 无效("no managed metadata")
- GCUService.exe 方法体被混淆剥离(签名可用), 原生 ACPIDriverDll 需 IDA/Ghidra 反汇编(未做)
- 源码输出: /tmp/opencode/cc/gcusvc (421 cs), /tmp/opencode/cc/src3 (Systray 31 cs)

## 九、0x76C-76E 实测结论（2026-08-20）

- 写入蓝(0,0,32)读回成功但灯色不变；重启后活动色=0x769-76B=1,1,1(灰白微光, EC 初始化值), 0x76C-76E 被 EC 重置回青(0,50,50)
- **0x76C-76E 非持久默认色存储, 不控制开机色 — 方案淘汰**
- kbd-rgb-restore 服务为唯一开机颜色恢复机制
- 附: ec_tool.py 已修复(/dev/mem 通道读 EC 区全 FF 不可靠, 统一 RKBC/WKBC; RKBC 参数 lo/hi 分字节, 返回数组首字节=值); Fn+X 实验"0x78C 恒 0xFF"为假象, 真实 0x78C=0x28(亮度1+TURBO=2), TURBO 档位疑似 0x78C bits2-3

## 十、性能模式寄存器排查结论（2026-08-20）

- Fn+X + 专用性能键 3 次按键: 0x78C/0x751/0x7C6/0x7D8-7DA/0x730-737 **全部寄存器不变** (0x78C=0x88, 0x751=0x10, 0x7C6=0x04, 0x7D8-7DA=0x63, 0x730-737=41 41 64 01|23 23 64 01)
- **结论: 性能模式状态在 EC 固件内部/WMI 层, 不反映在 EC 寄存器** — Fn+X 硬件切换实测有效(70↔92°C), Linux 按键即切
- Uniwill WMI GUID 系列 ABBC0F6A-ABBC0F72 (10个) = 官方控制台 WMI 接口; "Uniwill WMI hotkeys"=input14
- 程序化切档需 WMI 方法号(源码在 /tmp 重启已丢, 需重反编译 Windows 分区 GCUService)