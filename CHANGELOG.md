# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，语义化版本见各子模块（`现役_v6.0` / `jcc_console_v2.3`）。

## [未发布 / 2026-09-01]

### Changed（文档 / 合规）
- 同步 GM5BG0E 键盘 IRQ 上游补丁状态（`03_代码_Linux/固件修复_键盘/README.md`）。
- README 新增《关于官方电竞控制台》双语说明：三层服务链（三进程）、充电阈值控制无效、三种电池模式无效（性能策略花名）、省电下后台干扰与第三方省电冲突、建议离电模式彻底关闭官方栈；并对旧「开控制台=41W/关=9W」数字标注 0x7A6 已仲裁撤回、仅作定性理解。
- README 双系统对比表 / Key Conclusions / Known Issues 更新充电限流为「Linux 实测生效、Windows 固件不执行」。

## [未发布 / 2026-08-31]

### Changed（文档 / 合规）
- 新增 `THIRDPARTY.md`：声明 ryzenadj(LGPL-3.0)、WinRing0(Modified BSD)、inpoutx64(Freeware)、readjustService(LGPL) 的许可与出处。
- 新增 `.github/SECURITY.md` 安全政策。
- 新增 `CONTRIBUTING.md` 贡献指南（含"禁止提交私有/逆向原文"铁律）。
- README 顶部增加厂商逆向免责声明与风险提示。
- 修正过时描述：`smu_profile.json` 越界警告失效、`0x7A6` 实机仲裁定案为可写标志位（撤回"实时功率"误判）。

### Security
- 补脱敏 `OcScannerPwd123` / `OpenCLPwd123` 两处明文弱口令。
- `mr_ec_hw.ec_write` 聚合 WMI 后备回读验证；`mr_win_ctrl._reg_set` 增加 UAC 回退回读校验。

### Removed
- 清理公共层 `__pycache__` / 运行时日志；OEM 衍生物移入 `_private_不上传`。