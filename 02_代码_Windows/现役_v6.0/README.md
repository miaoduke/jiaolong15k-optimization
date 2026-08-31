# MR Control Center v6.0 (自制控制台_v6.0_20260826)
**构建**: 2026-08-26 · 基于 v5.4 成果 + 两轮穷尽调研 + 六项实验验证

## 一键启动
双击 **一键启动控制台.bat** （免管理员；自动拉起 GCUBridge）

## v6 新增(vs v5.4)
| 功能 | 通道 | 验证 |
|------|------|------|
| G-Helper 式一屏流 UI | Tkinter 自绘暗色 | 新写 |
| 性能模式四档 | MQTT probe_mode | ✅继承 |
| CPU/GPU 风扇 duty/RPM 实时 | EC(÷2编码修正) | ✅ |
| **自定义16点风扇曲线** | 官方MQTT SET_FAN_SPEED_CURVE_SETTING(固件执行) | ✅协议实证 |
| 强冷开关/恢复默认曲线 | MQTT FAN_BOOST | ✅ |
| **PL1 功耗墙直写** | EC 0x783(HELD实证) | ✅本轮 |
| 充电阈值 60-100 双阈值 | EC 0x7A8/7A9 | ✅ |
| **键盘背光三档** | EC 0x78C bit5-7 | ✅本轮目视 |
| 触摸板禁用/启用 | EC 0x7A6 bit6(NO-OP过;真写请先接外接鼠标) | 🔶 |
| **关机USB充电开关** | MQTT Setting/Control USB_CHARGER_ON/OFF(EC 0x767 bit4) | ✅本轮 |
| PL墙三值实时显示 | EC 0x783-785 | ✅ |

## 安全设计
- EC 地址白名单[0x000-0x7FF]双向守卫(_addr_ok)
- 所有写入读回校验; 曲线走官方通道固件执行, 无仲裁打架
- ec_profiles/mechrevo_gm5bg0e.json — 本机寄存器图谱外置(含验证状态标注)

## 已知边界
- Fn锁/全RGB流光: 异址待DSDT逆向(B类)
- AniMe/XGM/Ally等: ASUS专属硬件不存在(A类, 不做)
- 关机USB充电物理验证: 待下次关机时实测
