# jcc-config.ps1 - 读取appsettings.json中的JCCExtensions配置并应用
# 用于测试修改后的配置是否被识别
$ErrorActionPreference='Stop'
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

Write-Host "=== JCC Extensions Config Reader ===" -ForegroundColor Cyan
Write-Host ""

# 读取配置文件
$configPath=Join-Path $PSScriptRoot 'ControlCenter3_Test\appsettings.json'
if(-not (Test-Path $configPath)){
  Write-Host "[!] 配置文件不存在: $configPath" -ForegroundColor Red
  exit 1
}

Write-Host "[1/4] 读取配置文件..." -ForegroundColor Yellow
$config=Get-Content $configPath -Encoding UTF8 | ConvertFrom-Json

# 检查JCCExtensions是否存在
if(-not $config.JCCExtensions){
  Write-Host "[!] 未找到 JCCExtensions 配置节" -ForegroundColor Red
  Write-Host "  请先在appsettings.json中添加JCCExtensions配置" -ForegroundColor Gray
  exit 1
}

Write-Host "  [OK] 找到 JCCExtensions 配置" -ForegroundColor Green
Write-Host ""

# 显示配置概览
Write-Host "[2/4] 配置概览:" -ForegroundColor Yellow
Write-Host ("  充电阈值: " + $(if($config.JCCExtensions.ChargeThreshold.Enabled){"启用"}else{"禁用"}) + " | 阈值=" + $config.JCCExtensions.ChargeThreshold.ThresholdPercent + "%") -ForegroundColor White
Write-Host ("  电量灯: " + $(if($config.JCCExtensions.BatteryIndicator.Enabled){"启用"}else{"禁用"}) + " | 检测间隔=" + $config.JCCExtensions.BatteryIndicator.CheckIntervalMs + "ms") -ForegroundColor White
Write-Host ("  电源管理: " + $(if($config.JCCExtensions.PowerManagement.Enabled){"启用"}else{"禁用"})) -ForegroundColor White
Write-Host ""

# 应用充电阈值
Write-Host "[3/4] 应用配置..." -ForegroundColor Yellow
if($config.JCCExtensions.ChargeThreshold.Enabled){
  $thresh=$config.JCCExtensions.ChargeThreshold.ThresholdPercent
  $reg=[Convert]::ToInt32($config.JCCExtensions.ChargeThreshold.ECRegister.Replace('0x',''),16)
  $result=WEc $reg $thresh
  Write-Host ("  [OK] 充电阈值 → " + $thresh + "% (EC回读: " + $result + ")") -ForegroundColor Green
}else{
  Write-Host "  [--] 充电阈值未启用" -ForegroundColor Gray
}

# 应用电源管理
if($config.JCCExtensions.PowerManagement.Enabled){
  # 关机USB供电
  if($config.JCCExtensions.PowerManagement.ShutdownUSBPower.Enabled){
    $reg=[Convert]::ToInt32($config.JCCExtensions.PowerManagement.ShutdownUSBPower.ECRegister.Replace('0x',''),16)
    $val=$config.JCCExtensions.PowerManagement.ShutdownUSBPower.ValueOn
    $result=WEc $reg $val
    Write-Host ("  [OK] 关机USB供电 → 开启 (EC回读: " + $result + ")") -ForegroundColor Green
  }else{
    $reg=[Convert]::ToInt32($config.JCCExtensions.PowerManagement.ShutdownUSBPower.ECRegister.Replace('0x',''),16)
    $val=$config.JCCExtensions.PowerManagement.ShutdownUSBPower.ValueOff
    $result=WEc $reg $val
    Write-Host ("  [OK] 关机USB供电 → 关闭 (EC回读: " + $result + ")") -ForegroundColor Green
  }
  
  # 来电开机
  if($config.JCCExtensions.PowerManagement.WakeOnAC.Enabled){
    $reg=[Convert]::ToInt32($config.JCCExtensions.PowerManagement.WakeOnAC.ECRegister.Replace('0x',''),16)
    $val=$config.JCCExtensions.PowerManagement.WakeOnAC.ValueOn
    $result=WEc $reg $val
    Write-Host ("  [OK] 来电开机 → 开启 (EC回读: " + $result + ")") -ForegroundColor Green
  }else{
    $reg=[Convert]::ToInt32($config.JCCExtensions.PowerManagement.WakeOnAC.ECRegister.Replace('0x',''),16)
    $val=$config.JCCExtensions.PowerManagement.WakeOnAC.ValueOff
    $result=WEc $reg $val
    Write-Host ("  [OK] 来电开机 → 关闭 (EC回读: " + $result + ")") -ForegroundColor Green
  }
}else{
  Write-Host "  [--] 电源管理未启用" -ForegroundColor Gray
}
Write-Host ""

# 验证配置
Write-Host "[4/4] 验证EC状态:" -ForegroundColor Yellow
$batThresh=REc 0x7B9
$usbPower=REc 0x7C1
$wakeAC=REc 0x7C2
Write-Host ("  充电阈值: " + $batThresh + "%") -ForegroundColor White
Write-Host ("  关机USB: " + $(if($usbPower -eq 1){"开启"}else{"关闭"})) -ForegroundColor White
Write-Host ("  来电开机: " + $(if($wakeAC -eq 1){"开启"}else{"关闭"})) -ForegroundColor White

Write-Host ""
Write-Host "=== 配置应用完成 ===" -ForegroundColor Cyan
