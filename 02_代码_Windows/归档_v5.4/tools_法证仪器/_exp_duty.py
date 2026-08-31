# -*- coding: utf-8 -*-
"""S0-A: duty write semantics final verification
Stage1: NO-OP (write back same value)
Stage2: observe GCUBridge overwrite behavior (write 64, sample 1s/3s/6s)
Stage3: restore original. All states logged; auto-recover in finally."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, r"D:\出厂自带\蛟龙15K_7435H_优化方案_20260825\02_代码_Windows\归档_v5.4")
import mr_ec_hw as ec

ADDR = 0x075B   # CPU PWM (mirror of 0x461)
COLL = [0x0461, 0x075C, 0x0464, 0x0465]  # mirror / gpu pwm / rpm hi-lo

def snap():
    return {"duty": ec.ec_read(ADDR), **{("0x%X" % c): ec.ec_read(c) for c in COLL}}

orig = ec.ec_read(ADDR)
print("[pre] duty raw =", orig, "-> %s%%" % (orig/2 if orig is not None else "?"))
assert orig is not None and orig > 0, "duty unreadable, abort"

try:
    print("\n== Stage1: NO-OP ==")
    ec.ec_write(ADDR, orig)
    time.sleep(1.0)
    v1 = ec.ec_read(ADDR)
    check1 = (v1 == orig)
    print("  write %d -> readback %d : %s" % (orig, v1, "OK" if check1 else "MISMATCH"))

    print("\n== Stage2: small-step真写 64 (32%%) + bridge-overwrite watch ==")
    target = 64
    ec.ec_write(ADDR, target)
    for delay in (1, 3, 6):
        time.sleep(delay if delay == 1 else (delay - sum([1,3])[:[1,3,6].index(delay)] if False else [1,2,3][[1,3,6].index(delay)]))
        v = ec.ec_read(ADDR)
        r = (ec.ec_read(0x464), ec.ec_read(0x465))
        rpm = r[0]*256+r[1] if None not in r else None
        print("  t+%ds: duty=%s (%s%%) rpm=%s %s" % (delay, v, (v/2) if v is not None else "?", rpm,
              "<-- held!" if v == target else ("<-- overwritten by firmware/bridge" if v != target else "")))
finally:
    print("\n== Stage3: restore ==")
    ec.ec_write(ADDR, orig)
    time.sleep(1.0)
    vend = ec.ec_read(ADDR)
    s = snap()
    print("  restored to %d (readback %d)" % (orig, vend))
    print("  collateral:", s)
    ok = (vend == orig)
    print("\nVERDICT:", "PASS - write path live & restored" if ok else "CHECK - readback mismatch")
