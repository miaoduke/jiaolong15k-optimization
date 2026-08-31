# 蛟龙15K (Ryzen 7 7435H + RTX 4060) 电源与风扇控制 · 逆向与自制控制台
# Jiaolong 15K (Ryzen 7 7435H + RTX 4060) — Power & Fan Control · Reverse Engineering & Homebrew Console

> This repository is documented in **both English and Simplified Chinese**. Each section first appears in English, then in Chinese. Technical terms, register addresses, file names and URLs are intentionally kept in their original form in both languages.

> 本仓库以**中英双语**编写。每节先英文、后中文。技术术语、寄存器地址、文件名与链接在两种语言中保持一致原文。

---

## ⚠️ Disclaimer / 免责声明

**English:**

- This is a **personal, self-use reverse-engineering study** of a specific retail machine. It is **not affiliated with, endorsed by, or a product of Mechrevo or Uniwill**, and it is not intended as a competitive tool against any vendor.
- The project **directly reads and writes EC registers and SMU power registers**. A wrong value can destabilize the system or damage hardware / shorten its lifespan. **Use at your own risk**; the author accepts no liability for any loss.
- The repo ships only **conclusions, register maps, protocol specifications, methodologies, and self-authored code**. It deliberately does **not** include OEM proprietary binaries, decompiled artifacts, firmware images, credentials, or personal machine data (see "Unpublished Content" below).
- All credentials, usernames, and paths that could identify a specific device have been **redacted**.
- Superseded (retracted) conclusions are **kept and annotated, never deleted**; trust the latest module version and the README "Known Issues" section.

**中文：**

- 本项目为**个人学习与设备自用**性质的逆向工程记录，与机械革命 / Uniwill 官方**无任何关联、非官方支持**，不对任何厂商构成竞争用途。
- 本项目**直接读写 EC 寄存器与 SMU 功耗寄存器**，错误配置可能影响系统稳定性、损坏硬件或缩短寿命；**风险自负**，作者不对任何损失负责。
- 仓库**只包含**结论、寄存器映射、协议规范、方法论与自写代码；**不包含**任何 OEM 专有二进制、反编译产物、固件镜像、凭据或个人机器数据（见下方「未公开内容」）。
- 所有可能识别到具体设备的凭据、用户名、路径均已脱敏。
- 被推翻的旧结论一律**保留并标注**而非删除，请以子模块最新版本与本 README「已知问题」为准。

**Spec / 机型：**

> - **机型**：机械革命 蛟龙15K / AMD Ryzen 7 **7435H（Zen3+，35W）** + RTX 4060 Laptop
> - **主板**：Uniwill **GM5BG0E** / ProjectID=16 / **无 iGPU（dGPU only）**
> - **系统**：Windows 11 Pro 26200 + Linux Mint 22.3 双系统
> - **Model:** Mechrevo Jiaolong 15K / AMD Ryzen 7 **7435H (Zen3+, 35W)** + RTX 4060 Laptop
> - **Motherboard:** Uniwill **GM5BG0E** / ProjectID=16 / **no iGPU (dGPU only)**
> - **OS:** Dual-boot Windows 11 Pro 26200 + Linux Mint 22.3

The project documents the complete process of **reverse-engineering the official "Gaming Console" software**, **mapping the EC registers**, and **building a self-made replacement console**. All conclusions are based on physical-machine testing, with a correction ledger in which **retracted conclusions are kept and annotated rather than deleted**, to avoid repeating mistakes.

项目记录了对该机型官方「电竞控制台」的**协议逆向、EC 寄存器测绘、以及自制替代控制台**的完整过程。所有结论均基于实机实测，并保留纠错台账——**被推翻的旧结论不删除，而是明确标注**，避免重复踩坑。

---

## 🔬 Content Layering: Public vs Private / 内容分层原则（公开 vs 私有）

**English:**

This repository follows a "**publish conclusions & methodology, not cracking procedures / forensic originals**" layering strategy:

- **Public layer (`00`–`04`)** — only **conclusions, register maps, protocol specs, methodologies** and self-authored code, to document *what is possible and what the evidence is*.
- **Private layer (`_private_不上传/`, NOT committed)** — the actual cracking procedures (captured packets, string dumps, OEM registry snapshots, decryption/credential scripts, reverse-engineering gotchas). These involve vendor-proprietary content and personal data, so they are **not echoed or published**.
- The `01_协议_逆向成果/*.txt` packet captures and `get_cred*/get_key*` forensics scripts were migrated / marked as **not public**; public docs keep only the protocol **field specs and conclusions**, without raw captures or credentials.
- Please treat this repo as a "**methodology reference**", not a "cracking toolkit". Full forensic details are under a private-authorization scope.

> If you find any residual raw cracking content in the public layer (raw captures, OEM originals, credential scripts), move it into `_private_不上传/` per the migration rules in `04_过程_文档归档/旧目录地图_20260825.md`, or file an Issue.

**中文：**

- **公开层（00~04）**：仅保留可复用的 **结论、寄存器映射、协议规范、方法论** 与自写代码，用于说明「能做什么、结论依据是什么」。
- **私有层（`_private_不上传/`，不入库）**：保留**逆向破解的具体工序**（抓包样本、字符串 dump、OEM 注册表快照、解密/取凭据脚本、反编译踩坑细节），因涉及厂商专有内容且个资敏感，**不回显、不随公开仓发布**。
- `01_协议_逆向成果/*.txt` 抓包样本 与 `get_cred*/get_key*` 等取证脚本已迁移/标注为**不公开**；公开文档仅保留协议**字段规范与结论**，不含原始抓包与凭据。
- 对外请把本仓库视为「**方法论参考**」而非「破解工具包」。如需完整取证细节，属私有授权范围。

> 若你发现公开层仍残留逆向破解原始内容（原始抓包、OEM 原文、取凭据脚本），请按 `04_过程_文档归档/旧目录地图_20260825.md` 的迁移规则移入 `_private_不上传`，或提交 Issue 提醒维护。

---

## 📁 Directory Structure (by Knowledge-Asset Layer) / 目录结构（按知识资产类型分层）

**English:** Categorized by **decreasing evidence level + decreasing reusability**: the earlier a layer, the closer it is to "directly trustworthy conclusions"; the later, the closer to "process records".

**中文：** 分类依据：**证据等级递减 + 复用性递减**。越靠前越接近「可直接采信的结论」，越靠后越接近「过程记录」。

| Layer 层级 | Directory 目录 | Content 内容 | Position 定位 |
|------|------|------|------|
| **L1 Conclusions** | `00_结论_已确证/` | Status snapshots, final conclusions, correction ledger, audits, three full checklists 状态快照、终局结论、纠错台账、审计、三份全量清单 | **Read here first / 先读这里** |
| **L2 Protocol** | `01_协议_逆向成果/` | MQTT protocol spec, DefaultTool conclusions, EC/ACPI references (forensics originals moved private) MQTT 协议规范、DefaultTool 结论、EC/ACPI 参考源（取证原文已迁私） | Reusable spec 可复用的技术规范 |
| **L3 Code** | `02_代码_Windows/` | Active v6.0 / system-reinstall recovery / archived v5.4 / JCC-Win prototype 现役 v6.0 / 系统重装恢复方案 / 归档 v5.4 / JCC-Win 原型 | Run directly 可直接运行 |
| **L3 Code** | `03_代码_Linux/` | jcc_console v2.3, three-mode & thermal scripts, keyboard-firmware fix, experiments 实验脚本 | Run directly 可直接运行 |
| **L4 Process** | `04_过程_文档归档/` | Project process docs, historical reports, proposals, old-directory map 历史报告、设计提案、旧目录地图 | History & decisions 历史与决策轨迹 |
| — | `_private_不上传/` | **Not committed , see `.gitignore` / 不入库**，见 `.gitignore` | — |

```
00_结论_已确证/          11 files/文件  — 状态快照 / 终局结论 / 全量清单 | status snapshots / final conclusions / checklists
01_协议_逆向成果/         9 files/文件  — MQTT 协议规范 / DefaultTool 结论 / EC-ACPI 参考（取证原文已迁私）| spec / conclusions / EC-ACPI refs (forensics private)
02_代码_Windows/        212 files/文件  — 现役_v6.0 / 恢复方案 / 归档_v5.4 / 原型_JCC-Win | active v6.0 / recovery / archived v5.4 / JCC-Win prototype
03_代码_Linux/           47 files/文件  — jcc_console / 脚本 / 固件修复 / 实验 / 实测数据 | console / scripts / firmware fix / experiments / measurement data
04_过程_文档归档/        25 files/文件  — 项目过程 / 历史报告 / 提案 | process / historical reports / proposals
```

---

## 🚀 Quick Navigation / 快速导航

**English — what this machine can/cannot do:** `00_结论_已确证/全量清单/` (Windows 165 / Linux 54 / merged 124).
**Current runtime state snapshot:** `00_结论_已确证/本机生态当前状态_20260828.md`.

**中文 — 想了解这台机器能做什么、不能做什么:** `00_结论_已确证/全量清单/`（Windows 165 项 / Linux 54 项 / 合并 124 项）
**当前运行状态:** `00_结论_已确证/本机生态当前状态_20260828.md`

### Key Verified Conclusions / 重点结论（均已实测）

| Topic 主题 | Result 结论 |
|------|------|
| CPU undervolt 降压 | ⛔ **locked by SMU firmware** (`ryzenadj` rejected on all three channels, both OSes) ⛔ **SMU 固件锁死**（`ryzenadj` 三通道均 rejected，双系统一致） |
| GPU undervolt 降压 | only via MSI Afterburner manual VF curve; vBIOS power cap locked at 115 W 唯一途径 = MSI Afterburner VF 曲线手动；vBIOS 功耗墙 115W 锁死 |
| Charge limit 充电限制 | ⚠️ **writes persist & read back on Windows, but firmware does not enforce it** (still charges to 100%). `0x7B9`/`0x7D0` read back the *threshold*, not SoC ⚠️ **Windows 侧写入持久、读回一致，但固件不执行**（实测仍充至 100%）。阈值寄存器回读的是**阈值**而非 SoC |
| SMU power limits 功耗墙 | ✅ `stapm`/`fast-limit`/`slow-limit`/`tctl-temp` writable; defaults STAPM 80 W / FAST 100 W / Tctl 99°C; `stapm`/`fast-limit`/`slow-limit`/`tctl-temp` 可写；默认 STAPM 80W / FAST 100W / Tctl 99°C |
| Fan 风扇 | ✅ official MQTT `SET_FAN_SPEED_CURVE_SETTING` writes a 16-point curve (firmware-enforced) 官方 MQTT `SET_FAN_SPEED_CURVE_SETTING` 可写 16 点曲线（固件执行） |
| Keyboard backlight 键盘背光 | ✅ 3 levels, EC `0x78C` bits 5–7 三档，EC `0x78C` bit5-7 |

### Key EC Registers / 关键 EC 寄存器

(Full map in `00_结论_已确证/Windows侧交叉对照_EC寄存器_20260823.md` / 完整映射见 `00_结论_已确证/Windows侧交叉对照_EC寄存器_20260823.md`)

| Addr 地址 | Meaning 含义 |
|------|------|
| `0x43E` | CPU temperature CPU 温度 |
| `0x44C` | GPU temperature (`0x44F` is **deprecated**, older docs out of sync) GPU 温度（`0x44F` **已废弃**，旧文档未同步） |
| `0x461` / `0x469` | fan duty 风扇 duty |
| `0x751` | fan control 风扇控制 |
| `0x7B9` / `0x7D0` | charge thresholds (read back = threshold, not SoC) 充电阈值（读回=阈值，非 SoC） |
| `0x7A6` | ⚠️ **arbitrated on hardware (2026-08-30): writable flag bit, NOT a power sensor.** Write `bit6`(0x40) succeeds & reads back, then reverts; during a 2.5 s CPU-full-load run `0x7A6` stayed at 9, no response. No load response + writable ⇒ not a "live power W" register; using it as touchpad `bit6` in `mr_gui_v6` is legitimate. The old "live power" claim is retracted. ⚠️ **实机仲裁（2026-08-30）：可写标志位，非功率传感器**。实测：写 `bit6`(0x40) 成功且回读=写入值、写后即恢复原值；CPU 满载 2.5s 期间 0x7A6 恒为 9 无响应。负载零响应 + 可写 → 判据不支持「实时功率 W」，现役 `mr_gui_v6` 用作触摸板 `bit6` 属合理。原「实时功率」结论撤回 |
| `0x7A8` / `0x7A9` | ⛔ deprecated (early wrong addresses) ⛔ 已废弃（早期误判地址） |

---

## 🪟🐧 Dual-OS Capability Comparison (Windows vs Linux) / 双系统能力对比

**English:** Both OSes **directly read/write EC / SMU registers** (both via `ryzenadj` + EC port/ACPI), so the low-level capability is nearly identical; differences are mainly in **driver dependencies, auto-start mechanism, and GUI ecosystem**. Table aligned by feature; all tested on real hardware.

**中文：** 两台系统都**直接读写 EC / SMU 寄存器**（都走 `ryzenadj` + EC 端口/ACPI），因此**底层能力几乎一致**；差异主要在**驱动依赖、自启机制、GUI 生态**。下表按「功能」对齐，标记各自可行性。均已实测。

| Feature 功能 | Windows | Linux | Notes 说明 |
|------|:-------:|:-----:|------|
| CPU undervolt 降压 | ⛔ | ⛔ | SMU firmware locks it; `ryzenadj` rejected on all channels, both OSes SMU 固件锁死，`ryzenadj` 三通道均 rejected，双系统一致 |
| GPU undervolt 降压 | ✅ manual | ⚠️ limited | Win: MSI Afterburner VF curve; Linux: vBIOS 115 W cap only, no Afterburner equivalent Windows：MSI Afterburner VF 曲线；Linux：仅 vBIOS 功耗墙 115W 锁死，无等效 Afterburner |
| SMU power wall (STAPM/Fast/Slow/Tctl) 功耗墙 | ✅ | ✅ | `ryzenadj` writable on both; defaults 80W/100W/99°C 两平台均可写；默认 80W/100W/99°C |
| Fan curve (16-point) 风扇曲线 | ✅ | ✅ | Win via official MQTT `SET_FAN_SPEED_CURVE_SETTING`; Linux writes EC directly Windows 走官方 MQTT；Linux 直接写 EC |
| Fan duty / temperature read 风扇 duty/温度读取 | ✅ | ✅ | Same EC registers (`0x43E`/`0x44C`/`0x461`/`0x469`) 同为 EC 寄存器 |
| Keyboard backlight (3 levels) 键盘背光 | ✅ | ✅ | EC `0x78C` bits 5-7, writable on both 两平台均可写 |
| Charge threshold 充电阈值 | ⚠️ | ⚠️ | Firmware not implemented; writes persist in software but not enforced (both disproven) 固件不实现，软件层写持久但硬件不生效（都证伪） |
| Refresh-rate switch (165/60 Hz) 刷新率切换 | ✅ | — | Win: `mr_powersaver` auto AC/DC; Linux has no ready solution Windows：自动 AC/DC 切换；Linux 无此现成方案 |
| Power plan / AC-DC auto switch 电源计划/AC-DC 场景 | ✅ | ⚠️ manual | Win: `mr_daemon`+`mr_powersaver` fully automatic; Linux: manual shell scripts Windows：全自动；Linux：shell 脚本手动 |
| Official protocol (MQTT/UDP scenes) 官方协议 | ✅ | n/a | Win console implements it fully; Linux talks to EC directly, not via MQTT Windows 控制台完整实现；Linux 直接用 EC，不经 MQTT |
| GUI console 控制台 | ✅ dual GUI | ⚠️ simple | Win: `mr_gui_v6`/`v6qt`; Linux: `jcc_console` GTK |
| Driver dependency 驱动依赖 | needs `UWACPIDriver.sys`/WinRing0 | driver-free | Linux uses port I/O/`sysfs`, no Windows driver needed; but requires root Linux 用端口 I/O/`sysfs`，免内核驱动；需 root |

> **Conclusion 结论**：Apart from "GPU undervolt (Linux limited)" and "refresh-rate / power-plan automation (Windows only)", the **core EC/SMU capability is achievable on both OSes**. Windows wins on application-layer automation and GUI; Linux wins on being driver-free and clean. See `02_代码_Windows/` and `03_代码_Linux/` for details.

---

## 🚀 Quick Start / 快速开始

**English:** For the shortest path to visualize the effects, run the minimal commands below; full usage docs live in each code-layer README / comments.

**中文：** 想直接看到效果，按下面的最短路径跑起来；完整使用文档见各代码层目录内的 README/注释。

**Windows (active v6.0; start with the MQTT-lightest pieces) / Windows（现役 v6.0，推荐先跑无 MQTT 依赖的最小件）**

```bash
# Prereq: install UWACPIDriver.sys (OEM driver) and Python 3.10+ (active scripts use the stdlib; no extra pip deps)
# 前置：需已安装 UWACPIDriver.sys（原厂驱动）与 Python 3.10+（现役脚本使用标准库，无需额外 pip 依赖）
cd 02_代码_Windows/现役_v6.0
# Lightweight AC/DC auto-manager (refresh rate + power plan, no MQTT, try immediately)
# 轻量 AC/DC 自动管理（刷新率+电源计划，无 MQTT 依赖，可立即试）
pythonw mr_powersaver.py
# Full console (MQTT scene switching + GUI). NOTE: public MQTT password redacted to
#   <REDACTED_PWD_SALT> — for local run restore the real value from _private_不上传 (see "Redaction").
# 完整控制台（MQTT 场景切换 + GUI）。注意：公开版 MQTT 口令已脱敏为 <REDACTED_PWD_SALT>，
#   本机运行需先从 _private_不上传 取回真值（见「脱敏」节）
python mr_gui_v6.py
```

**Linux (jcc_console_v2.3, requires root) / Linux（jcc_console_v2.3，需 root）**

```bash
cd 03_代码_Linux/jcc_console_v2.3
sudo python3 jcc.py            # GTK control center entry / 控制中心入口（GTK）
# or use manual scripts only (no GUI) / 或仅用手动脚本（无需 GUI）：
#   apply_mode.sh / deploy_three_mode.sh   three-mode (A/B/C) scenes 三档(A/B/C)场景
#   readjust.py              temperature/power guard 温度/功耗守护
```

> ⚠️ Before first use, read the Disclaimer above and the Known Issues below. SMU/EC writes irreversibly change hardware behavior; **back up your original config and start with small values**.
>
> ⚠️ 首次使用前请务必读完顶部「免责声明」与下方「已知问题」。SMU/EC 写入不可逆地改变硬件行为，请务必备份原配置并从小幅参数开始。

---

## 🖥️ Windows Side: the Homebrew Console / Windows 侧：自制控制台

**English:** `02_代码_Windows/现役_v6.0/` is the current working directory. Core modules:

- `mr_powersaver.py` — lightweight AC/DC manager (refresh rate + power plan), auto-start, **no MQTT dependency** (recommended to try first) 轻量 AC/DC 自动管理，开机自启，无 MQTT 依赖
- `mr_daemon.py` — core engine: MQTT + UDP 13690 scene switching 核心引擎：MQTT + UDP 13690 场景切换
- `mr_console.py` — MQTT protocol wrapper MQTT 协议封装
- `mr_ec_hw.py` — EC hardware read/write (requires `UWACPIDriver.sys`) EC 硬件读写（需 UWACPIDriver.sys）
- `mr_win_ctrl.py` — power plan / refresh rate / process control 电源计划 / 刷新率 / 进程管理
- `mr_gui_v6.py` / `mr_gui_v6qt.py` — two GUIs 双 GUI

**Auto-start chain / 开机自启链：** `Startup\mr_powersaver.vbs` (**must be GBK-encoded / 必须 GBK 编码**) → `pythonw mr_powersaver.py` → AC: 165 Hz + "MR-均衡"; DC: 60 Hz + "MR-超级省电". Reinstall the OS? Use `02_代码_Windows/恢复方案_系统重装/install.py` for one-click restore / 重装系统后用 `02_代码_Windows/恢复方案_系统重装/install.py` 一键恢复。

```
mr_powersaver.py   ★ 轻量 AC/DC 自动管理（刷新率 + 电源计划），开机自启，无 MQTT 依赖 | lightweight AC/DC manager, auto-start, no MQTT
mr_daemon.py         核心引擎：MQTT + UDP 13690 场景切换 | core engine: MQTT + UDP 13690 scene switching
mr_console.py        MQTT 协议封装 | MQTT protocol wrapper
mr_ec_hw.py          EC 硬件读写（需 UWACPIDriver.sys）| EC hardware R/W (needs UWACPIDriver.sys)
mr_win_ctrl.py       电源计划 / 刷新率 / 进程管理 | power plan / refresh rate / process control
mr_gui_v6.py / mr_gui_v6qt.py   双 GUI | two GUIs
```

> ⚠️ **`readjustService.ps1` (third-party persistence service) — keep disabled.** `现役_v6.0/ryzenadj/readjustService.ps1` is a Falco-licensed third-party "watchdog" script for `ryzenadj` (LGPL); the `46W/25W` in it are the author's sample values **unrelated to `smu_profile.json` tiers**. Its job of "watching `fast_limit` so it isn't reset" overlaps with `mr_daemon`'s built-in `plan_watcher`; enabling both causes them to overwrite each other (readjust forces the daemon's tier back to the sample values). **Not recommended as an auto-start item** (2026-08-30 exhaustive-audit note).
>
> ⚠️ **readjustService.ps1（第三方持久化服务）— 保持停用**：`现役_v6.0/ryzenadj/readjustService.ps1` 是 Falco 开源的第三方 ryzenadj「监控保持」脚本（LGPL），其中 `46W/25W` 等为作者示例值，**与 smu_profile.json 档位无关**。它「盯守 fast_limit 防被改回」的职责与 mr_daemon 自带的 `plan_watcher` 重叠，两者同时启用会互相覆盖。**不建议作为自启项启用**（2026-08-30 穷尽审计注记）。

### ⚙️ SMU Power Tiers (`smu_profile.json`, tested values) / SMU 功耗档位（实测值）

**English:** Current four tiers (unit mW; `ryzenadj` converts `fast/slow/stapm` to W on write): 当前四档配置（值单位 mW）。

| Tier 档位 | tctl-temp | stapm | fast-limit | slow-limit | Purpose 用途 |
|------|:---------:|:-----:|:----------:|:----------:|------|
| `office` | 85°C | 35 W | 65 W | 65 W | Web/light, lowest power 办公/轻度，功耗最低 |
| `custom` | 90°C | 55 W | 80 W | 80 W | Custom balanced 自定义均衡档 |
| `gaming` | 95°C | 80 W | 100 W | 100 W | Gaming main tier (default play) 游戏主力档（默认 play） |
| `turbo` | 99°C | 80 W | 100 W | 100 W | Peak; Tctl pulled to HW ceiling 峰值，温度墙拉满至硬件上限 |

> All four tiers have `fast` ≤ the 100 W hardware FAST cap, safe to enable directly (the only out-of-range value is the vendor-native `CPU_PL2=150` captured in the wild — a vendor-metric issue, see Known Issues).
>
> 四档 `fast` 均 ≤ 硬件 FAST 上限 100 W，可安全直接启用（越界仅存在于抓包中的厂商原生读数 `CPU_PL2=150`，属厂商口径问题，见「已知问题」）。

---

## 🐧 Linux Side / Linux 侧

> **English:** Under `03_代码_Linux/`: `jcc_console_v2.3/` (GTK control center, entry `jcc.py`), `脚本_三档与温控/` (A/B/C scene scripts + thermal-wall guard, e.g. `apply_mode.sh`, `readjust.py`), `固件修复_键盘/` (DSDT override fixing PS2 keyboard IRQ polarity). No Windows-specific kernel driver is needed, but root is required.
>
> **中文：** `03_代码_Linux/`：`jcc_console_v2.3/`（GTK 控制中心）、`脚本_三档与温控/`（A/B/C 三场景 + 温度墙守护）、`固件修复_键盘/`（DSDT override 修复 PS2 键盘 IRQ 极性）。

---

## 🔒 Unpublished Content 未公开内容（重要）

> **English:** The items below are **NOT** included in this public repo for **copyright / licensing / privacy** reasons and are kept in local `_private_不上传/` (excluded via `.gitignore`): OEM proprietary binaries (driver backups, ControlCenter3 installer, UWP-unpacked `GamingCenter3_Cross.dll`, …); decompiled artifacts (`GCUService.decompiled.cs`, `gcu_full.cs`, OEM string dumps, UI translations); some third-party binaries (e.g. the LibreHardwareMonitor package, which contains a closed-source toolkit — not redistributable); firmware-derived files (original/modified `.dsl` DSDT, OEM factory fan table); personal machine data (battery report, OEM registry snapshot); runtime logs. **The repo ships only self-authored docs/code and methodology/test data frozen into conclusions; raw captures and credential-extraction steps are kept in `_private_不上传` and are not published.**
>
> **中文：** 以下内容因**版权 / 许可 / 隐私**原因**不包含在本仓库**，保留在本地 `_private_不上传/`（已被 `.gitignore` 排除）：

| Category 类别 | Content 内容 | Reason 原因 |
|------|------|------|
| OEM proprietary binaries OEM 专有二进制 | driver backups, ControlCenter3 installer, UWP-unpacked `GamingCenter3_Cross.dll`, … 官方驱动备份、ControlCenter3 安装包、UWP 解包 `GamingCenter3_Cross.dll` 等 | copyright 版权 |
| Decompiled artifacts 反编译产物 | `GCUService.decompiled.cs`, `gcu_full.cs`, OEM string dumps, UI translations | derivative copy, copyright risk 衍生复制，版权风险 |
| Third-party binaries 第三方二进制 | LibreHardwareMonitor package (closed-source toolkit, not redistributable) LHM 发行包（含闭源 toolkit，不可再分发） | license restriction 许可限制 |
| Firmware-derived 固件衍生 | original/modified DSDT `.dsl`, OEM factory fan table DSDT 原始/修改版 `.dsl`、OEM 出厂风扇表 | firmware derivative 固件衍生 |
| Personal machine data 机器个资 | battery report, OEM registry snapshot 电池报告、OEM 注册表快照 | privacy 隐私 |
| Runtime logs 运行时日志 | `powersaver.log`, etc. | not knowledge assets 非知识资产 |

> **The repo ships only self-authored docs/code and methodology/test data frozen into conclusions; raw captures and credential-extraction steps are kept in `_private_不上传` and are not published.**
>
> **仓库只包含自写文档、自写代码、以及固化为结论文档的方法论/实测数据；原始抓包与取证工序已迁入 `_private_不上传`（不入库），不随公开仓发布。**

---

## 🔐 About Redaction 关于脱敏

> **English:** In this public version the following have been redacted: MQTT password salt → `<REDACTED_PWD_SALT>`; AES key → `<REDACTED_AES_KEY>`; the Windows/Linux username → `<USER>`. **This makes the local MQTT feature non-functional** (the credentials in `mr_console.py` / `mr_daemon.py` are runtime constants). To run locally, restore the matching files from `_private_不上传/_脱敏前备份_*/` (that directory is **not** committed). `mr_powersaver.py` has no MQTT dependency and is unaffected.
>
> **中文：** 公开版本已替换以下内容：MQTT 口令盐值 → `<REDACTED_PWD_SALT>`；AES 密钥 → `<REDACTED_AES_KEY>`；Windows / Linux 用户名 → `<USER>`。

⚠️ **English / 中文:** This makes the local MQTT feature non-functional (credentials in `mr_console.py`/`mr_daemon.py` are runtime constants). To run locally, restore the matching files from `_private_不上传/_脱敏前备份_*/` (not committed). `mr_powersaver.py` has no MQTT dependency and is unaffected. / 这会**导致本地 MQTT 功能不可用**（`mr_console.py`、`mr_daemon.py` 中的口令是运行时常量）。如需本机运行，从 `_private_不上传/_脱敏前备份_*/` 取回对应文件覆盖即可（该目录不入库）。`mr_powersaver.py` 不依赖 MQTT，不受影响。

The password **composition rules** are in `01_协议_逆向成果/MQTT协议/协议破解文档_20260823.md`; the local **extraction method** (`dump_cred.ps1` reflection script) is a cracking procedure and has been moved to `_private_不上传/OEM反编译产物/01_协议_逆向成果_迁移/MQTT协议_取证/` (not committed), not published.

口令的**构成规则**见 `01_协议_逆向成果/MQTT协议/协议破解文档_20260823.md`；**本机提取方法**（`dump_cred.ps1` 反射取凭据脚本）属破解工序，已移入 `_private_不上传/OEM反编译产物/01_协议_逆向成果_迁移/MQTT协议_取证/`（不入库），不随公开仓发布。

---

## 🐛 Known Issues / Known issues (Open Items) 已知问题

> **Status icons 状态图标：** 🟥 to fix 待修 · 🟨 observe/third-party 待观察/第三方 · 🟩 resolved with impact/awareness 已解决但有影响/需知悉. `[x]` = closed or annotated at repo level; `[ ]` = still open. Evidence in `00_结论_已确证/电源模式联动审计_20260826.md` and `本机生态当前状态_20260828.md`.
>
> 状态图标：🟥 待修 · 🟨 待观察/第三方 · 🟩 已解决但有影响/需知悉。`[x]`=已在仓库层面关闭或注明；`[ ]`=仍开放。详细依据见 `00_结论_已确证/电源模式联动审计_20260826.md` 与 `本机生态当前状态_20260828.md`。

- [x] **smu_profile.json out-of-range warning is now obsolete** (`smu_profile.json` 越界警告已失效) — 🟩 resolved 2026-08-30. The largest current `fast=100000` (100 W) is ≤ the 100 W hardware cap, safe to enable. The only real out-of-range value is the vendor-native `CPU_PL1=120 / PL2=150 / PL4=200` (beyond its own `Maximum 80/80/100`) seen in captures — a vendor-metric issue, not our config. / 当前四档最大 `fast=100000`（100W）均 ≤ 硬件 FAST 上限，可直接启用。真正的越界仅存在于抓包中厂商原生读数 `Fan/Status: CPU_PL1=120 / PL2=150 / PL4=200`——属厂商侧口径问题，非本仓库配置。
- [ ] **L1 power-slider overlay has AC/DC direction swapped** (L1 电源滑块 overlay AC/DC 方向装反) — 🟥 to fix. AC mounts power-save, DC mounts high-performance; UI tier vs actual power plan are reversed. Scope: Windows `mr_gui_v6` overlay. / AC 挂省电、DC 挂高性能，UI 档位与实际电源计划相反。范围：Windows `mr_gui_v6` overlay。
- [ ] **MQTT broker listens on `0.0.0.0:13688` (not loopback-only) + plaintext auth** (MQTT broker 监听+明文认证) — 🟨 security note. Recommend firewall-blocking that inbound port; local loopback use unaffected. / 建议防火墙阻断该端口入站；不影响本机回环使用。
- [ ] **GPU temperature register `0x44C` has one counter-evidence** (GPU 温度寄存器 `0x44C` 一次反向证据) — 🟨 to arbitrate. A 22°C reading below ambient; needs third-party re-test. / 读数 22°C 低于环境温，需第三方复测仲裁。
- [ ] **Linux docs not synced with Windows-side corrections** (Linux 侧文档未同步 Windows 侧纠错) — 🟨 docs. Corrections like `0x44F→0x44C`, `45W→35W` not written back to Linux docs. / `0x44F→0x44C`、`45W→35W` 等纠错未回写到 Linux 相关文档。
- [x] **README layer-02 file count fixed** (README 02 层文件计数错误) — 🟩 2026-08-31. Was 214, actually 212; aligned with `git ls-files`. / 原声称 214，实为 212，已修正。

---

## 🤝 Contribution · Security · Updates 贡献 · 安全 · 更新

> Contributions and security reporting follow the guidelines below. / 贡献与安全报告请遵循以下指南。

- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution guide incl. the hard rule "never commit private / reverse-engineering originals" 贡献指南（含「禁止提交私有/逆向原文」铁律）
- [.github/SECURITY.md](.github/SECURITY.md) — Security policy & vulnerability disclosure 安全政策与漏洞报告渠道
- [CHANGELOG.md](CHANGELOG.md) — Change log 变更记录
- [THIRDPARTY.md](THIRDPARTY.md) — Third-party components & licenses 第三方组件与许可清单
- [.github/FUNDING.yml](.github/FUNDING.yml) — Donation/Sponsor placeholder template (left empty by default; enable only after the repo is public and you decide to accept sponsorship) 捐赠/Sponsor 占位模板（默认全留空，仓库公开且你决定开放赞助后再启用）

## 📄 License 许可

**English:** This project is licensed under the **MIT License** (see [LICENSE](LICENSE)), Copyright © **段雪健 (Duan Xuejian)**. The third-party components it references (ryzenadj = LGPL-3.0, WinRing0 = Modified BSD, inpoutx64.dll = Freeware, readjustService = LGPL, etc.) are distributed in parallel under their own licenses; list & sources in [THIRDPARTY.md](THIRDPARTY.md).

**中文：** 本项目以 **MIT License** 授权（见 [LICENSE](LICENSE)），版权归 **段雪健 (Duan Xuejian)**。本项目引用的第三方组件（ryzenadj = LGPL-3.0、WinRing0 = Modified BSD、inpoutx64.dll = Freeware、readjustService = LGPL 等）以各自独立许可**并行分发**，清单与出处见 [THIRDPARTY.md](THIRDPARTY.md)。

---

## 💰 Donation / Sponsorship 打赏 · 赞助

> If this project helps you, you are welcome to voluntarily support the author. Donations do not change the MIT free-license nature. / 若本项目对你有帮助，欢迎自愿支持作者。打赏不改变 MIT 的免费许可性质。

| 微信 (WeChat) | 支付宝 (Alipay) |
|------|------|
| ![微信收款码](assets/donate_wechat.jpg) | ![支付宝收款码](assets/donate_alipay.jpg) |