#!/bin/bash
# ============================================================
# 机械革命蛟龙15K Fn 功能键修复安装脚本
#   Fn+F4 (WiFi开关)  ->  WMI 事件  ->  nmcli radio wifi toggle
#   Fn+F5 (触控板开关) ->  F24 事件  ->  xinput 触控板切换
# 原理: EC 已上报 ACPI/WMI 事件, 通过 acpid 规则绑定处理
# ============================================================
set -e

echo "=============================================="
echo " 机械革命蛟龙15K Fn 功能键修复安装"
echo "=============================================="

if [ "$(id -u)" != "0" ]; then
    echo "请用 sudo 运行: sudo bash $0"
    exit 1
fi

# [1] Fn+F4 -> WiFi 开关脚本
echo "[1/3] 创建 WiFi 开关脚本..."
cat > /usr/local/bin/fn-f4-wifi.sh << 'EOF'
#!/bin/bash
# Fn+F4: 切换 WiFi (等效硬件射频开关)
nmcli radio wifi toggle
logger -t fn-f4 "WiFi toggled: $(nmcli -t -f WIFI general)"
EOF

# [2] Fn+F5 -> 触控板开关脚本
echo "[2/3] 创建触控板开关脚本..."
cat > /usr/local/bin/fn-f5-touchpad.sh << 'EOF'
#!/bin/bash
# Fn+F5: 切换触控板 (软件禁用/启用)
export DISPLAY=:0
export XAUTHORITY=/home/<USER>/.Xauthority
TP='UNIW0001:00 093A:0255 Touchpad'

if ! xinput list >/dev/null 2>&1; then
    exit 0
fi

STATE=$(xinput list-props "$TP" 2>/dev/null | awk '/Device Enabled/{print $NF}')
if [ "$STATE" = "1" ]; then
    xinput set-prop "$TP" "Device Enabled" 0
    logger -t fn-f5 "Touchpad disabled"
elif [ "$STATE" = "0" ]; then
    xinput set-prop "$TP" "Device Enabled" 1
    logger -t fn-f5 "Touchpad enabled"
fi
EOF

chmod +x /usr/local/bin/fn-f4-wifi.sh /usr/local/bin/fn-f5-touchpad.sh

# [3] acpid 规则
echo "[3/3] 写入 acpid 规则..."
cat > /etc/acpi/events/fn-f4-wifi << 'EOF'
event=wmi PNP0C14:00 000000d2
action=/usr/local/bin/fn-f4-wifi.sh
EOF

cat > /etc/acpi/events/fn-f5-touchpad << 'EOF'
event=button/f24
action=/usr/local/bin/fn-f5-touchpad.sh
EOF

# 重启 acpid 使规则生效
systemctl restart acpid

echo ""
echo "=============================================="
echo " 安装完成!"
echo " 测试: 按 Fn+F4 (WiFi开关) / Fn+F5 (触控板开关)"
echo " 日志: journalctl -t fn-f4 -t fn-f5 -n 20"
echo " 卸载: sudo rm /etc/acpi/events/fn-f4-wifi"
echo "            /etc/acpi/events/fn-f5-touchpad"
echo "            /usr/local/bin/fn-f4-wifi.sh"
echo "            /usr/local/bin/fn-f5-touchpad.sh"
echo "       sudo systemctl restart acpid"
echo "=============================================="