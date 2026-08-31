#!/bin/bash
# 关机时保存当前键盘 RGB 颜色（读 EC 0x769-76B）
mkdir -p /var/lib/kbd-rgb
python3 - <<'PYEOF'
import re
def rb(a):
    with open('/proc/acpi/call', 'w') as f:
        f.write(f'\\_SB.AMW0.RKBC 0x{a & 0xFF:02X} 0x{a >> 8:02X}')
    with open('/proc/acpi/call') as f:
        return int(re.findall(r'0x([0-9a-fA-F]+)', f.read())[0], 16)
with open('/var/lib/kbd-rgb/state', 'w') as f:
    f.write(f'{rb(0x769)} {rb(0x76A)} {rb(0x76B)}\n')
PYEOF
