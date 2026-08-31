#!/usr/bin/env bash
# kbd-battery.sh — 键盘灯电量显示（BatteryPercent 灯效，暗色省电版）
# 电量→颜色: >=75 绿 / >=50 黄 / >=25 橙 / <25 红 / <10 暗红
echo $$ > /var/run/kbd-battery.pid
while true; do
  CAP=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null)
  [ -z "$CAP" ] && exit 0
  if   [ "$CAP" -ge 75 ]; then python3 /usr/local/bin/kbd_rgb.py 0 127 0
  elif [ "$CAP" -ge 50 ]; then python3 /usr/local/bin/kbd_rgb.py 127 127 0
  elif [ "$CAP" -ge 25 ]; then python3 /usr/local/bin/kbd_rgb.py 127 64 0
  elif [ "$CAP" -ge 10 ]; then python3 /usr/local/bin/kbd_rgb.py 127 0 0
  else python3 /usr/local/bin/kbd_rgb.py 50 0 0; fi
  sleep 60
done
