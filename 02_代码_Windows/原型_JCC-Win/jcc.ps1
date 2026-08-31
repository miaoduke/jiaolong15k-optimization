# jcc.ps1 — JCC-Win v1 蛟龙控制中心 (Windows CLI 版)
# 目标: 替代官方 GamingCenter3 的本机全部可用功能
# 通路: 厂商 ACPIDriverDll.dll (ReadEC/WriteEC) — 已于 2026-08-23 实测打通
# 规则: 所有写入记录原值到 %TEMP%\jcc_writelog.csv; 写后必回读; 高危操作需 -Confirm
# 用法: powershell -File jcc.ps1 <命令> [参数] [-Confirm]
[CmdletBinding()]
param(
    [Parameter(Position=0)][string]$Cmd = "monitor",
    [Parameter(Position=1, ValueFromRemainingArguments=$true)][string[]]$Rest,
    [switch]$Confirm
)
$ErrorActionPreference = 'Stop'
$DLL = "C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
$LOG = Join-Path $env:TEMP "jcc_writelog.csv"

if (-not ('JccHal' -as [type])) {
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class JccHal {
    static IntPtr _h = IntPtr.Zero;
    public static bool Load(string path) {
        if (_h != IntPtr.Zero) return true;
        _h = LoadLibrary(path); return _h != IntPtr.Zero;
    }
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern IntPtr LoadLibrary(string path);
    [DllImport("ACPIDriverDll", EntryPoint="ReadEC",  SetLastError=true)] public static extern int ReadEC(int addr);
    [DllImport("ACPIDriverDll", EntryPoint="WriteEC", SetLastError=true)] public static extern int WriteEC(int addr, int val);
}
"@
}
if (-not [JccHal]::Load($DLL)) { throw "无法加载厂商 DLL: $DLL (官方控制台组件缺失?)" }

function Read-EcReg([int]$a) { [JccHal]::ReadEC($a) }
function Write-EcReg([int]$a, [int]$v, [bool]$confirmNeeded) {
    if ($confirmNeeded -and -not $Confirm) { throw "此为写入操作，需追加 -Confirm 执行" }
    $old = Read-EcReg $a
    [void][JccHal]::WriteEC($a, $v)
    $new = Read-EcReg $a
    if (-not (Test-Path $LOG)) { "time,addr,old,new,readback" | Set-Content $LOG }
    "{0},{1},{2},{3},{4}" -f (Get-Date -Format s), ('0x{0:X}' -f $a), $old, $v, $new | Add-Content $LOG
    if ($new -ne ($v -band 0xFF)) { Write-Warning ("回读不一致 addr=0x{0:X2} 写={1} 读={2}" -f $a,$v,$new) }
    return @{ Old=$old; New=$new }
}
# EC 寄存器地图 (Linux 侧逆向 + 官方 ECSpec 双重背书, OS 无关)
$REG = @{ Cptm=0x43E; Vgat=0x44F; Ffan=0x460; PwmCpu=0x461; RpmCHi=0x464; RpmCLo=0x465
          PeakT=0x463; PwmGpu=0x469; RpmGHi=0x46C; RpmGLo=0x46D; Adpt=0x49F
          FanCtl=0x751; Sup1=0x765; Sup2=0x766; Trig=0x767; CR=0x769; CG=0x76A; CB=0x76B
          KblSw=0x78C; FnWinLock=0x74E; ChargeLim=0x7B9; GateFan=0x7C6; Breath=0x7C5
          CurveMagicLo=0x0F5D; CurveMagicHi=0x0F5E; CurveMode=0x0F5F; CurveBase=0x0F00 }

# ---------- 功能实现 ----------
function Show-Monitor {
    $ac = if ((Read-EcReg $REG.Adpt) -eq 0x0A) {"AC"} else {"BAT"}
    $rpmC = (Read-EcReg $REG.RpmCHi) * 256 + (Read-EcReg $REG.RpmCLo)
    $rpmG = (Read-EcReg $REG.RpmGHi) * 256 + (Read-EcReg $REG.RpmGLo)
    $gpu = (& nvidia-smi --query-gpu=power.draw,temperature.gpu,utilization.gpu --format=csv,noheader,nounits) -split ', '
    $bat = Get-CimInstance Win32_Battery
    "JCC-Win 监控 @ $(Get-Date -Format HH:mm:ss)"
    "供电:$ac | CPU:{0}°C(峰值{1}) | GPU:{2}°C/{3}W/{4}%" -f (Read-EcReg $REG.Cptm),(Read-EcReg $REG.PeakT),$gpu[1],$gpu[0],$gpu[2]
    "风扇 CPU: PWM={0} RPM≈{1} | GPU: PWM={2} RPM≈{3} | FanCtl=0x{4:X2}" -f (Read-EcReg $REG.PwmCpu),$rpmC,(Read-EcReg $REG.PwmGpu),$rpmG,(Read-EcReg $REG.FanCtl)
    "电池: $($bat.EstimatedChargeRemaining)% | RGB当前: R{0} G{1} B{2}(Level制)" -f (Read-EcReg $REG.CR),(Read-EcReg $REG.CG),(Read-EcReg $REG.CB)
}

function Set-RgbColor([int]$r,[int]$g,[int]$b) {   # Level 制 0-50, 官方同款寄存器
    foreach ($t in @(@(0x769,$r),@(0x76A,$g),@(0x76B,$b))) { Write-EcReg $t[0] ([Math]::Min(50,$t[1])) $false }
    Write-EcReg 0x767 ((Read-EcReg 0x767) -bor 0x20) $false          # bit5 应用颜色
    "RGB 静态色已应用 ($r,$g,$b)/50"
}
function Set-RgbRainbow([bool]$on) {
    if ($on) { Write-EcReg 0x767 ((Read-EcReg 0x767) -bor 0x80) $false } else { Write-EcReg 0x767 ((Read-EcReg 0x767) -band (-bnot 0x80)) $false }
    "彩虹灯效: $on"
}
function Set-RgbPower([string]$s) {
    $cur = Read-EcReg 0x78C
    if ($s -eq 'off') { Write-EcReg 0x78C ($cur -bor 0x02) $false } else { Write-EcReg 0x78C ($cur -band (-bnot 0x02)) $false }
    "键盘灯电源: $s (0x78C -> 0x{0:X2})" -f (Read-EcReg 0x78C)
}
function Show-RgbState { "Trig=0x{0:X2} RGB=({1},{2},{3}) Breath(0x7C5)=0x{4:X2} Sup=0x{5:X2}/0x{6:X2}" -f `
    (Read-EcReg 0x767),(Read-EcReg $REG.CR),(Read-EcReg $REG.CG),(Read-EcReg $REG.CB),(Read-EcReg 0x7C5),(Read-EcReg $REG.Sup1),(Read-EcReg $REG.Sup2) }
function Set-RgbBattery {                           # 官方 BatteryPercent 灯效等效实现
    $c = (Get-CimInstance Win32_Battery).EstimatedChargeRemaining
    $col = if ($c -ge 60) {@(0,50,0)} elseif ($c -ge 30) {@(50,25,0)} else {@(50,0,0)}
    Set-RgbColor $col[0] $col[1] $col[2]; "电量灯: $c% -> 颜色已更新"
}

function Set-RgbBreathe([string]$s) {              # 呼吸灯 0x7C5（位协议待校准，标注实验性）
    if ($s -eq 'on') { Write-EcReg 0x7C5 ((Read-EcReg 0x7C5) -bor 0x01) $true } else { Write-EcReg 0x7C5 ((Read-EcReg 0x7C5) -band (-bnot 0x01)) $true }
    "呼吸灯效: $s (0x7C5 -> 0x{0:X2})" -f (Read-EcReg 0x7C5)
}
function Set-RgbLevel([int]$lv) {                  # 官方亮度 5 档 -> Level 基准 10/20/30/40/50，等比缩放当前色
    if ($lv -lt 1 -or $lv -gt 5) { throw "level 范围 1-5" }
    $base = $lv * 10
    $cR = Read-EcReg 0x769; $cG = Read-EcReg 0x76A; $cB = Read-EcReg 0x76B
    $max = [Math]::Max([Math]::Max($cR,$cG),$cB)
    if ($max -eq 0) { Write-EcReg 0x769 $base $false; Write-EcReg 0x76A $base $false; Write-EcReg 0x76B $base $false }
    else {
        Write-EcReg 0x769 ([Math]::Round($cR * $base / $max)) $false
        Write-EcReg 0x76A ([Math]::Round($cG * $base / $max)) $false
        Write-EcReg 0x76B ([Math]::Round($cB * $base / $max)) $false
    }
    Write-EcReg 0x767 ((Read-EcReg 0x767) -bor 0x20) $false
    "亮度档 $lv (基准 $base): RGB -> ({0},{1},{2})" -f (Read-EcReg 0x769),(Read-EcReg 0x76A),(Read-EcReg 0x76B)
}
function Set-FanMode([string]$m) {					# 官方 MyFanCTLByteFlag 语义
    switch ($m) {
      'normal' { Write-EcReg $REG.FanCtl 0x00 $true }
      'boost'  { Write-EcReg $REG.FanCtl 0x40 $true }        # FanBoost 一键增压
      default  {
        if ($m -match '^user([1-5])$') { Write-EcReg $REG.FanCtl (0x80 + [int]$Matches[1]) $true }
        else { throw "fan 模式: normal|boost|user1..user5" }
      }
    }
    "FanCtl(0x751) -> 0x{0:X2}" -f (Read-EcReg $REG.FanCtl)
}
function Set-FanPwm([int]$pwm) {                    # 直驱双风扇 0-200 (需持续写保持, 见 09 报告)
    if ($pwm -gt 200) { throw "PWM 上限 200 (EC 标度)" }
    Write-EcReg $REG.PwmCpu $pwm $true; Write-EcReg $REG.PwmGpu $pwm $true
    "注意: 单次写约 1.5s 后被 EC 覆写; 持续保持请用循环调用"
}
function Set-FanProfile([string]$p) {               # 官方智能风扇表协议 (09 报告实测版)
    $mode = @{ perf=1; balanced=2; standard=2; quiet=3; whisper=4 }[$p]
    if (-not $mode) { throw "profile: perf|balanced|quiet|whisper" }
    Write-EcReg $REG.CurveMode $mode $true
    Write-EcReg $REG.CurveMagicLo 0xFD $true; Write-EcReg $REG.CurveMagicHi 0xC9 $true
    Write-EcReg $REG.GateFan ((Read-EcReg $REG.GateFan) -bor 0x04) $true   # 门控 0x7C6 bit2
    "风扇曲线档 '$p' 已注入 (magic 校验: Lo=0x{0:X2} Hi=0x{1:X2})" -f (Read-EcReg $REG.CurveMagicLo),(Read-EcReg $REG.CurveMagicHi)
}

function Set-ChargeLimit([object]$v) {
    if ($v -eq 'show') { "充电阈值(0x7B9) = {0}%" -f (Read-EcReg $REG.ChargeLim); return }
    $n = [int]$v; if ($n -lt 40 -or $n -gt 100) { throw "范围 40-100" }
    Write-EcReg $REG.ChargeLim $n $true; "充电阈值已设为 $n%"
}
function Set-WinLock([string]$s) {
    $cur = Read-EcReg $REG.FnWinLock
    if ($s -eq 'on') { Write-EcReg $REG.FnWinLock ($cur -bor 0x20) $true } else { Write-EcReg $REG.FnWinLock ($cur -band (-bnot 0x20)) $true }
    "Win 锁(super_key): $s (0x74E -> 0x{0:X2})" -f (Read-EcReg $REG.FnWinLock)
}
function Set-FnLock([string]$s) {
    $cur = Read-EcReg $REG.FnWinLock
    if ($s -eq 'on') { Write-EcReg $REG.FnWinLock ($cur -bor 0x10) $true } else { Write-EcReg $REG.FnWinLock ($cur -band (-bnot 0x10)) $true }
    "Fn 锁: $s (0x74E -> 0x{0:X2})" -f (Read-EcReg $REG.FnWinLock)
}
function Set-RefreshHz([int]$hz) {
    if (-not ('JccDisp' -as [type])) { Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public struct DEVMODE { [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string dmDeviceName;
  public ushort dmSpecVersion,dmDriverVersion,dmSize,dmDriverExtra; public uint dmFields;
  public int dmPositionX,dmPositionY; public uint dmDisplayOrientation,dmDisplayFixedOutput;
  public short dmCmpMethod,dmCopies,dmPaperLength,dmPaperWidth,dmScale;
  public uint dmBitsPerPel,dmPelsWidth,dmPelsHeight,dmDisplayFlags,dmDisplayFrequency;
  public uint dmICMMethod,dmICMIntent,dmMediaType,dmDitherType,dmReserved1,dmReserved2,dmPanningWidth,dmPanningHeight; }
public static class JccDisp {
  [DllImport("user32")] public static extern int EnumDisplaySettings(string dev, int mode, ref DEVMODE dm);
  [DllImport("user32", CharSet=CharSet.Unicode)] public static extern int ChangeDisplaySettingsEx(string dev, ref DEVMODE dm, int hwnd, uint flags, System.IntPtr lp);
}
"@
    }
    Add-Type -AssemblyName System.Windows.Forms | Out-Null
    $dev = [System.Windows.Forms.Screen]::PrimaryScreen.DeviceName
    $dm = New-Object DEVMODE; $dm.dmSize = [Runtime.InteropServices.Marshal]::SizeOf([type][DEVMODE])
    [void][JccDisp]::EnumDisplaySettings($dev, -1, [ref]$dm)
    $w = $dm.dmPelsWidth; $h = $dm.dmPelsHeight
    $avail = @(); $i = 0; $tmp = New-Object DEVMODE; $tmp.dmSize = $dm.dmSize
    while ([JccDisp]::EnumDisplaySettings($dev, $i++, [ref]$tmp)) {
        if ($tmp.dmPelsWidth -eq $w -and $tmp.dmPelsHeight -eq $h) { $avail += $tmp.dmDisplayFrequency }
    }
    if ($avail -notcontains $hz) { throw "当前 ${w}x${h} 无 ${hz}Hz 模式。可用: $($avail | Sort-Object -Unique) " }
    $dm.dmFields = 0x80000 -bor 0x100000 -bor 0x400000   # PELSWIDTH|PELSHEIGHT|FREQUENCY
    $r = [JccDisp]::ChangeDisplaySettingsEx($dev, [ref]$dm, 0, 0, [IntPtr]::Zero)
    "刷新率 -> ${hz}Hz (ChangeDisplaySettingsEx 返回 $r, 0=成功)"
}
function Show-RefreshList {
    Add-Type @'
using System.Runtime.InteropServices;
public struct DEVMODE { [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string dmDeviceName;
  public ushort dmSpecVersion,dmDriverVersion,dmSize,dmDriverExtra; public uint dmFields;
  public int dmPositionX,dmPositionY; public uint dmDisplayOrientation,dmDisplayFixedOutput;
  public short dmCmpMethod,dmCopies,dmPaperLength,dmPaperWidth,dmScale;
  public uint dmBitsPerPel,dmPelsWidth,dmPelsHeight,dmDisplayFlags,dmDisplayFrequency;
  public uint dmICMMethod,dmICMIntent,dmMediaType,dmDitherType,dmReserved1,dmReserved2,dmPanningWidth,dmPanningHeight; }
public static class Disp {
  [DllImport("user32")] public static extern int EnumDisplaySettings(string dev, int mode, ref DEVMODE dm);
}
'@
    $dm = New-Object DEVMODE; $dm.dmSize = [Runtime.InteropServices.Marshal]::SizeOf([type][DEVMODE])
    $set = New-Object System.Collections.Generic.HashSet[string]; $i = 0
    while ([Disp]::EnumDisplaySettings($dev, $i++, [ref]$dm)) { [void]$set.Add("$($dm.dmPelsWidth)x$($dm.dmPelsHeight)@$($dm.dmDisplayFrequency)") }
    "可用显示模式:"; $set | Sort-Object | ForEach-Object { "  $_" }
}

function Show-CcStatus {
    $appx = Get-AppxPackage | Where-Object Name -match 'ControlCenter|GamingCenter'
    $svc = Get-Service GCUBridge -ErrorAction SilentlyContinue
    $proc = Get-Process | Where-Object { $_.Name -match 'GCUService|SystrayComponent|ControlCenterU|GamingCenterU' }
    "官方 CC Appx : $(if($appx){$appx.PackageFullName}else{'未安装'})"
    "GCUBridge    : $(if($svc){$svc.Status}else{'不存在'})"
    "相关进程     : $(if($proc){($proc.Name -join ', ')}else{'无'})"
    if ($proc -or ($svc -and $svc.Status -eq 'Running')) { Write-Warning "检测到官方组件活跃 — 双写者风险, 建议 jcc.ps1 cc-disable" }
}

# ---------- 分发 ----------
$Full = ((@($Cmd) + @($Rest)) -join ' ').Trim(); $T = $Full -split ' '; $A = @($T | Select-Object -Skip 2); switch -Regex ($Full) {
  '^monitor$|^m$'      { Show-Monitor }
  '^rgb color (\d+) (\d+) (\d+)$' { Set-RgbColor [int]$A[0] [int]$A[1] [int]$A[2] }
  '^rgb battery$'      { Set-RgbBattery }
  '^rgb state$'        { Show-RgbState }
  '^rgb power (on|off)$' { Set-RgbPower $A[0] }
  '^rgb rainbow (on|off)$' { Set-RgbRainbow ($A[0] -eq 'on') }
  '^fan (normal|boost|user[1-5])$' { Set-FanMode $T[1] }
  '^fan pwm (\d+)$'    { Set-FanPwm [int]$A[0] }
  '^fan profile (\w+)$'{ Set-FanProfile $A[0] }
  '^bat limit show$|^bat info$' { Set-ChargeLimit 'show' }
  '^bat limit (\d+)$'  { Set-ChargeLimit [int]$A[0] }
  '^sw winlock (on|off)$' { Set-WinLock $A[0] }
  '^sw fnlock (on|off)$' { Set-FnLock $A[0] }
  '^rgb breathe (on|off)$' { Set-RgbBreathe $A[0] }
  '^rgb level ([1-5])$' { Set-RgbLevel [int]$A[0] }
  '^disp refresh (\d+)$' { Set-RefreshHz [int]$A[0] }
  '^disp refresh-list$'{ Show-RefreshList }
  '^ec read 0x([0-9A-Fa-f]+)$' { $a=[Convert]::ToInt32($A[0],16); "0x{0:X} -> {1} (0x{1:X2})" -f $a,(Read-EcReg $a) }
  '^ec dump 0x([0-9A-Fa-f]+) (\d+)$' { $base=[Convert]::ToInt32($A[0],16); $n=[int]$A[1]
      for ($r=0; $r -lt $n; $r+=16) { $line = ""; for ($c=0; $c -lt 16 -and ($r+$c) -lt $n; $c++) { $line += "{0:X2} " -f (Read-EcReg ($base+$r+$c)) }
        "{0:X4}: {1}" -f ($base+$r), $line } }
  '^cc-status$'        { Show-CcStatus }
  '^selftest$' {
    $pidr = Read-EcReg 0x740
    Write-Host "1/5 DLL 加载与 ProjectID(0x740)=$pidr (期望 GM5 系列 16/17)" -NoNewline; ""
    "2/5 温度交叉: CPTM=$(Read-EcReg 0x43E)°C vs nvidia-smi VGAT=$(Read-EcReg 0x44F)°C"
    (& nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader) | ForEach-Object { "    nvidia-smi 报告 GPU=$_°C (差值<5 为正常漂移)" }
    "3/5 风扇区: FFAN=0x{0:X} PWM_CPU={1} PWM_GPU={2}" -f (Read-EcReg 0x460),(Read-EcReg 0x461),(Read-EcReg 0x469)
    "4/5 电源: ADPT=0x{0:X} (0x0A=AC)" -f (Read-EcReg 0x49F)
    "5/5 曲线 magic 区: 0x0F5D=0x{0:X2} 0x0F5E=0x{1:X2} Mode=0x{2:X2}" -f (Read-EcReg 0x0F5D),(Read-EcReg 0x0F5E),(Read-EcReg 0x0F5F)
    "SELFTEST 完成"
  }
  '^help$|^$' { @"
JCC-Win v1 命令 (对应官方 GamingCenter3 功能):
  monitor                     实时状态仪表盘
  rgb color R G B             键盘静态色 (Level 0-50)     [官方 Single]
  rgb rainbow on|off          彩虹灯效                    [官方 Rainbow]
  rgb power on|off            键盘灯开关                  [官方]
  rgb battery                 电量灯效                    [官方 BatteryPercent]
  rgb state                   灯效寄存器状态
  fan normal|boost|user1-5    风扇模式                    [官方 FanBoost/User5档]
  fan profile perf|balanced|quiet|whisper  智能曲线档     [官方 SmartFanTable]
  fan pwm N                   直驱 PWM 0-200              [高级]
  bat limit show|N            充电阈值 40-100             [官方充电管理]
  sw winlock on|off           Win 键锁                    [官方硬件开关]
  disp refresh-list           显示模式清单                [165Hz↔60Hz 前置]
  ec read 0xNN | ec dump 0xNNN M   EC 原始读写工具
  cc-status                   官方控制台共存检测
  selftest                    通路自检
写入类命令需加 -Confirm; 所有写入自动留痕 %TEMP%\jcc_writelog.csv
"@ }
  default { throw "未知命令: $Cmd (jcc.ps1 help 查看全部)" }
}
