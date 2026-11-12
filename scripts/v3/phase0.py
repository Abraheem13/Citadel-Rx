#!/usr/bin/env python
"""Phase 0 of the v3 campaign (docs/ROADMAP_9of10.md): machine probe, unit tests, reproduction of
stored records, and a throughput benchmark that decides how later phases are scheduled.

Run from the repository root inside the environment made by scripts/v3/setup_env.py:

    python scripts/v3/phase0.py                     # every step, about 1 to 1.5 hours
    python scripts/v3/phase0.py --steps bench       # one step again (env, tests, repro, bench)

Outputs (commit and push them afterwards; see the phase instructions):
    results/v3/phase0/env_<machine>.json      hardware and software of this machine
    results/v3/phase0/tests_<machine>.txt     pytest output
    results/v3/phase0/repro/*.json            the re-run reference records
    results/v3/phase0/repro_<machine>.json    block-by-block comparison with the stored records
    results/v3/phase0/bench/*.json            short benchmark runs
    results/v3/phase0/bench_<machine>.json    throughput per (device, parallel runs) and the choice
    logs/v3/phase0_<machine>.log              console output

Reproduction targets. Clean twin and plain white-box A1 at SIR 0 dB, seed 10, of the frozen Citadel-Rx
configuration, both run on the x86 Linux machine pool4. Four x86 Linux machines (cloud, pool4, pool13,
pool27) produced the clean record bit for bit across four code versions; the MacBook's records differ.
A Windows machine with newer numerical libraries may differ in the last bits; the comparison measures
by how much, which decides whether new results may be paired only with twins from this machine (the
rule of the campaign in any case) and whether the old records stay comparable.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
import time
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "results", "v3", "phase0")
RUN = os.path.join(ROOT, "scripts", "run_experiment.py")
REF_CLEAN = os.path.join(ROOT, "results", "rev_clean_pool4", "clean_0b811be896_s10_33981e132fc1.json")
REF_A1 = os.path.join(ROOT, "results", "rev2_peruser", "h7_citadel__a1_s10_3b97b1b5bb7f.json")
COMPARE_KEYS = ("ser", "gamma", "pass_nn", "pass_mm", "eta", "attacked")


class Tee:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, "a", encoding="utf-8")

    def __call__(self, msg: str = "") -> None:
        print(msg, flush=True)
        self.f.write(msg + "\n")
        self.f.flush()


def child_env(machine: str, threads: int = 1) -> Dict[str, str]:
    env = dict(os.environ)
    env.update(CITADEL_MACHINE=machine, CITADEL_THREADS=str(threads), OMP_NUM_THREADS=str(threads),
               MKL_NUM_THREADS=str(threads), PYTHONUTF8="1")
    env.pop("CITADEL_PRETRAIN_CACHE", None)   # every timing and reproduction run pre-trains itself
    return env


def write_cfg(record_path: str, dest: str) -> str:
    """The full configuration of a stored record as a YAML file run_experiment.py can read (options added
    to the code after the record was written take their defaults, as in Config.matches_record)."""
    import yaml
    from citadel_rx.config import Config
    cfg = Config.from_dict(json.load(open(record_path))["config"]).to_dict()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=True)
    return dest


def launch(cfg_yaml: str, seed: int, overrides: List[str], machine: str, log_path: str) -> subprocess.Popen:
    cmd = [sys.executable, RUN, cfg_yaml, "--quiet", "--force", "--seeds", str(seed), "--set", *overrides]
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    return subprocess.Popen(cmd, cwd=ROOT, env=child_env(machine), stdout=open(log_path, "w"), stderr=subprocess.STDOUT)


def newest(folder: str, name: str, seed: int) -> Optional[str]:
    import glob
    fs = glob.glob(os.path.join(folder, f"{name}_s{seed}_*.json"))
    return max(fs, key=os.path.getmtime) if fs else None


# ------------------------------------------------------------------------------------------- steps
def step_env(machine: str, say: Tee) -> dict:
    import torch
    info = {"machine": machine, "time": dt.datetime.now(dt.timezone.utc).isoformat(), "platform": platform.platform(),
            "processor": platform.processor(), "python": sys.version.split()[0], "logical_cpus": os.cpu_count(),
            "torch": torch.__version__, "torch_cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available()}
    try:
        import psutil
        info["physical_cpus"] = psutil.cpu_count(logical=False)
        info["ram_gb"] = round(psutil.virtual_memory().total / 2 ** 30, 1)
        info["disk_free_gb"] = round(psutil.disk_usage(ROOT).free / 2 ** 30, 1)
    except Exception as e:   # noqa: BLE001
        info["psutil_error"] = str(e)
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        info.update(gpu=p.name, gpu_mem_gb=round(p.total_memory / 2 ** 30, 1), capability=list(torch.cuda.get_device_capability(0)))
    import numpy
    import scipy
    info.update(numpy=numpy.__version__, scipy=scipy.__version__)
    try:
        info["git_commit"] = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:   # noqa: BLE001
        info["git_commit"] = "unknown"
    json.dump(info, open(os.path.join(OUT, f"env_{machine}.json"), "w"), indent=1)
    for k, v in info.items():
        say(f"   {k:16s} {v}")
    return info


def step_tests(machine: str, say: Tee) -> bool:
    path = os.path.join(OUT, f"tests_{machine}.txt")
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                       env=child_env(machine), capture_output=True, text=True)
    open(path, "w", encoding="utf-8").write(r.stdout + r.stderr)
    tail = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    say(f"   pytest: {tail}   ({(time.time() - t0) / 60:.1f} min, exit code {r.returncode})")
    return r.returncode == 0


def compare(new: dict, ref: dict) -> dict:
    nb, rb = new["blocks"], ref["blocks"]
    out = {"n_blocks": [len(nb), len(rb)], "ser_mean": [new["summary"]["ser_mean"], ref["summary"]["ser_mean"]],
           "window": [new["summary"].get("attack_window"), ref["summary"].get("attack_window")]}
    for k in COMPARE_KEYS:
        a = [b.get(k) for b in nb]
        b = [x.get(k) for x in rb]
        same = [x == y for x, y in zip(a, b)]
        num = [abs(x - y) for x, y in zip(a, b) if isinstance(x, (int, float)) and isinstance(y, (int, float))
               and not isinstance(x, bool)]
        out[k] = {"identical_blocks": int(sum(same)), "first_difference": next((i for i, s in enumerate(same) if not s), None),
                  "max_abs_diff": max(num) if num else None}
    out["bit_identical"] = all(out[k]["identical_blocks"] == len(rb) for k in ("ser", "gamma")) and len(nb) == len(rb)
    return out


def step_repro(machine: str, say: Tee) -> dict:
    folder = os.path.join(OUT, "repro")
    jobs = []
    for tag, ref in (("clean", REF_CLEAN), ("a1", REF_A1)):
        y = write_cfg(ref, os.path.join(OUT, "cfg", f"repro_{tag}.yaml"))
        name = f"p0_repro_{tag}"
        p = launch(y, 10, [f"run.name={name}", f"run.out_dir={folder}", "run.device=cpu"], machine,
                   os.path.join(ROOT, "logs", "v3", f"phase0_repro_{tag}_{machine}.log"))
        jobs.append((tag, ref, name, p))
        say(f"   started {name} (reference {os.path.relpath(ref, ROOT)})")
    t0 = time.time()
    res = {}
    for tag, ref, name, p in jobs:
        code = p.wait()
        f = newest(folder, name, 10)
        if code != 0 or f is None:
            say(f"!! {name} failed (exit {code}); see logs/v3/phase0_repro_{tag}_{machine}.log")
            res[tag] = {"error": f"exit {code}"}
            continue
        c = compare(json.load(open(f)), json.load(open(ref)))
        c["record"] = os.path.relpath(f, ROOT)
        c["reference"] = os.path.relpath(ref, ROOT)
        res[tag] = c
        say(f"   {tag:5s} bit-identical to the stored record: {c['bit_identical']}; identical SER on "
            f"{c['ser']['identical_blocks']}/{c['n_blocks'][1]} blocks, max |dSER| {c['ser']['max_abs_diff']}, "
            f"mean SER {c['ser_mean'][0]:.5f} vs {c['ser_mean'][1]:.5f}")
    res["minutes"] = round((time.time() - t0) / 60, 1)
    json.dump(res, open(os.path.join(OUT, f"repro_{machine}.json"), "w"), indent=1)
    return res


def bench_overrides(name: str, device: str, attacked: bool) -> List[str]:
    ov = [f"run.name={name}", f"run.out_dir={os.path.join(OUT, 'bench')}", f"run.device={device}", "frame.n_blocks=8"]
    if attacked:
        ov += ["attack.type=a1", "attack.sir_db=0", "attack.start_mode=fixed", "attack.start_block=2", "attack.end_block=8"]
    else:
        ov += ["attack.type=none"]
    return ov


def full_run_minutes(rec: dict) -> float:
    """Wall time of a full 100-block attacked run (40-block window) predicted from a short run."""
    s = rec["summary"]
    t_att = [b["t_attack"] for b in rec["blocks"] if b.get("attacked")]
    att = (sum(t_att) / len(t_att)) if t_att else 0.0
    return (s["pretrain_time_s"] + 100 * s["mean_t_rx_s"] + 40 * att) / 60


def step_bench(machine: str, say: Tee, env_info: dict) -> dict:
    import torch
    y = write_cfg(REF_CLEAN, os.path.join(OUT, "cfg", "bench.yaml"))
    folder = os.path.join(OUT, "bench")
    devices = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])
    phys = env_info.get("physical_cpus") or max(1, (os.cpu_count() or 2) // 2)
    logical = os.cpu_count() or phys
    levels = sorted({1, max(1, phys // 2), phys, logical})
    plan = [(d, n) for d in devices for n in (levels if d == "cpu" else sorted({1, 4, max(1, phys // 2)}))]
    rows = []
    for device, n in plan:
        say(f"   {device}: {n} parallel run(s) ...")
        t0 = time.time()
        procs = []
        for i in range(n):
            name = f"p0_bench_{device}_n{n}_{i}"
            procs.append((name, 100 + i, launch(y, 100 + i, bench_overrides(name, device, attacked=True), machine,
                                                os.path.join(ROOT, "logs", "v3", "bench", f"{name}.log"))))
        recs, failed = [], 0
        for name, seed, p in procs:
            if p.wait() != 0:
                failed += 1
                continue
            f = newest(folder, name, seed)
            if f:
                recs.append(json.load(open(f)))
        wall = (time.time() - t0) / 60
        if not recs:
            say(f"!! {device} x{n}: every run failed (see logs/v3/bench)")
            rows.append({"device": device, "parallel": n, "failed": failed})
            continue
        per_run = sum(full_run_minutes(r) for r in recs) / len(recs)
        row = {"device": device, "parallel": n, "failed": failed, "wall_min": round(wall, 2),
               "pretrain_s": round(sum(r["summary"]["pretrain_time_s"] for r in recs) / len(recs), 1),
               "t_rx_s": round(sum(r["summary"]["mean_t_rx_s"] for r in recs) / len(recs), 2),
               "full_run_min": round(per_run, 1), "runs_per_hour": round(len(recs) * 60 / per_run, 2)}
        rows.append(row)
        say(f"      pre-train {row['pretrain_s']} s, {row['t_rx_s']} s per block, a full 100-block attacked run "
            f"about {row['full_run_min']} min, throughput {row['runs_per_hour']} runs/hour, failed {failed}")
    ok = [r for r in rows if r.get("runs_per_hour") and not r["failed"]]
    best = max(ok, key=lambda r: r["runs_per_hour"]) if ok else None
    res = {"machine": machine, "rows": rows, "choice": best,
           "note": "throughput = parallel runs x 60 / predicted minutes of one full 100-block attacked run"}
    json.dump(res, open(os.path.join(OUT, f"bench_{machine}.json"), "w"), indent=1)
    if best:
        say(f"   best: device {best['device']} with {best['parallel']} parallel runs, about {best['runs_per_hour']} full runs per hour")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="*", default=["env", "tests", "repro", "bench"],
                    choices=["env", "tests", "repro", "bench"])
    ap.add_argument("--machine", default=os.environ.get("CITADEL_MACHINE", "ws5080"))
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    say = Tee(os.path.join(ROOT, "logs", "v3", f"phase0_{a.machine}.log"))
    say(f"== Phase 0 on {a.machine}, {dt.datetime.now():%Y-%m-%d %H:%M}, steps {a.steps}")
    status = {}
    env_info = {}
    if "env" in a.steps or "bench" in a.steps:
        say("== 1. machine")
        env_info = step_env(a.machine, say)
    if "tests" in a.steps:
        say("== 2. unit tests (a few minutes)")
        status["tests"] = step_tests(a.machine, say)
    if "repro" in a.steps:
        say("== 3. reproduction of two stored records (about 15 minutes)")
        r = step_repro(a.machine, say)
        status["repro"] = all("error" not in v for k, v in r.items() if isinstance(v, dict))
    if "bench" in a.steps:
        say("== 4. throughput benchmark (about 30-45 minutes)")
        b = step_bench(a.machine, say, env_info)
        status["bench"] = b["choice"] is not None
    say("== summary: " + ", ".join(f"{k} {'OK' if v else 'FAILED'}" for k, v in status.items()))
    say("   next: commit and push results/v3/phase0 and logs/v3 (see docs/v3/PHASE0.md)")
    return 0 if all(status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
