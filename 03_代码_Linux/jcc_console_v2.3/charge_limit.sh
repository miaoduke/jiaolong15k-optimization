#!/bin/bash
# charge_limit.sh - 蛟龙15K (GM5BG0E) 充电限制控制
# 用法:
#   charge_limit set <1-100>  设置充电上限百分比（内核原生 sysfs 通道）
#   charge_limit reset        恢复默认充电（充到 100%）
#   charge_limit status       查看充电限制状态
#
# 实现: 优先写内核原生 sysfs charge_control_end_threshold（EC 0x7B9 对应，无需直接 EC 操作）
# 协议参考（本机实测）: 0x7B9=Live Limit, 0x742 bit2=gate, 0x07C3=state
# 注: 原会话中的 EC 直写版本已不可考，本脚本改用 sysfs 原生接口（更安全、内核已暴露）
# ponytail: 选择 sysfs 而非 /dev/mem 直写，避免内核 taint 与重启失效问题

SYSFS_THRESHOLD="/sys/class/power_supply/BAT0/charge_control_end_threshold"
CMD="${1:-status}"

case "$CMD" in
  set)
    pct="${2:-}"
    if ! [[ "$pct" =~ ^[0-9]+$ ]] || [ "$pct" -lt 1 ] || [ "$pct" -gt 100 ]; then
      echo "用法: charge_limit set <1-100>"
      exit 1
    fi
    if [ -w "$SYSFS_THRESHOLD" ]; then
      echo "$pct" | sudo tee "$SYSFS_THRESHOLD" >/dev/null
      echo "充电上限已设为 ${pct}%"
    else
      echo "无法写入 $SYSFS_THRESHOLD（需 root 或该接口不可用）"
      exit 1
    fi
    ;;
  reset)
    if [ -w "$SYSFS_THRESHOLD" ]; then
      echo "100" | sudo tee "$SYSFS_THRESHOLD" >/dev/null
      echo "已恢复默认（充到 100%）"
    else
      echo "无法写入 $SYSFS_THRESHOLD"
      exit 1
    fi
    ;;
  status)
    if [ -r "$SYSFS_THRESHOLD" ]; then
      echo "当前充电上限: $(cat "$SYSFS_THRESHOLD")%"
    else
      echo "接口不可用: $SYSFS_THRESHOLD"
    fi
    ;;
  *)
    echo "用法: charge_limit <set <1-100>|reset|status>"
    exit 1
    ;;
esac
