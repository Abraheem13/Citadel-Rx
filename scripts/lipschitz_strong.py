#!/usr/bin/env python
"""Stronger estimates of the constants of Theorem 1 (reviewer audit A6).

For each channel family, a Citadel-Rx receiver is pre-trained and run on clean blocks; on
`--blocks` of them the script estimates
  * G_Phi with a finite-difference hill climb from `--probes` random directions (`--ascent` steps
    each), i.e. a search for the worst input direction rather than independent random probes;
  * L_theta and L_a with `--probes` random parameter/anchor directions.
It reports the maximum and the 95% upper quantile over all (block, probe) values, never the mean.
The H1 design (fast level started from the anchor) has L_theta = 0 by construction.

    python scripts/lipschitz_strong.py --blocks 50 --probes 100 --ascent 10 --families cosine jakes cost2100
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
torch.set_num_threads(int(os.environ.get("CITADEL_THREADS", "1")))

from citadel_rx.channels import make_channel  # noqa: E402
from citadel_rx.config import Config  # noqa: E402
from citadel_rx.eval.runner import pretraining_blocks, set_seed  # noqa: E402
from citadel_rx.frames import FrameGenerator  # noqa: E402
from citadel_rx.receivers import make_receiver  # noqa: E402
from citadel_rx.theory.bound import estimate_adaptation_lipschitz, estimate_input_gain_ascent  # noqa: E402


def run_family(family: str, args) -> dict:
    over = ["receiver.type=citadel", "run.device=cpu"] + args.set
    if family == "jakes":
        over.append("channel.fading=jakes")
    elif family == "cost2100":
        over.append("channel.model=cost2100")
    cfg = Config.from_yaml(args.config, over)
    set_seed(args.seed)
    cfg.channel.seed = args.seed
    frames = FrameGenerator(cfg)
    channel = make_channel(cfg.channel, frames.mod.is_complex)
    rx = make_receiver(cfg, torch.device("cpu"))
    rx.pretrain(pretraining_blocks(cfg, frames))
    G, Lt, La = [], [], []
    for b in range(args.warmup + args.blocks):
        st = channel.state(b)
        blk = frames.make(b)
        y_p = channel.transmit(blk.s_pilot, st)
        y_d = channel.transmit(blk.s_data, st)
        if b >= args.warmup:
            yf, it = rx.to_feat(y_p), rx.to_idx(blk.idx_pilot)
            G += estimate_input_gain_ascent(rx, yf, it, rx.eta_max, n_probe=args.probes, ascent=args.ascent, seed=b)
            _, lt, la = estimate_adaptation_lipschitz(rx, yf, it, rx.eta_max, n_probe=args.probes, seed=b)
            Lt.append(lt); La.append(la)
        rx.process_block(b, y_p, blk.idx_pilot, y_d, aux={"framer": frames})
    q = lambda a: {"max": float(np.max(a)), "q95": float(np.percentile(a, 95)), "n": len(a)}
    return {"family": family, "G_Phi": q(G), "L_theta": q(Lt), "L_a": q(La),
            "L_sum_max": float(np.max(Lt) + np.max(La))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/e5_a3_boiling_frog.yaml")
    ap.add_argument("--families", nargs="+", default=["cosine", "jakes", "cost2100"])
    ap.add_argument("--blocks", type=int, default=50)
    ap.add_argument("--probes", type=int, default=100)
    ap.add_argument("--ascent", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--set", nargs="*", default=[])
    ap.add_argument("--out", default="docs/lipschitz_strong.json")
    ap.add_argument("--frozen", action="store_true", help="measure the configuration frozen by the calibration phase")
    args = ap.parse_args()
    if args.frozen:
        fz = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "revision_frozen_citadel.json")))
        args.set = list(fz["citadel_overrides"]) + list(args.set)
    res = [run_family(f, args) for f in args.families]
    json.dump({"args": vars(args), "results": res}, open(args.out, "w"), indent=1)
    rows = ["| family | G_Phi max | G_Phi q95 | L_theta max | L_theta q95 | L_a max | L_a q95 | L_theta+L_a (max) |",
            "|---|---|---|---|---|---|---|---|"]
    for r in res:
        rows.append(f"| {r['family']} | {r['G_Phi']['max']:.3f} | {r['G_Phi']['q95']:.3f} | {r['L_theta']['max']:.3f} | "
                    f"{r['L_theta']['q95']:.3f} | {r['L_a']['max']:.3f} | {r['L_a']['q95']:.3f} | {r['L_sum_max']:.3f} |")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
