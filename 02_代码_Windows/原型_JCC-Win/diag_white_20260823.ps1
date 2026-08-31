# diag_white_20260823.ps1 — 白色背光硬件支持性诊断（寄存器级，只触碰键盘灯区）
# 流程: 记录原色 → 红通道量程探测(60..255) → 白色候选写入回读 → 黄色双通道对照
#       → commit 副作用窗口 diff → 自动恢复原色
$ErrorActionPreference='Continue'
$Dll="C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
if(-not('JG' -as [type])){Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class JG{[DllImport("kernel32",SetLastError=true,CharSet=CharSet.Unicode)]public static extern System.IntPtr LoadLibrary(string p);
[DllImport("ACPIDriverDll",EntryPoint="ReadEC",SetLastError=true)]public static extern int R(int a);
[DllImport("ACPIDriverDll",EntryPoint="WriteEC",SetLastError=true)]public static extern int W(int a,int v);}
"@}
[void][JG]::LoadLibrary($Dll)

function Get-Rgb { @{R=[JG]::R(0x769);G=[JG]::R(0x76A);B=[JG]::R(0x76B);Ctl=[JG]::R(0x767);Pwr=[JG]::R(0x78C)} }
function Set-Rgb($r,$g,$b){
  $c=[JG]::R(0x767)
  if($c -band 0x80){ [void][JG]::W(0x767,($c -bxor 0x80)); Start-Sleep -Milliseconds 30 }
  [void][JG]::W(0x769,[int]$r); [void][JG]::W(0x76A,[int]$g); [void][JG]::W(0x76B,[int]$b)
  [void][JG]::W(0x767,(([JG]::R(0x767)) -bor 0x20))
  Start-Sleep -Milliseconds 150
  return (Get-Rgb)
}
function Dump-Win { $h=@{}; foreach($a in 0x760..0x7CF){ $h[$a]=[JG]::R($a) }; return $h }

$orig=Get-Rgb
('[i] 原始: R={0} G={1} B={2} Ctl=0x{3:X2} Pwr=0x{4:X2}' -f $orig.R,$orig.G,$orig.B,$orig.Ctl,$orig.Pwr)

$results=@()

# ── 测试1: 红通道量程探测 ──
foreach($v in 60,80,100,128,200,255){
  $rb=(Set-Rgb $v 0 0)
  $verdict=if($rb.R -eq $v){'接受'}else{'钳位→'+$rb.R}
  $results+=[pscustomobject]@{项目='红通道量程'; 写入=$v; 回读=$rb.R; 结论=$verdict}
}
$maxAcc=0
foreach($v in 255,200,128,100,80,60){
  $hit=$results | Where-Object { $_.项目 -eq '红通道量程' -and $_.写入 -eq $v -and $_.结论 -eq '接受' }
  if($hit){ $maxAcc=$v; break }
}
if($maxAcc -eq 0){ $maxAcc=50 }
('[i] 红通道最大接受值 = {0}' -f $maxAcc)

# ── 测试2: 白色候选 ──
foreach($cand in @( @($maxAcc,$maxAcc,$maxAcc), @(50,50,50), @(49,49,49), @(35,35,35) )){
  $rb=(Set-Rgb $cand[0] $cand[1] $cand[2])
  $match=($rb.R -eq $cand[0] -and $rb.G -eq $cand[1] -and $rb.B -eq $cand[2])
  $verdict=if($match){'寄存器已接受'}else{'回读不一致'}
  $results+=[pscustomobject]@{项目='白色候选'; 写入=($cand -join ','); 回读=('{0},{1},{2}' -f $rb.R,$rb.G,$rb.B); 结论=$verdict}
}

# ── 测试3: 黄色双通道满载对照 ──
$rb=(Set-Rgb $maxAcc $maxAcc 0)
$verdict=if($rb.R -eq $maxAcc -and $rb.G -eq $maxAcc){'接受'}else{'异常'}
$results+=[pscustomobject]@{项目='黄色对照(双通道满载)'; 写入=('{0},{0},0' -f $maxAcc); 回读=('{0},{1},0' -f $rb.R,$rb.G); 结论=$verdict}

# ── 测试4: commit 副作用窗口 diff ──
$winBefore=Dump-Win
[void](Set-Rgb 50 50 50)
$winAfter=Dump-Win
$diffs=@()
foreach($k in $winBefore.Keys){ if($winBefore[$k] -ne $winAfter[$k]){ $diffs+=('0x{0:X3}:0x{1:X2}->0x{2:X2}' -f $k,$winBefore[$k],$winAfter[$k]) } }
'[i] commit 后窗口差异: ' + $(if($diffs.Count){ $diffs -join ' | ' }else{'无'})

# ── 恢复原色 ──
$fin=(Set-Rgb $orig.R $orig.G $orig.B)
''
$table=$results | Format-Table -AutoSize | Out-String -Width 160
$table
$finLine=('已恢复原色: R={0} G={1} B={2} Ctl=0x{3:X2}' -f $fin.R,$fin.G,$fin.B,$fin.Ctl)
$finLine

# ── 结果写入 UTF-8 报告文件（规避控制台代码页问题）──
$report=@()
$report+=('原始: R={0} G={1} B={2} Ctl=0x{3:X2}' -f $orig.R,$orig.G,$orig.B,$orig.Ctl)
$report+=('红通道最大接受值 = {0}' -f $maxAcc)
$report+=('commit 后窗口差异: ' + $(if($diffs.Count){ $diffs -join ' | ' }else{'无'}))
$report+=$table
$report+=$finLine
$rpt=Join-Path $PSScriptRoot 'diag_white_result_20260823.txt'
[System.IO.File]::WriteAllLines($rpt,$report,[System.Text.Encoding]::UTF8)

