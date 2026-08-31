# jcc-gui.ps1 v6 - JCC-Win 电池与电源管理工具
# 专注三大功能: 充电阈值管理 / 电量灯跟随(自定义) / 电源功能管理
# 不造轮子: 键盘灯效/风扇/性能/监控 全部交给官方控制台
$ErrorActionPreference='Stop'; $Dir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Dll="C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
if(-not('JG' -as [type])){Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class JG{[DllImport("kernel32",SetLastError=true,CharSet=CharSet.Unicode)]public static extern System.IntPtr LoadLibrary(string p);
[DllImport("ACPIDriverDll",EntryPoint="ReadEC",SetLastError=true)]public static extern int R(int a);
[DllImport("ACPIDriverDll",EntryPoint="WriteEC",SetLastError=true)]public static extern int W(int a,int v);}
"@}
[void][JG]::LoadLibrary($Dll)
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
try { Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class DpiJ{[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();}' -ErrorAction SilentlyContinue; [void][DpiJ]::SetProcessDPIAware() } catch {}

# ── helpers ──
function WEc($a,$v){ [void][JG]::W($a,$v); Start-Sleep -m 40; return [JG]::R($a) }
function REc($a){ return [JG]::R($a) }
function SS($m,$c){ if(!$c){$c=$cI}; $lSt.Text=('['+(Get-Date -f HH:mm:ss)+'] '+$m); $lSt.ForeColor=$c }

# ── colors ──
$cOk=[Drawing.Color]::FromArgb(120,220,140); $cEr=[Drawing.Color]::FromArgb(255,110,90)
$cI=[Drawing.Color]::FromArgb(160,200,255); $cD=[Drawing.Color]::FromArgb(100,100,110)
$cBg=[Drawing.Color]::FromArgb(32,32,36); $cN=[Drawing.Color]::FromArgb(50,50,60); $cNA=[Drawing.Color]::FromArgb(80,80,120)
$cW=[Drawing.Color]::White

# ── form ──
$f=New-Object Windows.Forms.Form; $f.Text='JCC-Win 电池与电源管理'
$f.Size=New-Object Drawing.Size(520,480); $f.StartPosition='CenterScreen'
$f.FormBorderStyle='FixedSingle'; $f.BackColor=$cBg; $f.TopMost=$true
function ABtn($p,$x,$y,$w,$h,$t,$c){ $b=New-Object Windows.Forms.Button; $b.Location=New-Object Drawing.Point($x,$y); $b.Size=New-Object Drawing.Size($w,$h); $b.Text=$t; $b.FlatStyle='Flat'; $b.FlatAppearance.BorderSize=0; $b.BackColor=$c; $b.ForeColor=$cW; $b.Font=New-Object Drawing.Font('微软雅黑',9.5,[Drawing.FontStyle]::Bold); $p.Controls.Add($b); return $b }
function ALbl($p,$x,$y,$t,$s,$c){ $l=New-Object Windows.Forms.Label; $l.Location=New-Object Drawing.Point($x,$y); $l.AutoSize=$true; $l.Text=$t; $l.ForeColor=$c; $l.Font=New-Object Drawing.Font('Consolas',$s); $p.Controls.Add($l); return $l }
function AChk($p,$x,$y,$t,$c){ $c=New-Object Windows.Forms.CheckBox; $c.Location=New-Object Drawing.Point($x,$y); $c.Text=$t; $c.ForeColor=$cW; $c.BackColor=$cBg; $c.AutoSize=$true; $p.Controls.Add($c); return $c }
function ANum($p,$x,$y,$v,$mn,$mx){
  $n=New-Object Windows.Forms.NumericUpDown; $n.Location=New-Object Drawing.Point($x,$y)
  $n.Size=New-Object Drawing.Size(70,22); $n.Minimum=$mn; $n.Maximum=$mx; $n.Value=$v
  $n.BackColor=$cN; $n.ForeColor=$cW; $p.Controls.Add($n); return $n
}

# ── header ──
ALbl $f 15 12 'JCC-WIN' 14 ([Drawing.Color]::FromArgb(0,170,255))
ALbl $f 115 18 '电池与电源管理 v6' 9 $cD

# ── nav ──
$script:pg=@(); $script:nb=@()
$navN=@('充电阈值','电量灯','电源功能')
for($i=0;$i -lt 3;$i++){ $b=ABtn $f (20+$i*150) 45 140 28 $navN[$i] $cN; $b.Tag=$i; $b.Add_Click({ for($j=0;$j -lt $script:pg.Count;$j++){ $script:pg[$j].Visible=($j -eq [int]$this.Tag); $script:nb[$j].BackColor=if($j -eq [int]$this.Tag){$cNA}else{$cN} } }); $script:nb+=$b }
function NP{ $p=New-Object Windows.Forms.Panel; $p.Location=New-Object Drawing.Point(10,80); $p.Size=New-Object Drawing.Size(485,330); $p.BackColor=$cBg; $f.Controls.Add($p); $script:pg+=$p; return $p }

# ── status bar ──
$lSt=ALbl $f 15 420 '' 9 $cI

# ═══════════════════════════════════════════════
# PAGE 1: 充电阈值管理
# ═══════════════════════════════════════════════
$p1=NP; $p1.Visible=$true
ALbl $p1 15 10 '── 充电阈值管理 ──' 10 $cD
ALbl $p1 15 35 '设置电池充电上限，延长电池寿命' 9 $cD

# 当前状态
$script:lBatSt=ALbl $p1 15 65 '当前阈值: ---%' 12 $cW
$script:lBatV=ALbl $p1 15 90 '电池电压: ---.--V' 10 $cI

# 阈值按钮
ALbl $p1 15 125 '选择充电阈值:' 9 $cD
$b80=ABtn $p1 15 150 80 35 '80%' ([Drawing.Color]::FromArgb(80,160,80))
$b100=ABtn $p1 105 150 80 35 '100%' ([Drawing.Color]::FromArgb(80,120,180))

$b80.Add_Click({
  WEc 0x7B9 80
  SS '充电阈值 → 80%' $cOk
  Update-ThreshStatus
})
$b100.Add_Click({
  WEc 0x7B9 100
  SS '充电阈值 → 100%' $cOk
  Update-ThreshStatus
})

# 自定义阈值
ALbl $p1 15 200 '自定义阈值:' 9 $cD
$script:nThresh=ANum $p1 120 198 80 20 100
$bCustom=ABtn $p1 200 195 80 28 '设置' $cN
$bCustom.Add_Click({
  $v=[int]$script:nThresh.Value
  WEc 0x7B9 $v
  SS ('充电阈值 → ' + $v + '%') $cOk
  Update-ThreshStatus
})

# 刷新按钮
$bRefresh=ABtn $p1 15 240 100 30 '刷新状态' $cN
$bRefresh.Add_Click({ Update-ThreshStatus })

function Update-ThreshStatus{
  $v=(REc 0x7B9)
  $script:lBatSt.Text=('当前阈值: ' + $v + '%')
  $script:lBatV.Text=('电池电压: ' + ('{0:N2}' -f ((REc 0x7D1)*256 + (REc 0x7D0))/1000) + 'V')
}

# ═══════════════════════════════════════════════
# PAGE 2: 电量灯跟随（自定义颜色）
# ═══════════════════════════════════════════════
$p2=NP; $p2.Visible=$false
ALbl $p2 15 10 '── 电量灯跟随 ──' 10 $cD
ALbl $p2 15 35 '根据电量自动切换键盘灯颜色' 9 $cD

# 开关
$script:chkFollow=AChk $p2 15 60 '启用电量灯跟随' $cW
$script:chkFollow.Checked=$true

# 当前状态
$script:lBatLv=ALbl $p2 15 90 '当前电量: ---%' 12 $cW
$script:lBatClr=ALbl $p2 15 115 '当前颜色: ---' 10 $cI

# 颜色配置
ALbl $p2 15 150 '颜色配置 (R, G, B):' 9 $cD

# 高电量 (>60%)
ALbl $p2 15 175 '高电量 (>60%):' 9 $cW
$script:nHiR=ANum $p2 130 173 0 0 255
$script:nHiG=ANum $p2 210 173 200 0 255
$script:nHiB=ANum $p2 290 173 0 0 255

# 中电量 (30-60%)
ALbl $p2 15 205 '中电量 (30-60%):' 9 $cW
$script:nMdR=ANum $p2 130 203 200 0 255
$script:nMdG=ANum $p2 210 203 150 0 255
$script:nMdB=ANum $p2 290 203 0 0 255

# 低电量 (<30%)
ALbl $p2 15 235 '低电量 (<30%):' 9 $cW
$script:nLoR=ANum $p2 130 233 255 0 255
$script:nLoG=ANum $p2 210 233 0 0 255
$script:nLoB=ANum $p2 290 233 0 0 255

# 阈值设置
ALbl $p2 15 270 '高/中阈值:' 9 $cD
$script:nHiTh=ANum $p2 130 268 60 10 90
ALbl $p2 210 270 '/' 9 $cD
$script:nMdTh=ANum $p2 230 268 30 5 80

# 应用按钮
$bApplyClr=ABtn $p2 15 295 100 28 '应用配置' $cN
$bApplyClr.Add_Click{
  $script:hiColor=@([Drawing.Color]::FromArgb([int]$script:nHiR.Value,[int]$script:nHiG.Value,[int]$script:nHiB.Value))
  $script:mdColor=@([Drawing.Color]::FromArgb([int]$script:nMdR.Value,[int]$script:nMdG.Value,[int]$script:nMdB.Value))
  $script:loColor=@([Drawing.Color]::FromArgb([int]$script:nLoR.Value,[int]$script:nLoG.Value,[int]$script:nLoB.Value))
  $script:hiThresh=[int]$script:nHiTh.Value
  $script:mdThresh=[int]$script:nMdTh.Value
  SS '电量灯配置已更新' $cOk
}

# 默认配置
$script:hiColor=@([Drawing.Color]::FromArgb(0,200,0))    # 绿色
$script:mdColor=@([Drawing.Color]::FromArgb(200,150,0))  # 橙色
$script:loColor=@([Drawing.Color]::FromArgb(255,0,0))    # 红色
$script:hiThresh=60
$script:mdThresh=30

# ═══════════════════════════════════════════════
# PAGE 3: 电源功能管理
# ═══════════════════════════════════════════════
$p3=NP; $p3.Visible=$false
ALbl $p3 15 10 '── 电源功能管理 ──' 10 $cD

# 关机USB供电
ALbl $p3 15 40 '关机USB供电:' 9 $cD
$bUsbOn=ABtn $p3 15 65 80 30 '开启' ([Drawing.Color]::FromArgb(80,160,80))
$bUsbOff=ABtn $p3 105 65 80 30 '关闭' ([Drawing.Color]::FromArgb(180,80,80))
$bUsbOn.Add_Click{ WEc 0x7C1 1; SS '关机USB供电 → 开启' $cOk }
$bUsbOff.Add_Click{ WEc 0x7C1 0; SS '关机USB供电 → 关闭' $cOk }

# 来电开机
ALbl $p3 15 110 '来电开机:' 9 $cD
$bAcOn=ABtn $p3 15 135 80 30 '开启' ([Drawing.Color]::FromArgb(80,160,80))
$bAcOff=ABtn $p3 105 135 80 30 '关闭' ([Drawing.Color]::FromArgb(180,80,80))
$bAcOn.Add_Click{ WEc 0x7C2 1; SS '来电开机 → 开启' $cOk }
$bAcOff.Add_Click{ WEc 0x7C2 0; SS '来电开机 → 关闭' $cOk }

# 刷新状态
$bRefPwr=ABtn $p3 15 180 100 30 '刷新状态' $cN
$bRefPwr.Add_Click{ Update-PwrStatus }

$script:lUsbSt=ALbl $p3 15 220 'USB供电: --' 10 $cI
$script:lAcSt=ALbl $p3 15 245 '来电开机: --' 10 $cI

function Update-PwrStatus{
  $usb=(REc 0x7C1)
  $ac=(REc 0x7C2)
  $script:lUsbSt.Text=('USB供电: ' + $(if($usb -eq 1){'开启'}else{'关闭'}))
  $script:lAcSt.Text=('来电开机: ' + $(if($ac -eq 1){'开启'}else{'关闭'}))
}

# ── 电量灯跟随定时器 ──
$script:timer=New-Object Windows.Forms.Timer; $script:timer.Interval=5000
$script:timer.Add_Tick{
  if(-not $script:chkFollow.Checked){ return }
  # 读取电量 (假设0x7D4是电量百分比)
  $bat=(REc 0x7D4)
  if($bat -le 0 -or $bat -gt 100){ return }
  
  # 确定颜色
  $clr=$script:hiColor[0]
  if($bat -le $script:mdThresh){ $clr=$script:loColor[0] }
  elseif($bat -le $script:hiThresh){ $clr=$script:mdColor[0] }
  
  # 设置键盘灯
  WEc 0x769 $clr.R; WEc 0x76A $clr.G; WEc 0x76B $clr.B
  WEc 0x767 (([JG]::R(0x767))-bor 0x20)
  
  # 更新界面
  $script:lBatLv.Text=('当前电量: ' + $bat + '%')
  $script:lBatClr.Text=('当前颜色: RGB(' + $clr.R + ',' + $clr.G + ',' + $clr.B + ')')
}
$script:timer.Start()

# ── 初始化 ──
Update-ThreshStatus
SS '就绪 | 电量灯跟随已启用' $cOk

# ── 显示 ──
[void]$f.ShowDialog()
$script:timer.Stop()
