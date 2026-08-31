# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
print(new_tab("https://api.github.com/repos/ViRb3/LenovoLegionToolkit"))
import time; time.sleep(2)
info = page_info()
print(str(info)[:400])
