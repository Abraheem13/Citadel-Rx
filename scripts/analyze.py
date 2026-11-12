#!/usr/bin/env python
"""Per-experiment analysis tables (mean ± std over seeds) printed as Markdown.

    python scripts/analyze.py e2 e1 ablate e7 e4
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np

RX_ORDER = ["lmmse", "online_deepsic", "meta_deepsic", "drift_deepsic", "medbn_deepsic", "titans_single", "citadel"]


def load(exp):
    out = []
    for fn in glob.glob(f"results/{exp}/*.json"):
        r = json.load(open(fn))
        out.append(r)
    return out


def ms(vals, fmt="{:.4f}"):
    v = np.array([x for x in vals if x is not None], dtype=float)
    if v.size == 0:
        return "–"
    s = fmt.format(v.mean())
    if v.size > 1:
        s += "±" + fmt.format(v.std(ddof=1))
    return s


def e2(exp="e2"):
    recs = load(exp)
    cells = defaultdict(list)
    for r in recs:
        c = r["config"]
        cells[(c["channel"]["fading"], c["receiver"]["type"], c["channel"]["snr_db"])].append(r["summary"]["ser_mean"])
    snrs = sorted({k[2] for k in cells})
    for fad in sorted({k[0] for k in cells}):
        print(f"\n### {exp}: clean SER vs SNR, fading = {fad} (mean±std over seeds)\n")
        print("| receiver | " + " | ".join(f"{s:g} dB" for s in snrs) + " |")
        print("|---|" + "---|" * len(snrs))
        for rx in RX_ORDER:
            row = [ms(cells.get((fad, rx, s), [])) for s in snrs]
            print(f"| {rx} | " + " | ".join(row) + " |")
        # dB gap of citadel to the best receiver at each SNR (interpolated in log-SER)
        best = {s: min(np.mean(cells[(fad, rx, s)]) for rx in RX_ORDER if (fad, rx, s) in cells) for s in snrs}
        cit = {s: np.mean(cells[(fad, "citadel", s)]) for s in snrs if (fad, "citadel", s) in cells}
        if len(cit) >= 2:
            print("\nCitadel SER / best SER per SNR: " + ", ".join(f"{s:g}: {cit[s] / best[s]:.2f}" for s in cit))


def e1():
    recs = load("e1")
    cells = defaultdict(list)
    for r in recs:
        c = r["config"]
        if c["attack"]["type"] != "a1":
            continue
        cells[(c["channel"]["linear"], c["receiver"]["type"], c["attack"]["knowledge"], c["attack"]["sir_db"])].append(r["summary"])
    sirs = sorted({k[3] for k in cells})
    for lin in (True, False):
        print(f"\n### E1 reproduction — {'linear' if lin else 'nonlinear (tanh PA)'} channel, SER in attack window\n")
        print("| receiver | attacker | pre | " + " | ".join(f"SIR {s:g}" for s in sirs) + " | post (SIR 0) | recovery (SIR 0) |")
        print("|---|---|---|" + "---|" * (len(sirs) + 2))
        for rx in ["online_deepsic", "meta_deepsic", "citadel"]:
            for know in ("whitebox", "transfer"):
                row = [ms([s["ser_attack"] for s in cells.get((lin, rx, know, sir), [])]) for sir in sirs]
                pre = ms([s["ser_pre"] for sir in sirs for s in cells.get((lin, rx, know, sir), [])])
                post = ms([s["ser_post"] for s in cells.get((lin, rx, know, 0.0), [])])
                rec = ms([s["recovery_blocks"] for s in cells.get((lin, rx, know, 0.0), [])], "{:.1f}")
                if any(x != "–" for x in row):
                    print(f"| {rx} | {know} | {pre} | " + " | ".join(row) + f" | {post} | {rec} |")


def ablate():
    recs = load("ablate")
    cells = defaultdict(list)
    for r in recs:
        tag = r["name"].replace("ablate_", "")
        cells[tag].append(r["summary"])
    print("\n### Ablations — Citadel variants under white-box A1 at SIR 0 dB (3 seeds)\n")
    print("| variant | pre | attack window | post | recovery | rejection of attacked | false rejection |")
    print("|---|---|---|---|---|---|---|")
    order = ["K1", "K2", "K4", "misaligned", "nogate", "g1", "g2", "g3", "last_only", "plain_gd", "adam_no_delta",
             "fixed_eta", "no_anchor", "jump_anchor", "no_fallback", "reject_keep"]
    for tag in order:
        v = cells.get(tag, [])
        if not v:
            continue
        print(f"| {tag} | {ms([s['ser_pre'] for s in v])} | {ms([s['ser_attack'] for s in v])} | {ms([s['ser_post'] for s in v])} | "
              f"{ms([s['recovery_blocks'] for s in v], '{:.1f}')} | {ms([s.get('gate_reject_rate_attacked') for s in v], '{:.2f}')} | "
              f"{ms([s.get('gate_false_reject_rate_clean') for s in v], '{:.3f}')} |")


def e7():
    recs = load("e7")
    cells = defaultdict(list)
    for r in recs:
        c = r["config"]
        cells[(tuple(c["citadel"]["gates"]), c["attack"]["gate_aware_weight"])].append(r["summary"])
    print("\n### E7 — gate-aware adaptive attacker at SIR 10 dB\n")
    print("| gates | penalty weight | n | attack window | post | rejection of attacked | false rejection |")
    print("|---|---|---|---|---|---|---|")
    for k in sorted(cells, key=lambda x: (len(x[0]), x[0], x[1])):
        v = cells[k]
        print(f"| {','.join(k[0]) or 'none'} | {k[1]:g} | {len(v)} | {ms([s['ser_attack'] for s in v])} | {ms([s['ser_post'] for s in v])} | "
              f"{ms([s.get('gate_reject_rate_attacked') for s in v], '{:.2f}')} | {ms([s.get('gate_false_reject_rate_clean') for s in v], '{:.3f}')} |")


def e3(exp="e3nl"):
    recs = load(exp)
    cells = defaultdict(list)
    for r in recs:
        c = r["config"]
        if c["attack"]["type"] != "a1":
            continue
        cells[(c["receiver"]["type"], c["attack"]["knowledge"], c["attack"]["sir_db"])].append(r["summary"])
    sirs = sorted({k[2] for k in cells})
    knows = sorted({k[1] for k in cells})
    for know in knows:
        print(f"\n### {exp}: {know} A1, SER in attack window (mean±std over seeds)\n")
        print("| receiver | pre | " + " | ".join(f"SIR {s:g}" for s in sirs) + " | post (0 dB) | recovery (0 dB) | rejection | false rej. |")
        print("|---|---|" + "---|" * (len(sirs) + 4))
        for rx in RX_ORDER:
            row = [ms([s["ser_attack"] for s in cells.get((rx, know, sir), [])]) for sir in sirs]
            if all(x == "–" for x in row):
                continue
            allc = [s for sir in sirs for s in cells.get((rx, know, sir), [])]
            print(f"| {rx} | {ms([s['ser_pre'] for s in allc])} | " + " | ".join(row)
                  + f" | {ms([s['ser_post'] for s in cells.get((rx, know, 0.0), [])])} | {ms([s['recovery_blocks'] for s in cells.get((rx, know, 0.0), [])], '{:.1f}')} | "
                  f"{ms([s.get('gate_reject_rate_attacked') for s in allc], '{:.2f}')} | {ms([s.get('gate_false_reject_rate_clean') for s in allc], '{:.3f}')} |")


def e4():
    recs = load("e4")
    print("\n### E4 — A2 targeted drift spoofing of user 0 (Jakes fD·Tb = 0.05), SIR 0 dB\n")
    print("| receiver | gates | pre SER | attack window SER (all users) | user-0 SER in window | other users' SER in window | rejection |")
    print("|---|---|---|---|---|---|---|")
    cells = defaultdict(list)
    for r in recs:
        c = r["config"]
        a0, a1 = c["attack"]["start_block"], c["attack"]["end_block"]
        win = r["blocks"][a0:a1]
        u0 = np.mean([b["ser_user"][0] for b in win])
        oth = np.mean([np.mean(b["ser_user"][1:]) for b in win])
        cells[(c["receiver"]["type"], tuple(c["citadel"]["gates"]))].append((r["summary"], u0, oth))
    for k in sorted(cells):
        v = cells[k]
        gates = ",".join(k[1]) if k[0] == "citadel" else "–"
        print(f"| {k[0]} | {gates} | {ms([s['ser_pre'] for s, _, _ in v])} | {ms([s['ser_attack'] for s, _, _ in v])} | "
              f"{ms([u for _, u, _ in v])} | {ms([o for _, _, o in v])} | {ms([s.get('gate_reject_rate_attacked') for s, _, _ in v], '{:.2f}')} |")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for exp in sys.argv[1:] or ["e2", "e1", "ablate", "e7", "e4"]:
        {"e2": e2, "e2nl": lambda: e2("e2nl"), "e2cost": lambda: e2("e2cost"), "e1": e1, "ablate": ablate,
         "e7": e7, "e4": e4, "e3": lambda: e3("e3"), "e3nl": lambda: e3("e3nl"), "e3cost": lambda: e3("e3cost")}[exp]()
