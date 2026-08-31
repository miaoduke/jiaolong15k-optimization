# FanControl 探索报告 — 能为本机解锁什么
**日期**: 2026-08-25 · **对象**: FanControl 271 (自带 LibreHardwareMonitorLib v?) + LHM v0.9.6 官方版交叉验证
**结论先行**: 风扇控制零增量; 但白送两组免管理员传感器数据源, 建议纳入 v6.0。

## 实验矩阵
| 实验 | 权限 | 结果 |
|------|------|------|
| FanControl userConfig 解析 | - | \`EmbeddedEC:true\` 为其后端开关; Controls/FanCurves 全空=未配置任何控制 |
| LHM(FanControl自带, net10) PS直调 | 免管 | ❌ .NET runtime 缺失(机器无 dotnet, 自包含部署不可外借) |
| pythonnet 桥 | 免管 | ❌ PYTHONNET_RUNTIME 无效路径 |
| **LHM v0.9.6 net472 官方版 PS直调** | 免管 | ✅ 6硬件115传感器 |
| 同上 | **管理员**(UAC一次) | ✅ 相同6硬件 — **无SuperIO增量** |

## 本机实测传感器清单(LHM视角)
### ✅ 可用增量(免管即得 → v6.0 SensorBus 数据源)
- **GPU 细分**: Hot Spot 44.6°C / Memory Junction 48°C / Package 功耗 W / PCIe Rx-Tp 吞吐 / 显存三件套 / D3D引擎负载×12
- **电池遥测**: 设计容量62.32Wh·满充62.32Wh(**损耗0%**)·电压14.51V·电流2.38A·**放电功率34.55W**·续航估计81min
### ❌ LHM 拿不到(管理员也一样)
- 风扇转速/PWM(Uniwill 走EC, 非SuperIO芯片; LHM Motherboard 下无子硬件)
- CPU 温度(Zen3+ SMN 读取失败 Tctl=0) → **继续用我们 EC 0x43E(µs级,更优)**
- EC 寄存器(v0.9.6 无 EmbeddedEC 类; FanControl 的 EmbeddedEC 后端未适配 Uniwill)

## 判决
1. **风扇**: FanControl 对本机无能为力 → 我们的 UWACPIDriver 直调仍是唯一/最优通道
2. **采纳**: \`mr_sensor_bus.py\` 以 PS Add-Type(net472 LHM) 为后端拉取 GPU细分+电池遥测, 免管µs→100ms级轮询
3. **方法论沉淀**: 中文路径经 UAC 提权传参会编码崩坏 → 内核类实验一律放 ASCII 目录(C:\LHMtmp 模式), 分阶段 trace 日志定位卡点(本次 addtype FAIL 即靠此定位)
