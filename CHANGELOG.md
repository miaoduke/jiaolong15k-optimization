# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，语义化版本见各子模块（`现役_v6.0` / `jcc_console_v2.3`）。

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