#!/usr/bin/env bash
# record_state.sh — 记录当前系统状态快照（改前留痕 / 对比用）
# 用法: bash record_state.sh [备注]   例: bash record_state.sh 场景B应用前
# 输出: 追加到 状态快照.log（本目录）; 含时间戳

set -u
NOTE="${1:-手动记录}"
TS=$(date '+%Y-%m-%d %H:%M:%S')
LOG="$(dirname "$0")/状态快照.log"

echo "===== $TS | $NOTE =====" | tee -a "$LOG"
{
  echo "--- 供电: $(cat /sys/class/power_supply/AC0/online 2>/dev/null | sed 's/1/AC/;s/0/DC(电池)/') / 电池: $(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null)%"
  echo "--- 环境温度: $(sensors | grep -i acpitz | head -1)"
  echo "--- CPU: governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null) EPP=$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null)"
  echo "--- CPU温度: $(sensors -u k10temp-pci-00c3 2>/dev/null | awk '/temp1_input/{print $2; exit}')°C"
  echo "--- GPU: $(nvidia-smi --query-gpu=temperature.gpu,power.draw,power.limit,utilization.gpu --format=csv,noheader 2>/dev/null)"
  echo "--- 服务: TLP=$(systemctl is-active tlp 2>/dev/null) PPD=$(systemctl is-active power-profiles-daemon 2>/dev/null) nvidia-powerd=$(systemctl is-active nvidia-powerd 2>/dev/null)"
  P0=$(cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null)
  sleep 10
  P1=$(cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null)
  IDLE_W=$(awk -v a="$P0" -v b="$P1" 'BEGIN{printf "%.1f W", (b-a)/1000000/10}')
  echo "--- 空闲功耗(RAPL 10s): $IDLE_W"
} | tee -a "$LOG"
echo "已记录 → $LOG"
