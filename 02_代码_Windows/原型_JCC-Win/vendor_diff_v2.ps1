# vendor_diff_v2.ps1 - 不停托盘，直接捕获官方操作前后的EC差异
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

Write-Host "=== Vendor Diff v2: 捕获官方EC写入 ===" -ForegroundColor Cyan
Write-Host "(不停托盘，直接对比操作前后)" -ForegroundColor Gray
Write-Host ""

# 1) Check if tray is running
$proc=Get-Process -Name 'SystrayComponent' -EA SilentlyContinue
if($proc){ Write-Host ("[OK] SystrayComponent 运行中 (PID=" + $proc.Id + ")") -ForegroundColor Green }
else { Write-Host "[!] SystrayComponent 未运行" -ForegroundColor Yellow }

# 2) Snapshot BEFORE (wide range: 0x740-0x7CF)
Write-Host ""
Write-Host "[1/3] 快照基线 (0x740-0x7CF)..." -ForegroundColor Yellow
$base=Dump-Range 0x740 0x7CF
Write-Host ("  键盘: R={0} G={1} B={2} Ctl=0x{3:X2}" -f $base[0x769],$base[0x76A],$base[0x76B],$base[0x767]) -ForegroundColor Gray

# 3) User action
Write-Host ""
Write-Host "[2/3] 请在官方控制台执行操作:" -ForegroundColor Yellow
Write-Host "  (等5秒让托盘稳定，然后操作，操作完再等5秒)" -ForegroundColor Gray
Write-Host ""
Write-Host "  示例操作:" -ForegroundColor White
Write-Host "    - 灯光设置 > 键盘背光 > 点击白色" -ForegroundColor White
Write-Host "    - 灯光设置 > 键盘背光 > 切换到多彩模式" -ForegroundColor White
Write-Host "    - 性能 > 切换到办公模式" -ForegroundColor White
Write-Host "    - 电池 > 修改充电阈值" -ForegroundColor White
Write-Host ""
Write-Host "  等待5秒让状态稳定..." -ForegroundColor Gray
Start-Sleep -Seconds 5
Read-Host "  操作完成后按回车"

# 4) Wait for stability
Write-Host "  等待5秒让托盘稳定..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# 5) Snapshot AFTER
Write-Host ""
Write-Host "[3/3] 快照对比..." -ForegroundColor Yellow
$after=Dump-Range 0x740 0x7CF

# 6) Diff
Write-Host ""
Write-Host "=== 变化的寄存器 ===" -ForegroundColor Cyan
$diffs=@()
foreach($a in 0x740..0x7CF){
  if($after[$a] -ne $base[$a]){
    $desc=switch($a){
      0x767 { '控制寄存器' }
      0x769 { 'R通道(Z1)' }
      0x76A { 'G通道(Z1)' }
      0x76B { 'B通道(Z1)' }
      0x76C { 'Z1控制' }
      0x76D { 'R通道(Z2)' }
      0x76E { 'G通道(Z2)' }
      0x76F { 'B通道(Z2)' }
      0x78C { '背光电源' }
      0x785 { '亮度/控制' }
      0x783 { 'R通道(Z3)' }
      0x784 { 'G通道(Z3)' }
      0x7A6 { 'R通道(Z4)' }
      0x7A7 { 'G通道(Z4)' }
      0x7A8 { 'B通道(Z4)' }
      0x7A9 { 'Z4控制' }
      0x751 { '风扇模式' }
      0x7B9 { '充电阈值' }
      0x74E { '快捷开关' }
      0x7C6 { '风扇控制' }
      default { '' }
    }
    $line='0x{0:X3}: {1,3}(0x{2:X2}) -> {3,3}(0x{4:X2})  {5}' -f $a,$base[$a],$base[$a],$after[$a],$after[$a],$desc
    Write-Host $line -ForegroundColor $(if($desc){'Green'}else{'White'})
    $diffs+=$line
  }
}
if($diffs.Count -eq 0){ Write-Host "  无变化" -ForegroundColor Gray }
else { Write-Host ("  共 {0} 个寄存器变化" -f $diffs.Count) -ForegroundColor Green }

# 7) Also check SystrayComponent status
$proc2=Get-Process -Name 'SystrayComponent' -EA SilentlyContinue
if($proc2){ Write-Host ("  SystrayComponent 仍在运行 (PID=" + $proc2.Id + ")") -ForegroundColor Gray }

# 8) Save
$rpt='D:\' + [char]0x51FA + [char]0x5382 + [char]0x81EA + [char]0x5E26 + '\' + [char]0x86DF + [char]0x9F99 + '15K_7435H_' + [char]0x4F18 + [char]0x5316 + [char]0x65B9 + [char]0x6848 + '_20260823\' + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + [char]0x5236 + [char]0x4F5C + '_20260823\vendor_diff_v2_log.txt'
$report=@("Vendor Diff v2 - " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$report+=("变化: " + $diffs.Count + " 个寄存器")
$report+=$diffs
$report+=""
$report+="完整当前状态 (0x760-0x7CF):"
foreach($a in 0x760..0x7CF){ $report+=('0x{0:X3}: {1,3} (0x{2:X2})' -f $a,$after[$a],$after[$a]) }
try{ [System.IO.File]::WriteAllLines($rpt,$report,(New-Object System.Text.UTF8Encoding($true))); Write-Host ""; Write-Host ("报告: " + $rpt) -ForegroundColor Green }catch{}
