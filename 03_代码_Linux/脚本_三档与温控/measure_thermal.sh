#!/usr/bin/env bash
# measure_thermal.sh — 1s 采样满载测试（内置安全红线）
# 用法: sudo RED=94 bash measure_thermal.sh [秒数=20] [--gpu | --gpu-only]
#   --gpu: 双烤模式 (CPU stress-ng + GPU gpu-burn 同时)
#   --gpu-only: GPU 单烤 (仅 gpu-burn)
#   RED=xx: 终止红线 (默认 92; 有 tctl 温度墙时建议 94 = 墙+2°C 抖动余量, 墙失效即触发)
# 铁律: 起始 >RED 拒测 / CPU或GPU >RED 立即终止 / 轮间冷却 ≥45s / 单轮 ≤60s / >95°C 熔断
# 注意: 测试前检查后台进程 (ps aux --sort=-%cpu | head -5)

set -u
DUR="${1:-20}"
GPU_MODE=0
[[ "${2:-}" == "--gpu" ]] && GPU_MODE=1
[[ "${2:-}" == "--gpu-only" ]] && GPU_MODE=2
RED="${RED:-92}"
if [[ $EUID -ne 0 ]]; then echo "需要 root"; exit 1; fi
if (( DUR > 60 )); then echo "铁律: 单轮满载 ≤60s，拒绝 ${DUR}s"; exit 1; fi

TEMP_SRC="k10temp-pci-00c3"
get_temp() { sensors -u "$TEMP_SRC" 2>/dev/null | awk '/temp1_input/{print $2; exit}'; }
get_gputemp() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null; }
get_gpupower() { nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>/dev/null; }
get_freq() { awk '{s+=$1;n++} END{if(n)printf "%.0f", s/n/1000}' /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq; }

# RAPL 容错: AMD 机可能无可用 energy_uj (实测 intel-rapl 为空), 功耗显示 N/A
RAPL=""
for p in amd_rapl:0 intel-rapl:0; do
  if [[ -r "/sys/class/powercap/$p/energy_uj" ]]; then
    V=$(cat "/sys/class/powercap/$p/energy_uj" 2>/dev/null)
    [[ -n "$V" && "$V" != "0" ]] && RAPL="/sys/class/powercap/$p/energy_uj" && break
  fi
done
[[ -n "$RAPL" ]] && echo "RAPL 可用: $RAPL" || echo "RAPL 不可用 — CPU 包功耗将显示 N/A"

kill_loads() {
  pkill -f "stress-ng --cpu" 2>/dev/null
  pkill -x gpu-burn 2>/dev/null
  pkill -f "/usr/sbin/gpu-burn" 2>/dev/null
}

T0=$(get_temp)
echo "起始温度: ${T0}°C (红线: >75°C 拒测)"
if (( $(echo "$T0 > 75" | bc -l) )); then echo "❌ 温度过高(${T0}°C)，拒绝测试。冷却 ≥45s 再试。"; exit 1; fi

echo "后台检查 (CPU >10% 的进程):"
ps aux --sort=-%cpu | awk '$3>10 && $11!="[kworker" {print "  "$11" "$3"%"} ' | head -5

E0=0; [[ -n "$RAPL" ]] && E0=$(cat "$RAPL")
TMAX=0; GMAX=0; PEAK="/tmp/measure_peak_$$.txt"; : > "$PEAK"
case $GPU_MODE in
  1) MODE="双烤" ;;
  2) MODE="GPU 单烤" ;;
  *) MODE="CPU 单烤" ;;
esac
echo "==> ${MODE}测试 ${DUR}s (1s 采样)..."
echo "    t=0s 起始 CPU ${T0}°C / GPU $(get_gputemp)°C"

( for i in $(seq 1 "$DUR"); do
    T=$(get_temp); G=$(get_gputemp); F=$(get_freq)
    GT=$([[ -n "$G" ]] && echo "$G" || echo "?")
    T=${T:-0}; G=${G:-0}
    (( $(echo "$T > $TMAX" | bc -l) )) && TMAX=$T
    (( $(echo "$G > $GMAX" | bc -l) )) && GMAX=$G
    echo "$TMAX $GMAX" > "$PEAK"
    echo "t=${i}s ${F}MHz CPU ${T}°C GPU ${GT}°C"
    if (( $(echo "$T > $RED" | bc -l) )) || (( $(echo "$G > $RED" | bc -l) )); then
      echo "🚨 超过 ${RED}°C 红线 (CPU ${T}°C / GPU ${GT}°C)，立即终止！"
      kill_loads
      exit 99
    fi
    sleep 1
  done ) &
SAMPLER=$!

# 启动负载 (stress-ng 默认方法已验证可满载顶墙; 此构建无 fma 方法)
case $GPU_MODE in
  1) stress-ng --cpu $(nproc) --timeout "${DUR}s" &
     /usr/sbin/gpu-burn "$DUR" >/dev/null 2>&1 & ;;
  2) /usr/sbin/gpu-burn "$DUR" >/dev/null 2>&1 & ;;
  *) stress-ng --cpu $(nproc) --timeout "${DUR}s" & ;;
esac
wait $SAMPLER; RC=$?
kill_loads
wait 2>/dev/null
read TMAX GMAX < "$PEAK"; rm -f "$PEAK"

E1=0; [[ -n "$RAPL" ]] && E1=$(cat "$RAPL")
if [[ $RC -eq 99 ]]; then echo "冷却 120s 后重新评估"; exit 99; fi
if [[ -n "$RAPL" ]]; then
  POWER=$(awk "BEGIN{printf \"%.1f\", ($E1-$E0)/1000000/${DUR}}")
else
  POWER="N/A"
fi
echo "==> 完成。${MODE}: CPU 峰值 ${TMAX}°C / GPU 峰值 ${GMAX}°C / CPU 包功耗 ≈ ${POWER} W"
echo "==> 记录: 环境=$(sensors | grep -i acpitz | head -1 | tr -s ' ') / GPU 功耗=$(get_gpupower)W"