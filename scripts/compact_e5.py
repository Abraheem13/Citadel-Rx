#!/usr/bin/env python
"""Compact E5 records: replace the in-JSON level snapshots (hundreds of MB per run) by the
per-block displacement curves needed for the retention certificate (Corollary 2.2).

For every attacked record it finds the clean record with the same periods and seed and stores
    paired_disp[k][b] = || theta_adv^(k)_b - theta_clean^(k)_b ||          (k = 1..K)
    self_disp[k][b]   = || theta^(k)_b - theta^(k)_0 ||
then strips `level_snapshots` from both files (snapshots are also saved to <record>.levels.npz,
compressed float16, which git ignores).

    python scripts/compact_e5.py results/e5
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np


def load_snaps(rec):
    snaps = rec.get("level_snapshots")
    if not snaps:
        return None
    K = len(snaps[0]["levels"])
    out = []
    for k in range(K):
        keys = sorted(snaps[0]["levels"][k].keys())
        out.append(np.stack([np.concatenate([np.asarray(s["levels"][k][key], dtype=np.float32).ravel() for key in keys])
                             for s in snaps]))  # (n_blocks, n_params)
    return out


def main(root):
    files = sorted(glob.glob(os.path.join(root, "*.json")))
    recs = {}
    for fn in files:
        with open(fn) as f:
            recs[fn] = json.load(f)
    snaps = {fn: load_snaps(r) for fn, r in recs.items()}
    by_key = {}
    for fn, r in recs.items():
        c = r["config"]
        by_key[(tuple(c["citadel"]["periods"]), r["seed"], c["attack"]["type"])] = fn
    for fn, r in recs.items():
        c = r["config"]
        s = snaps[fn]
        if s is None:
            continue
        r["self_disp"] = [np.linalg.norm(lv - lv[0], axis=1).tolist() for lv in s]
        if c["attack"]["type"] != "none":
            clean_fn = by_key.get((tuple(c["citadel"]["periods"]), r["seed"], "none"))
            if clean_fn and snaps[clean_fn] is not None:
                r["paired_disp"] = [np.linalg.norm(a - b, axis=1).tolist() for a, b in zip(s, snaps[clean_fn])]
                r["paired_with"] = os.path.basename(clean_fn)
        np.savez_compressed(fn.replace(".json", ".levels.npz"), **{f"level{k + 1}": lv.astype(np.float16) for k, lv in enumerate(s)})
        r.pop("level_snapshots", None)
        with open(fn, "w") as f:
            json.dump(r, f)
        print(f"compacted {os.path.basename(fn)}: {os.path.getsize(fn) / 1e6:.1f} MB"
              + (" (paired)" if "paired_disp" in r else ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/e5")
