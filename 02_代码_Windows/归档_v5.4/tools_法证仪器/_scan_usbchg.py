# -*- coding: utf-8 -*-
"""strings-scan GCUService.exe for USB-charge related commands"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
path = r"C:\Program Files\OEM\机械革命电竞控制台\UniwillService\MyControlCenter\GCUService.exe"
data = open(path, "rb").read()
print("size:", len(data))
pat = re.compile(rb"[\x20-\x7e]{5,}")
kw = re.compile(r"(?i)(usb|charge|charg|batterypass|powershare|off.?mode|always.?on)")
hits = {}
for m in pat.finditer(data):
    s = m.group().decode()
    if kw.search(s):
        hits.setdefault(s, m.start())
for s, off in sorted(hits.items(), key=lambda kv: kv[1]):
    print("%08X  %s" % (off, s[:110]))
print("total:", len(hits))
