# 蛟龙15K (GM5BG0E) 键盘修复方案

## 问题

**根因**：BIOS DSDT 中 PS2K 键盘 IRQ1 极性声明错误（ActiveLow→应为ActiveHigh），Linux 6.0+ 内核不再自动修正，GM5BG0E 不在内核兼容表中。

**现象**：内置键盘多键失效，Fn+F4/F5 无反应，外接 USB 键盘正常。

## 修复方案

### 方案1：DSDT Override（推荐，已部署）

**原理**：修改 DSDT 中 IRQ 极性，通过 initrd 注入覆盖 BIOS 原始 DSDT。

**优点**：安全可逆、持久生效、不影响其他功能。

**一键修复**：
```bash
sudo bash 脚本/fix-keyboard.sh
```

**验证**：
```bash
dmesg | grep "ACPI: DSDT ACPI table found in initrd"
grep ' 1:' /proc/interrupts  # 按键后计数应增加
```

### 方案2：i8042.dumbkbd=1（临时止血）

**用法**：在 GRUB_CMDLINE_LINUX_DEFAULT 添加 `i8042.dumbkbd=1`

**缺点**：键盘灯可能不亮，Fn 功能可能异常。

### 方案3：提交上游补丁（长期最优）

**原理**：在内核 `drivers/acpi/resource.c` 的 `irq1_edge_low_force_override[]` 添加 GM5BG0E。

**状态**：同平台 GM5HG0A 已进表，GM5BG0E 待提交。

## Fn 功能键修复

```bash
sudo bash 脚本/install-fn-fix.sh
```

**功能**：
- Fn+F4：WiFi 开关（acpid + nmcli）
- Fn+F5：触控板开关（acpid + xinput）

## 回滚

### DSDT Override 回滚
```bash
sudo rm /boot/acpi_override
# 编辑 /etc/default/grub 删除 GRUB_EARLY_INITRD_LINUX_CUSTOM 行
sudo update-grub
```

### Fn 键修复回滚
```bash
sudo rm /etc/acpi/events/fn-f4-wifi /etc/acpi/events/fn-f5-touchpad \
        /usr/local/bin/fn-f4-wifi.sh /usr/local/bin/fn-f5-touchpad.sh
sudo systemctl restart acpid
```

## 长期注意事项

1. **BIOS 升级**：只刷机械革命官方 7435H 版本；刷后需重新执行修复脚本
2. **内核升级**：不影响，DSDT Override 由 GRUB 加载
3. **重装系统**：需重新执行 `fix-keyboard.sh` 和 `install-fn-fix.sh`

## 文件清单

- `README.md` — 本文件
- `脚本/fix-keyboard.sh` — DSDT 修复部署脚本
- `脚本/install-fn-fix.sh` — Fn 键 acpid 规则安装脚本
- `DSDT文件/dsdt_修改版.dsl` — 修改后的 DSDT 源码
- `DSDT文件/dsdt_原始版.dsl` — BIOS 原始 DSDT 源码
- `DSDT文件/dsdt_原始二进制.dat` — BIOS 原始 DSDT 二进制

## 参考

- [内核 ACPI Override 文档](https://docs.kernel.org/admin-guide/acpi/initrd_table_override.html)
- [社区案例](https://www.cnblogs.com/kyanch/p/19031252)
- [内核补丁历史](https://lore.kernel.org/all/b84edc24-0a3a-a4d2-6481-fb3d4cee6dda@amd.com/T/)

---

**状态**：✅ 已修复并验证  
**适用**：机械革命蛟龙15K (GM5BG0E) + Linux 6.0+
