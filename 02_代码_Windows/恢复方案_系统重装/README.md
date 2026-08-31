# 蛟龙15K 系统重装恢复方案

## 机器信息

- 机型: 蛟龙15K (Uniwill GM5BG0E)
- CPU: AMD Ryzen 7 7435H
- GPU: RTX 4060 Laptop
- 系统: Windows 11 Pro Build 26200
- ProjectID: 16

## 关键路径

| 项目 | 路径 |
|------|------|
| Python | `C:\Users\<USER>\AppData\Local\Programs\Python\Python312\python.exe` |
| 工作目录 | `D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0\` |
| 恢复脚本 | `D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\恢复方案_系统重装\install.py` |

## MQTT信息

| 项目 | 值 |
|------|-----|
| Broker | `127.0.0.1:13688` |
| 进程 | GCUBridge.exe (必须安装) |
| 默认槽位 | 7 (候选: 7,3,4,2,6,8) |
| ClientId | `PluginClient_N` (N=进程号%10) |

## 电源计划

| 计划名 | GUID | PL1/PL2/PL4 | 用途 |
|--------|------|-------------|------|
| MR-极限性能 | 动态创建 | 80/80/100W | AC供电S1 |
| MR-均衡模式 | `19ff782b-5b3b-48a2-aaa3-b9b63ce751bc` | 65/65/100W | DC供电S2 |
| MR-超级省电 | `3a99624d-672a-43d3-93d6-9f78114bb9ae` | 35/35/100W | DC极限S3 |

## 三场景自动切换

| 场景 | MQTT模式 | 电源计划 | 刷新率 | 触发条件 |
|------|----------|----------|--------|----------|
| S1 带电极限 | turbo(2) | MR-极限性能 | 165Hz | 插电(auto=True) |
| S2 离电均衡 | gaming(1) | MR-均衡模式 | 165Hz | 拔电(auto=True) |
| S3 极限续航 | office(0) | MR-超级省电 | 60Hz | 手动选择 |

## UDP命令

端口: `127.0.0.1:13690` (UDP)

| 命令 | 功能 | auto状态 |
|------|------|----------|
| `perf` | 切到S1极限性能 | False |
| `bal` | 切到S2离电均衡 | False |
| `eco` | 切到S3极限续航 | False |
| `select max/bal/eco` | 切换场景 | True(保留) |
| `auto` | 恢复自动 | True |
| `status` | 查询状态(JSON) | - |

## 文件依赖关系

```
mr_daemon.py (核心引擎)
├── mr_console.py (MQTT协议)
│   └── mr_ec_hw.py (EC硬件读写, 需要UWACPIDriver.sys)
└── mr_win_ctrl.py (电源计划/刷新率/进程管理)

mr_gui_v6.py / mr_gui_v6qt.py (GUI控制台)
└── mr_console.py

mr_powersaver.py (轻量AC/DC切换: 刷新率+电源计划, 无MQTT依赖, 开机自启)
└── mr_win_ctrl.py
```

> **2026-08-28 变更**: 日常自动管理由 `mr_powersaver.py` 承担(Startup文件夹vbs自启, vbs必须GBK编码)。
> mr_daemon.py 仅在需要 MQTT/场景引擎 时手动启动。MRDaemon_SMU 计划任务已禁用。

## 恢复步骤

### 方案A: 一键安装(推荐)

```powershell
# 以管理员权限运行
Start-Process python -Verb RunAs -ArgumentList "D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\恢复方案_系统重装\install.py"
```

### 方案B: 手动恢复

```powershell
# 1. 安装依赖
pip install paho-mqtt PyQt5

# 2. 复制核心模块到工作目录
Copy-Item "核心模块\*" "D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\现役_v6.0\"

# 3. 创建电源计划
powercfg /duplicatescheme 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
# 记录新GUID, 重命名
powercfg /changename <GUID> "MR-极限性能"
powercfg /setacvalueindex <GUID> SUB_PROCESSOR PROCTHROTTLEMAX 100

# 4. 启动mr_powersaver(install.py会自动注册Startup自启vbs)
Start-Process pythonw "D:\...\自制控制台_v6.0_20260826\mr_powersaver.py"
```

### 方案C: 拖给AI

将本文件夹拖给AI，AI会:
1. 读取本README获取机器信息和配置
2. 执行install.py安装依赖和创建电源计划
3. 复制文件到工作目录
4. 启动daemon并验证

## 故障排查

| 问题 | 诊断命令 | 解决方案 |
|------|----------|----------|
| powersaver没自启 | `type "...\Startup\mr_powersaver.vbs"` | vbs必须GBK编码+三重引号转义; 看 powersaver.log |
| daemon未启动(如需) | `netstat -ano \| findstr 13690` | 杀掉占用进程后手动启动 |
| MQTT连接失败 | `tasklist \| findstr GCUBridge` | 启动GCUBridge.exe |
| 电源计划丢失 | `powercfg /list \| findstr MR-` | powersaver启动时自动重建(极限性能GUID动态, plan_guids.json只是缓存) |
| EC读写失败 | 检查UWACPIDriver.sys | 重新安装驱动 |

## 更新记录

- 2026-08-27: v2.2 plan_watcher/select命令/GUID缓存/恢复方案
- 2026-08-26: v2.1 三场景引擎/断线自愈/槽位轮询
- 2026-08-25: v6.0 控制台GUI/1155+按钮/29项测试
