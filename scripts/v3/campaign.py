#!/usr/bin/env python
"""Run one phase of the v3 campaign (docs/ROADMAP_9of10.md) on this machine. Resumable: a finished run
(same name, seed and settings) is skipped, so after any interruption the same command continues.

    python scripts/v3/campaign.py --phase 1 --dry                # list the runs and the estimated time
    python scripts/v3/campaign.py --phase 1 --workers 12         # run them
    python scripts/v3/campaign.py --phase 1 --only 1a 1b         # only these experiment groups

Attacked runs go to results/v3/p<phase>/, clean twins to results/v3/clean_<machine>/ (a twin is shared by
every attacked run of the same settings and seed, and it is computed once). Each run's console output is
in logs/v3/p<phase>/, one line per finished run in logs/v3/p<phase>_<machine>_tasks.jsonl.
With --push-every M the results are committed and pushed every M minutes (git must be able to push).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from citadel_rx.config import Config  # noqa: E402
from run_experiment import find_existing  # noqa: E402
from phases import PHASES, Job  # noqa: E402

BASE_CFG = os.path.join(ROOT, "configs", "e3_a1_defence.yaml")
FZ_CIT = os.path.join(ROOT, "configs", "revision_frozen_citadel.json")
FZ_BASE = os.path.join(ROOT, "configs", "revision_frozen_baselines.json")
RUN = os.path.join(ROOT, "scripts", "run_experiment.py")


def resolve_ov(ov: List[str]) -> List[str]:
    fz_cit, fz_base = json.load(open(FZ_CIT)), json.load(open(FZ_BASE))
    out: List[str] = []
    for o in ov:
        if o == "@CIT":
            out += fz_cit["citadel_overrides"]
        elif o.startswith("@BASE:"):
            out += fz_base[o[6:]]["overrides"]
        else:
            out.append(o)
    # later entries win (Config.set applies them in order), so an explicit override after @BASE stands
    return out


def tasks(phase: int, machine: str, only: Optional[List[str]], seeds: Optional[List[int]]) -> List[dict]:
    """Every (run, seed) of the phase, attacked runs before their twins, ordered by priority; duplicates removed."""
    out, seen = [], set()
    for j in sorted(PHASES[phase](), key=lambda j: j.priority):
        if only and j.group not in only:
            continue
        ov = resolve_ov(j.ov)
        Config.from_yaml(BASE_CFG, ov)          # raises on an unknown or malformed setting before anything runs
        variants = [(j.name, ov, os.path.join("results", "v3", f"p{phase}"))]
        if j.twin:
            cov = [o for o in ov if not o.startswith("attack.")] + ["attack.type=none"]
            cfg = Config.from_yaml(BASE_CFG, cov)
            nd = {k: v for k, v in cfg.nondefault().items() if not k.startswith("run.") or k == "run.save_params"}
            tname = "clean_" + hashlib.sha1(json.dumps(nd, sort_keys=True, default=str).encode()).hexdigest()[:10]
            variants.append((tname, cov, os.path.join("results", "v3", f"clean_{machine}")))
        for s in (seeds or j.seeds):
            if seeds and s not in j.seeds:
                continue
            for name, o, folder in variants:
                key = (folder, name, s)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"group": j.group, "name": name, "seed": s, "ov": o, "out": folder, "priority": j.priority,
                            "twin": name.startswith("clean_")})
    return out


def is_done(t: dict) -> str:
    cfg = Config.from_yaml(BASE_CFG, t["ov"] + [f"run.name={t['name']}", f"run.out_dir={t['out']}"])
    cfg.channel.seed = t["seed"]
    return find_existing(os.path.join(ROOT, t["out"]), t["name"], t["seed"], cfg)


class Runner:
    def __init__(self, phase: int, machine: str, workers: int, device: str, push_every: float, cache_gb: float):
        self.phase, self.machine, self.workers, self.device = phase, machine, workers, device
        self.push_every, self.cache_gb = push_every, cache_gb
        self.lock = threading.Lock()
        self.done = self.failed = 0
        self.t0 = time.time()
        self.last_push = time.time()
        self.logdir = os.path.join(ROOT, "logs", "v3", f"p{phase}")
        os.makedirs(self.logdir, exist_ok=True)
        self.tasklog = open(os.path.join(ROOT, "logs", "v3", f"p{phase}_{machine}_tasks.jsonl"), "a")

    def env(self) -> Dict[str, str]:
        e = dict(os.environ)
        e.update(CITADEL_MACHINE=self.machine, CITADEL_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                 PYTHONUTF8="1", CITADEL_PRETRAIN_CACHE=os.path.join(ROOT, "cache", "pretrain"),
                 CITADEL_PRETRAIN_CACHE_GB=str(self.cache_gb))
        return e

    def run_one(self, t: dict, total: int) -> None:
        cmd = [sys.executable, RUN, BASE_CFG, "--quiet", "--seeds", str(t["seed"]), "--set", *t["ov"],
               f"run.name={t['name']}", f"run.out_dir={t['out']}", f"run.device={self.device}"]
        log = os.path.join(self.logdir, f"{t['name']}_s{t['seed']}.log")
        t1 = time.time()
        with open(log, "w") as fh:
            code = subprocess.call(cmd, cwd=ROOT, env=self.env(), stdout=fh, stderr=subprocess.STDOUT)
        minutes = (time.time() - t1) / 60
        with self.lock:
            self.done += code == 0
            self.failed += code != 0
            n = self.done + self.failed
            el = (time.time() - self.t0) / 3600
            eta = el / n * (total - n) if n else 0
            print(f"[{dt.datetime.now():%H:%M}] {n}/{total} {'OK  ' if code == 0 else 'FAIL'} {t['group']} {t['name']} "
                  f"s{t['seed']} {minutes:.0f} min | {el:.1f} h elapsed, ~{eta:.1f} h left"
                  + ("" if code == 0 else f"  -> see {os.path.relpath(log, ROOT)}"), flush=True)
            self.tasklog.write(json.dumps({"time": dt.datetime.now().isoformat(), "group": t["group"], "name": t["name"],
                                           "seed": t["seed"], "ok": code == 0, "minutes": round(minutes, 2),
                                           "machine": self.machine}) + "\n")
            self.tasklog.flush()
            if self.push_every > 0 and time.time() - self.last_push > self.push_every * 60:
                self.last_push = time.time()
                push(self.phase, self.machine)

    def run(self, todo: List[dict]) -> int:
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            list(ex.map(lambda t: self.run_one(t, len(todo)), todo))
        return self.failed


def push(phase: int, machine: str) -> None:
    paths = [os.path.join("results", "v3"), os.path.join("logs", "v3")]
    subprocess.call(["git", "add", *paths], cwd=ROOT)
    if subprocess.call(["git", "diff", "--cached", "--quiet"], cwd=ROOT) == 0:
        return
    subprocess.call(["git", "commit", "-q", "-m", f"Phase {phase} results ({machine}, {dt.datetime.now():%Y-%m-%d %H:%M})"], cwd=ROOT)
    subprocess.call(["git", "pull", "-q", "--rebase", "origin", "main"], cwd=ROOT)
    ok = subprocess.call(["git", "push", "-q", "origin", "HEAD:main"], cwd=ROOT) == 0
    print(f"   push {'done' if ok else 'FAILED (results are kept here; push them by hand)'}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", type=int, required=True, choices=sorted(PHASES))
    ap.add_argument("--workers", type=int, default=0, help="parallel runs (default: from the Phase 0 benchmark, else cores - 2)")
    ap.add_argument("--device", default="", help="cpu or cuda (default: from the Phase 0 benchmark, else cpu)")
    ap.add_argument("--machine", default=os.environ.get("CITADEL_MACHINE", "ws5080"))
    ap.add_argument("--only", nargs="*", default=None, help="experiment groups, e.g. 1a 1b")
    ap.add_argument("--seeds", nargs="*", type=int, default=None, help="only these seeds (of each job's own list)")
    ap.add_argument("--push-every", type=float, default=0.0, help="minutes between automatic commits and pushes (0: never)")
    ap.add_argument("--cache-gb", type=float, default=5.0, help="size cap of the pre-training cache")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    bench = os.path.join(ROOT, "results", "v3", "phase0", f"bench_{a.machine}.json")
    choice = (json.load(open(bench)).get("choice") or {}) if os.path.exists(bench) else {}
    workers = a.workers or choice.get("parallel") or max(1, (os.cpu_count() or 4) - 2)
    device = a.device or choice.get("device") or "cpu"
    allt = tasks(a.phase, a.machine, a.only, a.seeds)
    todo = [t for t in allt if not is_done(t)]
    groups: Dict[str, Tuple[int, int]] = {}
    for t in allt:
        d, n = groups.get(t["group"], (0, 0))
        groups[t["group"]] = (d + (t not in todo), n + 1)
    print(f"== Phase {a.phase} on {a.machine}: {len(allt)} runs ({len(allt) - len(todo)} done, {len(todo)} to run), "
          f"{workers} parallel on {device}")
    for g, (d, n) in sorted(groups.items()):
        print(f"   group {g}: {d}/{n} done")
    if choice.get("full_run_min"):
        print(f"   rough estimate: {len(todo) * choice['full_run_min'] / max(workers, 1) / 60:.1f} h "
              f"(one attacked 100-block run ~{choice['full_run_min']} min at this parallelism; attacks with exact gates or"
              f" 16-QAM take several times longer)")
    if a.dry:
        for t in todo:
            print(f"   {t['group']:3s} {t['name']} s{t['seed']}")
        return 0
    failed = Runner(a.phase, a.machine, workers, device, a.push_every, a.cache_gb).run(todo)
    print(f"== Phase {a.phase} finished: {len(todo) - failed} runs OK, {failed} failed"
          + ("" if not failed else " (run the same command again to retry them)"))
    if a.push_every > 0:
        push(a.phase, a.machine)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
