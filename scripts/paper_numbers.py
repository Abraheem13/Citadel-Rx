#!/usr/bin/env python
"""Rebuild every table and figure of the paper from the JSON run records.

    python scripts/paper_numbers.py results/ [--out figures/]

Nothing in the manuscript may come from anywhere else.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from citadel_rx.eval.metrics import degradation_db  # noqa: E402


def load(root):
    recs = []
    for fn in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
        with open(fn) as f:
            r = json.load(f)
        if "summary" in r and "config" in r:
            r["_file"] = fn
            recs.append(r)
    return recs


def key(r):
    c = r["config"]
    return (c["receiver"]["type"] + ("+pre" if c["receiver"]["pretrain"] else ""), c["channel"]["model"],
            c["channel"]["fading"], c["channel"]["linear"],
            c["channel"]["snr_db"], c["attack"]["type"], c["attack"]["knowledge"], c["attack"]["sir_db"],
            tuple(c["citadel"]["gates"]), tuple(c["citadel"]["periods"]))


def mean_std(vals):
    v = np.array([x for x in vals if x is not None], dtype=float)
    if v.size == 0:
        return "n/a"
    return f"{v.mean():.4f} ± {v.std(ddof=1) if v.size > 1 else 0:.4f} (n={v.size})"


def table_summary(recs, out):
    groups = defaultdict(list)
    for r in recs:
        groups[key(r)].append(r)
    lines = ["| receiver | channel | fading | lin | SNR | attack | know | SIR | gates | periods | SER pre | SER attack | SER post | recovery | gate rej/false |",
             "|" + "---|" * 15]
    for k in sorted(groups, key=str):
        g = groups[k]
        s = [r["summary"] for r in g]
        rec = [x.get("recovery_blocks") for x in s]
        gr = mean_std([x.get("gate_reject_rate_attacked") for x in s])
        fr = mean_std([x.get("gate_false_reject_rate_clean") for x in s])
        lines.append("| " + " | ".join(map(str, k)) + f" | {mean_std([x.get('ser_pre', x['ser_mean']) for x in s])} | "
                     f"{mean_std([x.get('ser_attack') for x in s])} | {mean_std([x.get('ser_post') for x in s])} | "
                     f"{mean_std(rec)} | {gr} / {fr} |")
    path = os.path.join(out, "table_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {path} ({len(groups)} rows)")


def figure_ser_vs_block(recs, out):
    """One figure per (attack type, SIR): SER vs block for every receiver, seeds averaged,
    with the clean trajectory of the same receiver dashed and the attack window shaded."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    clean = defaultdict(list)
    attacked = defaultdict(lambda: defaultdict(list))
    for r in recs:
        c = r["config"]
        rx = c["receiver"]["type"]
        if c["attack"]["type"] == "none":
            clean[rx].append(r)
        else:
            attacked[(c["attack"]["type"], c["attack"]["sir_db"])][rx].append(r)
    for (atk, sir), by in sorted(attacked.items()):
        plt.figure(figsize=(6.4, 3.6))
        colors = {}
        for i, (rx, rs) in enumerate(sorted(by.items())):
            ser = np.mean([[b["ser"] for b in r["blocks"]] for r in rs], axis=0)
            line, = plt.semilogy(ser, label=f"{rx} under {atk} (n={len(rs)})")
            colors[rx] = line.get_color()
            if rx in clean:
                sc = np.mean([[b["ser"] for b in r["blocks"]] for r in clean[rx]], axis=0)
                plt.semilogy(sc[: len(ser)], "--", color=colors[rx], alpha=0.6, label=f"{rx} clean")
        c = next(iter(by.values()))[0]["config"]["attack"]
        plt.axvspan(c["start_block"], c["end_block"], color="red", alpha=0.08, label="attack window")
        plt.xlabel("coherence block"); plt.ylabel("SER"); plt.title(f"{atk}, SIR {sir:g} dB")
        plt.legend(fontsize=6, ncol=2); plt.grid(True, alpha=0.3); plt.tight_layout()
        path = os.path.join(out, f"fig_ser_vs_block_{atk}_sir{sir:g}.png")
        plt.savefig(path, dpi=200)
        plt.close()
        print(f"wrote {path}")


def figure_ser_vs_sir(recs, out):
    """Attack-window SER vs SIR per receiver, one panel per attacker knowledge; seeds averaged
    with std error bars; clean level of each receiver as a dotted line of the same colour."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    by = defaultdict(lambda: defaultdict(list))
    for r in recs:
        c = r["config"]
        if c["attack"]["type"] != "a1" or "ser_attack" not in r["summary"]:
            continue
        by[c["attack"]["knowledge"]][(c["receiver"]["type"], c["attack"]["sir_db"])].append(r["summary"])
    if not by:
        return
    fig, axes = plt.subplots(1, len(by), figsize=(5.2 * len(by), 3.6), sharey=True, squeeze=False)
    for ax, (know, cells) in zip(axes[0], sorted(by.items())):
        rxs = sorted({k[0] for k in cells})
        for rx in rxs:
            sirs = sorted({k[1] for k in cells if k[0] == rx})
            mean = [np.mean([s["ser_attack"] for s in cells[(rx, sir)]]) for sir in sirs]
            std = [np.std([s["ser_attack"] for s in cells[(rx, sir)]], ddof=1) if len(cells[(rx, sir)]) > 1 else 0
                   for sir in sirs]
            line = ax.errorbar(sirs, mean, yerr=std, marker="o", capsize=2, label=rx)
            pre = np.mean([s.get("ser_pre", np.nan) for sir in sirs for s in cells[(rx, sir)]])
            ax.axhline(pre, ls=":", color=line[0].get_color(), alpha=0.6)
        ax.set_yscale("log")
        ax.set_xlabel("SIR (dB)  — attacker energy relative to all users")
        ax.set_title(f"A1 pilot poisoning, {know} attacker")
        ax.grid(True, alpha=0.3)
    axes[0][0].set_ylabel("SER in attack window (dotted: clean level)")
    axes[0][-1].legend(fontsize=7)
    fig.tight_layout()
    path = os.path.join(out, "fig_ser_vs_sir_a1.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"wrote {path}")


def table_degradation(recs, out):
    """Delta_dB from e3snr runs: clean vs attacked SER-vs-SNR curves per receiver."""
    curves = defaultdict(lambda: defaultdict(list))
    for r in recs:
        c = r["config"]
        if not r["name"].startswith("e3snr"):
            continue
        curves[(c["receiver"]["type"], c["attack"]["type"])][c["channel"]["snr_db"]].append(
            r["summary"].get("ser_attack") if c["attack"]["type"] != "none" else r["summary"]["ser_mean"])
    lines = ["| receiver | SNR | SER clean | SER attacked | Δ_dB |", "|---|---|---|---|---|"]
    for rx in sorted({k[0] for k in curves}):
        if (rx, "none") not in curves or (rx, "a1") not in curves:
            continue
        snrs = sorted(set(curves[(rx, "none")]) & set(curves[(rx, "a1")]))
        if len(snrs) < 2:
            continue
        sc = np.array([np.mean(curves[(rx, "none")][s]) for s in snrs])
        sa = np.array([np.mean(curves[(rx, "a1")][s]) for s in snrs])
        dd = degradation_db(np.array(snrs, dtype=float), sc, sa)
        for s, a, b_, d in zip(snrs, sc, sa, dd):
            # a value equal to the remaining grid span means the attacked curve never reaches the clean
            # SER inside the grid: report it as a lower bound
            txt = "∞ (never within grid)" if np.isinf(d) else (f"> {d:.1f}" if abs(d - (max(snrs) - s)) < 1e-6 and d > 0 else f"{d:.2f}")
            lines.append(f"| {rx} | {s} | {a:.4f} | {b_:.4f} | {txt} |")
    path = os.path.join(out, "table_degradation_db.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="figures")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    recs = load(args.root)
    print(f"{len(recs)} records")
    if not recs:
        return
    table_summary(recs, args.out)
    table_degradation(recs, args.out)
    figure_ser_vs_block(recs, args.out)
    figure_ser_vs_sir(recs, args.out)


if __name__ == "__main__":
    main()
