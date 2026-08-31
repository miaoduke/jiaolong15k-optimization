
$c = Get-CimClass -Namespace root/wmi -ClassName AcpiTest_MULong -ErrorAction SilentlyContinue
Write-Host ("class_exists: " + [bool]$c)
$all = Get-CimInstance -Namespace root/wmi -ClassName AcpiTest_MULong -ErrorAction SilentlyContinue
Write-Host ("instances_cim: " + @($all).Count)
$all | ForEach-Object { Write-Host ("  cim_inst: " + $_.InstanceName) }
$old = Get-WmiObject -Namespace root/wmi -Class AcpiTest_MULong -ErrorAction SilentlyContinue
Write-Host ("instances_wmi: " + @($old).Count)
$old | ForEach-Object { Write-Host ("  wmi_inst: " + $_.InstanceName) }
$o = $null; $via = ""
if ($old) { $o = $old | Select-Object -First 1; $via = "GetWmiObject" }
elseif ($all) { $o = $all | Select-Object -First 1; $via = "GetCimInstance" }
if ($o) {
  Write-Host ("using: " + $via + " inst=" + $o.InstanceName)
  try {
    $null = $o.GetSetULong([UInt64]0x000001000000043E)
    Start-Sleep -Milliseconds 50
    $r = $o.GetULong()
    Write-Host ("temp43E_return: " + $r.Return)
  } catch { Write-Host ("call_fail: " + $_.Exception.Message) }
} else {
  Write-Host "NO_INSTANCE"
}
