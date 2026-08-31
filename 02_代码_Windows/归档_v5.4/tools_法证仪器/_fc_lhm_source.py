# -*- coding: utf-8 -*-
"""check FanControl source openness + pull LHM full tree"""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
def gh(url):
    p = subprocess.run(["curl.exe", "-sL", "--max-time", "40", url], capture_output=True)
    try: return json.loads(p.stdout.decode("utf-8", errors="replace"))
    except Exception as e:
        print("parse err:", p.stdout[:120]); return {}

print("=== FanControl repos by Rem0o ===")
res = gh("https://api.github.com/search/repositories?q=user:Rem0o&sort=updated&per_page=10")
for it in res.get("items", []):
    print("  %-45s %5d* fork=%s lang=%s" % (it["full_name"], it["stargazers_count"], it["fork"], it.get("language")))

print("=== LHM tree (key dirs) ===")
tree = gh("https://api.github.com/repos/LibreHardwareMonitor/LibreHardwareMonitor/git/trees/master?recursive=1")
items = tree.get("tree", [])
print("total files:", len(items))
import re
for t in items:
    if t["type"] != "blob": continue
    p = t["path"]
    if re.search(r"(?i)(ec|embedded|superio|lpcio|ring0|kerneldriver|winring)", p) and p.endswith((".cs", ".sys", ".csproj")):
        print("  %7d  %s" % (t.get("size", 0), p))
