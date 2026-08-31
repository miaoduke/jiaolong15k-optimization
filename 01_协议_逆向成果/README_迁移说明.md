# 迁移说明

本目录围绕「**只公开结论与方法论，不公开破解工序/取证原文**」的分层原则，将含 OEM 专有内容、机器个资、或属逆向破解工序的取证文件移入 `_private_不上传\OEM反编译产物\01_协议_逆向成果_迁移\`（不入库，见 README「内容分层原则」与 `.gitignore`）。

## 第一批迁移（2026-08-30 穷尽审计后）

OEM 衍生复制物（反编译产物/字串/个资）：

| 原路径 | 文件名 | 性质 |
|---|---|---|
| 官方配置样本/ | CCUWinUI_全大写token43.txt | OEM 字符串 dump（反编译产物） |
| 官方配置样本/ | CCUWinUI_指令相关串157.txt | OEM 字符串 dump（反编译产物） |
| 官方配置样本/ | 写入模板全表47个.txt | OEM 字符串 dump（反编译产物） |
| DefaultTool反射/ | TrayLanguage_zh-cn.json | 官方 UI 译文（反编译产物） |
| DefaultTool反射/ | processcontrol.reg | OEM 注册表快照（机器个资） |

## 第二批迁移（2026-08-31 内容分层加固）

按「严格」边界，将逆向破解工序与取证原文一并迁入私有层：

| 原路径 | 文件名 | 性质 |
|---|---|---|
| 抓包样本/ | 决定性抓包_SET_OPERATING_MODE_DETAIL_65指令.txt | 抓包样本（取证原文，106KB） |
| MQTT协议/ | 启动握手抓包_20260823.txt | 抓包样本（取证原文） |
| MQTT协议/ | dump_cred.ps1 / get_cred2.ps1 / get_key2.ps1 | 取凭据反射脚本（破解工序） |
| MQTT协议/ | reflect_cm.ps1 | CommandManager 反射取证脚本 |
| 官方配置样本/ | setup.ini / setup_new.ini / 官方UI驱动全量抓包_107KB.txt | OEM 配置样本 + 抓包原文 |
| DefaultTool反射/ | dt_enums.ps1 / dt_reflect.ps1 / dt_types.ps1 / verify_fan.ps1 | DefaultTool 反射取证脚本 |

## 保留在公开层的定位

- **自写方法/测试工具**（凭据已 `<REDACTED_PWD_SALT>` 占位）：`MQTT协议/mqtt_listen.ps1`、`mqtt_publish_test.ps1`
- **结论与协议规范**：`全部收获总汇_20260823.md`、`MQTT协议/协议破解文档_20260823.md`
- **参考源**：`EC与ACPI参考/`（uniwill-acpi.c 上游源码、ryzenadj、来源说明）

涉及已迁产物的技术结论（密钥构成、Token/指令串、模板表、寄存器映射）均已在《全部收获总汇》与各结论文档固化为**自写内容**，不依赖源文件即可索引；需查取证原件的，请到 `_private_不上传\OEM反编译产物\01_协议_逆向成果_迁移\` 对应位置。