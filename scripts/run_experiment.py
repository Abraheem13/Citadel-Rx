#!/usr/bin/env python
"""Run one configuration (optionally several seeds).

    python scripts/run_experiment.py configs/e2_clean.yaml --set receiver.type=citadel --seeds 0 1 2
    python scripts/run_experiment.py --quick            # smoke test on the laptop
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch  # noqa: E402

# Small per-user MLPs do not benefit from intra-op parallelism; several runs side by side do.
torch.set_num_threads(int(os.environ.get("CITADEL_THREADS", "1")))

from citadel_rx.config import Config  # noqa: E402
from citadel_rx.eval import run_experiment  # noqa: E402


def find_existing(out_dir: str, name: str, seed: int, probe) -> str:
    """A finished record of the same experiment: exact config hash, or (for records written before
    a config option was added) the same non-default settings."""
    import glob
    import json
    def complete(fn: str) -> bool:
        # a run that saves level snapshots is finished only when its snapshot file exists and reads
        # back (the machine may have stopped, or the disk filled, while the snapshots were written)
        if not probe.run.save_params:
            return True
        npz = fn.replace(".json", ".levels.npz")
        if not os.path.exists(npz):
            return False
        try:
            import json
            import zipfile
            n_levels = len(json.load(open(fn)).get("self_disp") or [None])   # one entry per level
            with zipfile.ZipFile(npz) as z:
                names = [n for n in z.namelist() if n.startswith("level")]
                # every level must be there (a write cut short can leave a readable file with fewer)
                if z.testzip() is not None or sorted(names) != [f"level{k + 1}.npy" for k in range(n_levels)]:
                    raise ValueError("bad snapshot file")
            return True
        except Exception:
            print(f"   (snapshot file {os.path.basename(npz)} is damaged: removed, the run is redone)")
            try:
                os.remove(npz)
            except OSError:
                pass
            return False

    exact = os.path.join(out_dir, f"{name}_s{seed}_{probe.hash()}.json")
    if os.path.exists(exact):
        try:
            json.load(open(exact))
            if complete(exact):
                return exact
        except Exception:   # truncated record from an interrupted run: run it again
            pass
    for fn in glob.glob(os.path.join(out_dir, f"{name}_s{seed}_*.json")):
        try:
            rec = json.load(open(fn))
        except Exception:
            continue
        if rec.get("seed") == seed and probe.matches_record(rec.get("config", {})) and complete(fn):
            return fn
    return ""


def claimed_elsewhere(name: str, seed: int) -> str:
    """configs/claims.json lists runs that other machines have taken over (the helper cloud machine and
    the pool machines of the second campaign); until a claim expires, the other machines skip those
    runs, then run whatever is still missing. "dropped" runs are left out of the plan for everyone."""
    import datetime as dt
    import json
    me = os.environ.get("CITADEL_MACHINE", "")
    fn = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "claims.json")
    if not me or not os.path.exists(fn):
        return ""
    try:
        c = json.load(open(fn))
        if seed in c.get("dropped", {}).get(name, []):
            return "nobody (dropped from the plan)"
        owners = dict(c.get("owners", {}))
        if c.get("owner"):
            owners.setdefault(c["owner"], {"until": c["until"], "runs": c.get("runs", {})})
        now = dt.datetime.now(dt.timezone.utc)
        for who, o in owners.items():
            if who == me or now >= dt.datetime.fromisoformat(o["until"]):
                continue
            if seed in o.get("runs", {}).get(name, []):
                return who
        return ""
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?", default=None)
    ap.add_argument("--set", nargs="*", default=[], help="dotted overrides, e.g. attack.sir_db=5")
    ap.add_argument("--seeds", nargs="*", type=int, default=None)
    ap.add_argument("--quick", action="store_true", help="tiny settings for a smoke test")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-run even if the record already exists")
    args = ap.parse_args()

    cfg = Config.from_yaml(args.config, args.set) if args.config else Config()
    if not args.config:
        for ov in args.set:
            cfg.set(ov)
    if args.quick:
        cfg.frame.n_blocks = min(cfg.frame.n_blocks, 12)
        cfg.frame.data_bits = min(cfg.frame.data_bits, 4000)
        cfg.receiver.epochs = min(cfg.receiver.epochs, 30)
        cfg.receiver.pretrain_epochs = min(cfg.receiver.pretrain_epochs, 30)
        cfg.receiver.meta_epochs = min(cfg.receiver.meta_epochs, 20)
        cfg.citadel.fast_steps = min(cfg.citadel.fast_steps, 30)
        cfg.citadel.periods = [1, 2, 4][: cfg.citadel.levels]
        cfg.attack.pgd_steps = min(cfg.attack.pgd_steps, 3)
        cfg.attack.start_block, cfg.attack.end_block = 4, 8
        cfg.run.name = cfg.run.name + "_quick"
        cfg.run.log_every = 1
    seeds = args.seeds if args.seeds is not None else cfg.run.seeds
    for s in seeds:
        # resume support: a run is identified by (name, seed, config hash); skip finished ones
        import copy
        probe = copy.deepcopy(cfg)
        probe.channel.seed = s
        existing = find_existing(cfg.run.out_dir, cfg.run.name, s, probe)
        if existing and not args.force and not args.no_save:
            print(f"== {cfg.run.name} seed {s}: exists, skipped ({existing})")
            continue
        owner = claimed_elsewhere(cfg.run.name, s)
        if owner and not args.force:
            print(f"== {cfg.run.name} seed {s}: taken over by the {owner} machine (configs/claims.json), skipped")
            continue
        rec = run_experiment(cfg, seed=s, save=not args.no_save, verbose=not args.quiet)
        summ = rec["summary"]
        print(f"== {cfg.run.name} seed {s}: ser_mean={summ['ser_mean']:.4f} "
              + " ".join(f"{k}={v:.4f}" for k, v in summ.items() if k.startswith("ser_") and isinstance(v, float) and k != "ser_mean"))


if __name__ == "__main__":
    main()
