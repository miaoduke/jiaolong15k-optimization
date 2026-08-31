
$out = [ordered]@{}
$all = Get-WmiObject -Namespace root/wmi -Class AcpiTest_MULong -ErrorAction SilentlyContinue
$out.instances_wmi_elevated = @($all).Count
$all | ForEach-Object { $out["inst_" + $_.InstanceName] = $_.InstanceName }
$o = $all | Select-Object -First 1
if ($o) {
  foreach ($a in @(0x43E, 0x44F, 0x461, 0x464, 0x465, 0x7B9, 0x7C1, 0x7C2)) {
    $null = $o.GetSetULong([UInt64](0x0000010000000000 -bor [UInt64]$a))
    Start-Sleep -Milliseconds 40
    $r = $o.GetULong()
    $out[("read_0x{0:X}" -f $a)] = $r.Return -band 0xFF
  }
}
$out | ConvertTo-Json | Out-File -Encoding utf8 "$PSScriptRoot\_ecadmin.json"
Write-Output ($out | ConvertTo-Json)
