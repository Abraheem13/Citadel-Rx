#!/usr/bin/env python
"""Result figures of the ten-page journal version (paper/main.tex), from the run records (test seeds).

  fig_j_headline   white-box A1 at SIR 0 dB: (a) SER per block of one test seed, attacked runs and
                   clean twins; (b) gate verdicts of CRC-Rollback and Citadel-Rx on that seed;
                   (c) excess SER per seed with the mean and its 95% interval; (d) excess SER against
                   the SIR and under transfer, with 95% intervals.
  fig_j_mechanism  CRC pass fraction of the gate's reference (attacked run and clean twin) and of the
                   poisoned fast level, blocks counted from each seed's attack start, mean over seeds:
                   (a) CRC-Rollback, (b) Citadel-Rx with LMMSE alone.
  fig_j_retention  (a) paired displacement of every level and of the anchor under A1 at SIR 0 dB with
                   the design and structural bounds on the slowest level; (b) A3* over 400 blocks,
                   slowest level, four perturbation settings, design bound.
  fig_j_umi        NR LDPC code blocks over TR 38.901 UMi drops: (a) clean BLER per block; (b) excess
                   BLER against the attacker's distance, with 95% intervals.

Every plotted value is computed by the functions that write paper/numbers.tex and paper/tables
(revision_numbers.cell, window, ser, twins, twin_of; paired_disp.extended_bound), on the same pairs of
attacked runs and clean twins. After drawing, the script formats the plotted values with the
formatters of revision_numbers and compares them with the macros in paper/numbers.tex; it exits with
status 1 if one differs (run revision_numbers.py first, as `make paper` does).

    python scripts/paper_figures.py [--seed 10]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import revision_numbers as rn  # noqa: E402
from paired_disp import extended_bound  # noqa: E402
from paper_style import panel_title, save  # noqa: E402
from revision_figures import C, LAB  # noqa: E402  (receiver colors and names of the existing figures)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

LAB = dict(LAB, lmmse="LMMSE")
SHADE = "0.92"          # attack window
CHECKS: list = []       # (figure, what, macro key, plotted value formatted as the macro)


def check(fig: str, what: str, key: str, text: str) -> None:
    CHECKS.append((fig, what, key, text))


def rowmajor(handles, ncol):
    """Matplotlib fills legend columns first; reorder so the entries read row by row."""
    rows = [handles[i:i + ncol] for i in range(0, len(handles), ncol)]
    return [r[j] for j in range(ncol) for r in rows if j < len(r)]


def shade(ax, w0, w1):
    ax.axvspan(w0, w1, color=SHADE, lw=0, zorder=0)


# ------------------------------------------------------------------------------------------- Fig. 4
HEAD_RX = ["citadel", "crc_rollback", "online_deepsic", "meta_deepsic", "online_select"]
SIR_CELLS = [("wb_sir-10", "$-10$"), ("wb_sir0", "$0$"), ("wb_sir10", "$+10$"), ("tr_sir0", "Tr. $0$")]


def headline(seed: int) -> None:
    cells = {(rx, cl): rn.cell("rev_p1", f"p1_{rx}__{cl}", rn.CLEAN_ALL) for rx in HEAD_RX for cl, _ in SIR_CELLS}
    if any(c is None for c in cells.values()):
        print("fig_j_headline: records missing for", [k for k, c in cells.items() if c is None])
        return
    fig, (aa, ab, ac, ad) = plt.subplots(1, 4, figsize=(7.16, 2.2))
    # (a), (b): one test seed, every block
    rows = {}
    for rx in HEAD_RX[:4]:
        pr = [p for p in cells[(rx, "wb_sir0")]["pairs"] if p[0]["seed"] == seed]
        if pr:
            rows[rx] = pr[0]
    w0, w1 = rn.window(rows["citadel"][0])
    for ax in (aa, ab):
        shade(ax, w0, w1)
    for rx, (a, c) in rows.items():
        x = np.arange(len(a["blocks"]))
        aa.semilogy(x, np.maximum(rn.ser(a), 1e-4), color=C[rx], lw=0.9)
        aa.semilogy(x, np.maximum(rn.ser(c), 1e-4), color=C[rx], lw=0.7, ls="--")
    aa.set_ylim(1e-4, 1.5)
    aa.set_xlabel("block index")
    aa.set_ylabel("SER")
    panel_title(aa, f"(a) SER per block, seed {seed}")
    for rx in ("crc_rollback", "citadel"):
        a = rows[rx][0]
        g = np.array([b["gamma"] if b.get("gamma") is not None else np.nan for b in a["blocks"]])
        ab.step(np.arange(g.size), g, where="mid", color=C[rx], lw=0.9)
    ab.axhline(0.5, color="k", lw=0.6, ls=":")
    ab.set_ylim(-0.05, 1.05)
    ab.set_xlabel("block index")
    ab.set_ylabel(r"gate verdict $\gamma_b$")
    panel_title(ab, "(b) Gate verdict")
    # (c): excess SER per seed at the headline cell, mean and 95% interval
    for i, rx in enumerate(HEAD_RX):
        c = cells[(rx, "wb_sir0")]
        y = np.array(c["seed_means"])
        ac.scatter(i + np.linspace(-0.22, 0.22, y.size), y, s=5, color=C[rx], zorder=3, lw=0)
        eb = ac.errorbar(i, c["excess"], yerr=[[c["excess"] - c["ci"][0]], [c["ci"][1] - c["excess"]]], fmt="_",
                    color="k", ms=7, lw=0.8, capsize=2, zorder=4)
        k = f"p1.{rx}.wb0"
        check("fig_j_headline (c)", f"{LAB[rx]}, mean", k + ".excess", rn.f_sig(c["excess"]))
        check("fig_j_headline (c)", f"{LAB[rx]}, 95% interval", k + ".ci", rn.f_ci(c["ci"]))
        check("fig_j_headline (c)", f"{LAB[rx]}, smallest seed", k + ".smin", rn.f_sig(min(c["seed_means"])))
        check("fig_j_headline (c)", f"{LAB[rx]}, largest seed", k + ".smax", rn.f_sig(max(c["seed_means"])))
        check("fig_j_headline (c)", f"{LAB[rx]}, seeds", k + ".n", str(c["n"]))
    ac.set_yscale("symlog", linthresh=1e-2)
    lo = min(0.0, min(min(cells[(rx, "wb_sir0")]["seed_means"]) for rx in HEAD_RX))
    ac.set_ylim(1.5 * lo, 1.5)
    ac.axhline(0, color="k", lw=0.5)
    ac.set_xticks(range(len(HEAD_RX)))
    ac.set_xticklabels([])
    ac.tick_params(axis="x", length=0)
    ac.set_xlim(-0.6, len(HEAD_RX) - 0.4)
    ac.set_xlabel("receiver")
    ac.set_ylabel("excess SER")
    ac.grid(axis="x", visible=False)
    panel_title(ac, "(c) Excess per seed")
    # (d): excess SER against the SIR (white-box) and under transfer, 95% intervals
    xpos = [0, 1, 2, 3.3]
    for i, rx in enumerate(HEAD_RX):
        off = (i - 2) * 0.1
        ex = [cells[(rx, cl)]["excess"] for cl, _ in SIR_CELLS]
        lo_ = [cells[(rx, cl)]["ci"][0] for cl, _ in SIR_CELLS]
        hi_ = [cells[(rx, cl)]["ci"][1] for cl, _ in SIR_CELLS]
        for j in range(4):
            open_ = SIR_CELLS[j][0].startswith("tr")
            ad.errorbar(xpos[j] + off, ex[j], yerr=[[ex[j] - lo_[j]], [hi_[j] - ex[j]]], fmt="o", ms=3,
                        color=C[rx], mfc="white" if open_ else C[rx], mew=0.8, lw=0.7, capsize=1.2, zorder=3)
        ad.plot([x + off for x in xpos[:3]], ex[:3], color=C[rx], lw=0.7, zorder=2)
        for (cl, _), e in zip(SIR_CELLS, ex):
            if cl != "wb_sir0":
                check("fig_j_headline (d)", f"{LAB[rx]}, {cl}", f"p1.{rx}.{rn.CK[cl]}.excess", rn.f_sig(e))
    ad.set_yscale("log")
    ad.set_xticks(xpos)
    ad.set_xticklabels([l for _, l in SIR_CELLS])
    ad.set_xlim(-0.5, 3.8)
    ad.set_xlabel("SIR (dB)")
    ad.set_ylabel("excess SER")
    panel_title(ad, "(d) Excess vs. SIR")
    eb.set_label("mean, 95% interval (c)")
    hs = [Line2D([], [], color=C[rx], marker="o", ms=3, lw=1.0, label=LAB[rx]) for rx in HEAD_RX] + [
        Line2D([], [], color="k", lw=0.9, label="attacked run (a)"),
        Line2D([], [], color="k", lw=0.7, ls="--", label="clean twin (a)"),
        Line2D([], [], color="k", lw=0.6, ls=":", label=r"$\gamma_b=1/2$ (b)"),
        eb,
        Line2D([], [], color="k", marker="o", ms=3, mfc="white", lw=0, label="transfer (d)")]
    fig.legend(handles=rowmajor(hs, 5), loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=5, fontsize=7,
               columnspacing=0.9, handlelength=1.6)
    fig.subplots_adjust(left=0.065, right=0.995, top=0.9, bottom=0.36, wspace=0.5)
    save(fig, "fig_j_headline")
    plt.close(fig)
    print(f"fig_j_headline: seed {seed}, window {w0}-{w1}")


# ------------------------------------------------------------------------------------------- Fig. 5
def mechanism() -> None:
    spec = [("crc_rollback", "crc", "(a) CRC-Rollback"), ("citadel", "cit", "(b) Citadel-Rx")]
    cells = {rx: rn.cell("rev_p1", f"p1_{rx}__wb_sir0", rn.CLEAN_ALL) for rx, _, _ in spec}
    if any(c is None for c in cells.values()):
        print("fig_j_mechanism: records missing")
        return
    fig, axs = plt.subplots(2, 1, figsize=(3.45, 2.9), sharex=True)
    rel = np.arange(-10, 50)
    for ax, (rx, tag, title) in zip(axs, spec):
        c = cells[rx]

        def curve(field, attacked):
            M = []
            for a, cl in c["pairs"]:
                w0 = rn.window(a)[0]
                r = a if attacked else cl
                M.append([float(r["blocks"][w0 + t][field]) for t in rel])
            return np.array(M).mean(0)
        shade(ax, 0, 40)
        ref_a, ref_c, nn_a = curve("pass_mm", True), curve("pass_mm", False), curve("pass_nn", True)
        ax.plot(rel, ref_a, color=C[rx], lw=1.0)
        ax.plot(rel, ref_c, color=C[rx], lw=0.9, ls="--")
        ax.plot(rel, nn_a, color=C[rx], lw=1.0, ls=":")
        win = (rel >= 0) & (rel < 40)
        assert all(rn.window(a)[1] - rn.window(a)[0] == 40 for a, _ in c["pairs"])
        check("fig_j_mechanism", f"{LAB[rx]}, reference, attacked", f"c1.{tag}.refatt", f"{ref_a[win].mean():.2f}")
        check("fig_j_mechanism", f"{LAB[rx]}, reference, clean twin", f"c1.{tag}.refcln", f"{ref_c[win].mean():.2f}")
        check("fig_j_mechanism", f"{LAB[rx]}, fast level, attacked", f"c1.{tag}.nnatt", f"{nn_a[win].mean():.2f}")
        if rx == "citadel":
            lm = curve("pass_lmmse", True)
            ax.plot(rel, lm, color=C["lmmse"], lw=0.9)
            check("fig_j_mechanism", "LMMSE alone, attacked", "gate.lmmseatt", f"{lm[win].mean():.2f}")
            check("fig_j_mechanism", "LMMSE alone, clean twin (not drawn)", "gate.lmmsecln",
                  f"{curve('pass_lmmse', False)[win].mean():.2f}")
        ax.set_ylim(-0.03, 1.03)
        ax.set_ylabel("CRC pass fraction")
        panel_title(ax, title)
    axs[1].set_xlabel("block index relative to the attack start")
    axs[1].set_xlim(-10, 49)
    hs = [Line2D([], [], color="k", lw=1.0, label="reference, attacked run"),
          Line2D([], [], color="k", lw=0.9, ls="--", label="reference, clean twin"),
          Line2D([], [], color="k", lw=1.0, ls=":", label="fast level, attacked run"),
          Line2D([], [], color=C["lmmse"], lw=0.9, label="LMMSE alone, attacked run (b)")]
    fig.legend(handles=rowmajor(hs, 2), loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=2, fontsize=6.5)
    fig.subplots_adjust(left=0.15, right=0.98, top=0.93, bottom=0.27, hspace=0.32)
    save(fig, "fig_j_mechanism")
    plt.close(fig)
    print("fig_j_mechanism: seeds", cells["citadel"]["seeds"])


# ------------------------------------------------------------------------------------------- Fig. 6
def retention() -> None:
    c = rn.cell("rev_p4_paired", "p4_citadel__sir0", rn.CLEAN_ALL)
    if c is None or not all("paired_disp" in a for a, _ in c["pairs"]):
        print("fig_j_retention: paired displacement missing in rev_p4_paired")
        return
    fig, (aa, ab) = plt.subplots(2, 1, figsize=(3.45, 4.0), gridspec_kw={"height_ratios": [1, 1]})
    # (a) A1 at SIR 0 dB: every level, the anchor, and both bounds on the slowest level
    a0 = c["pairs"][0][0]
    cfg = a0["config"]["citadel"]
    K = len(a0["paired_disp"])
    n = min(len(a["paired_disp"][0]) for a, _ in c["pairs"])
    w0, w1 = rn.window(a0)
    w1 = min(w1, n)
    assert all(rn.window(a) == (w0, rn.window(a0)[1]) for a, _ in c["pairs"])
    D = np.array([[a["paired_disp"][k][:n] for k in range(K)] for a, _ in c["pairs"]])   # (seeds, K, blocks)
    A = np.array([a["paired_anchor"][:n] for a, _ in c["pairs"]])
    eta_K, CK, kap = cfg["level_lr"][K - 2], cfg["periods"][K - 1], cfg["consol_clip"][K - 2]
    W = np.arange(w0, w1)
    design = 2 * kap * (np.floor((W + 1) / CK) - np.floor(w0 / CK))
    ext = np.array([extended_bound(a, cl, np.array(a["paired_disp"][K - 2]), eta_K, K, w0, w1) for a, cl in c["pairs"]])
    shade(aa, w0, w1)
    styles = [("level 1 (fast)", "#0072B2"), ("level 2", "#56B4E9"), (f"level $K={K}$ (slowest)", "#003F5C")]
    x = np.arange(n)
    for k in range(K):
        lab, col = styles[min(k, 2)]
        aa.plot(x, D[:, k].mean(0), color=col, lw=1.0, label=lab)
        aa.fill_between(x, D[:, k].min(0), D[:, k].max(0), color=col, alpha=0.15, lw=0)
    aa.plot(x, A.mean(0), color="#D55E00", lw=1.0, ls="--", label="anchor")
    aa.plot(W, design, color="k", lw=0.9, ls=":", label=r"design bound on $D_K$")
    aa.plot(W, ext.max(0), color="0.4", lw=0.9, ls="-.", label=r"structural bound on $D_K$")
    aa.set_xlim(0, n - 1)
    aa.set_xlabel("block index")
    aa.set_ylabel(r"$\|\theta_{\rm adv}-\theta_{\rm clean}\|$")
    panel_title(aa, r"(a) A1, SIR 0 dB, every level")
    aa.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=3, fontsize=6.5, handlelength=1.6,
              columnspacing=0.8)
    check("fig_j_retention (a)", "largest D_K in the window, mean over seeds", "ret.p4sir0.DK",
          f"{D[:, K - 1, w0:w1].max(1).mean():.2f}")
    check("fig_j_retention (a)", "design bound at the window end", "ret.p4sir0.design", f"{design.max():.1f}")
    check("fig_j_retention (a)", "structural bound, mean of the seed maxima", "ret.p4sir0.struct", f"{ext.max(1).mean():.1f}")
    check("fig_j_retention (a)", "largest anchor displacement, mean over seeds", "ret.p4sir0.anchor",
          f"{A[:, w0:w1].max(1).mean():.2f}")
    check("fig_j_retention (a)", "seeds", "ret.p4sir0.nsnap", str(len(c["pairs"])))
    # (b) A3* over 400 blocks: slowest level for each perturbation size, design bound
    cfgs = [("0.05", "", "5%", "#56B4E9"), ("0.2", "", "20%", "#0072B2"), ("0.5", "", "50%", "#003F5C"),
            ("0.5", "_guard", "50%, drift guard", "#D55E00")]
    drawn = None
    for e, g, lab, col in cfgs:
        cc = rn.cell("rev_p8_drift", f"p8_a3star_e{e}{g}__long", rn.CLEAN_ALL)
        if cc is None or not all("paired_disp" in a for a, _ in cc["pairs"]):
            continue
        b0 = cc["pairs"][0][0]
        Kb = len(b0["paired_disp"])
        nb = min(len(a["paired_disp"][Kb - 1]) for a, _ in cc["pairs"])
        Db = np.array([a["paired_disp"][Kb - 1][:nb] for a, _ in cc["pairs"]])
        ab.plot(np.arange(nb), Db.mean(0), color=col, lw=1.0, label=f"size {lab}")
        ab.fill_between(np.arange(nb), Db.min(0), Db.max(0), color=col, alpha=0.15, lw=0)
        v0, v1 = rn.window(b0)
        key = "ret.p8e" + e.replace(".", "") + g.replace("_", "")
        check("fig_j_retention (b)", f"{lab}: largest D_K in the window, mean over seeds", key + ".DK",
              f"{Db[:, v0:min(v1, nb)].max(1).mean():.2f}")
        check("fig_j_retention (b)", f"{lab}: seeds", key + ".nsnap", str(len(cc["pairs"])))
        drawn = (b0, v0, min(v1, nb), key)
    if drawn is not None:
        b0, v0, v1, key = drawn
        cb = b0["config"]["citadel"]
        Kb = len(b0["paired_disp"])
        Vb = np.arange(v0, v1)
        des_b = 2 * cb["consol_clip"][Kb - 2] * (np.floor((Vb + 1) / cb["periods"][Kb - 1]) - np.floor(v0 / cb["periods"][Kb - 1]))
        ab.plot(Vb, des_b, color="k", lw=0.9, ls=":", label=r"design bound on $D_K$")
        shade(ab, v0, v1)
        check("fig_j_retention (b)", "design bound at the window end", key + ".design", f"{des_b.max():.1f}")
    ab.set_xlabel("block index")
    ab.set_ylabel(r"$D_K$, slowest level")
    ab.set_xlim(0, 400)
    ab.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=3, fontsize=6.5, handlelength=1.6,
              columnspacing=0.8)
    panel_title(ab, r"(b) A3$^\ast$ over 400 blocks, slowest level")
    fig.subplots_adjust(left=0.15, right=0.98, top=0.95, bottom=0.17, hspace=0.95)
    save(fig, "fig_j_retention")
    plt.close(fig)
    print(f"fig_j_retention: A1 seeds {c['seeds']}, window {w0}-{w1}")


# ------------------------------------------------------------------------------------------- Fig. 7
UMI_RX = ["citadel", "online_deepsic", "crc_rollback", "lmmse"]
DIST = [35, 75, 150]


def umi() -> None:
    folder = "rev2_umi_ldpc_scr"
    cells = {(rx, d): rn.cell(folder, f"d23s_{rx}_d{d}__phys", rn.CLEAN_ALL, metric="bler") for rx in UMI_RX for d in DIST}
    if any(c is None for c in cells.values()):
        print("fig_j_umi: records missing for", [k for k, c in cells.items() if c is None])
        return
    fig, (aa, ab) = plt.subplots(1, 2, figsize=(3.45, 2.15))
    tw = rn.twins(rn.CLEAN_ALL)
    for rx in ("lmmse", "crc_rollback", "online_deepsic", "citadel"):   # clean twins of the 75 m runs (as revision_numbers.campaign2 for d23m.*)
        cl = [rn.twin_of(tw, a) for a in rn.load(folder) if a["name"] == f"d23s_{rx}_d75__phys"]
        cl = [x for x in cl if x is not None]
        nb = min(len(x["blocks"]) for x in cl)
        B = np.array([rn.ser(x, "bler")[:nb] for x in cl])
        m = B.mean(0)
        aa.plot(np.arange(nb), m, color=C[rx], lw=2.0 if rx == "lmmse" else 0.9, alpha=0.55 if rx == "lmmse" else 1.0)
        k = "d23." + rx.replace("_", "") + ".d75bler"
        check("fig_j_umi (a)", f"{LAB[rx]}: mean over blocks 5 to {nb - 1}", k + ".clean", rn.f_ser(float(m[5:].mean())))
        check("fig_j_umi (a)", f"{LAB[rx]}: mean over the last 20 blocks", "d23m." + rx.replace("_", "") + ".blerlast",
              rn.f_ser(float(m[-20:].mean())))
    aa.set_yscale("symlog", linthresh=1e-2)
    aa.set_ylim(0, 1.5)
    aa.set_xlabel("block index (1 ms)")
    aa.set_ylabel("BLER, clean runs")
    panel_title(aa, "(a) Clean BLER")
    for i, rx in enumerate(UMI_RX):
        off = (i - 1.5) * 0.12
        for j, d in enumerate(DIST):
            c = cells[(rx, d)]
            ab.errorbar(j + off, c["excess"], yerr=[[c["excess"] - c["ci"][0]], [c["ci"][1] - c["excess"]]], fmt="o",
                        ms=3, color=C[rx], lw=0.7, capsize=1.2, zorder=3)
            k = f"d23.{rx.replace('_', '')}.d{d}bler"
            check("fig_j_umi (b)", f"{LAB[rx]}, {d} m: excess", k + ".excess", rn.f_sig(c["excess"]))
            check("fig_j_umi (b)", f"{LAB[rx]}, {d} m: 95% interval", k + ".ci", rn.f_ci(c["ci"]))
            check("fig_j_umi (b)", f"{LAB[rx]}, {d} m: seeds", k + ".n", str(c["n"]))
    ab.set_xticks(range(len(DIST)))
    ab.set_xticklabels([str(d) for d in DIST])
    ab.set_xlim(-0.5, len(DIST) - 0.5)
    ab.set_ylim(-0.02, 1.0)
    ab.set_xlabel("attacker distance (m)")
    ab.set_ylabel("excess BLER")
    ab.grid(axis="x", visible=False)
    panel_title(ab, "(b) Excess BLER")
    hs = [Line2D([], [], color=C[rx], marker="o", ms=3, lw=2.0 if rx == "lmmse" else 0.9,
                 alpha=0.55 if rx == "lmmse" else 1.0, label=LAB[rx]) for rx in UMI_RX]
    fig.legend(handles=rowmajor(hs, 2), loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=2, fontsize=6.5)
    fig.subplots_adjust(left=0.13, right=0.98, top=0.9, bottom=0.36, wspace=0.55)
    save(fig, "fig_j_umi")
    plt.close(fig)
    print("fig_j_umi: seeds", cells[("citadel", 75)]["seeds"])


# ------------------------------------------------------------------------------------------- check
def macros() -> dict:
    out = {}
    path = os.path.join(ROOT, "paper", "numbers.tex")
    for line in open(path) if os.path.exists(path) else []:
        m = re.match(r"\\@namedef\{val@(.+?)\}\{(.*)\}$", line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def report() -> int:
    V = macros()
    bad = missing = 0
    print(f"\n{'figure':22s} {'plotted quantity':52s} {'macro':34s} {'plotted':22s} {'numbers.tex':22s}")
    for fig, what, key, text in CHECKS:
        mac = V.get(key)
        flag = "ok" if mac == text else ("NO MACRO" if mac is None else "MISMATCH")
        bad += flag == "MISMATCH"
        missing += mac is None
        print(f"{fig:22s} {what:52s} {key:34s} {text:22s} {str(mac):22s} {flag}")
    print(f"{len(CHECKS)} plotted values checked against paper/numbers.tex: {len(CHECKS) - bad - missing} equal, "
          f"{bad} different, {missing} without a macro")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=10, help="test seed of the per-block panels of fig_j_headline")
    args = ap.parse_args()
    os.chdir(ROOT)
    headline(args.seed)
    mechanism()
    retention()
    umi()
    sys.exit(report())


if __name__ == "__main__":
    main()
