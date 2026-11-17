#!/usr/bin/env python
"""Review of a v3 phase from its run records: pairing, integrity checks, excess SER with intervals,
gate rates and paired comparisons (docs/ROADMAP_9of10.md, protocol rules 3-6).

    python scripts/v3/analyze.py --phase 1            # writes docs/v3/PHASE1_TABLES.md and results/v3/p1_summary.json

Pairing: an attacked run is paired with the clean twin of the same settings (attack.* and run.* aside),
seed and machine. Integrity: both runs must have every block, no NaN, and agree bit for bit on SER and
verdict before the first attacked block (the attacker draws from its own generators), else the pair is
reported and dropped.
Statistics:
  excess SER   mean over seeds of (attacked - twin) over the cell's blocks; 95% moving-block bootstrap
               (seeds resampled, then circular runs of 2x the decorrelation length, at least 5 blocks)
  tests        exact two-sided Wilcoxon signed-rank on per-seed values
  equivalence  TOST at margin 0.005 SER: equivalent if the 90% interval of the paired difference lies in
               (-0.005, +0.005) (roadmap rule 5)
  rates        rejection of attacked / false rejection of twin blocks >= 5, with Wilson 95% intervals
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from revision_stats import decorrelation_length, moving_block_bootstrap, wilson, _wilcoxon_exact  # noqa: E402

MARGIN = 0.005

# cells whose blocks differ from the attack window: name -> (first block, end block) of the scored stretch
PHASE_RANGES = {
    1: {"v3p1c_citadel_ratchet__sir0": (50, 90), "v3p1c_citadel_burst__sir0": (50, 90)},
}
# Phase 2 comparisons; "p1:<name>" refers to a Phase 1 cell (same seeds 20-29, same machine)
# paired comparisons per phase: (label, cell A, cell B, metric) with metric "excess" or "window"
PHASE_COMPARE = {
    1: [("Citadel-Rx vs frozen + CRC selection, excess", "v3p1a_citadel__wb_sir0", "v3p1a_frozen_select__wb_sir0", "excess"),
        ("Citadel-Rx vs frozen + CRC selection, window SER", "v3p1a_citadel__wb_sir0", "v3p1a_frozen_select__wb_sir0", "window"),
        ("Citadel-Rx vs guarded ML, window SER", "v3p1a_citadel__wb_sir0", "v3p1_model_ml_guard__wb_sir0", "window"),
        ("Citadel-Rx vs guarded LMMSE, window SER", "v3p1a_citadel__wb_sir0", "v3p1_model_lmmse_guard__wb_sir0", "window"),
        ("Cold vs warm start, excess", "v3p1b_citadel_cold__a1_sir0", "v3p1b_citadel_warm__a1_sir0", "excess"),
        ("Ratchet + burst vs burst, excess in the burst", "v3p1c_citadel_ratchet__sir0", "v3p1c_citadel_burst__sir0", "excess")],
    2: [("Fix vs base, cold start, excess (seeds 30-34)", "v3p2Ft_fix_cold__a1_sir0", "v3p2Ft_base_cold__a1_sir0", "excess"),
        ("Fix vs base, warm A1, excess (seeds 30-34)", "v3p2Ft_fix_warm__a1_sir0", "v3p2Ft_base_warm__a1_sir0", "excess"),
        ("Citadel-Rx vs ML + CRC-verified guard, A1, window SER", "p1:v3p1a_citadel__wb_sir0", "v3p2G_ml_crc__wb_sir0", "window"),
        ("Citadel-Rx vs ML + guard without re-base, A1, window SER", "p1:v3p1a_citadel__wb_sir0", "v3p2G_ml_never__wb_sir0", "window"),
        ("Citadel-Rx vs ML + CRC-verified guard, spoof, window SER", "p1:v3p1d_citadel__spoof_sir0", "v3p2G_ml_crc__spoof_sir0", "window"),
        ("Citadel-Rx vs ML + guard without re-base, spoof, window SER", "p1:v3p1d_citadel__spoof_sir0", "v3p2G_ml_never__spoof_sir0", "window")],
}


def load(folder: str) -> List[dict]:
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, folder, "**", "*.json"), recursive=True)):
        try:
            r = json.load(open(f))
        except Exception:   # noqa: BLE001
            print(f"!! unreadable record {os.path.relpath(f, ROOT)}")
            continue
        if isinstance(r, dict) and "blocks" in r and "config" in r:
            r["_file"] = os.path.relpath(f, ROOT)
            out.append(r)
    return out


def mkey(cfg: dict) -> str:
    from citadel_rx.config import Config
    try:
        cfg = Config.from_dict(cfg).to_dict()
    except KeyError:
        pass
    return json.dumps({k: v for k, v in cfg.items() if k not in ("attack", "run")}, sort_keys=True)


def arr(r: dict, k: str = "ser") -> np.ndarray:
    return np.array([np.nan if b.get(k) is None else float(b[k]) for b in r["blocks"]], dtype=float)


def first_attacked(r: dict) -> int:
    return next((b["block"] for b in r["blocks"] if b.get("attacked")), len(r["blocks"]))


def check_pair(a: dict, c: dict) -> Optional[str]:
    if len(a["blocks"]) != a["config"]["frame"]["n_blocks"] or len(c["blocks"]) != len(a["blocks"]):
        return "incomplete"
    if np.isnan(arr(a)).any() or np.isnan(arr(c)).any():
        return "NaN SER"
    w0 = first_attacked(a)
    for k in ("ser", "gamma"):
        if [b.get(k) for b in a["blocks"][:w0]] != [b.get(k) for b in c["blocks"][:w0]]:
            return f"differs from its twin before block {w0} ({k})"
    return None


def pairs(phase: int) -> Tuple[Dict[str, List[Tuple[dict, dict]]], List[str], List[dict]]:
    att = [r for r in load(os.path.join("results", "v3", f"p{phase}")) if r["config"]["attack"]["type"] != "none"]
    plain = [r for r in load(os.path.join("results", "v3", f"p{phase}")) if r["config"]["attack"]["type"] == "none"]
    twins: Dict[Tuple[str, int, str], dict] = {}
    for f in glob.glob(os.path.join(ROOT, "results", "v3", "clean_*")):
        for r in load(os.path.relpath(f, ROOT)):
            twins[(mkey(r["config"]), r["seed"], r.get("machine", ""))] = r
    out: Dict[str, List[Tuple[dict, dict]]] = {}
    problems = []
    for a in att:
        c = twins.get((mkey(a["config"]), a["seed"], a.get("machine", "")))
        if c is None:
            problems.append(f"{a['_file']}: no clean twin from machine {a.get('machine')}")
            continue
        p = check_pair(a, c)
        if p:
            problems.append(f"{a['_file']}: {p}")
            continue
        out.setdefault(a["name"], []).append((a, c))
    return out, problems, plain


def scored(r: dict, rng: Optional[Tuple[int, int]]) -> Tuple[int, int]:
    if rng:
        return rng
    w = r["summary"].get("attack_window") or [r["config"]["attack"]["start_block"], r["config"]["attack"]["end_block"]]
    return int(w[0]), int(w[1])


def cell(prs: List[Tuple[dict, dict]], rng: Optional[Tuple[int, int]] = None) -> dict:
    prs = sorted(prs, key=lambda p: p[0]["seed"])
    diffs, post, win, cln, seeds = [], [], [], [], []
    rk = rn = fk = fn = 0
    for a, c in prs:
        w0, w1 = scored(a, rng)
        d = arr(a)[w0:w1] - arr(c)[w0:w1]
        diffs.append(d)
        win.append(float(np.mean(arr(a)[w0:w1])))
        cln.append(float(np.mean(arr(c)[w0:w1])))
        pa = arr(a)[w1:w1 + 30] - arr(c)[w1:w1 + 30]
        post.append(float(pa.mean()) if pa.size else np.nan)
        seeds.append(a["seed"])
        g = arr(a, "gamma")
        if not np.isnan(g).all():
            att = np.array([bool(b.get("attacked")) for b in a["blocks"]])
            sel = att & (np.arange(len(g)) >= w0) & (np.arange(len(g)) < w1) & ~np.isnan(g)
            rk += int((g[sel] < 0.5).sum())
            rn += int(sel.sum())
            gc = arr(c, "gamma")
            selc = (np.arange(len(gc)) >= 5) & ~np.isnan(gc)
            fk += int((gc[selc] < 0.5).sum())
            fn += int(selc.sum())
    L = max(5, 2 * decorrelation_length(diffs))
    per_seed = np.array([d.mean() for d in diffs])
    lo, hi = moving_block_bootstrap(diffs, L, n_boot=4000)
    out = {"n": len(prs), "seeds": seeds, "clean": float(np.mean(cln)), "window": float(np.mean(win)),
           "excess": float(per_seed.mean()), "ci": [lo, hi], "post": float(np.nanmean(post)) if post else None,
           "p": _wilcoxon_exact(per_seed) if len(per_seed) >= 2 and np.any(per_seed != 0) else 1.0,
           "per_seed": per_seed.tolist(), "boot_block": L}
    if rn:
        out.update(rej=rk / rn, rej_k=[rk, rn], rej_ci=list(wilson(rk, rn)))
    if fn:
        out.update(frej=fk / fn, frej_k=[fk, fn], frej_ci=list(wilson(fk, fn)))
    return out


def compare(pa: List[Tuple[dict, dict]], pb: List[Tuple[dict, dict]], metric: str) -> Optional[dict]:
    A = {a["seed"]: (a, c) for a, c in pa}
    B = {a["seed"]: (a, c) for a, c in pb}
    common = sorted(set(A) & set(B))
    if len(common) < 2:
        return None
    series = []
    for s in common:
        (a1, c1), (a2, c2) = A[s], B[s]
        w0, w1 = scored(a1, None)
        v0, v1 = scored(a2, None)
        x1 = arr(a1)[w0:w1] - (arr(c1)[w0:w1] if metric == "excess" else 0)
        x2 = arr(a2)[v0:v1] - (arr(c2)[v0:v1] if metric == "excess" else 0)
        n = min(len(x1), len(x2))
        series.append(x1[:n] - x2[:n])
    per = np.array([s.mean() for s in series])
    L = max(5, 2 * decorrelation_length(series))
    lo95, hi95 = moving_block_bootstrap(series, L, n_boot=4000)
    rng = np.random.default_rng(1)
    boots = []
    for _ in range(4000):   # 90% interval for TOST (same resampling as the 95% one)
        idx = rng.integers(0, len(series), size=len(series))
        vals = []
        for i in idx:
            x = series[i]
            nb = int(np.ceil(x.size / L))
            st = rng.integers(0, x.size, size=nb)
            vals.append(x[(st[:, None] + np.arange(L)[None, :]).reshape(-1)[:x.size] % x.size].mean())
        boots.append(np.mean(vals))
    lo90, hi90 = np.percentile(boots, [5, 95])
    return {"n": len(common), "diff": float(per.mean()), "ci95": [lo95, hi95], "ci90": [float(lo90), float(hi90)],
            "p": _wilcoxon_exact(per) if np.any(per != 0) else 1.0,
            "equivalent": bool(-MARGIN < lo90 and hi90 < MARGIN)}


REGIME_RX = {1: ["online_deepsic", "citadel", "frozen_deepsic", "model_lmmse", "model_ml", "model_kbest"],
             2: ["online_cc", "citadel_cc", "frozen_cc", "model_lmmse", "model_ml", "model_kbest"]}


def regime_scan(plain: List[dict], phase: int = 1) -> Optional[dict]:
    """Group 1R and the pre-registered rule of docs/v3/PHASE1.md: the main regime of Phase 2 is the R1-R5
    regime with the largest ratio r = SER(ML, LS CSI) / min(SER(online DeepSIC), SER(Citadel-Rx)), clean SER
    over blocks 50-99, geometric mean over seeds 0-2; if max r < 1.25, no regime favours the plain DeepSIC
    backbone and Phase 2 first introduces the channel-conditioned backbone and repeats the scan with it."""
    import re
    runs: Dict[Tuple[str, str], Dict[int, dict]] = {}
    for r in plain:
        m = re.match(rf"v3p{phase}R_(R\d\w*?)_(.+)__clean$", r["name"])
        if m:
            runs.setdefault((m.group(1), m.group(2)), {})[r["seed"]] = r
    if not runs:
        return None
    rows: Dict[str, dict] = {}
    for (reg, rx_), by_seed in sorted(runs.items()):
        s1 = [float(np.mean(arr(r)[5:])) for r in by_seed.values()]
        s2 = [max(float(np.mean(arr(r)[50:])), 1e-5) for r in by_seed.values()]
        row = rows.setdefault(reg, {"_seeds": {}})
        row[rx_] = (float(np.mean(s1)), float(np.exp(np.mean(np.log(s2)))))
        row["_seeds"][rx_] = {s: max(float(np.mean(arr(r)[50:])), 1e-5) for s, r in by_seed.items()}
        if rx_ in ("citadel", "citadel_cc"):
            g = np.concatenate([arr(r, "gamma")[5:] for r in by_seed.values()])
            row["frr"] = float(np.mean(g < 0.5))
    best, best_r = None, -1.0
    for reg, row in rows.items():
        sd = row["_seeds"]
        on, ci = REGIME_RX[phase][0], REGIME_RX[phase][1]
        if not all(k in sd for k in ("model_ml", on, ci)):
            continue
        seeds = sorted(set(sd["model_ml"]) & set(sd[on]) & set(sd[ci]))
        lr = [np.log(sd["model_ml"][s] / min(sd[on][s], sd[ci][s])) for s in seeds]
        row["ratio"] = float(np.exp(np.mean(lr))) if lr else float("nan")
        if reg != "R0sed" and lr and row["ratio"] > best_r:
            best, best_r = reg, row["ratio"]
    for row in rows.values():
        row.pop("_seeds", None)
    if best_r >= 1.25:
        decision = f"main regime {best} (r = {best_r:.2f})"
    elif phase == 1:
        decision = (f"no regime reaches r >= 1.25 (best {best}, r = {best_r:.2f}): Phase 2 introduces the channel-"
                    "conditioned backbone and repeats the scan with it")
    else:
        decision = (f"no regime reaches r >= 1.25 (best {best}, r = {best_r:.2f}): the paper is framed as protecting a "
                    "test-time learner, and the main regime is the one with the largest r")
    return {"receivers": REGIME_RX[phase], "rows": rows, "decision": decision, "best": best, "best_ratio": best_r}


def fmt(x, nd=4):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:+.{nd}f}" if isinstance(x, float) and abs(x) < 10 else str(x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, required=True)
    a = ap.parse_args()
    prs, problems, plain = pairs(a.phase)
    ranges = PHASE_RANGES.get(a.phase, {})
    cells = {name: cell(p, ranges.get(name)) for name, p in sorted(prs.items())}
    comps = {}
    other: Dict[int, dict] = {}

    def get(name):
        if name.startswith("p") and ":" in name:
            ph, nm = int(name[1:name.index(":")]), name[name.index(":") + 1:]
            if ph not in other:
                other[ph] = pairs(ph)[0]
            return other[ph].get(nm)
        return prs.get(name)
    for label, x, y, metric in PHASE_COMPARE.get(a.phase, []):
        px, py = get(x), get(y)
        if px and py:
            comps[label] = compare(px, py, metric)
    clean_only = {}
    for r in plain:
        clean_only.setdefault(r["name"], []).append(float(np.mean(arr(r)[5:])))
    lines = [f"# Phase {a.phase}: tables from the run records (scripts/v3/analyze.py)", "",
             f"Pairs: {sum(len(v) for v in prs.values())}; problems: {len(problems)}.", ""]
    if problems:
        lines += ["## Integrity problems (pairs dropped)", ""] + [f"- {p}" for p in problems] + [""]
    lines += ["## Cells", "", "| run | S | clean SER | window SER | excess [95% CI] | after | p (Wilcoxon) | rej. [k/n] | false rej. [k/n] |",
              "|---|---|---|---|---|---|---|---|---|"]
    for name, c in cells.items():
        rej = f"{c['rej']:.3f} [{c['rej_k'][0]}/{c['rej_k'][1]}]" if "rej" in c else "–"
        frej = f"{c['frej']:.3f} [{c['frej_k'][0]}/{c['frej_k'][1]}]" if "frej" in c else "–"
        lines.append(f"| {name} | {c['n']} | {c['clean']:.4f} | {c['window']:.4f} | {fmt(c['excess'])} "
                     f"[{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}] | {fmt(c['post'])} | {c['p']:.3g} | {rej} | {frej} |")
    if clean_only:
        lines += ["", "## Clean-only runs (mean SER over blocks 5+)", "", "| run | S | SER |", "|---|---|---|"]
        for n, v in sorted(clean_only.items()):
            lines.append(f"| {n} | {len(v)} | {np.mean(v):.4f} |")
    if comps:
        lines += ["", f"## Paired comparisons (A - B; TOST margin {MARGIN})", "",
                  "| comparison | S | A - B | 95% CI | 90% CI | p | equivalent |", "|---|---|---|---|---|---|---|"]
        for label, c in comps.items():
            if c:
                lines.append(f"| {label} | {c['n']} | {c['diff']:+.4f} | [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}] | "
                             f"[{c['ci90'][0]:+.4f}, {c['ci90'][1]:+.4f}] | {c['p']:.3g} | {c['equivalent']} |")
    regime = regime_scan(plain, a.phase) if a.phase in REGIME_RX else None
    if regime:
        lines += ["", f"## Regime scan (group {a.phase}R, calibration seeds 0-2, clean)", "",
                  "Clean SER over blocks 5-99 / 50-99 (steady state); Citadel-Rx false rejections over blocks 5-99.", "",
                  "| regime | " + " | ".join(regime["receivers"]) + " | Citadel FRR | ML / best adapting (50-99) |",
                  "|---|" + "---|" * (len(regime["receivers"]) + 2)]
        for reg, row in regime["rows"].items():
            cells_ = [f"{row[r][0]:.4f} / {row[r][1]:.4f}" if r in row else "–" for r in regime["receivers"]]
            lines.append(f"| {reg} | " + " | ".join(cells_) + f" | {row.get('frr', float('nan')):.3f} | {row.get('ratio', float('nan')):.2f} |")
        lines += ["", f"Rule (docs/v3/PHASE{a.phase}.md): {regime['decision']}"]
    os.makedirs(os.path.join(ROOT, "docs", "v3"), exist_ok=True)
    md = os.path.join(ROOT, "docs", "v3", f"PHASE{a.phase}_TABLES.md")
    open(md, "w").write("\n".join(lines) + "\n")
    json.dump({"cells": cells, "comparisons": comps, "problems": problems, "clean_only": clean_only},
              open(os.path.join(ROOT, "results", "v3", f"p{a.phase}_summary.json"), "w"), indent=1)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
