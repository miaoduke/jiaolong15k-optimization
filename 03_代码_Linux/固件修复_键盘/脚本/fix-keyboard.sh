#!/bin/bash
# ============================================================
# 机械革命蛟龙15K (GM5BG0E) 内置键盘部分键位失效修复脚本
# 原理: BIOS DSDT 中 PS2K 键盘中断极性写反 (ActiveLow -> ActiveHigh)
# 方法: DSDT Override (无需刷 BIOS, 安全可逆)
# 参考: 中文社区已验证方案 (Kyanch博客/洛水天依/Arch中文论坛)
# ============================================================
set -euo pipefail

echo "=============================================="
echo " 机械革命蛟龙15K (GM5BG0E) 键盘 DSDT 修复"
echo "=============================================="

# [0] 权限预检
if [ "$(id -u)" != "0" ]; then
    echo "请用 sudo 运行: sudo bash $0"
    exit 1
fi

# [1] 安装依赖工具
echo "[1/8] 检查/安装工具 (acpica-tools, cpio)..."
if ! command -v iasl >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y acpica-tools
fi
command -v cpio >/dev/null 2>&1 || apt-get install -y cpio
command -v iasl >/dev/null 2>&1 || { echo "ERROR: iasl 安装失败"; exit 1; }
echo "  OK: iasl = $(iasl -v 2>&1 | head -1)"

# [2] 提取并反编译 DSDT
echo "[2/8] 提取当前 DSDT..."
cat /sys/firmware/acpi/tables/DSDT > dsdt.dat
iasl -d dsdt.dat > /dev/null 2>&1 || { echo "ERROR: DSDT 反编译失败"; exit 1; }
echo "  OK: dsdt.dsl 已生成 ($(wc -l < dsdt.dsl) 行)"

# [3] 备份并检查 PS2K 段
cp dsdt.dsl dsdt_orig.dsl
echo "[3/8] PS2K 设备当前中断声明:"
IRQ_LINE=$(grep -A25 "PS2K" dsdt.dsl | grep -m1 "IRQ" || true)
if [ -n "$IRQ_LINE" ]; then
    echo "  $IRQ_LINE"
else
    echo "  警告: 未在 PS2K 段找到 IRQ 行, 继续尝试全局替换"
fi

# [4] 修正中断极性: PS2K 段内第一个 ActiveLow -> ActiveHigh
echo "[4/8] 修正 IRQ 极性 (ActiveLow -> ActiveHigh)..."
sed -i '/PS2K/,/ActiveLow/ s/ActiveLow/ActiveHigh/1' dsdt.dsl
if ! grep -A25 "PS2K" dsdt.dsl | grep -q "ActiveHigh"; then
    echo "  PS2K 段未找到 ActiveHigh, 尝试全局首个替换..."
    sed -i '0,/ActiveLow/s//ActiveHigh/' dsdt.dsl
fi
NEW_IRQ=$(grep -A25 "PS2K" dsdt.dsl | grep -m1 "IRQ" || true)
echo "  修改后: $NEW_IRQ"

# [5] DSDT 版本号 +1 (避免固件缓存冲突)
echo "[5/8] DSDT 版本号 +1..."
perl -pe 'if (/DefinitionBlock/) { s/(0x[0-9a-fA-F]+)/sprintf("0x%X",hex($1)+1)/e }' dsdt.dsl > dsdt_new.dsl
mv dsdt_new.dsl dsdt.dsl
grep -m1 "DefinitionBlock" dsdt.dsl

# [6] 编译
echo "[6/8] 编译修改后的 DSDT..."
iasl dsdt.dsl
[ -f dsdt.aml ] || { echo "ERROR: 编译失败, 原文件保留为 dsdt_orig.dsl"; exit 1; }
echo "  OK: dsdt.aml 已生成"

# [7] 打包并部署 ACPI Override
echo "[7/8] 打包部署 acpi_override..."
rm -rf kernel
mkdir -p kernel/firmware/acpi
cp dsdt.aml kernel/firmware/acpi/
find kernel | cpio -H newc --create > acpi_override
cp acpi_override /boot/
# 备份 GRUB 配置 (便于回滚, 社区脚本可取增量)
[ -f /etc/default/grub.bak ] || cp /etc/default/grub /etc/default/grub.bak
grep -q "GRUB_EARLY_INITRD_LINUX_CUSTOM" /etc/default/grub || \
    echo 'GRUB_EARLY_INITRD_LINUX_CUSTOM="acpi_override"' >> /etc/default/grub
echo "  OK: /boot/acpi_override 已部署"

# 追加 i8042.reset atkbd.reset 内核参数 (防挂起唤醒后键盘失灵, 社区脚本可取增量)
TARGET_PARAMS="i8042.reset atkbd.reset"
if grep -q "^GRUB_CMDLINE_LINUX_DEFAULT" /etc/default/grub; then
    if ! grep -q "$TARGET_PARAMS" /etc/default/grub; then
        sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=\"\(.*\)\"|GRUB_CMDLINE_LINUX_DEFAULT=\"\1 $TARGET_PARAMS\"|" /etc/default/grub
        echo "  OK: 已追加内核参数 $TARGET_PARAMS"
    else
        echo "  OK: 内核参数 $TARGET_PARAMS 已存在"
    fi
else
    echo "GRUB_CMDLINE_LINUX_DEFAULT=\"$TARGET_PARAMS\"" >> /etc/default/grub
fi

# [8] 更新 GRUB
echo "[8/8] 更新 GRUB..."
update-grub

echo ""
echo "=============================================="
echo " 修复完成!"
echo " 1. 重启:        sudo reboot"
echo " 2. 验证:        dmesg | grep -i 'IRQ 1 override'"
echo "    (应出现: ACPI: IRQ 1 override to edge)"
echo " 3. 按键测试:    grep ' 1:' /proc/interrupts"
echo "    (按内置键盘后计数应明显增加)"
echo "----------------------------------------------"
echo " 回滚方法:"
echo "   sudo rm /boot/acpi_override"
echo "   编辑 /etc/default/grub 删除 GRUB_EARLY_INITRD_LINUX_CUSTOM 行,"
echo "   并从 GRUB_CMDLINE_LINUX_DEFAULT 移除 i8042.reset atkbd.reset"
echo "   (如需完全还原可恢复备份: sudo cp /etc/default/grub.bak /etc/default/grub)"
echo "   sudo update-grub"
echo "=============================================="