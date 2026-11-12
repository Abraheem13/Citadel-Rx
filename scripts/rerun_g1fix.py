#!/usr/bin/env python
"""Re-run every attack that uses the soft-gate surrogate, after the fix of its G1 scale.

The soft G1 term of the attacker (pilot_poisoning.Attacker._g1_soft) averaged the squared residual over
the 2N real coordinates of the received vector, half the per-antenna scale of the receiver's G1
(gates/physics.model_residual) for complex modulation. The soft-gate objective is used by every attack
with attack.soft_gate=true and by every A4 and A3* attack (pilot_poisoning.py, `use_soft`), whenever
the victim has gates. Those records are re-run here with the fixed code; each new record takes its
settings from the record it replaces, so the fixed line is the only difference (docs/G1_SOFT_FIX.md).

Families (records are found automatically; receivers with gates only):

  softgate  results/rev_p3_adaptive   soft-gate and combined attacks           own clean twins
  a4        results/rev_p3_refdeg, rev2_abstain_v3, rev2_a4_pgd20 (A4)         pairs_as (below)
  a3star    results/rev_p8_drift, rev2_drift_guard, rev2_drift_long (A3*)       own clean twins,
                                                                                  with level snapshots

New records go to results/<folder>_g1fix. "Own clean twins": the clean twin of each attacked run is
run on the same machine (results/rev_clean_<machine>). "pairs_as": the attacked run is paired with the
existing clean twin of the machine that ran the replaced record; this is valid because every cloud
container gives bit-identical runs (checked: the clean twins of seeds 10-14 re-run on pool12 and pool13
equal those of cloud, pool1-pool5 block for block). Each machine that uses pairs_as first repeats that
check on its own hardware (`probe`, results/g1fix_probe/<machine>.json); revision_numbers.py honours
pairs_as only for a machine whose probe found identical runs.

    CITADEL_MACHINE=pool14 python scripts/rerun_g1fix.py --family a4 --shard 1/4 --workers 4
    CITADEL_MACHINE=pool18 python scripts/rerun_g1fix.py --family a3star --seeds 10 --workers 4
    python scripts/rerun_g1fix.py --family a4 --shard 1/4 --dry
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
RES = os.path.join(ROOT, "results")

FAMILIES = {
    "softgate": (["rev_p3_adaptive"], "own"),
    "a4": (["rev_p3_refdeg", "rev2_abstain_v3", "rev2_a4_pgd20"], "pairs_as"),
    "a3star": (["rev_p8_drift", "rev2_drift_guard", "rev2_drift_long"], "own"),
}
CLOUD_V1 = {"rev_p4_paired", "rev_p3_refdeg", "rev_cal_citadel", "rev_clean_cloud"}   # as in revision_numbers.machine
PROBE_REF = os.path.join(RES, "rev_clean_cloud")


def affected(r: dict) -> bool:
    """A record whose attacker used the soft-gate objective against a receiver with gates."""
    c = r.get("config", {})
    a = c.get("attack", {})
    if a.get("type", "none") == "none":
        return False
    soft = bool(a.get("soft_gate")) or a.get("type") in ("a4", "a3star")
    return soft and c.get("receiver", {}).get("type") == "citadel" and bool(c.get("citadel", {}).get("gates"))


def machine_of(r: dict, folder: str) -> str:
    if r.get("machine"):
        return r["machine"]
    return "cloud" if folder in CLOUD_V1 else "mac"


def records(folder: str):
    for fn in sorted(glob.glob(os.path.join(RES, folder, "*.json"))):
        try:
            r = json.load(open(fn))
        except Exception:
            continue
        if affected(r):
            yield fn, r


def done(out_dir: str, name: str, seed: int) -> bool:
    for f in glob.glob(os.path.join(out_dir, f"{name}_s{seed}_*.json")):
        try:
            json.load(open(f))
            return True
        except Exception:
            pass
    return False


def clean_cfg(cfg: dict) -> dict:
    c = json.loads(json.dumps(cfg))
    c["attack"]["type"] = "none"
    return c


def mkey(cfg: dict) -> str:
    return json.dumps({k: v for k, v in cfg.items() if k not in ("attack", "run")}, sort_keys=True)


def plan(family: str, seeds, machine: str, shard, only=None):
    folders, twins = FAMILIES[family]
    if only:   # a subset of the family's folders (to split one seed over several machines)
        folders = [f for f in folders if f in only]
    att, cln = [], {}
    for folder in folders:
        out = os.path.join(RES, folder + "_g1fix") if family != "softgate" else os.path.join(RES, "rev_p3_adaptive_g1fix")
        for fn, r in records(folder):
            if seeds and r["seed"] not in seeds:
                continue
            if family == "softgate" and r["name"] not in ("p3_citadel_strongest__sir0", "p3_citadel_softgate__sir0",
                                                          "p3_citadel_softgate__sir10"):
                continue
            est = float(r.get("summary", {}).get("total_time_s", 1800))
            pairs = machine_of(r, folder) if twins == "pairs_as" else None
            att.append({"kind": "attacked", "name": r["name"], "seed": r["seed"], "cfg": r["config"], "out": out,
                        "est": est, "pairs_as": pairs, "of": os.path.relpath(fn, ROOT)})
            if twins == "own":
                k = (mkey(r["config"]), r["seed"])
                if k not in cln:
                    h = hashlib.sha1(k[0].encode()).hexdigest()[:8]   # one name per clean configuration
                    cln[k] = {"kind": "clean", "name": f"g1fix_twin_b{r['config']['frame']['n_blocks']}_{h}",
                              "seed": r["seed"], "cfg": clean_cfg(r["config"]), "out": os.path.join(RES, f"rev_clean_{machine}"),
                              "est": est / 3, "pairs_as": None, "of": None}
    jobs = att + list(cln.values())
    if shard:   # longest-processing-time-first split of the attacked runs (own twins follow their runs)
        k, n = shard
        if twins == "own":
            raise SystemExit("--shard is for the pairs_as family; split the own-twin families by --seeds")
        loads, parts = [0.0] * n, [[] for _ in range(n)]
        for j in sorted(jobs, key=lambda j: (-j["est"], j["name"], j["seed"])):
            i = loads.index(min(loads))
            parts[i].append(j)
            loads[i] += j["est"]
        jobs = parts[k - 1]
    jobs.sort(key=lambda j: -j["est"])   # longest first
    if twins == "pairs_as":
        jobs.insert(0, {"kind": "probe", "name": "probe", "seed": 10, "est": 600})
    return jobs


def norm_key(cfg: dict) -> str:
    """Settings a clean twin must share (as revision_numbers.mkey): options added to the code after a
    record was written are filled in at their defaults, so records of different code versions compare."""
    from citadel_rx.config import Config
    try:
        cfg = Config.from_dict(cfg).to_dict()
    except KeyError:
        pass
    return mkey(cfg)


def run_probe(machine: str) -> str:
    """Repeat one stored clean run and compare it block for block with the stored cloud runs of the
    same settings and seed (and with the pool13 re-run, which equals them)."""
    from citadel_rx.config import Config
    from citadel_rx.eval import run_experiment
    ref_fn = sorted(glob.glob(os.path.join(RES, "rev_clean_pool13", "g1fix_twin_citadel_s10_*.json")))[0]
    ref = json.load(open(ref_fn))
    key = norm_key(ref["config"])
    cloud = [(f, json.load(open(f))) for f in sorted(glob.glob(os.path.join(PROBE_REF, "*.json")))]
    cloud = [(f, r) for f, r in cloud if r.get("seed") == 10 and norm_key(r["config"]) == key]
    rec = run_experiment(Config.from_dict(ref["config"]), seed=10, save=False, verbose=False)
    keys = ("ser", "gamma", "attacked")
    same = lambda a, b: all([blk.get(k) for blk in a["blocks"]] == [blk.get(k) for blk in b["blocks"]] for k in keys)
    to_ref, to_cloud = same(rec, ref), [same(rec, c) for _, c in cloud]
    out = {"machine": machine, "identical": bool(to_ref and to_cloud and all(to_cloud)),
           "identical_to_pool13_rerun": bool(to_ref), "identical_to_cloud": to_cloud,
           "compared_with": [os.path.relpath(ref_fn, ROOT)] + [os.path.relpath(f, ROOT) for f, _ in cloud],
           "fields": list(keys), "blocks": len(rec["blocks"]), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    os.makedirs(os.path.join(RES, "g1fix_probe"), exist_ok=True)
    json.dump(out, open(os.path.join(RES, "g1fix_probe", f"{machine}.json"), "w"), indent=1)
    return (f"probe: {'IDENTICAL' if out['identical'] else 'MISMATCH'} (pool13 re-run: {to_ref}; "
            f"{sum(to_cloud)}/{len(cloud)} stored cloud record(s) equal)")


def run_one(job):
    import torch
    torch.set_num_threads(1)
    machine = os.environ["CITADEL_MACHINE"]
    if job["kind"] == "probe":
        return run_probe(machine)
    from citadel_rx.config import Config
    from citadel_rx.eval import run_experiment
    if done(job["out"], job["name"], job["seed"]):
        return f"{job['kind']} {job['name']} s{job['seed']}: exists"
    cfg = Config.from_dict(job["cfg"])
    cfg.run.out_dir = job["out"]
    cfg.run.name = job["name"]
    t0 = time.time()
    rec = run_experiment(cfg, seed=job["seed"], save=True, verbose=False)
    if job["pairs_as"] or job["of"]:   # provenance: which record it replaces, which machine's twin it pairs with
        path = rec["path"]
        d = json.load(open(path))
        if job["of"]:
            d["g1fix_of"] = job["of"]
        if job["pairs_as"]:
            d["pairs_as"] = job["pairs_as"]
        tmp = path + ".tmp"
        json.dump(d, open(tmp, "w"))
        os.replace(tmp, path)
    return f"{job['kind']} {job['name']} s{job['seed']}: done in {time.time() - t0:.0f} s"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(FAMILIES), default="softgate")
    ap.add_argument("--seeds", nargs="*", type=int, default=None)
    ap.add_argument("--shard", default=None, help="k/n: the k-th of n balanced parts (pairs_as family)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--probe-only", action="store_true", help="only repeat the stored clean run (pairs_as check)")
    ap.add_argument("--folders", nargs="*", default=None, help="only these folders of the family")
    a = ap.parse_args()
    machine = os.environ.get("CITADEL_MACHINE", "")
    if not machine and not a.dry:
        raise SystemExit("set CITADEL_MACHINE (records name the machine that ran them)")
    shard = tuple(int(x) for x in a.shard.split("/")) if a.shard else None
    os.environ.setdefault("CITADEL_PRETRAIN_CACHE", os.path.join(ROOT, "cache", "pretrain"))
    os.environ["CITADEL_THREADS"] = "1"
    if a.probe_only:
        print(time.strftime("%H:%M:%S"), run_one({"kind": "probe"}), flush=True)
        return
    jobs = plan(a.family, a.seeds, machine or "DRY", shard, a.folders)
    total = sum(j["est"] for j in jobs) / 60
    for j in jobs:
        print(f"{j['kind']:9s} {j['name']:36s} seed {j['seed']:2d}  ~{j['est'] / 60:4.0f} min"
              + (f"  -> {os.path.relpath(j['out'], ROOT)}" if "out" in j else "")
              + (f"  pairs_as {j['pairs_as']}" if j.get("pairs_as") else ""))
    print(f"{len(jobs)} jobs, ~{total:.0f} CPU-min (times of the replaced records)")
    if a.dry:
        return
    with mp.get_context("spawn").Pool(a.workers, maxtasksperchild=1) as pool:
        for msg in pool.imap_unordered(run_one, jobs):
            print(time.strftime("%H:%M:%S"), msg, flush=True)


if __name__ == "__main__":
    main()
