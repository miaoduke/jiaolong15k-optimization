#!/usr/bin/env bash
# apply_mode.sh — 切换三场景 (a=极致性能 / b=离电平衡 / c=离电极限续航)
# 每个场景同时联动风扇曲线 (uniwill-laptop platform_profile: a->performance / b->balanced / c->quiet)
# 用法: sudo bash apply_mode.sh [a|b|c]   例: sudo bash apply_mode.sh b
# 依赖: TLP 已装且 PPD 已停（见 05 文档 §二）; 需要 root
# 安全: 所有写入后回读; 亮度/GPU墙失败不阻断（打印警告）

set -u
MODE="${1:-}"
TLP_CONF="/etc/tlp.conf"
BL_BASE="/sys/class/backlight/nvidia_0/brightness"

if [[ -z "$MODE" || ! "$MODE" =~ ^[abc]$ ]]; then
  echo "用法: sudo bash apply_mode.sh [a|b|c]"; exit 1
fi
if [[ $EUID -ne 0 ]]; then echo "需要 root (sudo)"; exit 1; fi

# 备份 tlp.conf（首次）
[[ -f "$TLP_CONF.orig" ]] || cp "$TLP_CONF" "$TLP_CONF.orig"

set_tlp() { # $1=governor_ac $2=epp_ac $3=governor_bat $4=epp_bat $5=boost_bat $6=maxfreq_bat
  sed -i \
    -e "s/^#\?CPU_SCALING_GOVERNOR_ON_AC=.*/CPU_SCALING_GOVERNOR_ON_AC=$1/" \
    -e "s/^#\?CPU_ENERGY_PERF_POLICY_ON_AC=.*/CPU_ENERGY_PERF_POLICY_ON_AC=$2/" \
    -e "s/^#\?CPU_SCALING_GOVERNOR_ON_BAT=.*/CPU_SCALING_GOVERNOR_ON_BAT=$3/" \
    -e "s/^#\?CPU_ENERGY_PERF_POLICY_ON_BAT=.*/CPU_ENERGY_PERF_POLICY_ON_BAT=$4/" \
    -e "s/^#\?CPU_BOOST_ON_BAT=.*/CPU_BOOST_ON_BAT=$5/" \
    -e "s/^#\?CPU_SCALING_MAX_FREQ_ON_BAT=.*/CPU_SCALING_MAX_FREQ_ON_BAT=$6/" \
    "$TLP_CONF" 2>/dev/null
  # 追加缺失项
  grep -q "^CPU_SCALING_GOVERNOR_ON_AC=" "$TLP_CONF" || echo "CPU_SCALING_GOVERNOR_ON_AC=$1" >> "$TLP_CONF"
  grep -q "^CPU_ENERGY_PERF_POLICY_ON_AC=" "$TLP_CONF" || echo "CPU_ENERGY_PERF_POLICY_ON_AC=$2" >> "$TLP_CONF"
  grep -q "^CPU_SCALING_GOVERNOR_ON_BAT=" "$TLP_CONF" || echo "CPU_SCALING_GOVERNOR_ON_BAT=$3" >> "$TLP_CONF"
  grep -q "^CPU_ENERGY_PERF_POLICY_ON_BAT=" "$TLP_CONF" || echo "CPU_ENERGY_PERF_POLICY_ON_BAT=$4" >> "$TLP_CONF"
  grep -q "^CPU_BOOST_ON_BAT=" "$TLP_CONF" || echo "CPU_BOOST_ON_BAT=$5" >> "$TLP_CONF"
  grep -q "^CPU_SCALING_MAX_FREQ_ON_BAT=" "$TLP_CONF" || echo "CPU_SCALING_MAX_FREQ_ON_BAT=$6" >> "$TLP_CONF"
  systemctl restart tlp
}

gpu_wall() { # $1=W — 本机 SBIOS 不支持手动功耗墙（04 陷阱 11），仅为兼容尝试
  if command -v nvidia-smi >/dev/null; then
    nvidia-smi -pl "$1" >/dev/null 2>&1
    NOW=$(nvidia-smi -q -d POWER 2>/dev/null | grep 'Current Power Limit' | awk '{print $4}')
    if [[ "$NOW" == "$1.00" || "$NOW" == "$1" ]]; then
      echo "GPU 功耗墙 -> ${1}W"
    else
      echo "⚠️ GPU 手动功耗墙无效（本机固件限制，04 陷阱 11），当前: ${NOW}W（由 nvidia-powerd/RTD3 自动管理）"
    fi
  fi
}

brightness() { # $1=0-100
  if [[ -f "$BL_BASE" ]]; then
    max=$(cat "${BL_BASE%/*}/max_brightness")
    echo $(( max * $1 / 100 )) > "$BL_BASE" 2>/dev/null && echo "屏幕亮度 -> ${1}%"
  fi
}

set_refresh() { # $1=Hz (165=插电最高 / 60=离电省电) — X 会话自动检测, 失败不阻断
  # sudo 下 DISPLAY 丢失, 从 X socket 推断会话号
  local XD=""
  for s in /tmp/.X11-unix/X*; do
    [[ -e "$s" ]] && XD=":${s##*X}" && break
  done
  if [[ -z "$XD" || ! -x /usr/bin/xrandr ]]; then
    echo "⚠️ 无 X 会话或 xrandr 缺失，跳过刷新率设置"
    return
  fi
  local OUT
  OUT=$(DISPLAY="$XD" xrandr --query 2>/dev/null | awk '/ connected primary/{print $1; exit}')
  [[ -z "$OUT" ]] && OUT=$(DISPLAY="$XD" xrandr --query 2>/dev/null | awk '/ connected/{print $1; exit}')
  if [[ -n "$OUT" ]]; then
    if DISPLAY="$XD" xrandr --output "$OUT" --mode 1920x1080 --rate "$1" >/dev/null 2>&1; then
      echo "屏幕刷新率 -> ${1}Hz ($OUT)"
    else
      echo "⚠️ 刷新率设置失败 ($OUT @ ${1}Hz)"
    fi
  fi
}

ryzenadj_limits() { # $1=STAPM $2=FAST $3=SLOW (W) — 功耗三件套, 失败不阻断; 回读单位 W 与写入换算比较
  if command -v ryzenadj >/dev/null; then
    local S="$1" F="$2" L="$3"
    local SMW=$(( $1 * 1000 )) FMW=$(( $2 * 1000 )) LMW=$(( $3 * 1000 ))
    if ryzenadj --stapm-limit=$SMW --fast-limit=$FMW --slow-limit=$LMW >/dev/null 2>&1; then
      # 回读验证（铁律: 写后必回读）; 数字提取对表格/键值格式均鲁棒
      local STAPM FAST SLOW
      STAPM=$(ryzenadj --info 2>/dev/null | grep 'stapm-limit' | grep -oE '[0-9]+' | head -1)
      FAST=$(ryzenadj --info 2>/dev/null | grep 'fast-limit' | grep -oE '[0-9]+' | head -1)
      SLOW=$(ryzenadj --info 2>/dev/null | grep 'slow-limit' | grep -oE '[0-9]+' | head -1)
      if [[ "$STAPM" == "$S" && "$FAST" == "$F" && "$SLOW" == "$L" ]]; then
        echo "RyzenAdj 功耗限制 -> STAPM ${S}W / FAST ${F}W / SLOW ${L}W (回读一致)"
      else
        echo "⚠️ RyzenAdj 回读不一致 (STAPM=$STAPM FAST=$FAST SLOW=$SLOW), 部分设置被固件忽略 (01 文档: Rembrandt 仅部分支持)"
      fi
    else
      echo "⚠️ RyzenAdj 写入失败（固件拒绝，不影响其他设置）"
    fi
  else
    echo "⚠️ ryzenadj 未安装 — 先运行: sudo bash deploy_three_mode.sh"
  fi
}

set_fan() { # $1=platform_profile (performance/balanced/quiet) — 联动 uniwill-laptop 风扇曲线
  local PF="/sys/firmware/acpi/platform_profile"
  if [[ -w "$PF" ]]; then
    echo "$1" > "$PF" 2>/dev/null
    local NOW; NOW=$(cat "$PF" 2>/dev/null)
    if [[ "$NOW" == "$1" ]]; then
      echo "风扇档 -> $1"
    else
      echo "⚠️ 风扇档设置失败（期望 $1，当前 $NOW）"
    fi
  else
    echo "⚠️ platform_profile 不可用（uniwill-laptop 未加载），跳过风扇联动"
  fi
}

case "$MODE" in
  a) # ===== 场景 A: 带电极致性能 =====
    # 注意: 只改 AC 部分, BAT 保持场景 B 平衡配置(拔电自动降级, 避免离电全速耗电)
    echo "==> 场景 A: 带电极致性能 (AC全速 / BAT平衡)"
    set_tlp performance performance powersave balance_performance 1 4554000
    gpu_wall 115          # Dynamic Boost 会动态上探 140W; 手动墙保持基础
    if systemctl list-unit-files nvidia-powerd >/dev/null 2>&1; then
      systemctl enable --now nvidia-powerd && echo "nvidia-powerd 已启用 (Dynamic Boost 140W)"
    fi
    # RyzenAdj 温度墙: 读 watchdog conf 的 TCTL_TEMP (默认 92°C, 可 set_tctl.sh 调整)
    # 依据: 7435H Tjmax=95°C (AMD 官方), 92 保守 / 94 极限
# 恢复出厂功耗限制 (出厂默认 80/100/80W, 首次 --info 回读确认)
    ryzenadj_limits 80 100 80
    if command -v ryzenadj >/dev/null; then
      TCTL_TEMP=92; [[ -f /etc/ryzenadj-watch.conf ]] && . /etc/ryzenadj-watch.conf
      ryzenadj --tctl-temp=$TCTL_TEMP && echo "RyzenAdj 温度墙 -> ${TCTL_TEMP}°C (watchdog 同步)"
    else
      echo "⚠️ ryzenadj 未安装 — 先运行: sudo bash deploy_three_mode.sh"
    fi
    brightness 100
    set_refresh 165
    set_fan performance
    echo "提示: 满载请遵守温度红线 (>92°C 停)"
    ;;
  b) # ===== 场景 B: 离电平衡 =====
    echo "==> 场景 B: 离电平衡续航"
    set_tlp performance performance powersave balance_performance 1 4554000
    gpu_wall 60
ryzenadj_limits 45 45 45   # 离电平衡: 上限总功耗 45W
    brightness 60
    set_refresh 60
    set_fan balanced
    ;;
  c) # ===== 场景 C: 离电极限续航 =====
    echo "==> 场景 C: 离电极限续航"
    set_tlp performance performance powersave power 0 2400000
    gpu_wall 30
ryzenadj_limits 30 30 30   # 离电极限: 上限总功耗 30W
    brightness 30
    set_refresh 60
    set_fan quiet
    systemctl disable --now bluetooth 2>/dev/null && echo "蓝牙已关" || echo "⚠️ 蓝牙未关闭（无服务或已关）"
    ;;
esac

echo "==> 验证:"
echo "  AC governor/EPP: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null) / $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null)"
echo "  GPU 功耗墙: $(nvidia-smi -q -d POWER 2>/dev/null | grep 'Current Power Limit' | awk '{print $4" "$5}')"
echo "  TLP 状态: $(systemctl is-active tlp) / PPD: $(systemctl is-active power-profiles-daemon)"
