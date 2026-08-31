# 蛟龙15K (Ryzen 7 7435H + RTX 4060) 电源与风扇控制 · 逆向与自制控制台

> **English (top-level overview)** — The primary documentation of this repo is written in **Simplified Chinese**. This short section summarizes what the project is and the key caveats before you dig in.

**Jiaolong 15K (Mechanical Revolution) — power & fan control.** This is a hobby project that reverse-engineers the official "gaming console" software of the Mechrevo Jiaolong 15K (AMD Ryzen 7 7435H, Zen3+, 35W; RTX 4060 Laptop; Uniwill `GM5BG0E` motherboard, no iGPU). It documents the MQTT protocol, the EC (Embedded Controller) register map, and builds a self-made replacement console (Python on Windows, GTK on Linux) that reads sensors and writes fan curves / power limits.

**Please note before using anything here:**
> - This is an **unofficial reverse-engineering study** — it is **not affiliated with, or endorsed by, Mechrevo or Uniwill**.
> - It **directly reads and writes EC and SMU registers**. A wrong value can destabilize the system or damage hardware. **Use at your own risk.**
> - The repo ships **conclusions, register maps, protocol specs and methodologies only** — it deliberately does **not** include OEM binaries, decompiled/dump artifacts, credentials, or personal machine data. Raw capture/payload files and credential-extraction scripts were moved out of the public repo.
> - Superseded conclusions are **kept and annotated, never deleted**; trust the latest module version and the README "known issues" section.

> **机型**：机械革命 蛟龙15K / AMD Ryzen 7 **7435H（Zen3+，35W）** + RTX 4060 Laptop
> **主板**：Uniwill **GM5BG0E** / ProjectID=16 / **无 iGPU（dGPU only）**
> **系统**：Windows 11 Pro 26200 + Linux Mint 22.3 双系统

> **⚠️ 免责声明（使用前请知悉）**
> - 本项目为**对特定个人机型的逆向研究与自制优化工具**，与机械革命 / Uniwill 官方**无任何关联、非官方支持**。
> - 本项目**直接读写 EC 寄存器与 SMU 功耗寄存器**，错误配置可能影响系统稳定性甚至硬件；**风险自负**，请理解并接受风险后再使用。
> - 项目含针对厂商专用软件/固件的**逆向研究结论**，仅供个人研究与学习；**未获授权不得再分发任何厂商源码/二进制/反编译原文**。厂商保留各自版权与商标。
> - 被推翻的旧结论一律**保留并标注**而非删除，请以子模块最新版本与本 README「已知问题」为准。

项目记录了对该机型官方「电竞控制台」的**协议逆向、EC 寄存器测绘、以及自制替代控制台**的完整过程。
所有结论均基于实机实测，并保留了纠错台账——**被推翻的旧结论不删除，而是明确标注**，避免重复踩坑。

---

## ⚠️ 免责声明

- 本项目为**个人学习与设备自用**性质的逆向工程记录，不针对任何厂商构成竞争用途。
- 文档中涉及的 **EC 寄存器写入、SMU 功耗墙调整、风扇曲线直写** 等操作**可能损坏硬件或缩短寿命**。
  请自行承担风险；作者不对任何损失负责。
- 仓库**不包含**任何 OEM 专有二进制、反编译产物或固件镜像（见下文「未公开内容」）。
- 所有可能识别到具体设备的凭据、用户名、路径均已脱敏。

### 🔬 内容分层原则（公开 vs 私有）
本仓库采取「**只公开结论与方法论，不公开破解工序/取证原文**」的分层策略：
- **公开层（00~04）**：仅保留可复用的 **结论、寄存器映射、协议规范、方法论** 与自写代码，用于说明"能做什么、结论依据是什么"。
- **私有层（`_private_不上传/`，不入库）**：保留**逆向破解的具体工序**（抓包样本、字符串 dump、OEM 注册表快照、解密/取凭据脚本、反编译踩坑细节），因这些涉及厂商专有内容且个资敏感，**不回显、不随公开仓发布**。
- `01_协议_逆向成果/*.txt 抓包样本` 与 `get_cred*/get_key*` 等取证脚本已在迁移/标注为**不公开**；公开文档仅保留协议**字段规范与结论**，不含原始抓包与凭据。
- 对外请把本仓库视为「**方法论参考**」而非「破解工具包」。如需完整取证细节，属私有授权范围。

> 若你发现公开层仍残留逆向破解原始内容（原始抓包、OEM 原文、取凭据脚本），请按 `04_过程_文档归档/旧目录地图_20260825.md` 的迁移规则移入 `_private_不上传`，或提交 Issue 提醒维护。

---

## 📁 目录结构（按知识资产类型分层）

分类依据：**证据等级递减 + 复用性递减**。越靠前越接近「可直接采信的结论」，越靠后越接近「过程记录」。

| 层级 | 目录 | 内容 | 定位 |
|------|------|------|------|
| **L1 结论** | `00_结论_已确证/` | 状态快照、终局结论、纠错台账、审计、三份全量清单 | **先读这里** |
| **L2 协议** | `01_协议_逆向成果/` | MQTT 协议规范、DefaultTool 结论、EC/ACPI 参考源（取证原文已迁私） | 可复用的技术规范 |
| **L3 代码** | `02_代码_Windows/` | 现役 v6.0 / 系统重装恢复方案 / 归档 v5.4 / JCC-Win 原型 | 可直接运行 |
| **L3 代码** | `03_代码_Linux/` | jcc_console v2.3、三档与温控脚本、键盘固件修复、实验脚本 | 可直接运行 |
| **L4 过程** | `04_过程_文档归档/` | 项目过程文档、历史报告、设计提案、旧目录地图 | 历史与决策轨迹 |
| — | `_private_不上传/` | **不入库**，见 `.gitignore` | — |

```
00_结论_已确证/          11 文件    — 状态快照 / 终局结论 / 全量清单
01_协议_逆向成果/         9 文件    — MQTT 协议规范 / DefaultTool 结论 / EC-ACPI 参考（取证原文已迁私）
02_代码_Windows/        212 文件    — 现役_v6.0 / 恢复方案 / 归档_v5.4 / 原型_JCC-Win
03_代码_Linux/           47 文件    — jcc_console / 脚本 / 固件修复 / 实验 / 实测数据
04_过程_文档归档/        25 文件    — 项目过程 / 历史报告 / 提案
```

---

## 🚀 快速导航

> **Quick navigation (EN)** — the full tables below are in Chinese; this is the English summary. All results are from physical-machine testing.

**What this machine can / cannot do:** see `00_结论_已确证/全量清单/` (Windows 165 items / Linux 54 / merged 124).
**Current runtime state snapshot:** `00_结论_已确证/本机生态当前状态_20260828.md`.

**Key verified conclusions (EN summary):**

| Topic | Result |
|------|--------|
| CPU undervolt | ⛔ **locked by SMU firmware** (`ryzenadj` rejected on all three channels, identical on both OSes) |
| GPU undervolt | only via MSI Afterburner manual VF curve; vBIOS power cap locked at 115 W |
| Charge limit | ⚠️ **writes persist & read back consistently on Windows, but the firmware does not enforce it** (still charges to 100% in practice). Threshold regs `0x7B9`/`0x7D0` read back the *threshold*, not the SoC |
| SMU power limits | ✅ `stapm` / `fast-limit` / `slow-limit` / `tctl-temp` writable; defaults STAPM 80 W / FAST 100 W / Tctl 99°C |
| Fan | ✅ official MQTT `SET_FAN_SPEED_CURVE_SETTING` writes a 16-point curve (firmware-enforced) |
| Keyboard backlight | ✅ 3 levels, EC `0x78C` bits 5–7 |

**Key EC registers (EN; full map in `00_结论_已确证/Windows侧交叉对照_EC寄存器_20260823.md`):**

| Addr | Meaning |
|------|---------|
| `0x43E` | CPU temperature |
| `0x44C` | GPU temperature (`0x44F` is **deprecated**; older docs still referencing it are out of sync) |
| `0x461` / `0x469` | fan duty |
| `0x751` | fan control |
| `0x7B9` / `0x7D0` | charge thresholds (read back = threshold, not SoC) |
| `0x7A6` | ⚠️ **arbitrated on hardware (2026-08-30): writable flag bit, NOT a power sensor.** Writing `bit6` (0x40) succeeds and reads back the written value, then reverts; during a 2.5 s CPU-full-load run (GPU power 2.50→2.91 W) `0x7A6` stayed at 9 with no response. No load response + writable ⇒ not a "live power W" register; using it as touchpad `bit6` in `mr_gui_v6` is legitimate. The old "live power" claim is retracted |
| `0x7A8` / `0x7A9` | ⛔ deprecated (early wrong addresses) |

详细中文表格见下方「重点结论」与「关键 EC 寄存器」。

**想了解这台机器能做什么、不能做什么** → `00_结论_已确证/全量清单/`（Windows 165 项 / Linux 54 项 / 合并 124 项）

**想知道当前运行状态** → `00_结论_已确证/本机生态当前状态_20260828.md`

**重点结论（均已实测）**：

| 主题 | 结论 |
|------|------|
| CPU 降压 | ⛔ **SMU 固件锁死**（`ryzenadj` 三通道均 rejected），双系统一致 |
| GPU 降压 | 唯一途径 = MSI Afterburner VF 曲线手动；vBIOS 功耗墙 115W 锁死 |
| 充电限制 | ⚠️ **Windows 侧写入持久、读回一致，但固件不执行**（实测仍充至 100%）。阈值寄存器 `0x7B9`/`0x7D0` 回读的是**阈值**而非 SoC |
| SMU 功耗墙 | ✅ `stapm` / `fast-limit` / `slow-limit` / `tctl-temp` 可写；默认 STAPM 80W / FAST 100W / Tctl 99°C |
| 风扇 | ✅ 官方 MQTT `SET_FAN_SPEED_CURVE_SETTING` 可写 16 点曲线（固件执行） |
| 键盘背光 | ✅ 三档，EC `0x78C` bit5-7 |

**关键 EC 寄存器**（详见 `00_结论_已确证/Windows侧交叉对照_EC寄存器_20260823.md`）：

| 地址 | 含义 |
|------|------|
| `0x43E` | CPU 温度 |
| `0x44C` | GPU 温度（`0x44F` **已废弃**，旧文档仍在使用的属未同步） |
| `0x461` / `0x469` | 风扇 duty |
| `0x751` | 风扇控制 |
| `0x7B9` / `0x7D0` | 充电阈值（读回=阈值，非 SoC） |
| `0x7A6` | ⚠️ **实机仲裁（2026-08-30）：可写标志位，非功率传感器**。实测：写 `bit6`(0x40) 成功且回读=写入值、写后即恢复原值；CPU 满载 2.5s（GPU 功率 2.50→2.91W）期间 0x7A6 恒为 9 无响应。负载零响应 + 可写 → 判据不支持「实时功率 W」，现役 `mr_gui_v6` 用作触摸板 `bit6` 属合理用法。原「实时功率」结论撤回 |
| `0x7A8` / `0x7A9` | ⛔ 已废弃（早期误判地址） |

---

## 🪟🐧 双系统能力对比（Windows vs Linux）

> 两台系统都**直接读写 EC / SMU 寄存器**（都走 `ryzenadj` + EC 端口/ACPI），因此**底层能力几乎一致**；差异主要在**驱动依赖、自启机制、GUI 生态**。下表按「功能」对齐，标记各自可行性。均已实测。

| 功能 | Windows | Linux | 说明 |
|------|:-------:|:-----:|------|
| CPU 降压 | ⛔ | ⛔ | SMU 固件锁死，`ryzenadj` 三通道均 rejected，双系统一致 |
| GPU 降压 | ✅ 手动 | ⚠️ 受限 | Windows：MSI Afterburner VF 曲线；Linux：仅 vBIOS 功耗墙 115W 锁死，无等效 Afterburner |
| SMU 功耗墙 (STAPM/Fast/Slow/Tctl) | ✅ | ✅ | 两平台 `ryzenadj` 均可写；默认 80W/100W/99°C |
| 风扇曲线 (16 点) | ✅ | ✅ | Windows 走官方 MQTT `SET_FAN_SPEED_CURVE_SETTING`；Linux 直接写 EC |
| 风扇 duty / 温度读取 | ✅ | ✅ | 同为 EC 寄存器 (`0x43E`/`0x44C`/`0x461`/`0x469`) |
| 键盘背光 (三档) | ✅ | ✅ | EC `0x78C` bits 5-7，两平台均可写 |
| 充电阈值 | ⚠️ | ⚠️ | 固件不实现，软件层写持久但硬件不生效（都证伪），双系统一致 |
| 屏幕刷新率切换 (165Hz/60Hz) | ✅ | — | Windows：`mr_powersaver` 自动 AC/DC 切换；Linux 无此现成方案 |
| 电源计划 / AC-DC 场景自动切换 | ✅ | ⚠️ 手动 | Windows：`mr_daemon`+`mr_powersaver` 全自动；Linux：shell 脚本手动/手动触发 |
| 官方协议 (MQTT/UDP 场景) | ✅ | 不适用 | Windows 现役控制台完整实现；Linux 直接用 EC，不经 MQTT |
| GUI 控制台 | ✅ 双 GUI | ⚠️ 简易 | Windows：`mr_gui_v6`/`v6qt`；Linux：`jcc_console` GTK |
| 驱动依赖 | 需 `UWACPIDriver.sys`/WinRing0 | 免内核驱动 | Linux 用端口 I/O/`sysfs`，无需 Windows 专属驱动；但需 root |

> **结论**：除「GPU 降压(Linux 受限)」「刷新率/电源计划自动化(仅 Win)」外，**核心 EC/SMU 能力两平台都能实现**。Windows 胜在应用层自动化与 GUI，Linux 胜在免驱动与纯净性。详见各 `02_代码_Windows/` 与 `03_代码_Linux/`。

---

## 🚀 快速开始（Quick Start）

> 想直接看到效果，按下面的最短路径跑起来；完整使用文档见各代码层目录内的 README/注释。

**Windows（现役 v6.0，推荐先跑无 MQTT 依赖的最小件）**
```bash
# 前置：需已安装 UWACPIDriver.sys（原厂驱动）与 Python 3.10+（现役脚本使用标准库，无需额外 pip 依赖）
cd 02_代码_Windows/现役_v6.0
# 轻量 AC/DC 自动管理（刷新率+电源计划，无 MQTT 依赖，可立即试）
pythonw mr_powersaver.py
# 完整控制台（MQTT 场景切换 + GUI）。注意：公开版 MQTT 口令已脱敏为
#   <REDACTED_PWD_SALT>，本机运行需先从 _private_不上传 取回真值（见「脱敏」节）
python mr_gui_v6.py
```

**Linux（jcc_console_v2.3，需 root）**
```bash
cd 03_代码_Linux/jcc_console_v2.3
sudo python3 jcc.py            # 控制中心入口（GTK）
# 或仅用手动脚本（无需 GUI）：
#   apply_mode.sh / deploy_three_mode.sh  三档(A/B/C)场景
#   readjust.py               温度/功耗守护
```

> ⚠️ 首次使用前请务必读完顶部「免责声明」与下方「已知问题」。SMU/EC 写入不可逆地改变硬件行为，请务必备份原配置并从小幅参数开始。

---

## 🖥️ Windows 侧：自制控制台

> **English (Windows)** — The current working code lives in `02_代码_Windows/现役_v6.0/`. Core modules:
> - `mr_powersaver.py` — lightweight AC/DC manager (refresh rate + power plan), auto-start, **no MQTT dependency** (recommended to try first).
> - `mr_daemon.py` — core engine: MQTT + UDP 13690 scene switching.
> - `mr_console.py` — MQTT protocol wrapper.
> - `mr_ec_hw.py` — EC hardware read/write (requires `UWACPIDriver.sys`).
> - `mr_win_ctrl.py` — power plan / refresh rate / process control.
> - `mr_gui_v6.py` / `mr_gui_v6qt.py` — two GUIs.
>
> Auto-start chain: `Startup\mr_powersaver.vbs` (**must be GBK-encoded**) → `pythonw mr_powersaver.py` → AC: 165 Hz + "MR-均衡"; DC: 60 Hz + "MR-超级省电". Reinstall the OS? Use `02_代码_Windows/恢复方案_系统重装/install.py` for one-click restore.

`02_代码_Windows/现役_v6.0/` 为当前工作区。

```
mr_powersaver.py   ★ 轻量 AC/DC 自动管理（刷新率 + 电源计划），开机自启，无 MQTT 依赖
mr_daemon.py         核心引擎：MQTT + UDP 13690 场景切换
mr_console.py        MQTT 协议封装
mr_ec_hw.py          EC 硬件读写（需 UWACPIDriver.sys）
mr_win_ctrl.py       电源计划 / 刷新率 / 进程管理
mr_gui_v6.py / mr_gui_v6qt.py   双 GUI
```

开机自启链：`Startup\mr_powersaver.vbs`（**必须 GBK 编码**）→ `pythonw mr_powersaver.py`
→ AC：165Hz + MR-均衡模式；DC：60Hz + MR-超级省电

> 重装系统后用 `02_代码_Windows/恢复方案_系统重装/install.py` 一键恢复。

> ⚠️ **readjustService.ps1（第三方持久化服务）— 保持停用**：`现役_v6.0/ryzenadj/readjustService.ps1` 是 Falco 开源的第三方 ryzenadj「监控保持」脚本（LGPL），其中 `46W/25W` 等为作者示例值，**与 smu_profile.json 档位无关**。它「盯守 fast_limit 防被改回」的职责与 mr_daemon 自带的 `plan_watcher` 重叠，两者同时启用会互相覆盖（readjust 会把 daemon 设好的档位强制改回示例值）。**不建议作为自启项启用**（2026-08-30 穷尽审计注记）。

### ⚙️ SMU 功耗档位（`smu_profile.json` 实测值）

当前四档配置（值单位为 mW；`ryzenadj` 写入时 `fast/slow/stapm` 换算为 W）：

| 档位 | tctl-temp | stapm | fast-limit | slow-limit | 用途 |
|------|:---------:|:-----:|:----------:|:----------:|------|
| `office` | 85°C | 35 W | 65 W | 65 W | 办公/轻度，功耗最低 |
| `custom` | 90°C | 55 W | 80 W | 80 W | 自定义均衡档 |
| `gaming` | 95°C | 80 W | 100 W | 100 W | 游戏主力档（默认 play） |
| `turbo` | 99°C | 80 W | 100 W | 100 W | 峰值，温度墙拉满至硬件上限 |

> 四档 `fast` 均 ≤ 硬件 FAST 上限 100 W，可安全直接启用（越界仅存在于抓包中的厂商原生读数 `CPU_PL2=150`，属厂商口径问题，见「已知问题」）。

---

## 🐧 Linux 侧

> **English (Linux)** — Under `03_代码_Linux/`: `jcc_console_v2.3/` (GTK control center, entry `jcc.py`), `脚本_三档与温控/` (A/B/C scene scripts + thermal-wall guard, e.g. `apply_mode.sh`, `readjust.py`), `固件修复_键盘/` (DSDT override to fix PS2 keyboard IRQ polarity). No Windows-specific kernel driver needed, but root is required.

`03_代码_Linux/`：`jcc_console_v2.3/`（GTK 控制中心）、`脚本_三档与温控/`（A/B/C 三场景 + 温度墙守护）、
`固件修复_键盘/`（DSDT override 修复 PS2 键盘 IRQ 极性）。

---

## 🔒 未公开内容（重要）

以下内容因**版权 / 许可 / 隐私**原因**不包含在本仓库**，保留在本地 `_private_不上传/`（已被 `.gitignore` 排除）：

| 类别 | 内容 | 原因 |
|------|------|------|
| OEM 专有二进制 | 官方驱动备份、ControlCenter3 安装包、UWP 解包 `GamingCenter3_Cross.dll` 等 | 版权 |
| 反编译产物 | `GCUService.decompiled.cs`、`gcu_full.cs`、OEM 字符串 dump、UI 译文 | 衍生复制，版权风险 |
| 第三方二进制 | LibreHardwareMonitor 发行包（含闭源 toolkit，不可再分发） | 许可限制 |
| 固件衍生 | DSDT 原始/修改版 `.dsl`、OEM 出厂风扇表 | 固件衍生 |
| 机器个资 | 电池报告、OEM 注册表快照 | 隐私 |
| 运行时日志 | `powersaver.log` 等 | 非知识资产 |

> **仓库只包含自写文档、自写代码、以及固化为结论文档的方法论/实测数据；原始抓包与取证工序已迁入 `_private_不上传`（不入库），不随公开仓发布。**

---

## 🔐 关于脱敏

公开版本已替换以下内容：

- MQTT 口令盐值 → `<REDACTED_PWD_SALT>`
- AES 密钥 → `<REDACTED_AES_KEY>`
- Windows / Linux 用户名 → `<USER>`

⚠️ **这会导致本地 MQTT 功能不可用**（`mr_console.py`、`mr_daemon.py` 中的口令是运行时常量）。
如需本机运行，从 `_private_不上传/_脱敏前备份_*/` 取回对应文件覆盖即可（该目录不入库）。
`mr_powersaver.py` 不依赖 MQTT，不受影响。

口令的**构成规则**见 `01_协议_逆向成果/MQTT协议/协议破解文档_20260823.md`；**本机提取方法**（`dump_cred.ps1` 反射取凭据脚本）属破解工序，已移入 `_private_不上传/OEM反编译产物/01_协议_逆向成果_迁移/MQTT协议_取证/`（不入库），不随公开仓发布。

---

## 🐛 已知问题（Known Issues / Open Items）

> 状态图标：🟥 待修 · 🟨 待观察/第三方 · 🟩 已解决但有影响/需知悉。`[x]`=已在仓库层面关闭或注明；`[ ]`=仍开放。详细依据见 `00_结论_已确证/电源模式联动审计_20260826.md` 与 `本机生态当前状态_20260828.md`。

- [x] **`smu_profile.json` 越界警告已失效**（🟩 已解决·2026-08-30 修订）— 当前四档最大 `fast=100000`（100W）均 ≤ 硬件 FAST 上限，可直接启用。真正的越界仅出现于抓包中厂商原生读数 `Fan/Status: CPU_PL1=120 / PL2=150 / PL4=200`（超出其自身 `Maximum 80/80/100`）——属厂商侧口径问题，非本仓库配置。
- [ ] **L1 电源滑块 overlay AC/DC 方向装反**（🟥 待修）— AC 挂省电、DC 挂高性能。影响：UI 档位与实际电源计划相反。范围：Windows `mr_gui_v6` overlay。
- [ ] **MQTT broker 监听 `0.0.0.0:13688`（非仅回环）+ 明文认证**（🟨 安全建议）— 建议防火墙阻断该端口入站；不影响本机回环使用。
- [ ] **GPU 温度寄存器 `0x44C` 存在一次反向证据**（🟨 待仲裁）— 读数 22°C 低于环境温，需第三方复测仲裁。
- [ ] **Linux 侧文档未同步 Windows 侧纠错**（🟨 文档）— `0x44F→0x44C`、`45W→35W` 等纠错未回写到 Linux 相关文档。
- [x] **README 02 层文件计数错误**（🟩 已修正·2026-08-31）— 原声称 214，实为 212，已修正且与 `git ls-files` 对齐。

---

## 🤝 贡献 · 安全 · 更新

- [CONTRIBUTING.md](CONTRIBUTING.md) — 贡献指南（含「禁止提交私有/逆向原文」铁律）
- [.github/SECURITY.md](.github/SECURITY.md) — 安全政策与漏洞报告渠道
- [CHANGELOG.md](CHANGELOG.md) — 变更记录
- [THIRDPARTY.md](THIRDPARTY.md) — 第三方组件与许可清单
- [.github/FUNDING.yml](.github/FUNDING.yml) — 捐赠/Sponsor 占位模板（默认全留空，仓库公开且你决定开放赞助后再启用）

## 📄 许可

本项目以 **MIT License** 授权（见 [LICENSE](LICENSE)），版权归 **段雪健 (Duan Xuejian)**。本项目引用的第三方组件（**ryzenadj = LGPL-3.0、WinRing0 = Modified BSD、inpoutx64.dll = Freeware、readjustService = LGPL** 等）以各自独立许可**并行分发**，清单与出处见 [THIRDPARTY.md](THIRDPARTY.md)。

**打赏 / 赞助**：若本项目对你有帮助，欢迎自愿支持作者。打赏不改变 MIT 的免费许可性质。以下是自愿赞助入口：

| 微信 (WeChat) | 支付宝 (Alipay) |
|------|------|
| ![微信收款码](assets/donate_wechat.jpg) | ![支付宝收款码](assets/donate_alipay.jpg) |
