#!/usr/bin/env python
"""Run further test seeds of existing experiments, each with a clean twin on the same machine.

The settings of an experiment are read from one of its records (the re-run with the fixed soft G1 term,
results/<folder>_g1fix, when there is one, else results/<folder>); only the seed differs. Attacked runs
go to results/<folder>_more, clean twins to results/rev_clean_<machine>. scripts/revision_numbers.py
adds the records of results/<folder>_more to those of results/<folder>, so a table cell then covers the
old and the new seeds, each run paired with the twin of its own machine.

    CITADEL_MACHINE=pool21 python scripts/extend_seeds.py --exps rev_p8_drift:p8_a3star_e0.05__long \
        rev2_drift_guard:h5_a3star_e0.05_guard__long --seeds 12 --workers 4
    python scripts/extend_seeds.py --set a3star_400 --seeds 12 --dry
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
SETS = {   # named groups of experiments (folder:name)
    "a3star_400": ["rev_p8_drift:p8_a3star_e0.05__long", "rev_p8_drift:p8_a3star_e0.2__long",
                   "rev_p8_drift:p8_a3star_e0.5__long", "rev_p8_drift:p8_a3star_e0.5_guard__long",
                   "rev2_drift_guard:h5_a3star_e0.05_guard__long"],
    "a3star_1000": ["rev2_drift_long:b5_a3star_e0.05__long1000"],
}


def base_record(folder: str, name: str) -> dict:
    for d in (folder + "_g1fix", folder):
        fs = sorted(glob.glob(os.path.join(RES, d, f"{name}_s*_*.json")))
        fs = [f for f in fs if not f.endswith(".levels.json")]
        if fs:
            return json.load(open(fs[0]))
    raise SystemExit(f"no record of {name} in {folder}")


def plan(exps, seeds, machine):
    att, cln = [], {}
    for e in exps:
        folder, name = e.split(":")
        rec = base_record(folder, name)
        for s in seeds:
            att.append({"kind": "attacked", "name": name, "seed": s, "cfg": rec["config"],
                        "out": os.path.join(RES, folder + "_more"), "est": float(rec["summary"].get("total_time_s", 1800)),
                        "pairs_as": None, "of": None})
            k = (mkey(rec["config"]), s)
            if k not in cln:
                h = hashlib.sha1(k[0].encode()).hexdigest()[:8]
                cln[k] = {"kind": "clean", "name": f"ext_twin_b{rec['config']['frame']['n_blocks']}_{h}", "seed": s,
                          "cfg": clean_cfg(rec["config"]), "out": os.path.join(RES, f"rev_clean_{machine}"),
                          "est": float(rec["summary"].get("total_time_s", 1800)) / 3, "pairs_as": None, "of": None}
    jobs = att + list(cln.values())
    jobs.sort(key=lambda j: -j["est"])
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exps", nargs="*", default=[])
    ap.add_argument("--set", nargs="*", default=[], choices=sorted(SETS))
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    machine = os.environ.get("CITADEL_MACHINE", "")
    if not machine and not a.dry:
        raise SystemExit("set CITADEL_MACHINE (an attacked run pairs with the clean twin of its own machine)")
    exps = list(a.exps) + [e for s in a.set for e in SETS[s]]
    os.environ.setdefault("CITADEL_PRETRAIN_CACHE", os.path.join(ROOT, "cache", "pretrain"))
    os.environ["CITADEL_THREADS"] = "1"
    jobs = plan(exps, a.seeds, machine or "DRY")
    for j in jobs:
        print(f"{j['kind']:9s} {j['name']:36s} seed {j['seed']:2d}  ~{j['est'] / 60:4.0f} min  -> {os.path.relpath(j['out'], ROOT)}")
    print(f"{len(jobs)} jobs, ~{sum(j['est'] for j in jobs) / 60:.0f} CPU-min")
    if a.dry:
        return
    with mp.get_context("spawn").Pool(a.workers, maxtasksperchild=1) as pool:
        for msg in pool.imap_unordered(run_one, jobs):
            print(time.strftime("%H:%M:%S"), msg, flush=True)


if __name__ == "__main__":
    main()
