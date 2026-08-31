# -*- coding: utf-8 -*-
"""fetch 4 mechrevo community project readmes"""
import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
repos = ["roj234/mechrevo_ec_api", "ZhongYic00/mechrevo-imini-ec", "hachimi-ak-ioi/mechrevo-perfd", "dumingqiao/uniwill-laptop-dkms"]
for r in repos:
    print("=== " + r + " ===")
    txt = None
    for br in ("master", "main"):
        url = "https://raw.githubusercontent.com/%s/%s/README.md" % (r, br)
        p = subprocess.run(["curl.exe", "-sL", "--max-time", "20", url], capture_output=True)
        t = p.stdout.decode("utf-8", errors="replace")
        if t and "404" not in t[:40]:
            txt = t
            break
    if txt:
        lines = txt.splitlines()[:20]
        print("\n".join(lines))
    else:
        print("(no readme)")
    print()
