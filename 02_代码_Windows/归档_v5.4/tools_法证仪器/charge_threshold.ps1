param(
    [Parameter(Mandatory=$true)][int]$Percent,
    [switch]$Get
)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Output "ERROR:需要管理员"
    exit 1
}
$o = Get-WmiObject -Namespace root\wmi -Class AcpiTest_MULong | Where-Object { $_.InstanceName -eq "ACPI\PNP0C14\1_0" }
if (-not $o) { Write-Output "ERROR:WMI实例未找到"; exit 1 }

function Read-EC([UInt16]$addr) {
    $data = [UInt64]0x0000010000000000 -bor [UInt64]$addr
    $r = $o.GetSetULong($data)
    if ($null -ne $r -and $null -ne $r.Return) { return [UInt32]($r.Return -band 0xFF) }
    return 0
}
function Write-EC([UInt16]$addr, [byte]$val) {
    $data = [UInt64]$val * 0x10000 + [UInt64]$addr
    $null = $o.GetSetULong($data)
}

if ($Get) {
    $v = Read-EC 0x7B9
    Write-Output "OK:$v"
} else {
    if ($Percent -lt 60 -or $Percent -gt 100) { Write-Output "ERROR:范围60-100"; exit 1 }
    Write-EC 0x7B9 $Percent
    Start-Sleep -Milliseconds 300
    $v = Read-EC 0x7B9
    if ($v -eq $Percent) {
        Write-Output "OK:$v"
    } else {
        Write-Output "WARN:写入$Percent 但回读$v"
    }
}
