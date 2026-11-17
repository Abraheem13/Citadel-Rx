#!/usr/bin/env python
"""Freeze the settings chosen on calibration seeds, by rules written before the runs (docs/v3/PHASE2.md).

    python scripts/v3/freeze.py --phase 2        # writes configs/v3_frozen_fix.json

Phase 2, fix of the cold-start hole (Phase 1 report, 1b). Candidates: base (first-version settings), F1
(rejected blocks vote for the memory), F2 (references seeded only by accepted blocks), F1F2. On seeds 0-2:
  * admissible: clean false-rejection rate <= 2% (clean twins, blocks >= 5);
  * chosen: the lowest mean of (warm A1 excess, cold A1 excess); within 0.001 of the lowest, the simplest
    in the order base, F2, F1, F1F2.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
spec = importlib.util.spec_from_file_location("v3analyze", os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phases import FIXES  # noqa: E402

OUT = os.path.join(ROOT, "configs", "v3_frozen_fix.json")
ORDER = ["base", "F2", "F1", "F1F2"]


def freeze_fix() -> dict:
    prs, problems, _ = A.pairs(2)
    table = {}
    for tag in ORDER:
        warm, cold = prs.get(f"v3p2F_{tag}_warm__a1_sir0", []), prs.get(f"v3p2F_{tag}_cold__a1_sir0", [])
        if not warm or not cold:
            continue
        cw, cc = A.cell(warm), A.cell(cold)
        k = n = 0
        twins = {a["seed"]: c for a, c in warm}   # one clean twin per seed (shared by the warm and cold cells)
        for c in twins.values():
            g = A.arr(c, "gamma")[5:]
            k += int(np.sum(g < 0.5))
            n += int(np.sum(~np.isnan(g)))
        table[tag] = {"warm_excess": cw["excess"], "cold_excess": cc["excess"], "score": (cw["excess"] + cc["excess"]) / 2,
                      "clean_frr": k / max(n, 1), "seeds": cw["seeds"], "overrides": FIXES[tag]}
    if not table:
        raise SystemExit("no calibration records of group 2F: run the cal stage first")
    adm = {t: v for t, v in table.items() if v["clean_frr"] <= 0.02} or table
    best = min(v["score"] for v in adm.values())
    chosen = next(t for t in ORDER if t in adm and adm[t]["score"] <= best + 0.001)
    return {"rule": __doc__.split("Phase 2,")[1].strip(), "table": table, "chosen": chosen,
            "overrides": FIXES[chosen], "problems": problems, "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, required=True, choices=[2])
    a = ap.parse_args()
    if os.path.exists(OUT):
        print(f"{os.path.relpath(OUT, ROOT)} exists already (frozen settings are never re-derived); delete it by hand only"
              " if the calibration runs changed")
        print(open(OUT).read())
        return 0
    res = freeze_fix()
    json.dump(res, open(OUT, "w"), indent=1)
    for t, v in res["table"].items():
        print(f"   {t:5s} warm {v['warm_excess']:+.4f}  cold {v['cold_excess']:+.4f}  score {v['score']:+.4f}"
              f"  clean FRR {v['clean_frr']:.3f}")
    print(f"== chosen: {res['chosen']} {res['overrides']}  -> {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
