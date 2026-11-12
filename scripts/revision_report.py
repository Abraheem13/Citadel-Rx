#!/usr/bin/env python
"""Runs every revision analysis after scripts/revision_campaign.py and writes docs/REV_*.md.

The paired-displacement analysis needs the level snapshots (*.levels.npz), which are not pushed:
it runs on the cloud machine that produced them and is skipped elsewhere. It stores the paired curves in the JSON
records so everything else can be regenerated anywhere.

    python scripts/revision_report.py
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CLEAN = "results/rev_clean"              # matched clean runs of the laptop jobs
CLEAN_CLOUD = "results/rev_clean_cloud"  # matched clean runs of the cloud jobs (same machine as their attacked runs)
GROUPS = {   # folder: (title, clean folder)
    "rev_p1": ("P1 headline grid (test seeds 10-19 at SIR 0 dB, 10-12 elsewhere; randomised window)", CLEAN),
    "rev_p2": ("P2 remaining and new baselines (C1-C4, C6, C7)", CLEAN),
    "rev_p3_adaptive": ("P3 attacks built against the defence (B4)", CLEAN),
    "rev_p3_refdeg": ("P3 joint pilot + data attack on the references (B2)", CLEAN_CLOUD),
    "rev_p3_phys": ("P3 physical rank-M attacker (B1)", CLEAN),
    "rev_p3_know": ("P3 grey-box, query attacker, signal-referenced budget (B6, B8)", CLEAN),
    "rev_p4_paired": ("P4 paired-displacement runs (E7, A2)", CLEAN_CLOUD),
    "rev_p5_ablate": ("P5 ablations on test seeds", CLEAN),
    "rev_p6_blocklen": ("P6 block length (D1)", CLEAN),
    "rev_p6_arrays": ("P6 arrays N > U (D4)", CLEAN),
    "rev_p6_qam16": ("P6 16-QAM (D5)", CLEAN),
    "rev_p6_deploy": ("P6 30-step and last-layer variants (D9)", CLEAN),
    "rev_p7_sens": ("P7 one-at-a-time sensitivity (E5)", CLEAN),
    "rev_p8_drift": ("P8 optimised slow drift over 400 blocks (B5)", CLEAN_CLOUD),
}


def run(args):
    print(">>", " ".join(args), flush=True)
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        print("   (failed, continuing)", flush=True)


def main():
    os.chdir(ROOT)
    for d in ("rev_p4_paired", "rev_p8_drift"):   # needs the level snapshots (*.levels.npz) of the cloud machine
        if os.path.isdir(os.path.join("results", d)) and glob.glob(os.path.join("results", d, "*.levels.npz")):
            run([PY, "scripts/paired_disp.py", f"results/{d}", "--clean", CLEAN_CLOUD, "--out", f"docs/figures/fig_{d}"])
    if os.path.isdir("results/rev_p1"):
        run([PY, "scripts/revision_stats.py", "--attacked", "results/rev_p1", "--clean", CLEAN, "--out", "docs/REV_P1_STATS.md"])
    for d, (title, clean) in GROUPS.items():
        if os.path.isdir(os.path.join("results", d)):
            run([PY, "scripts/revision_stats.py", "--by-name", "--attacked", f"results/{d}", "--clean", clean,
                 "--out", f"docs/REV_{d.upper()}.md", "--title", title])
    if os.path.isdir("results/rev_p3_deny"):   # denial / abrupt-change runs carry their own no-attack controls
        run([PY, "scripts/revision_stats.py", "--by-name", "--attacked", "results/rev_p3_deny", "--clean", "results/rev_p3_deny",
             "--out", "docs/REV_REV_P3_DENY.md", "--title", "P3 denial of adaptation and abrupt change (B3, D6)"])
    gates = [f"results/{d}" for d in ("rev_p1", "rev_p3_adaptive", "rev_p3_refdeg", "rev_p3_phys") if os.path.isdir(f"results/{d}")]
    if gates:
        run([PY, "scripts/gate_roc.py", *gates])
    print("done: docs/REV_*.md, docs/PAIRED_DISP.md and docs/figures/fig_rev_*")


if __name__ == "__main__":
    main()
