# -*- coding: utf-8 -*-
"""explore mechrevo_ec_api repo tree"""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
def gh(url):
    p = subprocess.run(["curl.exe", "-sL", "--max-time", "30", url], capture_output=True)
    return json.loads(p.stdout.decode("utf-8", errors="replace"))
info = gh("https://api.github.com/repos/roj234/mechrevo_ec_api")
print("stars:", info.get("stargazers_count"), "| lang:", info.get("language"), "| pushed:", str(info.get("pushed_at"))[:10])
tree = gh("https://api.github.com/repos/roj234/mechrevo_ec_api/git/trees/master?recursive=1")
if "tree" not in tree:
    tree = gh("https://api.github.com/repos/roj234/mechrevo_ec_api/git/trees/main?recursive=1")
for t in tree.get("tree", []):
    if t["type"] == "blob":
        print("  %6d  %s" % (t.get("size", 0), t["path"]))
