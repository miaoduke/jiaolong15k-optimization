# MR Console —— 机械革命电竞控制台（自制全功能版 v5.3）

> 基于官方 ControlCenter 5.17/5.56 逆向成果构建
> 零第三方依赖（原生 MQTT 3.1.1 + tkinter + ctypes）· Python 3.12
> v5.3 (20260825): 新增「电源·系统」页 · 智能场景自动应用 · 场景保存/应用闭环 ·
> E1功耗墙回读验证 · E2 EC实验入口 · 修复CLI断链/EC仪表键值/RPM字节序

## 启动
```powershell
python mr_console.py gui          # 图形界面(11个标签页)
python mr_console.py status       # CLI 全状态查询(需GCUBridge)
python mr_console.py monitor      # 实时监控
python mr_console.py power epp    # ★v5.3 Windows电源控制(免MQTT·不依赖桥)
python mr_v53_func_test.py        # v5.3 回归自检(26项)
```

## 标签页结构（11页）

| 标签页 | 功能项 | 支持度 |
|--------|--------|--------|
| 总览 | 模式大卡×4直切 · 仪表卡×5(含EC实时/GPU实时) · 六大状态查询 | ✅ |
| 性能中心 | OC滑条×11释放即发+撤销+默认钮 · 风扇强冷 · GPU降压锁频2100/2400 | ✅ |
| 风扇曲线 | 曲线读取 · 起转转速 · 恢复默认 | ✅ |
| 灯光键盘 | RGB颜色直发 · 26灯效 · 亮度5档 · Win键/Fn/小键盘/触控板 | ✅ |
| 显示器 | 5显示模式 · 游戏6参数 · OSD · 亮度WMI · 刷新率165/60 · TGP功耗墙(带回读) | ✅ |
| 电池电源 | HEALTHYMODE · 充电阈值EC直写(0x7B9实测) · ⚡四场景一键全栈 | ✅ |
| **电源·系统**★new | EPP/Boost/MaxState AC-DC双滑条(隐藏参数/qh实测) · 刷新率动态枚举 · HAGS/游戏模式/GameDVR/WiFi偏5G/节电计划 · GPU功耗墙140/115回读验证(E1) · 智能场景自动开关 | ✅ |
| 外设 | ServCMD 15条唯一入口 | ✅ |
| 协议学习·手动 | 抓包→入库→回放 · 手动发布 · 📸场景保存 + 📂场景应用闭环(v5.3) | ✅核心 |
| 🔴研究模式 | ⛔21项集中 + E2实验(0x7C1/0x7C2写读) | ⛔专页 |
| 日志 | 全指令轨迹 | ✅ |

## CLI power 子命令（v5.3 新增，免MQTT）
```
power epp [AC DC]          power boost [off|on|agg|eff|effagg AC DC]
power maxstate [AC DC]     power rates / setrate N / bright N
power hags on|off          power gamemode on|off
power gpuwall W / gpuinfo
```

## 📊 权威快照
**[Windows生态科学总览_v54.md](Windows生态科学总览_v54.md)** — 分层架构·通道矩阵

## 🔍 竞品调研(20260826)
**[调研成果总集](调研成果总集_20260826.md)** ← 总入口
- 矩阵12项目 + 补充4项(mechrevo三社区项目·ThrottleStop闭源参照) · 四种架构流派 · roj234 同通道先行者寄存器表交叉验证
- 重大发现: PWM地址双镜像(0x461≡0x75B)·duty编码=raw÷2·功耗墙活体(0x783-85)·duty显示bug待修
- 细节: FanControl源码穷尽 / 解锁探索报告 / 第二轮重大发现 / v6.0评审与GHelper照搬UI方案
- 专项: [A类硬件不存在清单+观感边界五方案](A类硬件清单与观感边界解决方案_20260826.md)(推荐Tkinter先行+F2 WinForms壳两阶段)
- 专项: [待解锁与B类科学实现路线图](待解锁与B类科学实现路线图_20260826.md)(六步NO-OP模板·U1-U6+B1-B3逐项路径·含新发现的关机USB充电)·地址基线·已证结论(K1-K12)·风险登记簿·复现命令(20260825)

## ⚖️ 铁律(用户令,永久生效)
- **单次任务一次性提权**: 所有需要管理员的操作必须打包进**单一提权会话**
  (当前唯一载荷: `_ecadmin_full.ps1`), 禁止零散多次UAC打扰。
- 批处理文件一律纯ASCII(cmd按ANSI解析,UTF-8中文必乱码);
  中文输出只允许出现在PowerShell侧或日志文件内。

## 已知问题(20260825实测)
- 🎉**EC直读已复活(v5.4)**: 经官方 UWACPIDriver 的 ACPIDriverDll.dll ReadEC(int addr) 直读,
  免管理员、数据鲜活(CPU温度/双风扇转速占空比)。旧 AcpiTest_WMI 口确认弃用(恒零铁案)。
- 🎉**EC读写双向打通(v5.4)**: ReadEC(int addr)/WriteEC(int addr,int value) 双签名经反汇编+
  零破坏实验定案(报告附录D); 充电阈值(0x7A8起始/0x7A9停止)读写功能回归, 全部免管理员。
- 📜 历史教训归档: 20260825 错误签名试探致内核崩溃重启一次; 方法论=先静态证明无指针解引用, 再做NO-OP实验。
- GPU功耗墙140W已被管理员权限仲裁为驱动拒绝(vBIOS锁定),按钮仅存验证入口
- CloseTimer/键盘亮度无回读通路(盲写);HEALTHYMODE单发不翻档(官方三档载荷待抓包)

## 安全设计
- 全局写入锁 + 研究页独立使能，双开关隔离危险操作
 - ⚠️ v5.3法证实测：服务端**无**钳制(PL1=200被原样接受)——GUI滑条边界是唯一防线；
   wire键与状态键不同名(写入PL1·回显CPU_PL1)；模式切换会重载OC档案默认值；
   滑条全部"释放即发+异步回读验证"
- 注册表 HKLM 写入经 UAC 提权；GPU 功耗墙设定后强制回读比对(E1)
- 关机指令(System_OFF)弹确认框二次警示

## 文件
- `mr_console.py` 协议层(MiniMQTT零依赖)+业务层+CLI(含免MQTT power分支)
- `mr_gui_v5.py` GUI v5.3（11标签页）
- `mr_win_ctrl.py` ★v5.3 Windows原生层: powercfg隐藏参数/DEVMODE完整结构/注册表/nvidia-smi解析
- `mr_ec_hw.py` EC组合通道(MQTT>WMI>RTCore64)
- `launch_v5.py` 管理员提权启动器
- `mr_science_test.py` 协议科学测试 · `mr_gui_autotest_v52.py` GUI穷举回归
- `mr_v53_func_test.py` ★v5.3 功能回归26项
- `learned_commands.json` 协议学习产物 · `custom_scenarios.json` 自定义场景库
