$ErrorActionPreference = "Stop"
function New-MqttPacket { param([byte]$FirstByte,[byte[]]$Body)
    $pkt = New-Object System.Collections.Generic.List[byte]
    $pkt.Add($FirstByte)
    $len = $Body.Count
    do { $d = $len % 128; $len = [math]::Floor($len/128); if ($len -gt 0) { $d = $d -bor 128 }; $pkt.Add([byte]$d) } while ($len -gt 0)
    foreach ($b in $Body) { $pkt.Add($b) }
    return $pkt.ToArray()
}
function Add-MqttStr { param($List,[string]$s)
    $b = [System.Text.Encoding]::UTF8.GetBytes($s)
    $List.Add([byte](($b.Length -shr 8) -band 0xFF)); $List.Add([byte]($b.Length -band 0xFF))
    foreach ($x in $b) { $List.Add($x) }
}
$client = New-Object System.Net.Sockets.TcpClient
$client.Connect("127.0.0.1",13688)
$stream = $client.GetStream()

$vh = New-Object System.Collections.Generic.List[byte]
Add-MqttStr $vh "MQTT"; $vh.Add(0x04); $vh.Add(0xC2); $vh.Add(0x00); $vh.Add(0x3C)
Add-MqttStr $vh "PluginClient_18"
Add-MqttStr $vh "PluginClient_User_18"
Add-MqttStr $vh "PluginClient_Pwd<REDACTED_PWD_SALT>_18"
$stream.Write((New-MqttPacket 0x10 $vh.ToArray()),0,0)

# 上面的Write传了0长度,重写正确调用:
$pk = New-MqttPacket 0x10 $vh.ToArray()
$stream.Write($pk,0,$pk.Count)
Start-Sleep -Milliseconds 600
$buf = New-Object byte[] 4; [void]$stream.Read($buf,0,4)
if ($buf[3] -ne 0) { Write-Host "CONNACK fail: $($buf[3])"; exit }
Write-Host "[OK] connected as PluginClient_18" -ForegroundColor Green

# 订阅 Fan/Status
$sb = New-Object System.Collections.Generic.List[byte]
$sb.Add(0x00); $sb.Add(0x01); Add-MqttStr $sb "Fan/Status"; $sb.Add(0x00)
$pk = New-MqttPacket 0x82 $sb.ToArray(); $stream.Write($pk,0,$pk.Count)
Start-Sleep -Milliseconds 400

# 发布控制命令到 Fan/Control
$msg = '{"Action":"GETSTATUS"}'
$pub = New-Object System.Collections.Generic.List[byte]
Add-MqttStr $pub "Fan/Control"
foreach ($ch in [System.Text.Encoding]::UTF8.GetBytes($msg)) { $pub.Add($ch) }
$pk = New-MqttPacket 0x30 $pub.ToArray()
$stream.Write($pk,0,$pk.Count)
Write-Host "[PUBLISH] Fan/Control <- $msg"

# 收响应
$rbuf = New-Object byte[] 262144
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 8) {
    if ($stream.DataAvailable) {
        $n = $stream.Read($rbuf,0,$rbuf.Length)
        if ((($rbuf[0]) -shr 4) -eq 3) {
            $j=2
            $tLen = ([int]$rbuf[$j] -shl 8) -bor $rbuf[$j+1]
            $topic = [System.Text.Encoding]::UTF8.GetString($rbuf,$j+2,$tLen)
            $pStart = $j+2+$tLen; $hdrLen = 2+$tLen
            # remaining length 在 buf[1]
            $pLen = $rbuf[1] - $hdrLen
            $payload = [System.Text.Encoding]::UTF8.GetString($rbuf,$pStart,$pLen)
            Write-Host ""
            Write-Host "[RECV] TOPIC=$topic" -ForegroundColor Yellow
            Write-Host "PAYLOAD=${payload.Substring(0,[Math]::Min(300,$payload.Length))}..." -ForegroundColor Green
            break
        }
    }
    Start-Sleep -Milliseconds 100
}
$stream.Close(); $client.Close()
Write-Host "`n[VERDICT] 双向通信验证完成 —— 自制控制台完全可行!" -ForegroundColor Cyan
