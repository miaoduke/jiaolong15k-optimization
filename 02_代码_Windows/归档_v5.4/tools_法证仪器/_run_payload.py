
# -*- coding: utf-8 -*-
"""elevated runner: chdir to self dir, run payload ps1 absolutely, log everything"""
import os
import subprocess
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
ps1 = os.path.join(HERE, "_ecadmin_full.ps1")
log = os.path.join(HERE, "_ec_bat_log.txt")
with open(log, "a", encoding="utf-8") as f:
    f.write("[runner] cwd=%s ps1_exists=%s\n" % (os.getcwd(), os.path.exists(ps1)))
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
    capture_output=True, text=True, errors="replace", timeout=420, cwd=HERE)
with open(log, "a", encoding="utf-8") as f:
    f.write("[runner] rc=%s\nstdout:\n%s\nstderr:\n%s\n" % (r.returncode, r.stdout or "", r.stderr or ""))
sys.exit(r.returncode)
