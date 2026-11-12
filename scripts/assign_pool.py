#!/usr/bin/env python
"""Campaign 5: hand the second campaign's unfinished runs to K pool machines.

The second campaign's queues (scripts/revision_fast.py, campaigns 2 and 3) are longer than the time
left on the machines that hold them, so the runs that are neither finished nor claimed by the
helper machine are split over K further cloud machines ("pool1" ... "poolK"):
  * a run whose record exists in results/ (this checkout, or the extra folders given) is left out;
  * every distinct run (attacked run or clean twin, identified by its resolved name and seed) is
    assigned once;
  * an attacked run is paired with a clean twin from its own machine (scripts/revision_numbers.py),
    so every pool machine runs its own twins (results/rev_clean_poolK), and all runs of one seed and
    one receiver go to the same machine: a twin is shared only by runs of the same receiver and seed,
    so it is computed once there, and the level snapshots that the paired displacement needs (P4, B5)
    are on the machine that uses them;
  * the groups are balanced by an estimated cost (longest first onto the least loaded machine).
The assignment is written to configs/pool_assign.json and claimed in configs/claims.json, so that the
machines that held these runs skip them (they read the claims before every run, after their next git
pull) until the claims expire. Nothing about a run's settings changes: names, folders and seeds stay
those of the campaign that defined it; only the clean twins go to results/rev_clean_poolK.

    python scripts/assign_pool.py --pools 5 --until 2026-11-07T20:00:00+00:00 --extra /home/user/cloudrun/results
    # later: give new groups to one more machine, keeping the assignment of the others
    python scripts/assign_pool.py --names pool6 --groups cloudw:D4s cloudw:P6s --merge --until 2026-11-07T20:00:00+00:00
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import revision_fast as rf  # noqa: E402

POOL_GROUPS = {("cloud", "B5"), ("cloud", "P4"), ("cloud", "P3refdeg"), ("cloud", "B2"), ("cloud", "P1"),
               ("cloudx", "D23"), ("cloudy", "H3v"), ("cloudz", "D8"),
               ("windows", "P3adapt"), ("windows", "P3phys"), ("windows", "B1"), ("windows", "P3know"),
               ("windows", "B3"), ("windows", "P3deny"), ("windows", "H7")}
BASE_MIN = {"citadel": 22, "meta_deepsic": 15, "lmmse": 2, "lmmse_robust": 2}   # unloaded core, 100 blocks; others 9


def cost(job, ov) -> float:
    rx = next((o.split("=", 1)[1] for o in ov if o.startswith("receiver.type=")), "online_deepsic")
    c = BASE_MIN.get(rx, 9.0)
    if "receiver.backbone=joint" in ov:
        c *= 1.5 if rx == "citadel" else 2.5
    if job.clean_twin:
        return c
    blocks = next((int(o.split("=")[1]) for o in ov if o.startswith("frame.n_blocks=")), 100)
    c *= blocks / 100
    name = job.name
    for key, m in (("unroll50", 4), ("pgd100", 3), ("strongest", 3), ("unroll10", 1.5), ("softgate", 1.5), ("_query", 2),
                   ("pgd20", 2.5), ("_a4_", 1.5), ("__phys", 1.3)):
        if key in name:
            c *= m
            break
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", type=int, default=5)
    ap.add_argument("--until", required=True, help="claims expire then (ISO time, UTC)")
    ap.add_argument("--extra", nargs="*", default=[], help="further results folders to look for finished runs in")
    ap.add_argument("--names", nargs="*", default=None, help="pool machine names (default pool1 ... poolK)")
    ap.add_argument("--groups", nargs="*", default=None, help="shard:group pairs to assign (default: POOL_GROUPS)")
    ap.add_argument("--merge", action="store_true", help="keep the existing assignment of the other pool machines")
    args = ap.parse_args()
    groups = {tuple(g.split(":")) for g in args.groups} if args.groups else POOL_GROUPS
    roots = [os.path.join(ROOT, "results")] + args.extra
    claims = json.load(open(os.path.join(ROOT, "configs", "claims.json")))
    helper = claims.get("runs", {})
    dropped = claims.get("dropped", {})
    fzc, fzb = json.load(open(rf.FZ_CIT)), json.load(open(rf.FZ_BASE))

    def exists(out, name, seed):
        return any(glob.glob(os.path.join(r, out, f"{name}_s{seed}_*.json")) for r in roots)

    chunks = collections.OrderedDict()   # (seed, receiver) -> list of (lid, seed, resolved name or None, cost)
    seen = set()
    n_done = n_helper = 0
    for j in rf.rev2_jobs() + rf.rev2x_jobs():
        if (j.shard, j.group) not in groups:
            continue
        for s in j.seeds:
            try:
                (out, name, _), ov = rf.resolve(j, s, fzc, fzb)
            except Exception:   # needs a feature freeze that is not there yet (abstain v3, second backbone)
                out, name, ov = j.out, (None if j.clean_twin else j.name), list(j.ov)
            rx = next((o.split("=", 1)[1] for o in j.ov if o.startswith("receiver.type=")), "?")
            if name is not None:
                if (name, s) in seen:
                    continue
                seen.add((name, s))
                if s in dropped.get(name, []):
                    continue
                if not j.clean_twin and s in helper.get(name, []):
                    n_helper += 1
                    continue
                if not j.clean_twin and exists(out, name, s):
                    n_done += 1
                    continue
            chunks.setdefault((s, rx), []).append((j.lid, s, name, cost(j, ov)))
    pools = args.names or [f"pool{i}" for i in range(1, args.pools + 1)]
    load = {p: 0.0 for p in pools}
    assign = {p: [] for p in pools}
    for key, runs in sorted(chunks.items(), key=lambda kv: -sum(r[3] for r in kv[1])):
        p = min(pools, key=lambda q: load[q])
        assign[p] += runs
        load[p] += sum(r[3] for r in runs)
    for p in pools:   # longest runs first on every machine
        assign[p].sort(key=lambda r: -r[3])
    out = {"note": "written by scripts/assign_pool.py; read by scripts/revision_fast.py --campaign 5",
           "assign": {p: [[r[0], r[1]] for r in v] for p, v in assign.items()},
           "estimated_core_minutes": {p: round(v) for p, v in load.items()}}
    if args.merge and os.path.exists(rf.POOL_ASSIGN):
        old = json.load(open(rf.POOL_ASSIGN))
        old["assign"].update(out["assign"])
        old["estimated_core_minutes"].update(out["estimated_core_minutes"])
        out = old
    json.dump(out, open(rf.POOL_ASSIGN, "w"), indent=1)
    owners = claims.setdefault("owners", {})
    for p, v in assign.items():
        runs = {}
        for lid, s, name, _ in v:
            if name is not None:
                runs.setdefault(name, []).append(s)
        owners[p] = {"until": args.until, "runs": runs}
    json.dump(claims, open(os.path.join(ROOT, "configs", "claims.json"), "w"), indent=1)
    per_group = collections.Counter(lid.split(":")[0] if lid.startswith("twin:") else "run" for v in chunks.values()
                                    for lid, *_ in v)
    print(f"{sum(len(v) for v in assign.values())} runs assigned ({n_done} already done, {n_helper} with the helper):",
          dict(per_group))
    for p in pools:
        print(f"  {p}: {len(assign[p])} runs, ~{load[p] / 60:.1f} core-hours (~{load[p] / 60 / 4:.1f} h on 4 cores)")


if __name__ == "__main__":
    main()
