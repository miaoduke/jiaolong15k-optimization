# vendor_diff_white.ps1 - 专门逆向白色键盘灯的EC写入
# 步骤: 基线→你在官方设白色→脚本自动捕获差异
$ErrorActionPreference='Continue'
$Dll="C:\Program Files\OEM\" + [char]0x673A + [char]0x68B0 + [char]0x9769 + [char]0x547D + [char]0x7535 + [char]0x7ADE + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + "\UniwillService\MyControlCenter\ACPIDriverDll.dll"
if(-not('JG' -as [type])){Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class JG{[DllImport("kernel32",SetLastError=true,CharSet=CharSet.Unicode)]public static extern System.IntPtr LoadLibrary(string p);
[DllImport("ACPIDriverDll",EntryPoint="ReadEC",SetLastError=true)]public static extern int R(int a);
[DllImport("ACPIDriverDll",EntryPoint="WriteEC",SetLastError=true)]public static extern int W(int a,int v);}
"@}
[void][JG]::LoadLibrary($Dll)

Write-Host "=== Vendor Diff: 白色键盘灯逆向 ===" -ForegroundColor Cyan
Write-Host ""

# 1) Stop SystrayComponent to avoid interference during baseline
$proc=Get-Process -Name 'SystrayComponent' -EA SilentlyContinue
if($proc){ Write-Host "[!] 检测到 SystrayComponent 运行中，先暂停..." -ForegroundColor Yellow; $proc|Stop-Process -Force -EA SilentlyContinue; Start-Sleep -m 500 }

# 2) Set a KNOWN color first (red) so we have a clean baseline
Write-Host "[1/4] 设置已知颜色(红色)作为基线..." -ForegroundColor Yellow
[void][JG]::W(0x769,255); [void][JG]::W(0x76A,0); [void][JG]::W(0x76B,0)
[void][JG]::W(0x767,(([JG]::R(0x767))-bor 0x20))
Start-Sleep -m 300

# 3) Snapshot baseline
Write-Host "[2/4] 快照基线..." -ForegroundColor Yellow
$base=@{}; foreach($a in 0x760..0x7CF){ $base[$a]=[JG]::R($a) }
Write-Host ("  当前: R={0} G={1} B={2} Ctl=0x{3:X2}" -f $base[0x769],$base[0x76A],$base[0x76B],$base[0x767]) -ForegroundColor Gray

# 4) User action
Write-Host ""
Write-Host "[3/4] 请执行以下操作:" -ForegroundColor Yellow
Write-Host "  1. 打开官方 机械革命电竞控制台" -ForegroundColor White
Write-Host "  2. 进入 灯光设置 > 键盘背光" -ForegroundColor White
Write-Host "  3. 确保选中 单色 模式" -ForegroundColor White
Write-Host "  4. 在色板中点击 白色" -ForegroundColor White
Write-Host "  5. 把亮度滑块拉到最大" -ForegroundColor White
Write-Host "  6. 回到这里按回车" -ForegroundColor White
Write-Host ""
Read-Host "  完成后按回车"

# 5) After snapshot
Write-Host ""
Write-Host "[4/4] 快照对比..." -ForegroundColor Yellow
$after=@{}; foreach($a in 0x760..0x7CF){ $after[$a]=[JG]::R($a) }

Write-Host ""
Write-Host "=== 结果 ===" -ForegroundColor Cyan
Write-Host ("白色状态: R={0} G={1} B={2} Ctl=0x{3:X2} Pwr=0x{4:X2}" -f $after[0x769],$after[0x76A],$after[0x76B],$after[0x767],$after[0x78C]) -ForegroundColor White

Write-Host ""
Write-Host "=== 变化的寄存器 ===" -ForegroundColor Cyan
$diffs=@()
foreach($a in 0x760..0x7CF){
  if($after[$a] -ne $base[$a]){
    $diffs+=('0x{0:X3}: {1,3}(0x{2:X2}) → {3,3}(0x{4:X2})  {5}' -f $a,$base[$a],$base[$a],$after[$a],$after[$a],
      $(switch($a){
        0x767 { '← 控制寄存器' }
        0x769 { '← R通道' }
        0x76A { '← G通道' }
        0x76B { '← B通道' }
        0x78C { '← 背光电源' }
        0x785 { '← 可能亮度' }
        default { '' }
      })
    )
    Write-Host $diffs[-1] -ForegroundColor $(if($a -in 0x769,0x76A,0x76B,0x767){'Green'}else{'Yellow'})
  }
}

if($diffs.Count -eq 0){ Write-Host "  无变化（可能官方没写入，或颜色相同）" -ForegroundColor Gray }

# 6) Also dump the FULL current state for reference
Write-Host ""
Write-Host "=== 完整键盘区当前值 ===" -ForegroundColor Cyan
$row=''
foreach($a in 0x760..0x7CF){
  $row += ('{0:X2} ' -f $after[$a])
  if(($a - 0x760 + 1) % 16 -eq 0){ Write-Host $row -ForegroundColor Gray; $row='' }
}

# 7) Save
$rpt='D:\' + [char]0x51FA + [char]0x5382 + [char]0x81EA + [char]0x5E26 + '\' + [char]0x86DF + [char]0x9F99 + '15K_7435H_' + [char]0x4F18 + [char]0x5316 + [char]0x65B9 + [char]0x6848 + '_20260823\' + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + [char]0x5236 + [char]0x4F5C + '_20260823\vendor_diff_white.txt'
$report=@()
$report+=('Vendor Diff White - ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$report+=('白色状态: R={0} G={1} B={2} Ctl=0x{3:X2} Pwr=0x{4:X2}' -f $after[0x769],$after[0x76A],$after[0x76B],$after[0x767],$after[0x78C])
$report+='变化的寄存器:'
$report+=$diffs
$report+=''
$report+='完整键盘区:'
foreach($a in 0x760..0x7CF){ $report+=('0x{0:X3}: {1,3} (0x{2:X2})' -f $a,$after[$a],$after[$a]) }
try{ [System.IO.File]::WriteAllLines($rpt,$report,[System.Text.Encoding]::UTF8); Write-Host ""; Write-Host ("报告: " + $rpt) -ForegroundColor Green }catch{}
