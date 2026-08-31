# 迁移说明（2026-08-30 穷尽审计后）

本目录中以下 **OEM 衍生复制物** 已于 2026-08-30 移入 `_private_不上传\OEM反编译产物\01_协议_逆向成果_迁移\`，依据 README L103-114「未公开内容不入库」之声明（与仓库自述一致化）：

| 原路径 | 文件名 | 性质 |
|---|---|---|
| 官方配置样本/ | CCUWinUI_全大写token43.txt | OEM 字符串 dump（反编译产物） |
| 官方配置样本/ | CCUWinUI_指令相关串157.txt | OEM 字符串 dump（反编译产物） |
| 官方配置样本/ | 写入模板全表47个.txt | OEM 字符串 dump（反编译产物） |
| DefaultTool反射/ | TrayLanguage_zh-cn.json | 官方 UI 译文（反编译产物） |
| DefaultTool反射/ | processcontrol.reg | OEM 注册表快照（机器个资） |

涉及这些产物的技术结论（Token 清单、指令串、模板表）已在各抓包文档与《全部收获总汇》中固化为自写内容，不依赖源文件即可索引；需要查原件的请到私有目录对应位置。其余保留文件（setup.ini / setup_new.ini / 官方UI驱动全量抓包 / dt_*.ps1 / verify_fan.ps1）为本项目自采抓包或自写脚本，维持公开。