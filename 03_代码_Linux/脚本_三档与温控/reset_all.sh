#!/usr/bin/env bash
# reset_all.sh — 回滚到保守默认（应用前状态）
# 用法: sudo bash reset_all.sh
# 还原: EPP=performance / governor=performance / GPU 115W / TLP 默认 / 蓝牙开 / 亮度 100%

set -u
if [[ $EUID -ne 0 ]]; then echo "需要 root"; exit 1; fi

echo "==> 回滚到保守默认..."

# 1. CPU: governor/EPP 手动复位
for c in /sys/devices/system/cpu/cpu*/cpufreq/; do
  echo performance > "$c/scaling_governor" 2>/dev/null
  echo performance > "$c/energy_performance_preference" 2>/dev/null
done
echo "  CPU: governor=performance EPP=performance"

# 2. GPU 功耗墙（本机手动 -pl 无效，04 陷阱 11；命令保留仅为兼容）
nvidia-smi -pl 115 >/dev/null 2>&1
echo "  GPU: 功耗墙由 nvidia-powerd 管理（手动 -pl 在本机无效）"

# 3. nvidia-powerd 停用
systemctl disable --now nvidia-powerd 2>/dev/null && echo "  nvidia-powerd 已停用"

# 4. TLP 恢复原配置（若有备份）
if [[ -f /etc/tlp.conf.orig ]]; then
  cp /etc/tlp.conf.orig /etc/tlp.conf && echo "  tlp.conf 已还原（备份于 apply_mode.sh 首次运行）"
fi
systemctl restart tlp 2>/dev/null

# 5. 蓝牙 + 亮度
systemctl enable --now bluetooth 2>/dev/null || true
if [[ -f /sys/class/backlight/nvidia_0/max_brightness ]]; then
  echo $(cat /sys/class/backlight/nvidia_0/max_brightness) > /sys/class/backlight/nvidia_0/brightness && echo "  亮度 100%"
fi

echo "==> 完成。验证:"
echo "  EPP=$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference)"
echo "  GPU墙=$(nvidia-smi -q -d POWER 2>/dev/null | grep 'Current Power Limit' | awk '{print $4" "$5}')"
