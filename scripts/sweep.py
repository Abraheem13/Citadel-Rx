#!/usr/bin/env python
"""Parameter sweeps for the paper experiments, run as separate processes.

    python scripts/sweep.py e3 --seeds 0 1 2 --workers 4 [--dry]
    python scripts/sweep.py e2 --receivers citadel meta_deepsic --snrs 6 8 10 12
"""
from __future__ import annotations

import argparse
import itertools
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "scripts", "run_experiment.py")

ALL_RX = ["lmmse", "online_deepsic", "meta_deepsic", "drift_deepsic", "medbn_deepsic", "titans_single", "citadel"]


def grid(exp: str, args) -> List[Dict[str, str]]:
    rx = args.receivers or ALL_RX
    jobs = []
    if exp == "e1":
        for r, lin, sir, know in itertools.product(["online_deepsic", "meta_deepsic"], [True, False],
                                                   args.sirs or [-10, -5, 0, 5, 10], ["whitebox", "transfer"]):
            jobs.append({"receiver.type": r, "receiver.pretrain": "false", "channel.linear": str(lin).lower(),
                         "attack.type": "a1", "attack.knowledge": know, "attack.sir_db": str(sir),
                         "run.name": f"e1_{r}_{'lin' if lin else 'nl'}_{know}_sir{sir}"})
    elif exp == "e2":
        for r, snr, fad in itertools.product(rx, args.snrs or [4, 6, 8, 10, 12, 14, 16], ["cosine", "jakes"]):
            jobs.append({"receiver.type": r, "channel.snr_db": str(snr), "channel.fading": fad, "attack.type": "none",
                         "run.name": f"e2_{r}_{fad}_snr{snr}"})
    elif exp in ("e2nl", "e2cost"):  # clean parity where DeepSIC's model-based gains show
        extra = {"channel.linear": "false"} if exp == "e2nl" else {"channel.model": "cost2100"}
        for r, snr in itertools.product(rx, args.snrs or [4, 6, 8, 10, 12, 14, 16]):
            jobs.append({"receiver.type": r, "channel.snr_db": str(snr), "attack.type": "none", **extra,
                         "run.name": f"{exp}_{r}_snr{snr}"})
    elif exp in ("e3nl", "e3cost"):  # A1 defence on the nonlinear / COST2100 channel
        extra = {"channel.linear": "false"} if exp == "e3nl" else {"channel.model": "cost2100"}
        for r, sir in itertools.product(rx, args.sirs or [-10, -5, 0, 5, 10]):
            jobs.append({"receiver.type": r, "attack.type": "a1", "attack.sir_db": str(sir), **extra,
                         "run.name": f"{exp}_{r}_sir{sir}"})
    elif exp == "e3":
        for r, sir, know in itertools.product(rx, args.sirs or [-10, -5, 0, 5, 10], ["whitebox", "transfer"]):
            jobs.append({"receiver.type": r, "attack.type": "a1", "attack.knowledge": know, "attack.sir_db": str(sir),
                         "run.name": f"e3_{r}_{know}_sir{sir}"})
        for r in rx:  # equal-power jamming control
            jobs.append({"receiver.type": r, "attack.type": "data_jam", "attack.sir_db": "0",
                         "run.name": f"e3_{r}_datajam_sir0"})
    elif exp == "e3snr":  # SER-vs-SNR curves with and without attack, for the Delta_dB metric
        for r, snr, atk in itertools.product(rx, args.snrs or [4, 6, 8, 10, 12, 14, 16], ["none", "a1"]):
            jobs.append({"receiver.type": r, "channel.snr_db": str(snr), "attack.type": atk, "attack.sir_db": "0",
                         "run.name": f"e3snr_{r}_{atk}_snr{snr}"})
    elif exp == "e4":
        for r, g3 in itertools.product(["citadel", "meta_deepsic", "online_deepsic"], [True, False]):
            gates = "[g1,g2,g3]" if g3 else "[g1,g2]"
            jobs.append({"receiver.type": r, "citadel.gates": gates, "attack.type": "a2",
                         "run.name": f"e4_{r}_{'g3' if g3 else 'nog3'}"})
    elif exp == "e5":
        for ck in [8, 32, 128]:
            jobs.append({"receiver.type": "citadel", "citadel.periods": f"[1,{max(2, ck // 4)},{ck}]", "attack.type": "a3",
                         "run.save_params": "true", "run.name": f"e5_citadel_CK{ck}"})
            jobs.append({"receiver.type": "citadel", "citadel.periods": f"[1,{max(2, ck // 4)},{ck}]", "attack.type": "none",
                         "run.save_params": "true", "run.name": f"e5_citadel_CK{ck}_clean"})
    elif exp == "e3rel":  # relative G2 slack on the low-SER cells where the absolute slack is loose
        rel = {"receiver.type": "citadel", "citadel.g2_slack_mode": "relative"}
        for sir in args.sirs or [-10, -5, 0, 5, 10]:
            jobs.append({**rel, "channel.model": "cost2100", "attack.type": "a1", "attack.sir_db": str(sir),
                         "run.name": f"e3rel_cost_citadel_sir{sir}"})
        jobs.append({**rel, "channel.model": "cost2100", "attack.type": "none", "run.name": "e3rel_cost_citadel_clean"})
        for snr, atk in itertools.product(args.snrs or [10, 12, 14, 16], ["none", "a1"]):
            jobs.append({**rel, "channel.snr_db": str(snr), "attack.type": atk, "attack.sir_db": "0",
                         "run.name": f"e3rel_snr_citadel_{atk}_snr{snr}"})
        for sir in args.sirs or [-10, -5, 0, 5, 10]:  # sanity: the linear reference cell must not regress
            jobs.append({**rel, "attack.type": "a1", "attack.sir_db": str(sir), "run.name": f"e3rel_lin_citadel_sir{sir}"})
    elif exp == "e8":  # larger system: 8x8 QPSK, clean and A1 white-box
        big = {"channel.n_user": "8", "channel.n_ant": "8"}
        for r in rx:
            jobs.append({**big, "receiver.type": r, "attack.type": "none", "run.name": f"e8_{r}_clean"})
            for sir in args.sirs or [-10, 0, 10]:
                jobs.append({**big, "receiver.type": r, "attack.type": "a1", "attack.sir_db": str(sir),
                             "run.name": f"e8_{r}_sir{sir}"})
    elif exp == "e9":  # 16-QAM-free alternative: BPSK and higher Doppler, robustness of the gates to the modulation/fading
        for r, fad, fd in itertools.product(rx, ["jakes"], [0.01, 0.05, 0.1]):
            jobs.append({"receiver.type": r, "channel.fading": fad, "channel.jakes_fd_tb": str(fd), "attack.type": "a1",
                         "attack.sir_db": "0", "run.name": f"e9_{r}_jakes_fd{fd}"})
    elif exp == "e7":
        for gates in ["[g1]", "[g1,g2]", "[g1,g2,g3]", "[]"]:
            tag = gates.strip("[]").replace(",", "") or "nogate"
            jobs.append({"receiver.type": "citadel", "citadel.gates": gates, "attack.type": "adaptive",
                         "run.name": f"e7_citadel_{tag}_adaptive"})
    elif exp == "ablate":
        base = {"receiver.type": "citadel", "attack.type": "a1", "attack.sir_db": "0"}
        variants = {
            "K1": {"citadel.levels": "1", "citadel.periods": "[1]"},
            "K2": {"citadel.levels": "2", "citadel.periods": "[1,8]"},
            "K4": {"citadel.levels": "4", "citadel.periods": "[1,4,16,64]"},
            "misaligned": {"citadel.periods": "[1,3,7]"},
            "nogate": {"citadel.gates": "[]"},
            "g1": {"citadel.gates": "[g1]"}, "g2": {"citadel.gates": "[g2]"}, "g3": {"citadel.gates": "[g3]"},
            "last_only": {"citadel.adaptable": "last"},
            "plain_gd": {"citadel.fast_rule": "gd"},
            "adam_no_delta": {"citadel.fast_rule": "adam"},
            "fixed_eta": {"citadel.surprise_lr": "false"},
            "no_anchor": {"citadel.prox_lambda": "0.0", "citadel.reanchor_beta": "0.0"},
            "jump_anchor": {"citadel.reanchor_mode": "jump", "citadel.reanchor_beta": "0.25"},
            "no_fallback": {"citadel.fallback_on_reject": "false"},
            "reject_keep": {"citadel.reject_action": "keep"},
        }
        for tag, ov in variants.items():
            if args.variants and tag not in args.variants:
                continue
            jobs.append({**base, **ov, "run.name": f"ablate_{tag}"})
    else:
        raise SystemExit(f"unknown experiment {exp}")
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("exp")
    ap.add_argument("--config", default=None)
    ap.add_argument("--seeds", nargs="*", type=int, default=[0])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--receivers", nargs="*", default=None)
    ap.add_argument("--snrs", nargs="*", type=float, default=None)
    ap.add_argument("--sirs", nargs="*", type=float, default=None)
    ap.add_argument("--variants", nargs="*", default=None, help="ablate: run only these variant tags")
    ap.add_argument("--extra", nargs="*", default=[], help="extra dotted overrides applied to every job")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    cfg = args.config or os.path.join(ROOT, "configs", {
        "e1": "e1_reproduce_attack.yaml", "e2": "e2_clean_parity.yaml", "e3": "e3_a1_defence.yaml",
        "e2nl": "e2_clean_parity.yaml", "e2cost": "e2_clean_parity.yaml",
        "e3nl": "e3_a1_defence.yaml", "e3cost": "e3_a1_defence.yaml",
        "e3snr": "e3_a1_defence.yaml", "e4": "e4_a2_drift_spoof.yaml", "e5": "e5_a3_boiling_frog.yaml",
        "e7": "e7_adaptive_attacker.yaml", "ablate": "e3_a1_defence.yaml",
        "e3rel": "e3_a1_defence.yaml", "e8": "e3_a1_defence.yaml", "e9": "e3_a1_defence.yaml"}[args.exp])
    jobs = grid(args.exp, args)
    out_dir = f"results/{args.exp}"
    cmds = []
    for j in jobs:
        # tiny per-user MLPs: CPU is as fast as the GPU and many CUDA processes side by side crash
        # (illegal memory access / CUBLAS errors). Override with --extra run.device=cuda if wanted.
        ov = [f"{k}={v}" for k, v in j.items()] + [f"run.out_dir={out_dir}", "run.device=cpu"] + args.extra
        cmds.append([sys.executable, RUN, cfg, "--quiet", "--seeds", *map(str, args.seeds), "--set", *ov])
    print(f"{len(cmds)} jobs x {len(args.seeds)} seeds")
    if args.dry:
        for c in cmds:
            print(" ".join(c))
        return

    def run(c):
        r = subprocess.run(c, capture_output=True, text=True)
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        print(("OK  " if r.returncode == 0 else "FAIL") + " " + tail + ("" if r.returncode == 0 else "\n" + r.stderr[-2000:]), flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(run, cmds))


if __name__ == "__main__":
    main()
