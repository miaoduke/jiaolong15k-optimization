# vendor_diff_mode_change.ps1 - 测试模式切换时的EC写入
# 步骤: 基线 → 切换到彩虹 → 对比 → 切换回单色白 → 对比
$ErrorActionPreference='Continue'
$Dll="C:\Program Files\OEM\" + [char]0x673A + [char]0x68B0 + [char]0x9769 + [char]0x547D + [char]0x7535 + [char]0x7ADE + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + "\UniwillService\MyControlCenter\ACPIDriverDll.dll"
if(-not('JG' -as [type])){Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class JG{[DllImport("kernel32",SetLastError=true,CharSet=CharSet.Unicode)]public static extern System.IntPtr LoadLibrary(string p);
[DllImport("ACPIDriverDll",EntryPoint="ReadEC",SetLastError=true)]public static extern int R(int a);
[DllImport("ACPIDriverDll",EntryPoint="WriteEC",SetLastError=true)]public static extern int W(int a,int v);}
"@}
[void][JG]::LoadLibrary($Dll)

function Dump-Range($s,$e){ $h=@{}; foreach($a in $s..$e){ $h[$a]=[JG]::R($a) }; return $h }
function Show-Reg($tag,$h){
  Write-Host ("  [{0}] 0x767=0x{1:X2} 0x768=0x{2:X2} | Z1:({3},{4},{5}) Z2:({6},{7},{8}) Z3:({9},{10},{11}) Z4:({12},{13},{14})" -f $tag,
    $h[0x767],$h[0x768],$h[0x769],$h[0x76A],$h[0x76B],$h[0x76D],$h[0x76E],$h[0x76F],
    $h[0x783],$h[0x784],$h[0x785],$h[0x7A6],$h[0x7A7],$h[0x7A8]) -ForegroundColor Gray
}
function Show-Diff($base,$after,$tag){
  $diffs=@()
  foreach($a in 0x760..0x7CF){
    if($after[$a] -ne $base[$a]){
      $diffs+=('0x{0:X3}: {1,3}(0x{2:X2}) -> {3,3}(0x{4:X2})' -f $a,$base[$a],$base[$a],$after[$a],$after[$a])
    }
  }
  if($diffs.Count -gt 0){
    Write-Host ("  [{0}] {1} 个寄存器变化:" -f $tag,$diffs.Count) -ForegroundColor Green
    $diffs | ForEach-Object { Write-Host "    $_" -ForegroundColor White }
  }else{
    Write-Host ("  [{0}] 无变化" -f $tag) -ForegroundColor Gray
  }
  return $diffs
}

Write-Host "=== 模式切换 Vendor Diff ===" -ForegroundColor Cyan
Write-Host ""

# 1) Baseline
Write-Host "[1/4] 快照基线..." -ForegroundColor Yellow
$base=Dump-Range 0x760 0x7CF
Show-Reg "基线" $base

# 2) Switch to rainbow
Write-Host ""
Write-Host "[2/4] 请在官方控制台切换到 [多彩/彩虹] 模式..." -ForegroundColor Yellow
Write-Host "  (灯光设置 > 键盘背光 > 选择 多彩/彩虹)" -ForegroundColor Gray
Write-Host "  等待5秒让效果稳定..." -ForegroundColor Gray
Start-Sleep -Seconds 5
Read-Host "  切换完成后按回车"
Start-Sleep -Seconds 3

$afterRainbow=Dump-Range 0x760 0x7CF
Show-Reg "彩虹后" $afterRainbow
$r1=Show-Diff $base $afterRainbow "彩虹"

# 3) Switch to static white
Write-Host ""
Write-Host "[3/4] 请切换到 [单色] 模式并选择 [白色]..." -ForegroundColor Yellow
Write-Host "  (灯光设置 > 键盘背光 > 选择 单色 > 点击白色 > 亮度最大)" -ForegroundColor Gray
Write-Host "  等待5秒让效果稳定..." -ForegroundColor Gray
Start-Sleep -Seconds 5
Read-Host "  切换完成后按回车"
Start-Sleep -Seconds 3

$afterWhite=Dump-Range 0x760 0x7CF
Show-Reg "白色后" $afterWhite
$r2=Show-Diff $afterRainbow $afterWhite "白色"

# 4) Summary
Write-Host ""
Write-Host "=== 总结 ===" -ForegroundColor Cyan
Write-Host ("  基线 -> 彩虹: {0} 个变化" -f $r1.Count) -ForegroundColor $(if($r1.Count -gt 0){'Green'}else{'Gray'})
Write-Host ("  彩虹 -> 白色: {0} 个变化" -f $r2.Count) -ForegroundColor $(if($r2.Count -gt 0){'Green'}else{'Gray'})

# 5) Save
$rpt='D:\' + [char]0x51FA + [char]0x5382 + [char]0x81EA + [char]0x5E26 + '\' + [char]0x86DF + [char]0x9F99 + '15K_7435H_' + [char]0x4F18 + [char]0x5316 + [char]0x65B9 + [char]0x6848 + '_20260823\' + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + [char]0x5236 + [char]0x4F5C + '_20260823\vendor_diff_mode_change.txt'
$report=@("=== 模式切换 Vendor Diff - " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " ===")
$report+=("")
$report+=("基线: 0x767=0x{0:X2} 0x768=0x{1:X2}" -f $base[0x767],$base[0x768])
$report+=("彩虹后: 0x767=0x{0:X2} 0x768=0x{1:X2}" -f $afterRainbow[0x767],$afterRainbow[0x768])
$report+=("白色后: 0x767=0x{0:X2} 0x768=0x{1:X2}" -f $afterWhite[0x767],$afterWhite[0x768])
$report+=("")
$report+=("彩虹变化: " + $r1.Count + " 个寄存器")
$report+=$r1
$report+=("")
$report+=("白色变化: " + $r2.Count + " 个寄存器")
$report+=$r2
try{ [System.IO.File]::WriteAllLines($rpt,$report,(New-Object System.Text.UTF8Encoding($true))); Write-Host ""; Write-Host ("报告: " + $rpt) -ForegroundColor Green }catch{}
