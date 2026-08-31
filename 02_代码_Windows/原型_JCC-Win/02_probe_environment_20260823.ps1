<#
.SYNOPSIS
  JCC-Win M0 环境探测脚本（只读，不修改任何系统状态）
.DESCRIPTION
  为 JCC-Win 设计方案 §3.0 收集四要素证据：
  ① 厂商二进制(ACPIDriverDll.dll/GCUService.exe)存在性
  ② UWACPIDriver 驱动/服务装载状态
  ③ Uniwill WMI (root\wmi ABBC*) 接口清单
  ④ HVCI/内存完整性与驱动封锁相关安全策略状态
.NOTES
  建议: 以管理员身份运行 PowerShell 后执行。
  运行: powershell -ExecutionPolicy Bypass -File .\02_probe_environment_20260823.ps1
#>

[CmdletBinding()]
param()
$ErrorActionPreference = 'Continue'
$sect = 0
function Section($title) {
    $script:sect++
    ""
    "=" * 78
    "[$sect] $title"
    "=" * 78
}

Section "系统信息"
$os = Get-CimInstance Win32_OperatingSystem
"OS          : $($os.Caption) build $($os.BuildNumber)"
"版本         : $([Environment]::OSVersion.VersionString)"
"机型         : $((Get-CimInstance Win32_ComputerSystem).Manufacturer) / $((Get-CimInstance Win32_ComputerSystem).Model)"
"BIOS        : $((Get-CimInstance Win32_BIOS).SMBIOSBIOSVersion) ($((Get-CimInstance Win32_BIOS).ReleaseDate))"
"管理员权限   : $(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))"

Section "④ 安全策略: 内存完整性(HVCI) / 易受攻击驱动封锁"
try {
    $dg = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard -ErrorAction Stop
    "VBS 状态            : $($dg.VirtualizationBasedSecurityStatus) (0=off 1=enabled-not-running 2=running)"
    "HVCI 运行中          : $(($dg.SecurityServicesRunning -contains 2))"
    "易受攻击驱动封锁列表 : $(($dg.VulnerableDriverBlocklistEnable))"
} catch { "读取失败: $_" }
"(封锁列表开启时 WinRing0 类驱动无法加载 —— JCC-Win 不使用它们, 此项仅作环境记录)"

Section "① 厂商控制台安装目录探测 (Program Files\OEM)"
$oemRoots = @("C:\Program Files\OEM", "C:\Program Files (x86)\OEM")
foreach ($r in $oemRoots) {
    if (Test-Path $r) {
        "[存在] $r"
        Get-ChildItem $r -Recurse -Include *.exe,*.dll -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match 'ACPIDriver|GCUService|Systray|UWACPI|Gaming|Control' } |
            ForEach-Object { "   $($_.FullName)  ($('{0:N0}' -f $_.Length) bytes)" }
    } else { "[不存在] $r" }
}
$ccGuess = Get-ChildItem "C:\Program Files" -Directory -ErrorAction SilentlyContinue | Where-Object Name -match '机械革命|MechRevo|OEM'
if ($ccGuess) { "[补充匹配目录]" ; $ccGuess | ForEach-Object { "   $($_.FullName)" } }

Section "官方 UWP 包 (GamingCenter) 存在性 → 双写者互斥对象"
try {
    $appx = Get-AppxPackage | Where-Object { $_.Name -match 'GamingCenter|ControlCenter|Mechrevo' -or $_.Publisher -match 'Mechrevo' }
    if ($appx) { $appx | ForEach-Object { "包名: $($_.PackageFullName)"; "  InstallLocation: $($_.InstallLocation)" } }
    else { "未发现已安装的官方控制台 Appx 包 (可能已清理)" }
} catch { "Get-AppxPackage 失败: $_" }

Section "② 相关服务状态 (GCU/Systray/Uniwill/UWACPI)"
Get-Service -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'GCU|Systray|UWACPI|Uniwill' -or $_.DisplayName -match 'GCU|Systray|Uniwill|UWACPI|机械革命'
} | Format-Table Name, Status, StartType, DisplayName -AutoSize

Section "② 内核驱动装载状态 (uwacpidriver 等)"
Get-CimInstance Win32_SystemDriver -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'uwacpi|uniwill' -or $_.PathName -match 'uwacpi|uniwill'
} | Format-Table Name, State, StartMode, PathName -AutoSize
"[DriverStore 备份在档检查]"
$dbk = "D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\驱动备份\drivers_backup"
Get-ChildItem $dbk -Directory -ErrorAction SilentlyContinue | Where-Object Name -match 'uwacpidriver' | ForEach-Object { "   $($_.FullName)" }

Section "② PnP 设备: UWACPI / INOU / Uniwill ACPI 节点"
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.FriendlyName -match 'UWACPI|INOU|Uniwill' -or $_.InstanceId -match 'UWACPI|INOU'
} | Format-Table Status, Class, FriendlyName, InstanceId -AutoSize

Section "③ Uniwill WMI 接口枚举 (root\wmi, GUID ABBC0F6A~F72 族)"
try {
    $ns = [WMIClass]"root\wmi:__NAMESPACE"
    $classes = Get-CimClass -Namespace root\wmi -ErrorAction Stop | Where-Object { $_.CimClassName -match 'ABBC|UNIWILL|INOU' }
    if ($classes) {
        $classes | ForEach-Object {
            "类: $($_.CimClassName)"
            $_.CimClassMethods | ForEach-Object { "   方法: $($_.Name)" }
        }
    } else { "root\wmi 下未发现 ABBC*/UNIWILL*/INOU* 类 (后端 B 不可用)" }
} catch { "WMI 枚举失败: $_" }

Section "GPU: NVIDIA 驱动与功耗墙只读查询"
$nvidiaSmi = @("$env:SystemRoot\System32\nvidia-smi.exe",
               "C:\Windows\System32\nvidia-smi.exe",
               "$env:ProgramFiles\NVIDIA Corporation\NVSMI\nvidia-smi.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $nvidiaSmi) {
    $cmd = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($cmd) { $nvidiaSmi = $cmd.Source }
}
if ($nvidiaSmi) {
    "nvidia-smi: $nvidiaSmi"
    & $nvidiaSmi --query-gpu=name,driver_version,power.limit,power.max_limit,power.min_limit,temperature.gpu --format=csv,noheader
    "(若 power.max_limit 显示 [N/A] 即为陷阱11 同款: SBIOS 未开放手动改墙 — 方案已按'不做 GPU 手动调墙'设计)"
} else { "未找到 nvidia-smi" }

Section "电池与电源"
Get-CimInstance Win32_Battery | Format-List Name, EstimatedChargeRemaining, BatteryStatus
powercfg /a 2>$null | Select-Object -First 8
"活动电源方案:"
powercfg /getactivescheme

Section ".NET 运行时 (JCC-Win 目标 .NET 8)"
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if ($dotnet) { dotnet --list-runtimes 2>$null } else { "未检测到 dotnet CLI (不影响单文件自包含发布运行)" }

Section "探测完成"
"请将以上全部输出回填至 01_JCC-Win_总体设计方案_v1_20260823.md §3.0 并归档。"
