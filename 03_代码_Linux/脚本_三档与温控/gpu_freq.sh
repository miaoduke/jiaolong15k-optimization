#!/usr/bin/env bash
# gpu_freq.sh — GPU 频率锁定/恢复（降频限温工具）
# 用法:
#   sudo bash gpu_freq.sh lock [min,max]   例: sudo bash gpu_freq.sh lock 1800 2200
#   sudo bash gpu_freq.sh reset            恢复默认频率范围
#   sudo bash gpu_freq.sh status           查看当前/上限频率
# 铁律: 写后必回读（clocks.max.gr 回读验证）
# 说明: 4060 140W 满载 boost ~2280MHz; 锁 1800,2200 ≈ 上限 -4% 频率, GPU 温度预期降 3-6°C

set -u

read_maxgr() { nvidia-smi --query-gpu=clocks.max.gr --format=csv,noheader,nounits 2>/dev/null; }
read_cur()   { nvidia-smi --query-gpu=clocks.gr --format=csv,noheader,nounits 2>/dev/null; }
read_temp()  { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null; }

# 回读验证: clocks.max.gr 不反映锁定(始终=硬件上限3105);
# 可靠指标 = 当前频率: 锁定后 idle 钳在 MIN, 未锁 idle=465MHz << MIN; 满载 ≤ MAX
verify_locked() { # $1=min $2=max; 返回0=已锁定
  local cur
  cur=$(read_cur)
  [[ "$cur" =~ ^[0-9]+$ ]] && (( cur >= $1 && cur <= $2 ))
}

if [[ $EUID -ne 0 ]]; then echo "需要 root (sudo)"; exit 1; fi
if ! command -v nvidia-smi >/dev/null; then echo "nvidia-smi 不可用"; exit 1; fi

case "${1:-}" in
  lock)
    MIN="${2:-1800}"; MAX="${3:-2200}"
    if ! [[ "$MIN" =~ ^[0-9]+$ ]] || ! [[ "$MAX" =~ ^[0-9]+$ ]] || (( MIN > MAX )); then
      echo "参数错误: lock [min,max]"; exit 1
    fi
    if nvidia-smi -lgc "$MIN,$MAX" >/dev/null 2>&1; then
      sleep 1
      if verify_locked "$MIN" "$MAX"; then
        echo "GPU 频率锁定 -> ${MIN}-${MAX}MHz (回读: 当前 $(read_cur)MHz ∈ [${MIN},${MAX}])"
      else
        echo "⚠️ GPU 频率锁定回读不一致 (当前 $(read_cur)MHz), 请重试或检查固件"
      fi
    else
      echo "⚠️ nvidia-smi -lgc 写入失败（固件拒绝）"
    fi
    ;;
  reset)
    if nvidia-smi -rgc >/dev/null 2>&1; then
      sleep 1
      echo "GPU 频率已恢复默认 (当前 $(read_cur)MHz / 上限 $(read_maxgr)MHz)"
    else
      echo "⚠️ nvidia-smi -rgc 失败"
    fi
    ;;
  status)
    echo "当前频率: ${MIN:-}$(read_cur) MHz / 上限: $(read_maxgr) MHz / 温度: $(read_temp)°C"
    ;;
  *)
    echo "用法: sudo bash gpu_freq.sh lock [min=1800,max=2200] | reset | status"
    exit 1
    ;;
esac
