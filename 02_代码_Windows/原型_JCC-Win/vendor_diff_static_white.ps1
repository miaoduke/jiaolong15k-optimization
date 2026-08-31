# vendor_diff_static_white.ps1 - 精确捕获官方设置静态白色时的EC写入
# 步骤: 重置状态 → 快照基线 → 你只做一个操作(静态白) → 快照对比
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
  Write-Host ("  [{0}] 0x767=0x{1:X2} 0x768=0x{2:X2} | Z1: R={3} G={4} B={5} | Z2: R={6} G={7} B={8}" -f $tag,$h[0x767],$h[0x768],$h[0x769],$h[0x76A],$h[0x76B],$h[0x76D],$h[0x76E],$h[0x76F]) -ForegroundColor Gray
}

Write-Host "=== 静态白色 精确逆向 ===" -ForegroundColor Cyan
Write-Host ""

# 1) 先重置到已知状态: 退出厂商模式, 设红色
Write-Host "[1/5] 重置: 退出厂商模式, 设红色..." -ForegroundColor Yellow
[void][JG]::W(0x767,0x00)  # 清除厂商模式
[void][JG]::W(0x768,0x00)  # 子模式清零
[void][JG]::W(0x769,255)   # R=255
[void][JG]::W(0x76A,0)     # G=0
[void][JG]::W(0x76B,0)     # B=0
# 触发commit
[void][JG]::W(0x767,(([JG]::R(0x767))-bor 0x20))
Start-Sleep -Seconds 2

# 2) 确认重置成功
$check=Dump-Range 0x760 0x7CF
Show-Reg "重置后" $check
if($check[0x767] -ne 0 -or $check[0x768] -ne 0){
  Write-Host "  [!] 厂商模式仍在, 再次尝试..." -ForegroundColor Yellow
  [void][JG]::W(0x767,0x00)
  [void][JG]::W(0x768,0x00)
  Start-Sleep -Seconds 1
  $check=Dump-Range 0x760 0x7CF
  Show-Reg "再次重置" $check
}

# 3) Snapshot baseline
Write-Host ""
Write-Host "[2/5] 快照基线..." -ForegroundColor Yellow
$base=Dump-Range 0x760 0x7CF
Show-Reg "基线" $base

# 4) Instructions
Write-Host ""
Write-Host "[3/5] 请执行以下操作（只做一个）:" -ForegroundColor Yellow
Write-Host "  1. 打开官方 机械革命电竞控制台" -ForegroundColor White
Write-Host "  2. 进入 灯光设置 > 键盘背光" -ForegroundColor White
Write-Host "  3. 确保选中 [单色] 模式（不是多彩/呼吸/闪烁）" -ForegroundColor White
Write-Host "  4. 在色板中点击 [白色]" -ForegroundColor White
Write-Host "  5. 亮度滑块拉到最大" -ForegroundColor White
Write-Host "  6. 确认键盘灯变成了白色" -ForegroundColor White
Write-Host "  7. 回到这里按回车" -ForegroundColor White
Write-Host ""
Write-Host "  注意: 只做这一个操作，不要切换其他功能" -ForegroundColor Gray
Read-Host "  完成后按回车"

# 5) Wait for EC to settle
Write-Host "  等待3秒让EC稳定..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# 6) After snapshot
Write-Host ""
Write-Host "[4/5] 快照对比..." -ForegroundColor Yellow
$after=Dump-Range 0x760 0x7CF
Show-Reg "操作后" $after

# 7) Diff
Write-Host ""
Write-Host "[5/5] === 变化的寄存器 ===" -ForegroundColor Cyan
$diffs=@()
foreach($a in 0x760..0x7CF){
  if($after[$a] -ne $base[$a]){
    $desc=switch($a){
      0x767 { '控制寄存器' }
      0x768 { '子模式(NEW!)' }
      0x769 { 'R通道(Z1)' }
      0x76A { 'G通道(Z1)' }
      0x76B { 'B通道(Z1)' }
      0x76C { 'Z1控制' }
      0x76D { 'R通道(Z2)' }
      0x76E { 'G通道(Z2)' }
      0x76F { 'B通道(Z2)' }
      0x783 { 'R通道(Z3)' }
      0x784 { 'G通道(Z3)' }
      0x785 { 'B通道(Z3)' }
      0x7A6 { 'R通道(Z4)' }
      0x7A7 { 'G通道(Z4)' }
      0x7A8 { 'B通道(Z4)' }
      0x7A9 { 'Z4控制' }
      0x78C { '背光电源' }
      default { '' }
    }
    $line='0x{0:X3}: {1,3}(0x{2:X2}) -> {3,3}(0x{4:X2})  {5}' -f $a,$base[$a],$base[$a],$after[$a],$after[$a],$desc
    Write-Host $line -ForegroundColor $(if($a -in 0x769,0x76A,0x76B,0x767,0x768){'Green'}else{'White'})
    $diffs+=$line
  }
}
if($diffs.Count -eq 0){ Write-Host "  无变化" -ForegroundColor Gray }
else { Write-Host ("  共 {0} 个寄存器变化" -f $diffs.Count) -ForegroundColor Green }

# 8) Analysis
Write-Host ""
Write-Host "=== 分析 ===" -ForegroundColor Cyan
Write-Host ("  0x767 (控制): 0x{0:X2} -> 0x{1:X2}" -f $base[0x767],$after[0x767]) -ForegroundColor $(if($after[0x767] -eq 0){'Green'}else{'Yellow'})
Write-Host ("  0x768 (子模式): 0x{0:X2} -> 0x{1:X2}" -f $base[0x768],$after[0x768]) -ForegroundColor $(if($after[0x768] -eq 0){'Green'}else{'Yellow'})
Write-Host ("  Z1 RGB: ({0},{1},{2}) -> ({3},{4},{5})" -f $base[0x769],$base[0x76A],$base[0x76B],$after[0x769],$after[0x76A],$after[0x76B]) -ForegroundColor White

# 9) Save
$rpt='D:\' + [char]0x51FA + [char]0x5382 + [char]0x81EA + [char]0x5E26 + '\' + [char]0x86DF + [char]0x9F99 + '15K_7435H_' + [char]0x4F18 + [char]0x5316 + [char]0x65B9 + [char]0x6848 + '_20260823\' + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + [char]0x5236 + [char]0x4F5C + '_20260823\vendor_diff_static_white.txt'
$report=@("=== 静态白色 Vendor Diff - " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " ===")
$report+=("")
$report+=("基线: 0x767=0x{0:X2} 0x768=0x{1:X2} Z1=({2},{3},{4})" -f $base[0x767],$base[0x768],$base[0x769],$base[0x76A],$base[0x76B])
$report+=("操作后: 0x767=0x{0:X2} 0x768=0x{1:X2} Z1=({2},{3},{4})" -f $after[0x767],$after[0x768],$after[0x769],$after[0x76A],$after[0x76B])
$report+=("")
$report+=("变化: " + $diffs.Count + " 个寄存器")
$report+=$diffs
try{ [System.IO.File]::WriteAllLines($rpt,$report,(New-Object System.Text.UTF8Encoding($true))); Write-Host ""; Write-Host ("报告: " + $rpt) -ForegroundColor Green }catch{}
