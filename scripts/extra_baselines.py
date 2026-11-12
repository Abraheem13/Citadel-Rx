#!/usr/bin/env python
"""Two reference receivers for the headline cell (white-box A1, SIR 0 dB, seeds 10-19), each with a clean
twin on the same machine: exhaustive ML detection with the LS channel estimate (receiver.type=ml) and the
pre-trained DeepSIC that never adapts (online DeepSIC with receiver.epochs=0). Settings are those of the
online DeepSIC headline record; attacked runs go to results/rev_p1_more (read with results/rev_p1).

    CITADEL_MACHINE=pool13 python scripts/extra_baselines.py --seeds 10 11 12 13 14 15 16 17 18 19 --workers 3
"""
from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from rerun_g1fix import clean_cfg, run_one  # noqa: E402

RES = os.path.join(ROOT, "results")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    machine = os.environ["CITADEL_MACHINE"]
    os.environ.setdefault("CITADEL_PRETRAIN_CACHE", os.path.join(ROOT, "cache", "pretrain"))
    os.environ["CITADEL_THREADS"] = "1"
    base = json.load(open(sorted(glob.glob(os.path.join(RES, "rev_p1", "p1_online_deepsic__wb_sir0_s10_*.json")))[0]))["config"]
    jobs = []
    for name, rx in (("p1_ml__wb_sir0", {"type": "ml"}), ("p1_frozen_deepsic__wb_sir0", {"type": "online_deepsic", "epochs": 0})):
        cfg = json.loads(json.dumps(base))
        cfg["receiver"].update(rx)
        for s in a.seeds:
            jobs.append({"kind": "attacked", "name": name, "seed": s, "cfg": cfg, "out": os.path.join(RES, "rev_p1_more"),
                         "est": 300, "pairs_as": None, "of": None})
            jobs.append({"kind": "clean", "name": name.replace("__wb_sir0", "__clean"), "seed": s, "cfg": clean_cfg(cfg),
                         "out": os.path.join(RES, f"rev_clean_{machine}"), "est": 300, "pairs_as": None, "of": None})
    with mp.get_context("spawn").Pool(a.workers, maxtasksperchild=1) as pool:
        for msg in pool.imap_unordered(run_one, jobs):
            print(time.strftime("%H:%M:%S"), msg, flush=True)


if __name__ == "__main__":
    main()
