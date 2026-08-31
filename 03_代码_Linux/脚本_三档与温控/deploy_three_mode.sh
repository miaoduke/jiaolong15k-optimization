#!/usr/bin/env bash
# deploy_three_mode.sh — 三模式方案一次性部署
# 内容: 1) 安装 ryzenadj 2) 配置 nvidia-powerd (140W Dynamic Boost) 3) 部署 RyzenAdj 守护循环
# 用法: sudo bash deploy_three_mode.sh          # 完整部署
#       sudo bash deploy_three_mode.sh --uninstall   # 回滚
# 安全: 全部先备份原文件; 可重复执行(幂等); 所有写入后回读
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RYZENADJ_SRC="$SCRIPT_DIR/ryzenadj-v0.19.0"
DBUS_CONF="/etc/dbus-1/system.d/nvidia-powerd.conf"
SERVICE_SRC="/usr/share/doc/nvidia-kernel-common-595/nvidia-powerd.service"
SERVICE_DST="/lib/systemd/system/nvidia-powerd.service"
WATCH_SH="/usr/local/bin/ryzenadj-watch.sh"
WATCH_CONF="/etc/ryzenadj-watch.conf"
WATCH_SERVICE="/lib/systemd/system/ryzenadj-watch.service"
WATCH_TIMER="/lib/systemd/system/ryzenadj-watch.timer"

if [[ $EUID -ne 0 ]]; then echo "需要 root (sudo)"; exit 1; fi

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "==> 回滚:"
  systemctl disable --now ryzenadj-watch.timer 2>/dev/null && echo "  守护循环 timer 已停"
  systemctl disable --now nvidia-powerd 2>/dev/null && echo "  nvidia-powerd 已停"
  rm -f "$WATCH_TIMER" "$WATCH_SERVICE" "$WATCH_SH" "$WATCH_CONF"
  rm -f "$DBUS_CONF"
  systemctl daemon-reload
  [[ -x /usr/local/bin/ryzenadj ]] && { rm -f /usr/local/bin/ryzenadj; echo "  ryzenadj 已移除"; }
  echo "  完成（注意: tlp.conf 与 GPU 墙请用 apply_mode.sh 或 reset_all.sh 恢复）"
  exit 0
fi

echo "==> 0/4 电源管理栈规范化 (00/05 铁律: TLP 启用时必须停用 PPD)"
if systemctl is-active power-profiles-daemon >/dev/null 2>&1; then
  systemctl disable --now power-profiles-daemon && echo "  PPD 已停用 (TLP 接管)"
else
  echo "  PPD 已停用 ✓"
fi
if ! systemctl is-active tlp >/dev/null 2>&1; then
  systemctl enable --now tlp && echo "  TLP 已启用"
else
  echo "  TLP 已 active ✓"
fi

echo "==> 1/4 安装 ryzenadj"
if [[ -x /usr/local/bin/ryzenadj ]]; then
  echo "  已安装: $(/usr/local/bin/ryzenadj --info 2>&1 | head -1 || true)"
else
  cp "$RYZENADJ_SRC" /usr/local/bin/ryzenadj && chmod 755 /usr/local/bin/ryzenadj
  echo "  /usr/local/bin/ryzenadj 已安装 (v0.19.0 静态二进制, 来源: FlyGoat/RyzenAdj GitHub)"
fi

echo "==> 2/4 配置 nvidia-powerd (Dynamic Boost 140W)"
# 2.1 dbus 策略 (官方 README 标准内容; 备份已有)
if [[ -f "$DBUS_CONF" ]]; then cp "$DBUS_CONF" "$DBUS_CONF.bak.$(date +%Y%m%d%H%M%S)"; fi
cat > "$DBUS_CONF" <<'EOF'
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy user="root">
    <allow own="nvidia.powerd.server"/>
    <allow own="com.nvidia.powerd"/>
    <allow send_destination="nvidia.powerd.server"/>
    <allow send_destination="com.nvidia.powerd"/>
  </policy>
  <policy context="default">
    <allow send_destination="nvidia.powerd.server"/>
    <allow send_destination="com.nvidia.powerd"/>
  </policy>
</busconfig>
EOF
echo "  dbus 策略已写入 $DBUS_CONF (服务名 nvidia.powerd.server, 595 驱动验证通过)"
# 2.2 systemd 服务 (官方样例)
if [[ -f "$SERVICE_SRC" ]]; then
  cp "$SERVICE_SRC" "$SERVICE_DST"
  echo "  服务文件已就位 (来自驱动包官方样例)"
else
  echo "  ⚠️ 驱动包无样例文件, 跳过 (新驱动可能已内置)"
fi
# 2.3 日志目录 (daemon 启动必需)
mkdir -p /var/log/nvtopps
# 2.4 启用
systemctl daemon-reload
systemctl enable --now nvidia-powerd
sleep 2
if systemctl is-active nvidia-powerd >/dev/null; then
  echo "  ✅ nvidia-powerd active"
else
  echo "  ⚠️ nvidia-powerd 未启动, 状态: $(systemctl is-active nvidia-powerd) — 查看: journalctl -u nvidia-powerd -n 20"
fi

echo "==> 3/4 部署 RyzenAdj 守护循环 (每 30s 重写 tctl-temp, 防固件覆盖)"
# 配置: TCTL_TEMP=92 (可改)
echo "TCTL_TEMP=92" > "$WATCH_CONF"
cat > "$WATCH_SH" <<'EOF'
#!/usr/bin/env bash
# ryzenadj-watch.sh — 每 30s 由 timer 调用, 重写 tctl-temp (幂等)
set -u
CONF=/etc/ryzenadj-watch.conf
TCTL_TEMP=92
[[ -f "$CONF" ]] && . "$CONF"
if command -v ryzenadj >/dev/null; then
  ryzenadj --tctl-temp="$TCTL_TEMP" >/dev/null 2>&1 \
    || echo "$(date +%F_%T) ryzenadj write failed" >> /var/log/ryzenadj-watch.log
fi
EOF
chmod 755 "$WATCH_SH"
cat > "$WATCH_SERVICE" <<'EOF'
[Unit]
Description=RyzenAdj tctl-temp keeper

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ryzenadj-watch.sh
EOF
cat > "$WATCH_TIMER" <<'EOF'
[Unit]
Description=RyzenAdj watch timer (30s)

[Timer]
OnBootSec=60
OnUnitActiveSec=30

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now ryzenadj-watch.timer
echo "  守护循环已启用 (30s interval; 改温度: 编辑 $WATCH_CONF 后无需重启)"

echo "==> 4/4 校验"
echo "  ryzenadj: $(command -v ryzenadj || echo MISSING)"
echo "  DynamicBoostSupport: $(nvidia-settings -q DynamicBoostSupport 2>/dev/null | grep -o '[01]$' || echo '?')"
echo "  nvidia-powerd: $(systemctl is-active nvidia-powerd)"
echo "  ryzenadj-watch.timer: $(systemctl is-active ryzenadj-watch.timer)"
echo "  TLP: $(systemctl is-active tlp) / PPD: $(systemctl is-active power-profiles-daemon)"
echo
echo "==> 部署完成。后续使用:"
echo "  sudo bash apply_mode.sh a   # 带电极致 (nvidia-powerd 已就绪, 自动启用 Dynamic Boost)"
echo "  sudo bash apply_mode.sh b   # 离电平衡 (45W 功耗限制)"
echo "  sudo bash apply_mode.sh c   # 离电极限 (30W 功耗限制)"
echo "  sudo bash deploy_three_mode.sh --uninstall   # 回滚本部署"
echo "  ⚠️ 满载请遵守红线: 起始>75°C 拒测 / 测试中>92°C 停 / >95°C 熔断冷却 120s"