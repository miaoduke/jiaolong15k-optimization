# MQTT 被动监听器 v2 - 连接 GCUBridge (127.0.0.1:13688) 订阅所有主题
$ErrorActionPreference = "Stop"

function New-MqttPacket {
    param([byte]$FirstByte, [byte[]]$Body)
    $pkt = New-Object System.Collections.Generic.List[byte]
    $pkt.Add($FirstByte)
    $len = $Body.Count
    do {
        $d = $len % 128
        $len = [math]::Floor($len / 128)
        if ($len -gt 0) { $d = $d -bor 128 }
        $pkt.Add([byte]$d)
    } while ($len -gt 0)
    foreach ($b in $Body) { $pkt.Add($b) }
    return $pkt.ToArray()
}

function Add-MqttStr {
    param([System.Collections.Generic.List[byte]]$List, [string]$s)
    $b = [System.Text.Encoding]::UTF8.GetBytes($s)
    $List.Add([byte](($b.Length -shr 8) -band 0xFF))
    $List.Add([byte]($b.Length -band 0xFF))
    foreach ($x in $b) { $List.Add($x) }
}

$client = New-Object System.Net.Sockets.TcpClient
$client.Connect("127.0.0.1", 13688)
$stream = $client.GetStream()

# CONNECT (MQTT 3.1.1, CleanSession)
$vh = New-Object System.Collections.Generic.List[byte]
Add-MqttStr $vh "MQTT"
$vh.Add(0x04); $vh.Add(0xC2); $vh.Add(0x00); $vh.Add(0x3C)
Add-MqttStr $vh "PluginClient_17"
Add-MqttStr $vh "PluginClient_User_17"
Add-MqttStr $vh "PluginClient_Pwd<REDACTED_PWD_SALT>_17"
$connect = New-MqttPacket 0x10 $vh.ToArray()
$stream.Write($connect, 0, $connect.Count)
Start-Sleep -Milliseconds 800

if (-not $stream.DataAvailable) { Write-Host "[!] No CONNACK" -ForegroundColor Red; $client.Close(); exit }
$buf = New-Object byte[] 4
[void]$stream.Read($buf, 0, 4)
$rc = $buf[3]
Write-Host ("[CONNACK] returnCode=0x{0:X2}" -f $rc)
switch ($rc) {
    0 { Write-Host "  => ACCEPTED!" -ForegroundColor Green }
    4 { Write-Host "  => bad user/pass" -ForegroundColor Red }
    5 { Write-Host "  => not authorized" -ForegroundColor Red }
    default { Write-Host "  => other code" -ForegroundColor Yellow }
}
if ($rc -ne 0) { $stream.Close(); $client.Close(); exit }

# SUBSCRIBE '#'
$sb = New-Object System.Collections.Generic.List[byte]
$sb.Add(0x00); $sb.Add(0x01)
Add-MqttStr $sb "#"
$sb.Add(0x00)
$subscribe = New-MqttPacket 0x82 $sb.ToArray()
$stream.Write($subscribe, 0, $subscribe.Count)
Write-Host "[SUBSCRIBE] '#' sent" -ForegroundColor Cyan

# Listen 30s
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$log = New-Object System.Collections.Generic.List[string]
$rbuf = New-Object byte[] 262144
Write-Host "`nListening 30s (operate the official console UI now)...`n" -ForegroundColor Cyan

while ($sw.Elapsed.TotalSeconds -lt 60) {
    if ($stream.DataAvailable) {
        $n = $stream.Read($rbuf, 0, $rbuf.Length)
        $i = 0
        while ($i -lt ($n - 2)) {
            $pktType = ($rbuf[$i] -shr 4)
            if ($pktType -eq 9) { Write-Host "[SUBACK] ok" -ForegroundColor Green; break }
            if ($pktType -eq 3) {
                $mul = 1; $rl3 = 0; $j = $i + 1
                do { $d = $rbuf[$j]; $rl3 += (($d -band 127) * $mul); $mul *= 128; $j++ } while (($d -band 128) -ne 0 -and $j -lt $n)
                if (($j + 2 + $rl3) -gt $n) { break }
                $tLen = ([Int16](([int]$rbuf[$j]) -shl 8)) -bor ([int]$rbuf[$j+1])
                $topic = [System.Text.Encoding]::UTF8.GetString($rbuf, $j+2, $tLen)
                $qos = ($rbuf[$i] -shr 1) -band 3
                $hdrLen = 2 + $tLen + $(if ($qos -gt 0) { 2 } else { 0 })
                $pStart = $j + $hdrLen
                $pLen = $rl3 - $hdrLen
                if ($pLen -gt 0) {
                    $payloadTxt = [System.Text.Encoding]::UTF8.GetString($rbuf, $pStart, $pLen)
                    $line = "[$(Get-Date -Format 'HH:mm:ss')] TOPIC: $topic | PAYLOAD: $payloadTxt"
                    Write-Host $line -ForegroundColor Yellow
                    $log.Add($line)
                }
                $i = $j + $rl3
            } else { break }
        }
    }
    Start-Sleep -Milliseconds 100
}

$stream.Close(); $client.Close()
$log | Out-File "C:\Users\<USER>\AppData\Local\Temp\opencode\mqtt_capture.txt" -Encoding UTF8
Write-Host "`nDone. Captured $($log.Count) messages."