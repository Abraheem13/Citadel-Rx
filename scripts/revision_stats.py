#!/usr/bin/env python
"""Revision statistics (reviewer audit E1, E3, E6, E8).

E1  Blocks are correlated through the channel and the receiver's memory, so per-block tests
    overstate the evidence. This script
      * measures the decorrelation length of the paired per-block differences (first lag at
        which the pooled autocorrelation falls below 1/e) and uses a moving-block bootstrap
        with block length max(5, 2 x that length): seeds are resampled, and within each seed
        contiguous runs of blocks are resampled (circularly);
      * runs seed-level paired tests on per-seed means: exact two-sided Wilcoxon signed-rank
        (with n seeds the smallest attainable p is 2^(1-n)), the sign test, and a paired t-test.
E3  The primary metric is EXCESS SER: SER of the attacked run minus SER of the clean run with the
    same seed and configuration, on the same blocks (the window, and the 30 blocks after it).
    The raw window SER is reported as secondary.
E6  Rates come with their counts and Wilson 95% intervals.
E8  Every multiple-comparison family is listed with its hypotheses and its size; Holm's
    correction is applied within the family.

    python scripts/revision_stats.py --attacked results/e3 --clean results/e3snr --out docs/STATS_REVISION.md
    (a clean run is matched on seed and on every setting except attack.*, run.* and channel.snr_db
     equal to the attacked run's)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict
from itertools import product
from typing import Dict, List, Tuple

import numpy as np
from scipy.stats import binomtest, ttest_1samp, wilcoxon

LABEL = {"lmmse": "LMMSE", "lmmse_robust": "LMMSE, robust LS", "online_deepsic": "Online DeepSIC",
         "meta_deepsic": "Meta-DeepSIC", "drift_deepsic": "Drift-detection", "medbn_deepsic": "Median-of-means gradient",
         "titans_single": "Single-memory Titans", "crc_rollback": "CRC-Rollback", "rollback_allgates": "Rollback, all gates",
         "l2sp_deepsic": "L2-SP", "ewc_deepsic": "EWC", "ema_deepsic": "EMA teacher", "dd_deepsic": "CRC-verified DD",
         "cotta_deepsic": "CoTTA-style", "eata_deepsic": "EATA-style", "citadel": "Citadel-Rx"}


# ---------------------------------------------------------------------------------- records
def load(folder: str) -> List[dict]:
    out = []
    for fn in glob.glob(os.path.join(folder, "*.json")):
        try:
            out.append(json.load(open(fn)))
        except Exception:
            pass
    return out


def match_key(cfg: dict) -> str:
    """Everything that defines the channel, frames and receiver, without the attack and run."""
    c = {k: v for k, v in cfg.items() if k not in ("attack", "run")}
    return json.dumps(c, sort_keys=True)


def pair_runs(attacked: List[dict], clean: List[dict]) -> List[Tuple[dict, dict]]:
    idx = {}
    for r in clean:
        if r["config"]["attack"]["type"] == "none":
            idx[(match_key(r["config"]), r["seed"])] = r
    pairs = []
    for r in attacked:
        if r["config"]["attack"]["type"] == "none":
            continue
        m = idx.get((match_key(r["config"]), r["seed"]))
        if m is not None:
            pairs.append((r, m))
    return pairs


def window_of(r: dict) -> Tuple[int, int]:
    w = r["summary"].get("attack_window")
    if w:
        return int(w[0]), int(w[1])
    return int(r["config"]["attack"]["start_block"]), int(r["config"]["attack"]["end_block"])


# ---------------------------------------------------------------------------------- statistics
def decorrelation_length(series: List[np.ndarray]) -> int:
    """First lag at which the pooled autocorrelation of the (demeaned) series drops below 1/e."""
    x = [s - s.mean() for s in series if s.size > 3]
    if not x:
        return 1
    max_lag = min(40, min(s.size for s in x) - 1)
    var = sum(float((s * s).sum()) for s in x)
    if var <= 0:
        return 1
    for lag in range(1, max_lag + 1):
        ac = sum(float((s[:-lag] * s[lag:]).sum()) for s in x) / var
        if ac < np.exp(-1):
            return lag
    return max_lag


def moving_block_bootstrap(series: List[np.ndarray], block: int, n_boot: int = 5000, seed: int = 0):
    """Resample seeds, then contiguous (circular) runs of `block` blocks within each seed."""
    rng = np.random.default_rng(seed)
    S = len(series)
    means = np.empty(n_boot)
    for i in range(n_boot):
        vals = []
        for s in rng.integers(0, S, size=S):
            x = series[s]
            n = x.size
            nb = int(np.ceil(n / block))
            starts = rng.integers(0, n, size=nb)
            idx = (starts[:, None] + np.arange(block)[None, :]).reshape(-1)[:n] % n
            vals.append(x[idx].mean())
        means[i] = np.mean(vals)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _wilcoxon_exact(x: np.ndarray) -> float:
    """Exact two-sided Wilcoxon signed-rank p-value (scipy renamed `mode` to `method`)."""
    try:
        return float(wilcoxon(x, alternative="two-sided", method="exact").pvalue)
    except TypeError:
        return float(wilcoxon(x, alternative="two-sided", mode="exact").pvalue)


def seed_tests(seed_means: np.ndarray) -> Dict[str, float]:
    d = np.asarray(seed_means, dtype=float)
    out = {"n_seeds": int(d.size)}
    nz = d[d != 0]
    out["wilcoxon_p"] = _wilcoxon_exact(nz) if nz.size >= 1 else 1.0
    out["min_attainable_p"] = float(2.0 ** (1 - nz.size)) if nz.size else 1.0
    k = int((nz > 0).sum())
    out["sign_p"] = float(binomtest(k, nz.size, 0.5).pvalue) if nz.size else 1.0
    out["t_p"] = float(ttest_1samp(d, 0.0).pvalue) if d.size > 1 and d.std() > 0 else 1.0
    return out


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def holm(pvals: List[float]) -> List[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return list(adj)


# ---------------------------------------------------------------------------------- tables
def excess_rows(pairs, cell_filter, label: str):
    """Per receiver: window and post-attack excess SER with moving-block CIs and seed tests."""
    by_rx = defaultdict(list)
    for a, c in pairs:
        if cell_filter(a["config"]):
            by_rx[a["config"]["receiver"]["type"]].append((a, c))
    rows, family = [], []
    for rx, prs in sorted(by_rx.items(), key=lambda kv: kv[0]):
        win, post, raw = [], [], []
        for a, c in sorted(prs, key=lambda p: p[0]["seed"]):
            w0, w1 = window_of(a)
            sa = np.array([b["ser"] for b in a["blocks"]])
            sc = np.array([b["ser"] for b in c["blocks"]])
            n = min(sa.size, sc.size)
            win.append(sa[w0:min(w1, n)] - sc[w0:min(w1, n)])
            post.append(sa[w1:min(w1 + 30, n)] - sc[w1:min(w1 + 30, n)])
            raw.append(sa[w0:min(w1, n)])
        L = decorrelation_length(win)
        blk = max(5, 2 * L)
        lo, hi = moving_block_bootstrap(win, blk)
        plo, phi = moving_block_bootstrap(post, blk) if all(p.size for p in post) else (np.nan, np.nan)
        sm = np.array([w.mean() for w in win])
        st = seed_tests(sm)
        family.append((rx, st["wilcoxon_p"]))
        rows.append({"rx": rx, "n": len(prs), "excess": float(np.mean(sm)), "ci": (lo, hi),
                     "post": float(np.mean([p.mean() for p in post])) if post else np.nan, "post_ci": (plo, phi),
                     "raw": float(np.mean([r.mean() for r in raw])), "decor": L, "block": blk, **st})
    adj = holm([p for _, p in family])
    for r, a in zip(rows, adj):
        r["holm_p"] = a
    lines = [f"**{label}**", "",
             "| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {LABEL.get(r['rx'], r['rx'])} | {r['n']} | {r['excess']:+.4f} [{r['ci'][0]:+.4f}, {r['ci'][1]:+.4f}] | "
                     f"{r['post']:+.4f} [{r['post_ci'][0]:+.4f}, {r['post_ci'][1]:+.4f}] | {r['raw']:.4f} | {r['decor']} / {r['block']} | "
                     f"{r['wilcoxon_p']:.4f} ({r['holm_p']:.4f}) | {r['min_attainable_p']:.4f} | {r['sign_p']:.4f} |")
    fam = f"Holm family '{label}': H0(receiver) = 'mean excess SER is zero', one per receiver row, size {len(family)}."
    return lines, fam


def gate_rows(records, cell_filter, label: str):
    lines = [f"**{label}**", "", "| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |",
             "|---|---|---|---|---|"]
    by = defaultdict(lambda: [0, 0, 0, 0])
    for r in records:
        if not cell_filter(r["config"]) or "gamma" not in r["blocks"][0]:
            continue
        acc = by[r["config"]["receiver"]["type"]]
        for b in r["blocks"]:
            if b["block"] < 5:
                continue
            rej = b["gamma"] < 0.5
            if b.get("attacked"):
                acc[0] += rej; acc[1] += 1
            else:
                acc[2] += rej; acc[3] += 1
    for rx, (k1, n1, k0, n0) in sorted(by.items()):
        a1, b1 = wilson(k1, n1); a0, b0 = wilson(k0, n0)
        lines.append(f"| {LABEL.get(rx, rx)} | {k1} / {n1} | {k1 / max(n1, 1):.3f} [{a1:.3f}, {b1:.3f}] | {k0} / {n0} | "
                     f"{k0 / max(n0, 1):.3f} [{a0:.3f}, {b0:.3f}] |")
    return lines


def by_name_rows(pairs, records, label: str):
    """Generic table: one row per attacked configuration (run name), every receiver it ran."""
    groups = defaultdict(list)
    for a, c in pairs:
        groups[a["name"]].append((a, c))
    lines = [f"**{label}**", "",
             "| configuration | seeds | excess SER in window [95% MB CI] | excess SER after [CI] | raw window SER | seed Wilcoxon p | rejection [Wilson] (k/n) | false rejection [Wilson] (k/n) |",
             "|---|---|---|---|---|---|---|---|"]
    for name, prs in sorted(groups.items()):
        win, post, raw = [], [], []
        k1 = n1 = k0 = n0 = 0
        for a, c in prs:
            w0, w1 = window_of(a)
            sa = np.array([b["ser"] for b in a["blocks"]]); sc = np.array([b["ser"] for b in c["blocks"]])
            n = min(sa.size, sc.size)
            win.append(sa[w0:min(w1, n)] - sc[w0:min(w1, n)])
            post.append(sa[w1:min(w1 + 30, n)] - sc[w1:min(w1 + 30, n)])
            raw.append(sa[w0:min(w1, n)])
            if "gamma" in a["blocks"][0]:
                for b in a["blocks"]:
                    if b["block"] < 5:
                        continue
                    rej = b["gamma"] < 0.5
                    if b.get("attacked"):
                        k1 += rej; n1 += 1
                    else:
                        k0 += rej; n0 += 1
        blk = max(5, 2 * decorrelation_length(win))
        lo, hi = moving_block_bootstrap(win, blk, n_boot=2000)
        pl, ph = moving_block_bootstrap(post, blk, n_boot=2000) if all(p.size for p in post) else (np.nan, np.nan)
        st = seed_tests(np.array([w.mean() for w in win]))
        rj = (f"{k1 / n1:.3f} [{wilson(k1, n1)[0]:.3f}, {wilson(k1, n1)[1]:.3f}] ({k1}/{n1})" if n1 else "-")
        fr = (f"{k0 / n0:.3f} [{wilson(k0, n0)[0]:.3f}, {wilson(k0, n0)[1]:.3f}] ({k0}/{n0})" if n0 else "-")
        lines.append(f"| {name} | {len(prs)} | {np.mean([w.mean() for w in win]):+.4f} [{lo:+.4f}, {hi:+.4f}] | "
                     f"{np.mean([p.mean() for p in post]) if post else float('nan'):+.4f} [{pl:+.4f}, {ph:+.4f}] | "
                     f"{np.mean([r.mean() for r in raw]):.4f} | {st['wilcoxon_p']:.4f} | {rj} | {fr} |")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attacked", nargs="+", required=True)
    ap.add_argument("--clean", nargs="+", required=True)
    ap.add_argument("--out", default="docs/STATS_REVISION.md")
    ap.add_argument("--sirs", nargs="*", type=float, default=[-10, 0, 10])
    ap.add_argument("--by-name", action="store_true", help="one generic row per attacked configuration")
    ap.add_argument("--title", default="Attacked configurations")
    args = ap.parse_args()
    if args.by_name:
        att = [r for f in args.attacked for r in load(f)]
        cln = [r for f in args.clean for r in load(f)]
        lines = by_name_rows(pair_runs(att, cln), att, args.title)
        txt = "\n".join(["# " + args.title + " (scripts/revision_stats.py --by-name)", ""] + lines) + "\n"
        open(args.out, "w").write(txt)
        print(txt)
        return
    att = [r for f in args.attacked for r in load(f)]
    cln = [r for f in args.clean for r in load(f)]
    pairs = pair_runs(att, cln)
    out = ["# Revision statistics (scripts/revision_stats.py)", "",
           "Primary metric: excess SER = attacked minus clean SER on the same blocks of the same seed and "
           "configuration (audit E3). Intervals: moving-block bootstrap over seeds and contiguous runs of blocks, "
           "with the block length set to twice the measured decorrelation length (audit E1). Tests: exact "
           "seed-level Wilcoxon signed-rank on per-seed mean excess SER, Holm-corrected within each family "
           "(families listed at the end, audit E8). Rates: counts and Wilson 95% intervals (audit E6).",
           f"", f"Matched attacked/clean pairs: {len(pairs)}.", ""]
    families = []
    for know, sir in product(("whitebox", "transfer"), args.sirs):
        f = lambda c, k=know, s=sir: c["attack"]["type"] == "a1" and c["attack"]["knowledge"] == k and float(c["attack"]["sir_db"]) == s \
            and c["receiver"]["type"] != ("lmmse" if k == "whitebox" else "")
        lines, fam = excess_rows(pairs, f, f"A1 {know}, SIR {sir:g} dB")
        if len(lines) > 4:
            out += lines + [""]
            families.append(fam)
    f_jam = lambda c: c["attack"]["type"] == "data_jam"
    lines, fam = excess_rows(pairs, f_jam, "Data-jamming control, 0 dB")
    if len(lines) > 4:
        out += lines + [""]
        families.append(fam)
    out += ["## Gate rates with counts", ""]
    for know, sir in product(("whitebox", "transfer"), args.sirs):
        out += gate_rows(att, lambda c, k=know, s=sir: c["attack"]["type"] == "a1" and c["attack"]["knowledge"] == k
                         and float(c["attack"]["sir_db"]) == s, f"A1 {know}, SIR {sir:g} dB") + [""]
    out += ["## Multiple-comparison families (audit E8)", ""] + [f"- {f}" for f in families] + [""]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(args.out, "w").write("\n".join(out))
    print("\n".join(out[:60]))


if __name__ == "__main__":
    main()
