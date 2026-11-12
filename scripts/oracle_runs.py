#!/usr/bin/env python
"""Exact-gate attacker (attack.oracle_scales): the optimised perturbation of an existing adaptive attack
is scaled by each factor, every candidate is run through an exact copy of the victim, and the most
damaging one is sent (oracle_mode max_ser), or the most damaging one the gates accept (accepted).

Experiments (settings read from the soft-G1 re-run of the base attack; only attack.oracle_* added):

  p3_citadel_oracle_maxser__sir0   soft gates, unroll 10, PGD 20, then exact selection, highest SER
  p3_citadel_oracle_acc__sir0      the same, highest SER among the accepted candidates
  b2_a4_a0.25_pgd20_oracle_acc__sir0  A4, alpha 0.25, PGD 20, exact selection among accepted candidates

Attacked runs go to results/rev_p3_oracle, each seed's clean twin (one per seed, the experiments share
their settings apart from attack.*) to results/rev_clean_<machine>.

    CITADEL_MACHINE=pool27 python scripts/oracle_runs.py --seeds 10 --workers 4
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from rerun_g1fix import clean_cfg, mkey, run_one  # noqa: E402

RES = os.path.join(ROOT, "results")
OUT = os.path.join(RES, "rev_p3_oracle")
SCALES = [1.0, 0.5, 0.35, 0.25, 0.18, 0.12, 0.08, 0.05]
EXPS = [("p3_citadel_oracle_maxser__sir0", "rev_p3_adaptive_g1fix", "p3_citadel_softgate__sir0", "max_ser"),
        ("p3_citadel_oracle_acc__sir0", "rev_p3_adaptive_g1fix", "p3_citadel_softgate__sir0", "accepted"),
        ("b2_a4_a0.25_pgd20_oracle_acc__sir0", "rev2_a4_pgd20_g1fix", "b2_a4_a0.25_pgd20__sir0", "accepted")]


def base_cfg(folder: str, name: str) -> dict:
    fs = sorted(f for f in glob.glob(os.path.join(RES, folder, f"{name}_s*_*.json")) if not f.endswith(".levels.json"))
    if not fs:
        raise SystemExit(f"no record of {name} in {folder}")
    rec = json.load(open(fs[0]))
    return rec["config"], float(rec["summary"].get("total_time_s", 1800))


def plan(seeds, machine):
    jobs, twins = [], {}
    for name, folder, base, mode in EXPS:
        cfg, est = base_cfg(folder, base)
        cfg = json.loads(json.dumps(cfg))
        cfg["attack"]["oracle_scales"], cfg["attack"]["oracle_mode"] = SCALES, mode
        for s in seeds:
            jobs.append({"kind": "attacked", "name": name, "seed": s, "cfg": cfg, "out": OUT,
                         "est": est * 1.6, "pairs_as": None, "of": None})
            k = (mkey(cfg), s)
            if k not in twins:
                h = hashlib.sha1(k[0].encode()).hexdigest()[:8]
                twins[k] = {"kind": "clean", "name": f"oracle_twin_{h}", "seed": s, "cfg": clean_cfg(cfg),
                            "out": os.path.join(RES, f"rev_clean_{machine}"), "est": 600, "pairs_as": None, "of": None}
    jobs += list(twins.values())
    jobs.sort(key=lambda j: -j["est"])
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    machine = os.environ.get("CITADEL_MACHINE", "")
    if not machine and not a.dry:
        raise SystemExit("set CITADEL_MACHINE")
    os.environ.setdefault("CITADEL_PRETRAIN_CACHE", os.path.join(ROOT, "cache", "pretrain"))
    os.environ["CITADEL_THREADS"] = "1"
    jobs = plan(a.seeds, machine or "DRY")
    for j in jobs:
        print(f"{j['kind']:9s} {j['name']:38s} seed {j['seed']:2d}  ~{j['est'] / 60:4.0f} min  -> {os.path.relpath(j['out'], ROOT)}")
    if a.dry:
        return
    with mp.get_context("spawn").Pool(a.workers, maxtasksperchild=1) as pool:
        for msg in pool.imap_unordered(run_one, jobs):
            print(time.strftime("%H:%M:%S"), msg, flush=True)


if __name__ == "__main__":
    main()
