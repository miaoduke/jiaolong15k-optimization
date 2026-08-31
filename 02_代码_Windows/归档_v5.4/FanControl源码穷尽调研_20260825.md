# FanControl/LHM 源码穷尽调研 — 权限问题的源码级规避
**日期**: 2026-08-25 · 用户命题: "从开源项目源码穷尽调研规避本机权限限制" — 完全成立且已执行

---

## 一、开源度查证(第一发现)
| 组件 | 开源状态 | 可调研性 |
|------|---------|---------|
| **FanControl 主程序** | ❌ **闭源**(Rem0o 名下仅 Releases/i18n/插件仓) | 只能黑盒 |
| FanControl 插件(HWInfo/Dell/ADLX/IntelCtl) | ✅ C# 开源 | 参考价值: 插件架构模式 |
| **LibreHardwareMonitorLib** | ✅ MPL2 全开源(master 分支含未发布新特性) | 本轮主矿 |

## 二、悬案告破: "EmbeddedEC:true" 到底是什么
- v0.9.6 release 库中**不存在**任何 EmbeddedEC 类 → FanControl 271 配置项指向 LHM master 新代码
- 源码实证 \`EmbeddedController.cs\`(32KB): 映射表仅覆盖 **BoardFamily.Amd400/500/600/800 桌面主板**
  (芯片组温度/VRM温度/水冷进出水温/水流量/可选CPU风扇 —— 分流器玩家向)
- **判决: 该功能与笔记本 Uniwill EC 零关联**, 本机零增量的根因就此闭环

## 三、LHM 的 EC 访问协议(源码级)
\`\`\`
端口:   0x66=命令 0x62=数据 (ACPI 规范 ch.12 标准协议)
命令:   RD_EC=0x80 WR_EC=0x81 BE_EC/BD_EC=0x82/83 QR_EC=0x84
安全层: GlobalMutex(WaitEc 10ms) + 重试×5 + OBF/IBF 等待(ASUS 兼容回退)
寻址:   16位 = bank<<8 | index, 经 0xFF 寄存器切 bank
内核:   PawnIO 签名驱动做端口 IO (WinRing0 的继任者)
自评:   源码注释原话 "unsafe but universal ... possible race condition
        between this application and the PC firmware"
\`\`\`
**对比结论**: 我们的 UWACPIDriver 路线经厂商 ACPI 规范接口访问, 天然规避 LHM 自认的竞态风险;
其"bank 切换"概念已被 ACPIDriver 的 16 位地址空间隐含覆盖(0x100+ 地址实测可读)。

## 四、SuperIO/CPU 温度路线源码确认
- \`LpcIO.cs\`(29KB) 芯片 ID 表: ITE/Nuvoton/Fintek 桌面 SuperIO 检测 — Uniwill 笔记本不挂此类芯片(风扇走EC), 与本机实测"管理员下 Motherboard 亦无子硬件"互证
- AMD CPU 温度走 SMN(PCI 0x00:00.0 + SMN 地址), 本机 Zen3+ 读 0 为 LHM 已知短板
- ⇒ **第三方通用库对本机传感的增量天花板 = GPU细分 + 电池遥测**(上轮已采纳), 源码级复核无遗漏

## 五、方法论沉淀
> **权限墙 ≠ 调研墙**: 本机跑不了的 ring0 路径, 其实现细节在开源仓库里全裸。
> 本次以 raw.githubusercontent 直拉 4 个 .cs 文件(~47KB)完成, 零提权、零风险、可复现
> (脚本 tools_法证仪器/_fc_lhm_source.py + _lhm_ec_pull.py)

## 六、行动项更新(v6.0)
1. SensorBus 维持上轮采纳(GPU细分+电池遥测, 免管)
2. 否决"借 PawnIO/WinRing0 补风扇控制"设想 — ACPIDriver 更优, 无必要引入第二内核驱动
3. 曲线引擎借鉴其 Mutex+重试+bank 抽象写法(纯软件层)
