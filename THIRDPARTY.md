# 第三方组件清单（THIRDPARTY）

本仓库在公开表现层引用了以下第三方组件。它们以**各自独立许可**附带/分发，与项目主体的 MIT License 并行共存，**非派生混合体**。使用/再分发前请核对各上游许可全文。

| 组件 | 上游/来源 | 许可证 | 用途 | 说明 |
|---|---|---|---|---|
| `ryzenadj`（`ryzenadj.exe` / `libryzenadj.dll`） | [FlyGoat/RyzenAdj](https://github.com/FlyGoat/RyzenAdj) | **LGPL-3.0** | SMU / APU 功耗与温度访问 | 动态链接开源库；保留源码头版权与许可声明；LGPL 允许在可替换的基础上继续自由使用 |
| `WinRing0x64.sys` / `WinRing0x64.dll` | OpenLibSys（hiyohiyo） | **Modified BSD**（⚠️ 存在以 GPL 重新授权的 fork 变体，**以随包文件头为准**） | 内核级 I/O 端口 / MSR / PCI 访问 | 宽松许可，与 MIT 兼容 |
| `inpoutx64.dll` | Logix4U / Highresolution Enterprises | **闭源 Freeware** | 免安装驱动的 I/O 访问回退 | 非开源免费组件。**仅限个人本机使用（个人研究/自用）**：免费授权不含再分发权利，**不得随本仓库把动态库二进制复制分发**，也不得自行修改再分发；若改用为内核 I/O，请改由仓库自有/已授权驱动承担该通路 |
| `readjustService.ps1` | Falco（readjust 工具派生） | **LGPL**（具体版本以其源文件头为准） | 功耗保持脚本 | 仅在归档/说明中提及，**现役已停用** |
| 官方「电竞控制台」反编译产物（字符串 dump / UI 译文 / OEM 注册表快照） | 机械革命/Uniwill 原厂 | **专有·非公开**（厂商保留版权） | 逆向研究参照 | **不随公开仓发布**；个人使用用途，未获授权请勿再分发 |

## 许可依据（核对日期 2026-08-31）
- `ryzenadj`：LGPL-3.0（上游源码 SPDX 头、[Arch AUR 元数据](https://aur.archlinux.org/packages/ryzenadj)、公开使用手册）
- `WinRing0`：Modified BSD（[原 OpenLibSys 声明](https://www.freefixer.com/library/file/winring0x64.sys-274804)、[winring0_1_3_0](https://github.com/5455945/WinRing0_1_3_0)）
- `inpoutx64.dll`：Freeware（[dll 元数据](https://gridinsoft.com/online-virus-scanner/id/a617f81aa9082b5743833ab93d9c2a47af81dfdae26edbcd8a6ecd1308aaa06a)）

> ⚠️ 以上许可证判定基于公开检索，非法律意见。对外公开发布前请从各上游官方仓库核实装订的许可证全文，并在 `THIRDPARTY` 中保留精确版本号。