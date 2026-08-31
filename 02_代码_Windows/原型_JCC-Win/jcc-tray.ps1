# jcc-tray.ps1 — JCC-Win v1.5 托盘版（右键托盘操作；配置 profiles.json）
$ErrorActionPreference = 'Stop'
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CfgPath = Join-Path $Dir 'profiles.json'
$Dll = "C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\ACPIDriverDll.dll"
if (-not ('JT' -as [type])) { Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class JT {
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Unicode)] public static extern System.IntPtr LoadLibrary(string p);
    [DllImport("ACPIDriverDll", EntryPoint="ReadEC", SetLastError=true)] public static extern int R(int a);
    [DllImport("ACPIDriverDll", EntryPoint="WriteEC", SetLastError=true)] public static extern int W(int a,int v);
}
"@ }
[void][JT]::LoadLibrary($Dll)
if (Test-Path $CfgPath) { $script:Cfg = Get-Content $CfgPath -Raw -Encoding UTF8 | ConvertFrom-Json } else {
$script:Cfg = [pscustomobject]@{ binding=[pscustomobject]@{ac='游戏';bat='办公'}; profiles=[pscustomobject]@{
    '游戏'=[pscustomobject]@{fan='perf';rgb=@(50,0,0);charge=80;scheme='8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'}
    '办公'=[pscustomobject]@{fan='quiet';rgb=@(0,20,0);charge=80;scheme='381b4222-f694-41f0-9685-ff5bb260df2e'} } }
$script:Cfg | ConvertTo-Json -Depth 5 | Set-Content $CfgPath -Encoding UTF8 }
$MODE = @{ perf=1; balanced=2; standard=2; quiet=3; whisper=4 }
function Invoke-Profile([string]$name) {
    $p = $script:Cfg.profiles.$name; if (-not $p) { return }
    try {
        if ($p.fan) { $m=$MODE[$p.fan]; if ($m) { [void][JT]::W(0x0F5F,$m); [void][JT]::W(0x0F5D,0xFD); [void][JT]::W(0x0F5E,0xC9); [void][JT]::W(0x7C6,([JT]::R(0x7C6) -bor 4)) } }
        if ($p.rgb) { [void][JT]::W(0x769,[int]$p.rgb[0]); [void][JT]::W(0x76A,[int]$p.rgb[1]); [void][JT]::W(0x76B,[int]$p.rgb[2]); [void][JT]::W(0x767,([JT]::R(0x767) -bor 0x20)) }
        if ($null -ne $p.charge) { [void][JT]::W(0x7B9,[int]$p.charge) }
        if ($p.scheme) { Start-Process powercfg "/setactive $($p.scheme)" -WindowStyle Hidden }
        $script:ni.ShowBalloonTip(1500,'JCC-Win',"已套用档案: $name",'Info')
    } catch { $script:ni.ShowBalloonTip(2500,'JCC-Win 错误',$_.Exception.Message,'Warning') }
}
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
$form = New-Object Windows.Forms.Form; $form.ShowInTaskbar=$false; $form.WindowState='Minimized'
$ni = New-Object Windows.Forms.NotifyIcon; $ni.Text='JCC-Win'; $ni.Icon=[System.Drawing.SystemIcons]::Shield; $ni.Visible=$true
$menu = New-Object Windows.Forms.ContextMenuStrip
$st = New-Object Windows.Forms.ToolStripMenuItem('状态')
$st.Add_Click({ $b=(Get-CimInstance Win32_Battery).EstimatedChargeRemaining
    $ac=if([JT]::R(0x49F)-eq 0x0A){'AC'}else{'BAT'}
    $script:ni.ShowBalloonTip(2500,"JCC-Win  $ac 电池$b%",("CPU {0}C  GPU {1}C  FanCtl=0x{2:X2}" -f [JT]::R(0x43E),[JT]::R(0x44F),[JT]::R(0x751)),'Info') })
[void]$menu.Items.Add($st)
foreach($n in @($script:Cfg.profiles.PSObject.Properties.Name)){
    $it = New-Object Windows.Forms.ToolStripMenuItem("档案: $n"); $it.Tag = $n
    $it.Add_Click({ Invoke-Profile $this.Tag })
    [void]$menu.Items.Add($it)
}
$script:autoOn = $true
$auto = New-Object Windows.Forms.ToolStripMenuItem('AC/DC 自动绑定: 开'); $auto.Checked=$true
$auto.Add_Click({ $script:autoOn = -not $script:autoOn; $auto.Checked=$script:autoOn; $auto.Text="AC/DC 自动绑定: $(if($script:autoOn){'开'}else{'关'})" })
[void]$menu.Items.Add($auto)
[void]$menu.Items.Add('-')
$ex = New-Object Windows.Forms.ToolStripMenuItem('退出')
$ex.Add_Click({ $script:ni.Visible=$false; $form.Close() })
[void]$menu.Items.Add($ex)
$ni.ContextMenuStrip = $menu
$script:last = ''
$timer = New-Object Windows.Forms.Timer; $timer.Interval=3000
$timer.Add_Tick({ try {
    $ac = if ([JT]::R(0x49F) -eq 0x0A) {'ac'} else {'bat'}
    if ($ac -ne $script:last) { $script:last = $ac; if ($script:autoOn) { Invoke-Profile $script:Cfg.binding.$ac } }
} catch {} })
$timer.Start()
Invoke-Profile $script:Cfg.binding.ac
[System.Windows.Forms.Application]::Run($form)
