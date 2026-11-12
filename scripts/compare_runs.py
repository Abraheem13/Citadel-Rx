#!/usr/bin/env python
"""Side-by-side comparison of run records in a directory (pre/attack/post SER, recovery, gate rates).

    python scripts/compare_runs.py results/smoke
"""
import glob
import json
import os
import sys

rows = []
for fn in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    r = json.load(open(fn))
    s, c = r["summary"], r["config"]
    rows.append((r["name"], r["receiver"], c["attack"]["type"], c["attack"]["sir_db"],
                 s.get("ser_pre", s["ser_mean"]), s.get("ser_attack"), s.get("ser_post"), s.get("recovery_blocks"),
                 s.get("gate_reject_rate_attacked"), s.get("gate_false_reject_rate_clean"), s.get("gamma_mean"),
                 s["mean_t_rx_s"]))
hdr = ("name", "rx", "atk", "SIR", "SER pre", "SER att", "SER post", "recov", "rej|att", "frej|clean", "gamma", "s/blk")
print("{:34s} {:14s} {:8s} {:>5s} {:>8s} {:>8s} {:>8s} {:>6s} {:>7s} {:>10s} {:>6s} {:>5s}".format(*hdr))
for row in rows:
    f = lambda v, w=8, p=4: (f"{v:{w}.{p}f}" if isinstance(v, float) else f"{str(v):>{w}s}")
    print(f"{row[0]:34s} {row[1]:14s} {row[2]:8s} {f(row[3],5,1)} {f(row[4])} {f(row[5])} {f(row[6])} {f(row[7],6,0)} "
          f"{f(row[8],7,2)} {f(row[9],10,2)} {f(row[10],6,2)} {f(row[11],5,1)}")
