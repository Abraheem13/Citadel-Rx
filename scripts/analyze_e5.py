#!/usr/bin/env python
"""E5 — retention certificate check (Corollary 2.2).

For each attacked run (A3 boiling frog, blocks start..end) paired with its clean twin
(same periods, same seed), plot the displacement of the slowest level
    D_K(b) = || theta_adv^(K)_b - theta_clean^(K)_b ||
against the block index, and the displacement after W attacked blocks against 1/C_K.
The certificate predicts D_K(W) <= eta_K rho eps G (1 - p_rej) W / C_K, i.e. a slope in W
proportional to 1/C_K; the empirical slope ratio between C_K = 8, 32, 128 is the test.

    python scripts/analyze_e5.py results/e5 figures/e5
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np


def main(root, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(out, exist_ok=True)
    by = defaultdict(list)
    for fn in glob.glob(os.path.join(root, "*.json")):
        r = json.load(open(fn))
        if "paired_disp" not in r:
            continue
        c = r["config"]
        by[c["citadel"]["periods"][-1]].append(r)
    if not by:
        print("no paired E5 records")
        return
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    rows = ["| C_K | n | SER pre | SER in A3 window | SER post | gate rejection | D_K at end of window (mean±std) | D_K slope per attacked block | D_1 (fast) at end |",
            "|---|---|---|---|---|---|---|---|---|"]
    slopes = {}
    for ck in sorted(by):
        rs = by[ck]
        a0, a1 = rs[0]["config"]["attack"]["start_block"], rs[0]["config"]["attack"]["end_block"]
        DK = np.array([r["paired_disp"][-1] for r in rs])          # (n, blocks)
        D1 = np.array([r["paired_disp"][0] for r in rs])
        mean, std = DK.mean(0), DK.std(0)
        axes[0].plot(mean, label=f"$C_K$={ck}")
        axes[0].fill_between(range(len(mean)), mean - std, mean + std, alpha=0.15)
        w = np.arange(a0, a1)
        slope = np.polyfit(w - a0, mean[a0:a1], 1)[0]
        slopes[ck] = slope
        rows.append(f"| {ck} | {len(rs)} | {np.mean([r['summary']['ser_pre'] for r in rs]):.4f} | "
                    f"{np.mean([r['summary']['ser_attack'] for r in rs]):.4f} | {np.mean([r['summary']['ser_post'] for r in rs]):.4f} | "
                    f"{np.mean([r['summary'].get('gate_reject_rate_attacked', float('nan')) for r in rs]):.2f} | "
                    f"{mean[a1 - 1]:.2f}±{std[a1 - 1]:.2f} | {slope:.4f} | {D1.mean(0)[a1 - 1]:.2f} |")
    axes[0].axvspan(a0, a1, color="red", alpha=0.07, label="A3 window")
    axes[0].set_xlabel("block"); axes[0].set_ylabel("$\\|\\theta^{(K)}_{adv}-\\theta^{(K)}_{clean}\\|$")
    axes[0].set_title("slow-level displacement under boiling-frog A3"); axes[0].legend(fontsize=8); axes[0].grid(alpha=0.3)
    cks = sorted(slopes)
    axes[1].loglog([1 / c for c in cks], [slopes[c] for c in cks], "o-", label="measured slope")
    ref = slopes[cks[0]] * np.array([cks[0] / c for c in cks])
    axes[1].loglog([1 / c for c in cks], ref, "--", color="gray", label="$\\propto 1/C_K$ (certificate)")
    axes[1].set_xlabel("$1/C_K$"); axes[1].set_ylabel("displacement per attacked block"); axes[1].legend(fontsize=8); axes[1].grid(alpha=0.3, which="both")
    fig.tight_layout()
    path = os.path.join(out, "fig_e5_certificate.png")
    fig.savefig(path, dpi=200)
    print("\n".join(rows))
    print(f"wrote {path}")
    print("slope ratios vs C_K=%d: " % cks[0] + ", ".join(f"C_K={c}: {slopes[c] / slopes[cks[0]]:.3f} (1/C ratio {cks[0] / c:.3f})" for c in cks))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/e5", sys.argv[2] if len(sys.argv) > 2 else "figures/e5")
