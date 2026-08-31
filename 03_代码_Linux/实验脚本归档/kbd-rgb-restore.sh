#!/bin/bash
# 开机恢复上次键盘 RGB 颜色（写 LED class，不碰亮度→Fn 保持硬件）
[ -f /var/lib/kbd-rgb/state ] || exit 0
echo "$(cat /var/lib/kbd-rgb/state)" > /sys/class/leds/uniwill:multicolor:kbd_backlight/multi_intensity
