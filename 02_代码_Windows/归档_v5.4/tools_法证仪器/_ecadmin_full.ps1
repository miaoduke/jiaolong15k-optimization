# EC payload v4 - ASCII only - encoding-variant matrix + alt channels
$ErrorActionPreference = "Continue"
$out = [ordered]@{}
$jpath = "$PSScriptRoot\_ecadmin.json"
function Dump { $out | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 $jpath }
$out.started = (Get-Date -Format "HH:mm:ss")
# --- CC 5.17 process recon (UI is running) ---
$cc = Get-Process | Where-Object { $_.Name -match 'ControlCenter|CCenter' } | Select-Object -First 1
if ($cc) {
  $out.cc = @{ pid = $cc.Id; path = $cc.Path }
  try {
    $mods = @($cc.Modules | ForEach-Object { $_.ModuleName })
    $out.cc_suspect_modules = @($mods | Where-Object { $_ -match '(?i)ec|wmi|drv|io|hid|uniwill|tongfang|ite|entersys|winring|rtcore' })
    $out.cc_module_count = @($mods).Count
  } catch { $out.cc_modules_err = $_.Exception.Message }
} else { $out.cc = "not_running" }
Dump
# --- tri-client WMI comparison on inst ACPI\PNP0C14\1_0 reg 0x43E ---
$t0 = Get-WmiObject -Namespace root/wmi -Class AcpiTest_MULong -ErrorAction SilentlyContinue | Where-Object { $_.InstanceName -eq 'ACPI\PNP0C14\1_0' } | Select-Object -First 1
if ($t0) {
  $null = $t0.GetSetULong([UInt64]0x000001000000043E); Start-Sleep -Milliseconds 40
  $out.client_ps_getwmi = ($t0.GetULong()).Return -band 0xFF
} else { $out.client_ps_getwmi = "no_inst" }
$c0 = Get-CimInstance -Namespace root/wmi -ClassName AcpiTest_MULong -ErrorAction SilentlyContinue | Where-Object InstanceName -eq 'ACPI\PNP0C14\1_0' | Select-Object -First 1
if ($c0) {
  $null = $c0 | Invoke-CimMethod -MethodName GetSetULong -Arguments @{ Data = [UInt64]0x000001000000043E }
  Start-Sleep -Milliseconds 40
  $rr = $c0 | Invoke-CimMethod -MethodName GetULong
  $out.client_cim = $rr.Return -band 0xFF
} else { $out.client_cim = "no_inst" }
$wm = cmd /c "wmic /namespace:\\\\root\\wmi path AcpiTest_MULong where InstanceName='ACPI\\PNP0C14\\1_0' call GetULong" 2>&1 | Out-String
$out.client_wmic_snip = $wm.Substring(0, [Math]::Min(300, $wm.Length))
Dump
Write-Host "[1/5] alt channels: thermal zone + battery classes"
$tz = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue
if ($tz) { $out.thermalzone = @($tz | ForEach-Object { @{inst=$_.InstanceName; celsius=[math]::Round(($_.CurrentTemperature/10)-273.15,1)} }) } else { $out.thermalzone = "none" }
$bt = Get-CimInstance -Namespace root/wmi -ClassName BatteryTemperature -ErrorAction SilentlyContinue
if ($bt) { $out.batterytemp = @($bt | ForEach-Object { $_ | Select-Object InstanceName,Temperature }) } else { $out.batterytemp = "none" }
Dump
Write-Host "[2/5] enumerating instances ..."
$all = Get-WmiObject -Namespace root/wmi -Class AcpiTest_MULong -ErrorAction SilentlyContinue
$out.instances = @($all).Count
function Enc([int]$id, [int]$a) {
  switch ($id) {
    0 { return [UInt64](0x0000010000000000 -bor [UInt64]$a) }
    1 { return [UInt64]$a }
    2 { return [UInt64]($a * 0x100) }
    3 { return [UInt64](0x10000 -bor [UInt64]$a) }
    4 { return [UInt64](0x0000000100000000 -bor [UInt64]($a * 0x100)) }
  }
  return [UInt64]$a
}
$names = @("old_flag","plain","shift8","wordflag","flag_shift8")
$hits = @()
Write-Host "[3/5] variant matrix: 10 instances x 5 encodings x temp-reg ..."
foreach ($o in $all) {
  for ($e = 0; $e -lt 5; $e++) {
    $arg = Enc $e 0x43E
    $null = $o.GetSetULong([UInt64]$arg); Start-Sleep -Milliseconds 30
    $t = ($o.GetULong()).Return -band 0xFF
    $ok = ($t -ge 15 -and $t -le 110)
    $out[("m_{0}_{1}" -f $o.InstanceName.Replace("\","_"), $names[$e])] = $t
    if ($ok) { $hits += ,@($o.InstanceName, $e, $t) }
  }
  Dump
}
$out.hits = $hits
Write-Host ("    hits: " + ($hits | ForEach-Object { $_ -join ":" }) -join " | ")
if (@($hits).Count -eq 0) {
  $out.verdict = "ALL_ENCODINGS_DEAD"
  $out.finished = (Get-Date -Format "HH:mm:ss")
  Dump
  Write-Host "[4/5] no live encoding found. DONE."
  exit
}
Write-Host "[4/5] locking first hit - charge/E2/sweep ..."
$hit = $hits[0]
$lockName = $hit[0]; $encId = [int]$hit[1]
$out.locked = @{inst=$lockName; enc=$names[$encId]; temp=$hit[2]}
$o = $all | Where-Object { $_.InstanceName -eq $lockName } | Select-Object -First 1
function Rd([int]$a) {
  $null = $o.GetSetULong([UInt64](Enc $encId $a)); Start-Sleep -Milliseconds 40
  return ($o.GetULong()).Return -band 0xFF
}
function Wr([int]$a, [int]$v) {
  $arg = (Enc $encId $a)
  $packed = [UInt64]([UInt64]$arg -bor ([UInt64]$v -shl 48))
  $null = $o.GetSetULong($packed); Start-Sleep -Milliseconds 200
}
foreach ($a in @(0x44F,0x461,0x469,0x464,0x465)) {
  $out[("rd_0x{0:X}" -f $a)] = Rd $a
}
$out.finished = (Get-Date -Format "HH:mm:ss")
Dump
Write-Host "[5/5] PAYLOAD_OK (read-only lock-in). Write experiments pending v5."