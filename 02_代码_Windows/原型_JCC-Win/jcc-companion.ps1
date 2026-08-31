# jcc-companion.ps1 - 官方控制台伴随面板
# 检测官方控制台窗口 → 在旁边创建悬浮面板 → 增加官方未实现功能
# 不修改官方程序，只是"贴"在旁边
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
try { Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class DpiJ{[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();}' -ErrorAction SilentlyContinue; [void][DpiJ]::SetProcessDPIAware() } catch {}

# ── EC 接口 ──
$Dll="C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
if(-not('JG' -as [type])){Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class JG{[DllImport("kernel32",SetLastError=true,CharSet=CharSet.Unicode)]public static extern System.IntPtr LoadLibrary(string p);
[DllImport("ACPIDriverDll",EntryPoint="ReadEC",SetLastError=true)]public static extern int R(int a);
[DllImport("ACPIDriverDll",EntryPoint="WriteEC",SetLastError=true)]public static extern int W(int a,int v);}
"@}
[void][JG]::LoadLibrary($Dll)
function WEc($a,$v){ [void][JG]::W($a,$v); Start-Sleep -m 40; return [JG]::R($a) }
function REc($a){ return [JG]::R($a) }

# ── 查找官方控制台窗口 ──
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class WinFind {
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cn, string wn);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, int ih, int x, int y, int w, int f);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
}
"@

# 尝试多种方式查找官方窗口
$proc=Get-Process -Name 'ControlCenter','GamingCenter3','MechRevoCenter' -EA SilentlyContinue | Select-Object -First 1
$hwnd=$null
if($proc){
  $hwnd=$proc.MainWindowHandle
  if($hwnd -eq [IntPtr]::Zero){
    # 尝试 FindWindow
    $hwnd=[WinFind]::FindWindow($null, $null)
    # 遍历查找
    $allProcs=Get-Process | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero }
    foreach($p in $allProcs){
      if($p.ProcessName -match 'Control|Gaming|Center|Revo'){
        $hwnd=$p.MainWindowHandle
        break
      }
    }
  }
}

# ── 颜色定义 ──
$cBg=[Drawing.Color]::FromArgb(40,40,45)
$cOk=[Drawing.Color]::FromArgb(120,220,140)
$cI=[Drawing.Color]::FromArgb(160,200,255)
$cD=[Drawing.Color]::FromArgb(100,100,110)
$cW=[Drawing.Color]::White
$cN=[Drawing.Color]::FromArgb(60,60,70)
$cGreen=[Drawing.Color]::FromArgb(80,160,80)
$cRed=[Drawing.Color]::FromArgb(180,80,80)
$cBlue=[Drawing.Color]::FromArgb(80,120,180)

# ── 创建伴随面板 ──
$cf=New-Object Windows.Forms.Form
$cf.Text='JCC 伴随面板'
$cf.Size=New-Object Drawing.Size(220,520)
$cf.FormBorderStyle='FixedSingle'
$cf.BackColor=$cBg
$cf.TopMost=$true
$cf.StartPosition='Manual'

# 定位到官方窗口旁边
if($hwnd -ne $null -and $hwnd -ne [IntPtr]::Zero){
  $rect=New-Object WinFind+RECT
  [WinFind]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
  $cf.Location=New-Object Drawing.Point($rect.R + 10, $rect.T)
  Write-Host "找到官方窗口，伴随面板定位到右侧" -ForegroundColor Green
}else{
  $cf.Location=New-Object Drawing.Point(100, 100)
  Write-Host "未找到官方窗口，面板显示在默认位置" -ForegroundColor Yellow
}

# ── 控件工具 ──
function ABtn($p,$x,$y,$w,$h,$t,$c){
  $b=New-Object Windows.Forms.Button; $b.Location=New-Object Drawing.Point($x,$y)
  $b.Size=New-Object Drawing.Size($w,$h); $b.Text=$t; $b.FlatStyle='Flat'
  $b.FlatAppearance.BorderSize=0; $b.BackColor=$c; $b.ForeColor=$cW
  $b.Font=New-Object Drawing.Font('微软雅黑',9,[Drawing.FontStyle]::Bold)
  $p.Controls.Add($b); return $b
}
function ALbl($p,$x,$y,$t,$s,$c){
  $l=New-Object Windows.Forms.Label; $l.Location=New-Object Drawing.Point($x,$y)
  $l.AutoSize=$true; $l.Text=$t; $l.ForeColor=$c; $l.Font=New-Object Drawing.Font('Consolas',$s)
  $p.Controls.Add($l); return $l
}
function ANum($p,$x,$y,$v,$mn,$mx){
  $n=New-Object Windows.Forms.NumericUpDown; $n.Location=New-Object Drawing.Point($x,$y)
  $n.Size=New-Object Drawing.Size(60,22); $n.Minimum=$mn; $n.Maximum=$mx; $n.Value=$v
  $n.BackColor=$cN; $n.ForeColor=$cW; $p.Controls.Add($n); return $n
}

# ═══════════════════════════════════════════════
# Section 1: 充电阈值快捷设置
# ═══════════════════════════════════════════════
ALbl $cf 15 10 '── 充电阈值 ──' 9 $cD
$lThresh=ALbl $cf 15 30 '当前: ---%' 11 $cW

$b80=ABtn $cf 15 55 60 30 '80%' $cGreen
$b100=ABtn $cf 85 55 60 30 '100%' $cBlue

$b80.Add_Click{ WEc 0x7B9 80; $lThresh.Text='当前: 80%'; SS '阈值→80%' }
$b100.Add_Click{ WEc 0x7B9 100; $lThresh.Text='当前: 100%'; SS '阈值→100%' }

# 自定义
$nCustom=ANum $cf 15 92 80 20 100
$bCustom=ABtn $cf 85 90 60 28 '设定' $cN
$bCustom.Add_Click{ $v=[int]$nCustom.Value; WEc 0x7B9 $v; $lThresh.Text="当前: $v%"; SS "阈值→$v%" }

# ═══════════════════════════════════════════════
# Section 2: 电量灯跟随
# ═══════════════════════════════════════════════
ALbl $cf 15 130 '── 电量灯 ──' 9 $cD
$lBat=ALbl $cf 15 150 '电量: ---%' 10 $cI
$lColor=ALbl $cf 15 170 '灯色: ---' 9 $cD

$chkFollow=New-Object Windows.Forms.CheckBox
$chkFollow.Location=New-Object Drawing.Point(15,192)
$chkFollow.Text='自动跟随'
$chkFollow.ForeColor=$cW
$chkFollow.Checked=$true
$cf.Controls.Add($chkFollow)

# 颜色配置
ALbl $cf 15 215 '高(>60%):' 8 $cD
$nHiR=ANum $cf 75 213 0 0 255
$nHiG=ANum $cf 115 213 200 0 255
$nHiB=ANum $cf 155 213 0 0 255

ALbl $cf 15 240 '中(30-60%):' 8 $cD
$nMdR=ANum $cf 75 238 200 0 255
$nMdG=ANum $cf 115 238 150 0 255
$nMdB=ANum $cf 155 238 0 0 255

ALbl $cf 15 265 '低(<30%):' 8 $cD
$nLoR=ANum $cf 75 263 255 0 255
$nLoG=ANum $cf 115 263 0 0 255
$nLoB=ANum $cf 155 263 0 0 255

$bApply=ABtn $cf 15 290 80 26 '应用' $cN
$bApply.Add_Click{ SS '电量灯配置已更新' $cOk }

# ═══════════════════════════════════════════════
# Section 3: 电源功能
# ═══════════════════════════════════════════════
ALbl $cf 15 320 '── 电源功能 ──' 9 $cD

$bUsbOn=ABtn $cf 15 340 55 26 'USB开' $cGreen
$bUsbOff=ABtn $cf 75 340 55 26 'USB关' $cRed
$bUsbOn.Add_Click{ WEc 0x7C1 1; SS 'USB供电→开' $cOk }
$bUsbOff.Add_Click{ WEc 0x7C1 0; SS 'USB供电→关' $cOk }

$bAcOn=ABtn $cf 15 372 55 26 '来电开' $cGreen
$bAcOff=ABtn $cf 75 372 55 26 '来电关' $cRed
$bAcOn.Add_Click{ WEc 0x7C2 1; SS '来电开机→开' $cOk }
$bAcOff.Add_Click{ WEc 0x7C2 0; SS '来电开机→关' $cOk }

# 状态
$lUsb=ALbl $cf 15 405 'USB: --' 8 $cI
$lAc=ALbl $cf 15 420 '来电: --' 8 $cI

# ── 状态栏 ──
$lSt=ALbl $cf 15 455 '' 8 $cI
function SS($m,$c){ if(!$c){$c=$cI}; $lSt.Text=$m; $lSt.ForeColor=$c }

# ── 定时器: 电量灯跟随 + 状态刷新 ──
$timer=New-Object Windows.Forms.Timer; $timer.Interval=3000
$timer.Add_Tick{
  if(-not $chkFollow.Checked){ return }
  
  $bat=(REc 0x7D4)
  if($bat -le 0 -or $bat -gt 100){ return }
  
  # 确定颜色
  $r=[int]$nHiR.Value; $g=[int]$nHiG.Value; $b=[int]$nHiB.Value
  if($bat -le 30){ $r=[int]$nLoR.Value; $g=[int]$nLoG.Value; $b=[int]$nLoB.Value }
  elseif($bat -le 60){ $r=[int]$nMdR.Value; $g=[int]$nMdG.Value; $b=[int]$nMdB.Value }
  
  # 设置键盘灯
  WEc 0x769 $r; WEc 0x76A $g; WEc 0x76B $b
  WEc 0x767 (([JG]::R(0x767))-bor 0x20)
  
  # 更新界面
  $lBat.Text="电量: $bat%"
  $lColor.Text="灯色: RGB($r,$g,$b)"
}
$timer.Start()

# ── 初始状态 ──
$lThresh.Text="当前: " + (REc 0x7B9) + "%"
$lUsb.Text="USB: " + $(if((REc 0x7C1) -eq 1){'开'}else{'关'})
$lAc.Text="来电: " + $(if((REc 0x7C2) -eq 1){'开'}else{'关'})
SS '伴随面板就绪' $cOk

# ── 拖动支持 ──
$dragging=$false; $dragX=0; $dragY=0
$cf.Add_MouseDown({ if($_.Button -eq 'Left'){ $script:dragging=$true; $script:dragX=$_.X; $script:dragY=$_.Y } })
$cf.Add_MouseMove({ if($script:dragging){ $cf.Location=New-Object Drawing.Point($cf.Location.X+$_.X-$script:dragX, $cf.Location.Y+$_.Y-$script:dragY) } })
$cf.Add_MouseUp({ $script:dragging=$false })

# ── 显示 ──
Write-Host "=== JCC 伴随面板 ===" -ForegroundColor Cyan
Write-Host "面板已启动，拖动标题栏可移动" -ForegroundColor Green
Write-Host "关闭面板结束脚本" -ForegroundColor Gray

[void]$cf.ShowDialog()
$timer.Stop()
