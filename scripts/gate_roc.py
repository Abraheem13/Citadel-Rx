#!/usr/bin/env python
"""Gate operating characteristics and per-block cost from the run records.

1. ROC of the gate verdict gamma as a detector of poisoned blocks (label = block attacked), per
   experiment folder and per gate, pooled over seeds and SIRs; AUC and the operating point used
   by the receiver (gamma < 0.5).
2. Per-block receiver time (mean_t_rx_s) for every receiver type, pooled over the clean records of
   the given folders, with the pre-training time; the attacker's PGD time is listed separately.

    python scripts/gate_roc.py results/e3 results/e3nl results/e3cost results/e4 results/e7
Writes docs/figures/fig_gate_roc.png and prints Markdown tables (appended to docs/TABLES.md with --write).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np


def roc(scores: np.ndarray, labels: np.ndarray):
    order = np.argsort(-scores)
    s, y = scores[order], labels[order]
    tp = np.cumsum(y); fp = np.cumsum(1 - y)
    tpr = tp / max(y.sum(), 1); fpr = fp / max((1 - y).sum(), 1)
    # unique thresholds
    keep = np.r_[np.diff(s) != 0, True]
    tpr, fpr = np.r_[0, tpr[keep]], np.r_[0, fpr[keep]]
    auc = float(np.trapezoid(tpr, fpr)) if hasattr(np, "trapezoid") else float(np.trapz(tpr, fpr))
    return fpr, tpr, auc


def load(folder):
    recs = []
    for fn in glob.glob(os.path.join(folder, "*.json")):
        r = json.load(open(fn))
        if r["config"]["receiver"]["type"] == "citadel" and r["config"]["attack"]["type"] not in ("none",) \
                and "gamma" in r["blocks"][0] and r["config"]["citadel"]["gates"]:
            recs.append(r)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from paper_style import save, panel_title
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.35))
    NAMES = {"e3/a1": "A1, SED 4x4", "e3/data_jam": "data jamming, SED 4x4", "e3nl/a1": "A1, tanh PA",
             "e3rel/a1": "A1, COST2100 + SED, relative slack", "e8/a1": "A1, SED 8x8", "e9/a1": "A1, Jakes",
             "e4/a2": "A2 targeted, Jakes", "e7/adaptive": "gate-aware, SED 4x4"}
    rows = ["| experiment | attack | n blocks (poisoned/clean) | AUC gamma | AUC G1 | AUC G2 | AUC G3 | TPR at gamma<0.5 | FPR at gamma<0.5 |",
            "|---|---|---|---|---|---|---|---|---|"]
    for folder in args.folders:
        recs = load(folder)
        if not recs:
            continue
        by_attack = defaultdict(list)
        for r in recs:
            by_attack[r["config"]["attack"]["type"]].append(r)
        for atk, rs in sorted(by_attack.items()):
            blocks = [b for r in rs for b in r["blocks"] if b["block"] >= 5]   # skip gate warm-up
            y = np.array([float(b.get("attacked", False)) for b in blocks])
            if y.sum() == 0 or (1 - y).sum() == 0:
                continue
            score = {"gamma": np.array([1 - b["gamma"] for b in blocks])}
            for g, sign in (("g1", 1), ("g2", -1), ("g3", 1)):
                v = np.array([b.get(f"gate_{g}", np.nan) for b in blocks], dtype=float)
                if np.isfinite(v).all():
                    score[g] = sign * v
            aucs = {k: roc(v, y)[2] for k, v in score.items()}
            fpr, tpr, _ = roc(score["gamma"], y)
            hard = np.array([b["gamma"] < 0.5 for b in blocks])
            tp_op, fp_op = hard[y == 1].mean(), hard[y == 0].mean()
            tag = f"{os.path.basename(folder)}/{atk}"
            axes[0].plot(fpr, tpr, label=f"{NAMES.get(tag, tag)} (AUC {aucs['gamma']:.3f})")
            rows.append(f"| {os.path.basename(folder)} | {atk} | {int(y.sum())}/{int((1-y).sum())} | {aucs['gamma']:.3f} | "
                        f"{aucs.get('g1', float('nan')):.3f} | {aucs.get('g2', float('nan')):.3f} | {aucs.get('g3', float('nan')):.3f} | "
                        f"{tp_op:.3f} | {fp_op:.3f} |")
    axes[0].set_xlabel("false-rejection rate (clean blocks)")
    axes[0].set_ylabel("rejection rate (poisoned blocks)")
    axes[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=2, fontsize=6.5)
    axes[0].set_xlim(0, 0.25); axes[0].set_ylim(0.5, 1.005)
    panel_title(axes[0], "(a) Combined verdict $\\gamma$, per experiment")
    # per-gate ROC on the primary folder
    recs = load(args.folders[0])
    blocks = [b for r in recs if r["config"]["attack"]["type"] == "a1" for b in r["blocks"] if b["block"] >= 5]
    y = np.array([float(b.get("attacked", False)) for b in blocks])
    for g, sign, lab in (("g1", 1, "G1 residual"), ("g2", -1, "G2 CRC"), ("g3", 1, "G3 prior")):
        v = sign * np.array([b[f"gate_{g}"] for b in blocks])
        fpr, tpr, auc = roc(v, y)
        axes[1].plot(fpr, tpr, label=f"{lab} (AUC {auc:.3f})")
    fpr, tpr, auc = roc(np.array([1 - b["gamma"] for b in blocks]), y)
    axes[1].plot(fpr, tpr, "k", lw=1.4, label=f"combined $\\gamma=\\min$ (AUC {auc:.3f})")
    axes[1].set_xlabel("false-rejection rate (clean blocks)")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=2, fontsize=6.5)
    axes[1].set_xlim(0, 0.25); axes[1].set_ylim(0.5, 1.005)
    panel_title(axes[1], "(b) Individual gates, A1 on the SED 4x4 grid")
    fig.subplots_adjust(left=0.07, right=0.99, top=0.9, bottom=0.46, wspace=0.2); save(fig, "fig_roc")

    # ---- cost table -------------------------------------------------------------------------
    cost = defaultdict(list); pre = defaultdict(list); tatk = []
    for folder in args.folders:
        for fn in glob.glob(os.path.join(folder, "*.json")):
            r = json.load(open(fn))
            rt = r["config"]["receiver"]["type"]
            cost[rt].append(r["summary"]["mean_t_rx_s"]); pre[rt].append(r["summary"].get("pretrain_time_s", 0.0))
            if r["config"]["attack"]["type"] == "a1":
                tatk += [b["t_attack"] for b in r["blocks"] if b.get("attacked")]
    crow = ["| receiver | per-block time [s] (mean ± sd over runs) | pre-training [s] | relative to online DeepSIC |", "|---|---|---|---|"]
    ref = np.mean(cost.get("online_deepsic", [1.0]))
    for rt in ["lmmse", "online_deepsic", "meta_deepsic", "drift_deepsic", "medbn_deepsic", "titans_single", "citadel"]:
        if rt in cost:
            crow.append(f"| {rt} | {np.mean(cost[rt]):.2f} ± {np.std(cost[rt]):.2f} | {np.mean(pre[rt]):.1f} | {np.mean(cost[rt]) / ref:.2f}x |")
    crow.append(f"| (attacker A1 PGD, per attacked block) | {np.mean(tatk):.2f} ± {np.std(tatk):.2f} | – | – |")
    out = "\n## Gate operating characteristics\n\n" + "\n".join(rows) + \
          "\n\n![gate ROC](figures/fig_gate_roc.png)\n\n## Per-block compute cost (CPU, single thread, 300 adaptation epochs)\n\n" + "\n".join(crow) + "\n"
    print(out)
    if args.write:
        open("docs/TABLES.md", "a").write(out)
    print("wrote docs/figures/fig_gate_roc.png")


if __name__ == "__main__":
    main()
