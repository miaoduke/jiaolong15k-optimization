# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = r"C:\Program Files\OEM"
PAT16 = "W\x00r\x00i\x00t\x00e\x00E\x00C\x00".encode("utf-16-le")[2:]  # strip BOM-ish, keep pairs
PAT16 = b"W\x00r\x00i\x00t\x00e\x00E\x00C\x00"
for dirpath, dirs, files in os.walk(ROOT):
    for f in files:
        if not f.lower().endswith((".exe", ".dll")):
            continue
        p = os.path.join(dirpath, f)
        try:
            b = open(p, "rb").read()
            hits = []
            if b.find(b"WriteEC\x00") >= 0: hits.append("ascii")
            if b.find(PAT16) >= 0: hits.append("utf16")
            if hits:
                print("%s  [%s] size=%d" % (p, ",".join(hits), len(b)), flush=True)
        except Exception as e:
            print("ERR %s %r" % (p, e), flush=True)
print("--- done ---", flush=True)
