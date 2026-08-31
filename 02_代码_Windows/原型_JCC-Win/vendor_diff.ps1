# vendor_diff.ps1 - 监测官方控制台的EC写入行为
# 用法: 运行脚本 → 快照基线 → 在官方控制台操作 → 按回车 → 查看差异
# 适用: 任何官方功能的EC寄存器逆向（颜色/风扇/电池/...）
$ErrorActionPreference='Continue'
$Dll="C:\Program Files\OEM\" + [char]0x673A + [char]0x68B0 + [char]0x9769 + [char]0x547D + [char]0x7535 + [char]0x7ADE + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + "\UniwillService\MyControlCenter\ACPIDriverDll.dll"
if(-not('JG' -as [type])){Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class JG{[DllImport("kernel32",SetLastError=true,CharSet=CharSet.Unicode)]public static extern System.IntPtr LoadLibrary(string p);
[DllImport("ACPIDriverDll",EntryPoint="ReadEC",SetLastError=true)]public static extern int R(int a);
[DllImport("ACPIDriverDll",EntryPoint="WriteEC",SetLastError=true)]public static extern int W(int a,int v);}
"@}
[void][JG]::LoadLibrary($Dll)

function Dump-Range($start,$end){
  $h=@{}; foreach($a in $start..$end){ $h[$a]=[JG]::R($a) }; return $h
}
function Show-Diff($before,$after,$start,$end){
  $diffs=@()
  foreach($a in $start..$end){
    $ob=$before[$a]; $na=$after[$a]
    if($na -ne $ob){
      $diffs+=[pscustomobject]@{
        Addr=('0x{0:X3}' -f $a)
        Before=('{0,4} (0x{1:X2})' -f $ob,$ob)
        After=('{0,4} (0x{1:X2})' -f $na,$na)
        Delta=('{0:+##;-##;0}' -f ($na-$ob))
      }
    }
  }
  return $diffs
}

Write-Host "=== Vendor Diff Tool ===" -ForegroundColor Cyan
Write-Host "监测官方控制台的EC寄存器写入行为"
Write-Host ""

# 1) Baseline snapshot (keyboard zone)
Write-Host "[1/3] 快照基线 (0x760-0x7CF 键盘区 + 0x740-0x75F 风扇区)..." -ForegroundColor Yellow
$baselineKB=Dump-Range 0x760 0x7CF
$baselineFan=Dump-Range 0x740 0x75F
Write-Host "  基线完成. 键盘区当前值:" -ForegroundColor Green
Write-Host ("  R={0} G={1} B={2} Ctl=0x{3:X2} Pwr=0x{4:X2}" -f $baselineKB[0x769],$baselineKB[0x76A],$baselineKB[0x76B],$baselineKB[0x767],$baselineKB[0x78C])

# 2) User action
Write-Host ""
Write-Host "[2/3] 请在官方控制台执行操作..." -ForegroundColor Yellow
Write-Host "  例如: 设置白色 / 切换风扇模式 / 修改充电阈值 / ..."
Write-Host "  操作完成后按回车继续" -ForegroundColor Gray
Read-Host "  按回车"

# 3) After snapshot + diff
Write-Host ""
Write-Host "[3/3] 快照对比..." -ForegroundColor Yellow
$afterKB=Dump-Range 0x760 0x7CF
$afterFan=Dump-Range 0x740 0x75F

Write-Host ""
Write-Host "=== 键盘区差异 (0x760-0x7CF) ===" -ForegroundColor Cyan
$diffKB=Show-Diff $baselineKB $afterKB 0x760 0x7CF
if($diffKB.Count -gt 0){
  $diffKB | Format-Table -AutoSize | Out-String -Width 200
  Write-Host ("  官方写入了 {0} 个寄存器" -f $diffKB.Count) -ForegroundColor Green
}else{
  Write-Host "  无变化" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== 风扇区差异 (0x740-0x75F) ===" -ForegroundColor Cyan
$diffFan=Show-Diff $baselineFan $afterFan 0x740 0x75F
if($diffFan.Count -gt 0){
  $diffFan | Format-Table -AutoSize | Out-String -Width 200
  Write-Host ("  官方写入了 {0} 个寄存器" -f $diffFan.Count) -ForegroundColor Green
}else{
  Write-Host "  无变化" -ForegroundColor Gray
}

# 4) Save report
$rpt='D:\' + [char]0x51FA + [char]0x5382 + [char]0x81EA + [char]0x5E26 + '\' + [char]0x86DF + [char]0x9F99 + '15K_7435H_' + [char]0x4F18 + [char]0x5316 + [char]0x65B9 + [char]0x6848 + '_20260823\' + [char]0x63A7 + [char]0x5236 + [char]0x53F0 + [char]0x5236 + [char]0x4F5C + '_20260823\vendor_diff_log.txt'
$report=@()
$report+=('Vendor Diff - ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$report+=('键盘区变化: ' + $diffKB.Count + ' 个寄存器')
$report+=('风扇区变化: ' + $diffFan.Count + ' 个寄存器')
$report+=$diffKB | Format-Table -AutoSize | Out-String -Width 200
$report+=$diffFan | Format-Table -AutoSize | Out-String -Width 200
try{
  [System.IO.File]::WriteAllLines($rpt,$report,[System.Text.Encoding]::UTF8)
  Write-Host ""
  Write-Host ("报告已保存: " + $rpt) -ForegroundColor Green
}catch{
  Write-Host ("保存失败: " + $_.Exception.Message) -ForegroundColor Red
}
