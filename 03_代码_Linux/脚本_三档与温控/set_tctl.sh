#!/usr/bin/env bash
# set_tctl.sh — 切换 CPU 温度墙 (tctl), 与 watchdog 同步
# 用法: sudo bash set_tctl.sh [90|91|92|93|94|95]   例: sudo bash set_tctl.sh 94
# 原理: 权威入口是 /etc/ryzenadj-watch.conf 的 TCTL_TEMP (watchdog 每 5s 重写此值)
#   直接 ryzenadj --tctl-temp 会被 watchdog 立即覆盖, 必须改 conf
# 依据: 7435H Tjmax=95°C (AMD 官方); 92 为默认保守值, 94 为极限档 (余量仅 1°C)
# 安全: 写入后回读验证; 范围校验 90-95; 95 仅作理论值不建议使用

set -u
TARGET="${1:-}"
CONF="/etc/ryzenadj-watch.conf"

if [[ ! "$TARGET" =~ ^(9[0-5])$ ]]; then
  echo "用法: sudo bash set_tctl.sh [90-95]  (7435H Tjmax=95, 建议 92/94)"
  exit 1
fi
if [[ $EUID -ne 0 ]]; then echo "需要 root (sudo)"; exit 1; fi

# 备份 conf (首次)
[[ -f "$CONF.orig" ]] || cp "$CONF" "$CONF.orig"

# 1. 写入 conf (权威值, watchdog 会持续应用)
if grep -q "^TCTL_TEMP=" "$CONF"; then
  sed -i "s/^TCTL_TEMP=.*/TCTL_TEMP=$TARGET/" "$CONF"
else
  echo "TCTL_TEMP=$TARGET" >> "$CONF"
fi

# 2. 立即应用一次 (不等 5s 周期)
ryzenadj --tctl-temp=$TARGET >/dev/null 2>&1

# 3. 回读验证 (铁律: 写后必回读)
NOW=$(ryzenadj --info 2>/dev/null | grep -iE "tctl" | grep -oE '[0-9]+\.?[0-9]*' | head -1)
if [[ "$NOW" == "$TARGET" || "$NOW" == "$TARGET.000" ]]; then
  echo "✅ CPU 温度墙 -> ${TARGET}°C (watchdog 同步, 回读一致)"
else
  echo "⚠️ 回读不一致: 期望 ${TARGET}, 实际 ${NOW} (请检查 ryzenadj 状态)"
fi
echo "  提示: 92=默认保守 / 94=极限(余量1°C, 长期满载慎用)"