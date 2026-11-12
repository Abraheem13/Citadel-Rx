#!/usr/bin/env python
"""Paired memory displacement under attack (reviewer audit E7, A2, H1).

For every attacked Citadel-Rx record with a matching clean record (same seed and configuration
apart from the attack) whose level snapshots exist (run.save_params=true -> <record>.levels.npz),
this script computes, per block b,

    D_k(b)      = || theta_adv^(k)_b - theta_clean^(k)_b ||    for every level k, and
    D_anchor(b) = || a_adv_b - a_clean_b ||,  a = sum_k w_k theta^(k) (the anchor),

stores them in the attacked JSON (`paired_disp`, `paired_anchor`, `paired_with`) so the analysis
survives without the large .npz files, and draws them (mean over seeds, min-max band) together with

  * the design bound of Theorem 1(iii): D_K(W) <= 2 kappa_K n(W) when the consolidation clip
    kappa (citadel.consol_clip) is enabled -- it needs no measured quantity and holds for any
    attacker and any gate verdicts;
  * the extended structural bound of Theorem 1(i'), valid for unequal verdicts (audit A2):
      D_K(W) <= (Delta(W) + Omega(W)) (1 - (1 - eta_K)^n(W)) + sum_n |s_n - s'_n| ||theta'_K,n - m'_n||,
    (valid for citadel.consol_mean=normalized, where the gated weights of every consolidation sum to one;
    the first-version rule sub-normalised them when the verdict mass was below one),
    with Delta(W) the largest paired displacement of the level-(K-1) states buffered in the window,
    Omega(W) = max_n ||w_n - w'_n||_1 r_n, and (w, s, r, ||theta - m||) logged at every consolidation.

    python scripts/paired_disp.py results/e7paired --out docs/figures/fig_paired_disp
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def match_key(cfg):
    try:   # options added to the code after a record was written: at their defaults
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from citadel_rx.config import Config
        cfg = Config.from_dict(cfg).to_dict()
    except Exception:
        pass
    return json.dumps({k: v for k, v in cfg.items() if k not in ("attack", "run")}, sort_keys=True)


def load_levels(json_path):
    npz = json_path.replace(".json", ".levels.npz")
    if not os.path.exists(npz):
        return None
    try:
        z = np.load(npz)
        K = len([k for k in z.files if k.startswith("level")])
        return [z[f"level{k + 1}"].astype(np.float32) for k in range(K)]
    except Exception as e:   # e.g. written while the disk was full
        print(f"   skipped {os.path.basename(npz)}: cannot be read ({type(e).__name__}: {e})")
        return None


def consolidation_events(rec, level):
    ev = []
    for b in rec["blocks"]:
        for e in (b.get("consolidations") or []):
            if e["level"] == level:
                ev.append(e)
    return ev


def _s_eff(e, clip):
    """Step actually taken: the logged step s, scaled down when the consolidation clip was active."""
    s = float(e.get("s", 0.0))
    if e.get("clipped") and clip > 0 and float(e.get("inc_norm", 0.0)) > 0:
        s *= clip / float(e["inc_norm"])
    return s


def extended_bound(adv, cln, D_prev, eta_K, K, w0, w1):
    """Extended structural bound (A2) evaluated at every block of the window. With the clip the
    effective step s_eff = s * min(1, kappa / ||increment||) <= s <= eta_K replaces s."""
    cl = adv["config"]["citadel"].get("consol_clip") or []
    clip = float(cl[K - 2]) if len(cl) >= K - 1 else 0.0
    ea, ec = consolidation_events(adv, K), consolidation_events(cln, K)
    pairs = [(a, c) for a, c in zip(ea, ec) if w0 <= a["block"] < w1 and a["block"] == c["block"]]
    out = np.zeros(w1 - w0)
    if D_prev is None:
        return out
    delta = np.maximum.accumulate(D_prev[w0:w1])
    n_cons, omega, extra = 0, 0.0, 0.0
    j = 0
    for t in range(w1 - w0):
        b = w0 + t
        while j < len(pairs) and pairs[j][0]["block"] <= b:
            a, c = pairs[j]
            wa, wc = np.asarray(a.get("w", [])), np.asarray(c.get("w", []))
            if wa.size and wa.size == wc.size:
                omega = max(omega, float(np.abs(wa - wc).sum()) * float(c.get("r", 0.0)))
            extra += abs(_s_eff(a, clip) - _s_eff(c, clip)) * float(c.get("d_to_mean", 0.0))
            n_cons += 1
            j += 1
        out[t] = (delta[t] + omega) * (1 - (1 - eta_K) ** n_cons) + extra
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--clean", nargs="*", default=None, help="folder(s) of the clean twins (default: same folder)")
    ap.add_argument("--out", default="docs/figures/fig_paired_disp")
    args = ap.parse_args()
    recs = {fn: json.load(open(fn)) for fn in glob.glob(os.path.join(args.folder, "*.json"))}
    for folder in args.clean or []:   # several machines' clean folders: a record is paired with the twin of its own machine
        recs.update({fn: json.load(open(fn)) for fn in glob.glob(os.path.join(folder, "*.json"))})
    # clean twins; two clean runs with the same settings (one saved with snapshots, one without) are
    # the same deterministic run, so prefer the one whose snapshot file exists
    clean = {}
    for fn, r in sorted(recs.items(), key=lambda kv: os.path.exists(kv[0].replace(".json", ".levels.npz"))):
        if r["config"]["attack"]["type"] == "none":
            clean[(match_key(r["config"]), r["seed"], r.get("machine"))] = fn
    results = []
    for fn, r in recs.items():
        c = r["config"]
        if c["attack"]["type"] == "none" or c["receiver"]["type"] != "citadel":
            continue
        cfn = clean.get((match_key(c), r["seed"], r.get("machine")))
        if cfn is None:
            continue
        la, lc = load_levels(fn), load_levels(cfn)
        K_rec = len(r.get("self_disp") or []) or len(c["citadel"]["periods"])
        if la is not None and lc is not None and not (len(la) == len(lc) == K_rec):
            print(f"   skipped {os.path.basename(fn)}: snapshot files hold {len(la)} and {len(lc)} levels, "
                  f"the receiver has {K_rec} (a file written while the disk was full); re-run it")
            la = None
        if la is None or lc is None:
            if "paired_disp" in r:   # already computed on the machine that had the snapshots
                results.append((r, recs[cfn]))
            continue
        n = min(la[0].shape[0], lc[0].shape[0])
        r["paired_disp"] = [np.linalg.norm(a[:n] - b[:n], axis=1).tolist() for a, b in zip(la, lc)]
        w = np.asarray(c["citadel"]["level_weights"][: len(la) - 1], dtype=float)
        w = w / w.sum()
        anc_a = sum(wk * la[k + 1][:n] for k, wk in enumerate(w))
        anc_c = sum(wk * lc[k + 1][:n] for k, wk in enumerate(w))
        r["paired_anchor"] = np.linalg.norm(anc_a - anc_c, axis=1).tolist()
        # how far each run's levels moved from their common state at the window start: the paired
        # displacement is at most the sum of the two (triangle inequality), so a small `adv` and a
        # `clean` close to D_k mean the attacked run stood still while the clean run followed the channel
        w0 = int((r["summary"].get("attack_window") or [c["attack"]["start_block"]])[0])
        r["paired_move"] = {"adv": [np.linalg.norm(a[:n] - a[w0], axis=1).tolist() for a in la],
                            "clean": [np.linalg.norm(b[:n] - b[w0], axis=1).tolist() for b in lc]}
        r["paired_with"] = os.path.basename(cfn)
        json.dump(r, open(fn, "w"))
        results.append((r, recs[cfn]))
    if not results:
        print("no attacked/clean pairs with snapshots or stored paired displacement")
        return
    from paper_style import panel_title, save
    import matplotlib.pyplot as plt
    groups = {}
    for r, cr in results:
        at = r["config"]["attack"]
        key = (at["type"], at["sir_db"], tuple(r["config"]["citadel"]["consol_clip"]),
               at.get("a3_eps_small") if at["type"] == "a3star" else None, r["config"]["citadel"].get("drift_guard", 0.0))
        groups.setdefault(key, []).append((r, cr))
    rows = ["| attack | SIR | clip kappa | seeds | max D_K in window | design bound 2 kappa_K n(W) | extended structural bound (A2) | max D_anchor |",
            "|---|---|---|---|---|---|---|---|"]
    for (atk, sir, clip, eps, guard), grp in sorted(groups.items(), key=lambda kv: str(kv[0])):
        r0 = grp[0][0]
        c = r0["config"]
        K = len(r0["paired_disp"])
        w0, w1 = r0["summary"].get("attack_window", [c["attack"]["start_block"], c["attack"]["end_block"]])
        n_blocks = min(len(r["paired_disp"][0]) for r, _ in grp)
        w1 = min(w1, n_blocks)
        D = np.array([[r["paired_disp"][k][:n_blocks] for k in range(K)] for r, _ in grp])   # (S, K, n)
        A = np.array([r["paired_anchor"][:n_blocks] for r, _ in grp])
        eta_K = c["citadel"]["level_lr"][K - 2] if K > 1 else 1.0
        C_K = c["citadel"]["periods"][K - 1]
        W = np.arange(w1 - w0)
        n_cons = np.floor((w0 + W + 1) / C_K) - np.floor(w0 / C_K)
        design = 2 * clip[K - 2] * n_cons if (len(clip) >= K - 1 and clip[K - 2] > 0) else None
        ext = np.array([extended_bound(r, cr, np.array(r["paired_disp"][K - 2]), eta_K, K, w0, w1) for r, cr in grp]).max(0)
        fig, ax = plt.subplots(1, 1, figsize=(3.45, 2.3))
        ax.axvspan(w0, w1, color="0.92", zorder=0)
        styles = [("level 1 (fast)", "#0072B2", "-"), ("level 2", "#56B4E9", "-"), ("level 3 (slowest)", "#003F5C", "-")]
        for k in range(K):
            lab, col, ls = styles[min(k, 2)]
            m = D[:, k].mean(0)
            ax.plot(np.arange(n_blocks), m, color=col, ls=ls, lw=1.0, label=lab)
            ax.fill_between(np.arange(n_blocks), D[:, k].min(0), D[:, k].max(0), color=col, alpha=0.15, lw=0)
        ax.plot(np.arange(n_blocks), A.mean(0), color="#D55E00", lw=1.1, ls="--", label="anchor")
        if design is not None:
            ax.plot(w0 + W, design, color="k", lw=0.9, ls=":", label=r"design bound on level $K$, $2\kappa_K n(W)$")
        ax.plot(w0 + W, ext, color="0.4", lw=0.9, ls="-.", label=r"structural bound on level $K$")
        ax.set_xlabel("block"); ax.set_ylabel(r"paired displacement $\|\theta_{\rm adv}-\theta_{\rm clean}\|$")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, fontsize=6.5)
        fig.subplots_adjust(left=0.17, right=0.98, top=0.97, bottom=0.42)
        tag = f"{atk}_sir{sir:g}" + (f"_e{eps:g}" if eps is not None else "") + ("_guard" if guard else "") + \
            ("_clip" if design is not None else "")
        save(fig, os.path.basename(args.out) + "_" + tag)
        rows.append(f"| {atk}{f' e={eps:g}' if eps is not None else ''}{' guard' if guard else ''} | {sir:g} | {list(clip) or '-'} | {len(grp)} | {D[:, K - 1, w0:w1].max():.2f} | "
                    f"{(design.max() if design is not None else float('nan')):.2f} | {ext.max():.2f} | {A[:, w0:w1].max():.2f} |")
    print("\n".join(rows))
    md = os.path.join("docs", f"PAIRED_DISP_{os.path.basename(os.path.normpath(args.folder))}.md")
    open(md, "w").write("# Paired displacement (scripts/paired_disp.py)\n\n" + "\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
