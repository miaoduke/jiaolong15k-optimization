$L = { param($m) Add-Content -Path ($PSScriptRoot + '\_lhm_trace.log') -Value ((Get-Date -Format 'HH:mm:ss.fff') + ' ' + $m) }
& $L 'start'
Set-Location $PSScriptRoot
try { Add-Type -Path '.\LibreHardwareMonitorLib.dll'; & $L 'addtype ok' } catch { & $L ('addtype FAIL: ' + $_.Exception.Message); exit 1 }
$c = New-Object LibreHardwareMonitor.Hardware.Computer; & $L 'computer obj'
'IsCpuEnabled','IsGpuEnabled','IsMemoryEnabled','IsMotherboardEnabled','IsStorageEnabled','IsBatteryEnabled','IsControllerEnabled' | ForEach-Object { $c.$_ = $true }
& $L 'flags set'
try { $c.Open(); & $L 'open ok' } catch { & $L ('open FAIL: ' + $_.Exception.Message); exit 1 }
Start-Sleep 2; & $L ('hardware count: ' + @($c.Hardware).Count)
$out = New-Object System.Collections.Generic.List[string]
function Walk($hw,$ind){ $hw.Update(); $out.Add(('[HW] ' + $hw.Name + ' | ' + $hw.HardwareType)); foreach($s in $hw.Sensors){ $v = if($null -ne $s.Value){[math]::Round([double]$s.Value,2)}else{'-'}; $out.Add(('   [' + $s.SensorType + '] ' + $s.Name + ' = ' + $v)) }; foreach($sub in $hw.SubHardware){ Walk $sub ($ind+'   ') } }
foreach($hw in $c.Hardware){ Walk $hw '' }
& $L ('walked, sensors lines: ' + $out.Count)
try { $c.Close(); & $L 'closed' } catch {}
$out | Out-File ($PSScriptRoot + '\_lhm_admin_out.txt') -Encoding UTF8
& $L 'file written DONE'