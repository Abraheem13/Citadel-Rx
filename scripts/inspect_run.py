#!/usr/bin/env python
"""Print a compact per-block trace of one or more run records (for debugging)."""
import json
import sys

for path in sys.argv[1:]:
    r = json.load(open(path))
    s = r["summary"]
    print(f"== {r['name']} seed={r['seed']} rx={r['receiver']} hash={r['config_hash']}")
    print("   " + " ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in s.items()))
    keys = [k for k in ("ser", "ber", "bler", "attacked", "gamma", "surprise_ratio", "eta", "gate_g1", "gate_g2",
                        "gate_g3", "fast_step_norm", "level2_disp", "level3_disp", "fast_to_slow", "t_rx")
            if k in r["blocks"][0]]
    print("   block " + " ".join(f"{k:>10s}" for k in keys))
    for b in r["blocks"]:
        row = []
        for k in keys:
            v = b.get(k)
            row.append(f"{v:10.4f}" if isinstance(v, float) else f"{str(v):>10s}")
        print(f"   {b['block']:5d} " + " ".join(row))
