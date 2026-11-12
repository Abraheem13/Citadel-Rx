#!/usr/bin/env python
"""Revision campaign sized for a MacBook (M4, 10 cores) plus one 4-core cloud machine.

The GPU workstation is unavailable, so the full plan (scripts/revision_campaign.py, ~1,600 runs)
is reduced: every reviewer item keeps an experiment, with fewer seeds and cells. The two machines
never run the same job (disjoint result folders), so their pushes merge without conflicts.

  shard "cloud"  : Citadel-Rx calibration (seeds 0-2, pre-registered rule), and the jobs that save
                   parameter snapshots or are expensive per block: paired displacement (P4), joint
                   pilot + data reference degradation (B2), optimised slow drift over 400 blocks (B5).
  shard "laptop" : baseline tuning (seeds 0-2, pre-registered rule), headline grid (P1), adaptive,
                   physical, grey-box, query and budget attacks (B1, B4, B6, B8), ablations (P5),
                   denial of adaptation (B3, D6), remaining baselines (P2), block length, arrays,
                   16-QAM, deployable variants (P6), sensitivity (P7).

Tiers run in order (1 = needed for the revised claims, 2 = remaining items, 3 = sensitivity);
the run can be stopped at any time: results are pushed every 45 minutes and every table states
its number of seeds. Test seeds: 10-19 for the headline cell (white-box A1 at SIR 0 dB), 10-12
for the other headline cells, 10-11 elsewhere, 10 for sensitivity.

Frozen settings (written by pre-registered rules, never by hand):
  configs/revision_frozen_citadel.json    cloud, after its calibration
  configs/revision_frozen_baselines.json  laptop, after its tuning
The laptop fetches only the Citadel-Rx file from GitHub before its first Citadel-Rx job.

    python scripts/revision_fast.py --shard laptop --workers 8     # resumable
    python scripts/revision_fast.py --shard laptop --push-only     # commit + push results now
    python scripts/revision_fast.py --shard cloud --workers 4
    python scripts/revision_fast.py --dry                          # list, count, validate settings
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import hashlib
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from citadel_rx.config import Config  # noqa: E402

RUN = os.path.join(ROOT, "scripts", "run_experiment.py")
CFG = os.path.join(ROOT, "configs", "e3_a1_defence.yaml")
BRANCH = "claude/fervent-cray-ah5drn"
FZ_CIT = os.path.join(ROOT, "configs", "revision_frozen_citadel.json")
FZ_BASE = os.path.join(ROOT, "configs", "revision_frozen_baselines.json")
CACHE = os.path.join(ROOT, "cache", "pretrain")
LOGS = os.path.join(ROOT, "logs")
CAL = [0, 1, 2]
T10, T3, T2, T1 = list(range(10, 20)), [10, 11, 12], [10, 11], [10]
KAPPA = "[8.5,4.5]"      # clean p99 of the consolidation increments (levels 2, 3), calibration runs
CANDIDATES = {           # pre-registered (scripts/revision_campaign.py)
    "rel_select_clip": ["citadel.g2_slack_mode=relative", "citadel.crc_select=true", f"citadel.consol_clip={KAPPA}", "citadel.consol_mean=normalized"],
    "derived_select_clip": ["citadel.g2_slack_mode=derived", "citadel.crc_select=true", f"citadel.consol_clip={KAPPA}", "citadel.consol_mean=normalized"],
    "rel_select_clip_anchorstart": ["citadel.g2_slack_mode=relative", "citadel.crc_select=true", f"citadel.consol_clip={KAPPA}", "citadel.consol_mean=normalized",
                                    "citadel.fast_init=anchor", "citadel.fast_radius=13"],
}
CAL_CELLS = {"clean": ["attack.type=none"], "a1": ["attack.type=a1", "attack.sir_db=0"],
             "cost": ["channel.model=cost2100", "attack.type=a1", "attack.sir_db=0"]}
CAL_DIRS = ("rev_cal_citadel", "cal")    # results/cal: earlier records of the same configurations (seeds 0-1)
MATCH_IGNORE = ("run.out_dir", "run.device", "run.seeds", "run.name")
RND = ["attack.start_mode=random"]
ONLINE_BASED = {"online_deepsic", "online_select", "crc_rollback", "rollback_allgates", "l2sp_deepsic", "ema_deepsic",
                "ewc_deepsic", "dd_deepsic", "cotta_deepsic", "eata_deepsic"}
CLEAN_DIR = {"laptop": "rev_clean", "cloud": "rev_clean_cloud", "windows": "rev_clean_win",
             "cloudx": "rev_clean_cloud", "cloudy": "rev_clean_cloud", "cloudz": "rev_clean_cloud", "cloudw": "rev_clean_cloud",   # more drivers on the cloud
             "helper": "rev_clean_helper",   # a second cloud machine
             **{f"pool{i}": f"rev_clean_pool{i}" for i in range(1, 13)},   # campaign 5: further cloud machines, one folder each
             "local": "rev_clean_local"}   # campaign 6: the whole second campaign on one machine
FZ_ABST = os.path.join(ROOT, "configs", "revision2_frozen_abstain.json")
FZ_JOINT = os.path.join(ROOT, "configs", "revision2_frozen_joint.json")
FZ_ABSTV = os.path.join(ROOT, "configs", "revision2_frozen_abstain_verified.json")
POOL_ASSIGN = os.path.join(ROOT, "configs", "pool_assign.json")
FROZEN_FILE = {"abst": FZ_ABST, "abstv": FZ_ABSTV, "joint": FZ_JOINT}
T5 = [10, 11, 12, 13, 14]   # second campaign: the 2-seed experiments get seeds 12-14, the 3-seed cells 13-14
NEW3, NEW2 = [12, 13, 14], [13, 14]


# ------------------------------------------------------------------------------------ jobs
class Job:
    def __init__(self, shard, tier, group, out, name, seeds, ov, clean_twin=False, kind="test", parent=None):
        self.shard, self.tier, self.group, self.out, self.name = shard, tier, group, out, name
        self.seeds, self.ov, self.clean_twin, self.kind = seeds, ov, clean_twin, kind
        self.parent = parent   # clean twin: the attacked job it belongs to

    @property
    def lid(self) -> str:
        """Logical id (the twin's own name is a hash of its resolved settings)."""
        return f"twin:{self.parent}" if self.clean_twin else self.name

    @property
    def needs(self) -> set:
        n = set()
        for o in self.ov:
            if o == "@CIT":
                n.add("cit")
            elif o.startswith("@BASE:"):
                n.add("base")
            elif o in ("@ABST", "@ABSTV", "@JOINT"):
                n.add(o[1:].lower())
        return n


def rx_ov(rx: str) -> List[str]:
    if rx == "citadel":
        return ["receiver.type=citadel", "@CIT"]
    if rx == "meta_deepsic":
        return ["receiver.type=meta_deepsic", "@BASE:meta_deepsic"]
    if rx in ONLINE_BASED:   # built on online DeepSIC: use online DeepSIC's tuned optimiser settings
        return [f"receiver.type={rx}", "@BASE:online_deepsic"]
    return [f"receiver.type={rx}"]


def J(shard, tier, group, out, name, seeds, ov, kind="test") -> List[Job]:
    return [Job(shard, tier, group, out, name, seeds, ov, kind=kind)]


def JT(shard, tier, group, out, name, seeds, ov) -> List[Job]:
    """Attacked job + its matched clean job (same settings, attack.* removed, same machine).
    The clean job is named by a hash of its resolved settings, so it is run once and shared."""
    return J(shard, tier, group, out, name, seeds, ov) + [Job(shard, tier, group, CLEAN_DIR[shard], None, seeds, ov, clean_twin=True,
                                                              parent=name)]


def calibration_jobs() -> List[Job]:
    jobs: List[Job] = []
    for rx, ep, lr, wd in itertools.product(["online_deepsic", "meta_deepsic"], [30, 100, 300], [1e-3, 5e-3], [0.0, 1e-4]):
        jobs += J("laptop", 0, "tune", "rev_cal_tune", f"tune_{rx}_ep{ep}_lr{lr:g}_wd{wd:g}", CAL,
                  [f"receiver.type={rx}", f"receiver.epochs={ep}", f"receiver.lr={lr}", f"receiver.weight_decay={wd}",
                   "attack.type=none"], kind="tune")
    for tag, ov in CANDIDATES.items():
        for cell, cov in CAL_CELLS.items():
            jobs += J("cloud", 0, "calibrate", "rev_cal_citadel", f"cand_{tag}__{cell}", CAL, ["receiver.type=citadel"] + ov + cov,
                      kind="cal")
    return jobs


def test_jobs() -> List[Job]:
    L, C = "laptop", "cloud"
    a1 = lambda s: ["attack.type=a1", f"attack.sir_db={s}"]
    jobs: List[Job] = []
    # ===== laptop, tier 1 ===================================================================
    P1RX = ["citadel", "online_deepsic", "meta_deepsic", "crc_rollback", "online_select"]
    for rx in P1RX:   # P1 headline cell, 10 test seeds (E2, E3, C1, C5, H6)
        jobs += JT(L, 1, "P1", "rev_p1", f"p1_{rx}__wb_sir0", T10, rx_ov(rx) + RND + a1(0))
    lite = ["attack.soft_gate=true", "attack.unroll_steps=10", "attack.pgd_steps=50", "attack.restarts=2", "attack.eot=2"]
    adaptive = {"unroll10": ["attack.unroll_steps=10"], "softgate": ["attack.soft_gate=true", "attack.unroll_steps=10"],
                "pgd100_r5": ["attack.pgd_steps=100", "attack.restarts=5"]}
    for tag, aov in adaptive.items():   # B4 attacks built against the defence
        for s in (0, 10):
            jobs += JT(L, 1, "P3adapt", "rev_p3_adaptive", f"p3_citadel_{tag}__sir{s}", T2, rx_ov("citadel") + RND + a1(s) + aov)
    jobs += JT(L, 1, "P3adapt", "rev_p3_adaptive", "p3_citadel_strongest__sir0", T2, rx_ov("citadel") + RND + a1(0) + lite)
    jobs += JT(L, 1, "P3adapt", "rev_p3_adaptive", "p3_citadel_unroll50__sir0", T2, rx_ov("citadel") + RND + a1(0) + ["attack.unroll_steps=50"])
    jobs += JT(L, 1, "P3adapt", "rev_p3_adaptive", "p3_online_strongest__sir0", T2, rx_ov("online_deepsic") + RND + a1(0) + lite[1:])
    cells = {"wb_sir-10": a1(-10), "wb_sir10": a1(10), "tr_sir0": a1(0) + ["attack.knowledge=transfer"],
             "jam": ["attack.type=data_jam", "attack.sir_db=0"]}
    for rx in P1RX:   # P1 other cells, 3 test seeds
        for cell, cov in cells.items():
            jobs += JT(L, 1, "P1", "rev_p1", f"p1_{rx}__{cell}", T3, rx_ov(rx) + RND + cov)
    ab = {"K1": ["citadel.levels=1", "citadel.periods=[1]", "citadel.consol_clip=[]"],
          "K2": ["citadel.levels=2", "citadel.periods=[1,8]", "citadel.consol_clip=[8.5]"],
          "nogate": ["citadel.gates=[]"], "g1": ["citadel.gates=[g1]"], "g2": ["citadel.gates=[g2]"], "g3": ["citadel.gates=[g3]"],
          "no_anchor": ["citadel.prox_lambda=0.0", "citadel.reanchor_beta=0.0"], "no_fallback": ["citadel.fallback_on_reject=false"],
          "no_select": ["citadel.crc_select=false"], "no_clip": ["citadel.consol_clip=[]"]}
    for tag, aov in ab.items():   # P5 ablations on test seeds (C1: K=1 now reverts and falls back)
        jobs += JT(L, 1, "P5", "rev_p5_ablate", f"p5_{tag}__wb_sir0", T2, rx_ov("citadel") + aov + RND + a1(0))
    for tag, pov in {"M1": ["attack.attacker_antennas=1"], "M2": ["attack.attacker_antennas=2"],
                     "M2_csi0.1": ["attack.attacker_antennas=2", "attack.attacker_csi_err=0.1"]}.items():   # B1
        for rx in ("citadel", "online_deepsic"):
            jobs += JT(L, 1, "P3phys", "rev_p3_phys", f"p3_{rx}_{tag}__sir0", T2, rx_ov(rx) + RND + a1(0) + pov)
    jobs += JT(L, 1, "P3know", "rev_p3_know", "p3_citadel_greybox__sir0", T2,   # B6 grey-box: Citadel-Rx surrogate
               rx_ov("citadel") + RND + a1(0) + ["attack.knowledge=transfer", "attack.surrogate=citadel"])
    for rx in ("citadel", "online_deepsic"):   # B6 query attacker on NACK feedback, B8 signal-referenced budget
        jobs += JT(L, 1, "P3know", "rev_p3_know", f"p3_{rx}_query__sir0", T2, rx_ov(rx) + RND + a1(0) + ["attack.knowledge=query"])
        jobs += JT(L, 1, "P3know", "rev_p3_know", f"p3_{rx}_sigbudget__sir0", T2, rx_ov(rx) + RND + a1(0) + ["attack.budget_ref=signal"])
    abrupt = {"redraw": ["channel.abrupt_block=50", "channel.abrupt_type=redraw"],
              "snrdrop": ["channel.abrupt_block=50", "channel.abrupt_type=snr_drop"]}
    deny = ["attack.type=deny", "attack.sir_db=10", "attack.start_block=40", "attack.end_block=90"]
    for rx, base in (("citadel", rx_ov("citadel")), ("citadel_streak", rx_ov("citadel") + ["citadel.streak_k=5"]),
                     ("online_deepsic", rx_ov("online_deepsic")), ("lmmse", ["receiver.type=lmmse"])):   # B3, D6
        jobs += J(L, 1, "P3deny", "rev_p3_deny", f"p3_{rx}_redraw__none", T2, base + abrupt["redraw"] + ["attack.type=none"])
        jobs += J(L, 1, "P3deny", "rev_p3_deny", f"p3_{rx}_redraw__deny", T2, base + abrupt["redraw"] + deny)
        jobs += J(L, 1, "P3deny", "rev_p3_deny", f"p3_{rx}_snrdrop__none", T2, base + abrupt["snrdrop"] + ["attack.type=none"])
    # ===== laptop, tier 2 ===================================================================
    for rx in ["lmmse", "lmmse_robust", "rollback_allgates", "l2sp_deepsic", "ema_deepsic", "ewc_deepsic", "dd_deepsic",
               "cotta_deepsic", "eata_deepsic", "drift_deepsic", "titans_single", "medbn_deepsic"]:   # C1-C4, C6, C7
        jobs += JT(L, 2, "P2", "rev_p2", f"p2_{rx}__wb_sir0", T2, rx_ov(rx) + RND + a1(0))
    for w in (1e-3, 1e-1, 1.0):   # L2-SP weight (C2); 1e-2 is the default above
        jobs += JT(L, 2, "P2", "rev_p2", f"p2_l2sp_w{w:g}__wb_sir0", T2, rx_ov("l2sp_deepsic") + [f"receiver.reg_weight={w}"] + RND + a1(0))
    for nd, npil in itertools.product((1000, 5000), (32, 100)):   # D1 block length
        for rx in ("citadel", "online_deepsic"):
            jobs += JT(L, 2, "P6", "rev_p6_blocklen", f"p6_{rx}_nd{nd}_np{npil}__sir0", T2,
                       rx_ov(rx) + [f"frame.data_bits={2 * nd}", f"frame.pilot_bits={2 * npil}"] + RND + a1(0))
    for rx in ("citadel", "online_deepsic", "lmmse"):   # D4 N > U, D5 16-QAM
        jobs += JT(L, 2, "P6", "rev_p6_arrays", f"p6_{rx}_4x16__sir0", T2, rx_ov(rx) + ["channel.n_user=4", "channel.n_ant=16"] + RND + a1(0))
        jobs += JT(L, 2, "P6", "rev_p6_qam16", f"p6_{rx}_qam16__sir0", T2,
                   rx_ov(rx) + ["frame.modulation=QAM16", "receiver.hidden_base=16", "channel.snr_db=20", "frame.data_bits=100000",
                                "frame.pilot_bits=400"] + RND + a1(0))
    for tag, vov in {"steps30": ["citadel.fast_steps=30"], "last_layer": ["citadel.adaptable=last"]}.items():   # D9
        jobs += JT(L, 2, "P6", "rev_p6_deploy", f"p6_citadel_{tag}__sir0", T2, rx_ov("citadel") + vov + RND + a1(0))
    # ===== laptop, tier 3: one-at-a-time sensitivity at x0.5 and x2 (E5) =====================
    sens = {"g1_slack": ("citadel.g1_tau", lambda m: 1 + 0.25 * m), "g3_slack": ("citadel.g3_tau", lambda m: 1 + 3 * m),
            "tighten": ("citadel.tighten_floor", lambda m: 1 - 0.3 * m), "soft_width": ("citadel.gate_kappa", lambda m: 0.1 * m),
            "prox_lambda": ("citadel.prox_lambda", lambda m: 0.5 * m), "delta": ("citadel.dgd_delta", lambda m: 0.1 * m),
            "crc_rel": ("citadel.g2_rel_slack", lambda m: 1.0 * m)}
    for par, (key, f) in sens.items():
        for m in (0.5, 2.0):
            jobs += JT(L, 3, "P7", "rev_p7_sens", f"p7_{par}_x{m:g}__wb_sir0", T1, rx_ov("citadel") + [f"{key}={f(m):g}"] + RND + a1(0))
    for m in (0.5, 2.0):
        jobs += JT(L, 3, "P7", "rev_p7_sens", f"p7_eta3_x{m:g}__wb_sir0", T1,
                   rx_ov("citadel") + [f"citadel.level_lr=[1.0,{0.5 * m:g}]"] + RND + a1(0))
    # ===== cloud, tier 1 ====================================================================
    for s in (0, 10):   # P4 paired displacement with level snapshots (E7, A2); fixed window as in the paper
        jobs += JT(C, 1, "P4", "rev_p4_paired", f"p4_citadel__sir{s}", T3, rx_ov("citadel") + a1(s) + ["run.save_params=true"])
    for a in (0.25, 0.75):   # B2: joint pilot + data attack on the references, +/- the abstain state (H3)
        for abst in (False, True):
            jobs += JT(C, 1, "P3refdeg", "rev_p3_refdeg", f"p3_a4_a{a:g}{'_abstain' if abst else ''}__sir0", T2,
                       rx_ov("citadel") + (["citadel.abstain=true"] if abst else []) + RND +
                       ["attack.type=a4", f"attack.a4_alpha={a}", "attack.sir_db=0", "attack.pgd_steps=6"])
        jobs += J(C, 1, "P3refdeg", "rev_p3_refdeg", f"p3_jamctl_a{a:g}__sir0", T2,   # jamming only, same data power
                  rx_ov("citadel") + RND + ["attack.type=data_jam", f"attack.sir_db={-10 * math.log10(1 - a):.3f}"])
    for e, g in ((0.05, False), (0.2, False), (0.5, False), (0.5, True)):   # B5 optimised slow drift, 400 blocks (H5)
        # (moved to the laptop after the cloud machine was stopped)
        jobs += JT(L, 1, "P8", "rev_p8_drift", f"p8_a3star_e{e:g}{'_guard' if g else ''}__long", T2,
                   rx_ov("citadel") + (["citadel.drift_guard=0.05"] if g else []) +
                   ["frame.n_blocks=400", "attack.type=a3star", f"attack.a3_eps_small={e}", "attack.start_block=30",
                    "attack.end_block=330", "run.save_params=true"])
    return jobs


# ------------------------------------------------------------------------------------ campaign 2
def rev2_jobs() -> List[Job]:
    """Second revision campaign (closes the items the first one reduced or left open). Shards:
    "cloud" (this 4-core machine: long runs, snapshot runs, expensive attacks, the P1 cells with
    Meta-DeepSIC, the further baselines and the 8 x 32 array) and "windows" (the author's laptop).
    Seeds are only ever added to the pre-registered test set 10-19; nothing is re-tuned."""
    W, C = "windows", "cloud"
    a1 = lambda s: ["attack.type=a1", f"attack.sir_db={s}"]
    jobs: List[Job] = []
    P1RX = ["citadel", "online_deepsic", "meta_deepsic", "crc_rollback", "online_select"]
    # ===== cloud, tier 1 =====================================================================
    for rx in ("citadel", "online_deepsic"):   # D7: 2000-block clean horizon
        jobs += J(C, 1, "D7", "rev2_long_clean", f"d7_{rx}__clean2000", T2, rx_ov(rx) + ["frame.n_blocks=2000", "attack.type=none"])
    drift = ["attack.type=a3star", "attack.a3_eps_small=0.05", "attack.start_block=30", "run.save_params=true"]
    jobs += JT(C, 1, "H5", "rev2_drift_guard", "h5_a3star_e0.05_guard__long", T2,   # H5: the guard against an accepted drift
               rx_ov("citadel") + ["citadel.drift_guard=0.05", "frame.n_blocks=400", "attack.end_block=330"] + drift)
    jobs += JT(C, 1, "B5", "rev2_drift_long", "b5_a3star_e0.05__long1000", T2,      # B5: accepted drift over 900 blocks
               rx_ov("citadel") + ["frame.n_blocks=1000", "attack.end_block=930"] + drift)
    for s in (0, 10):   # P4 paired displacement: seeds 13-14 (E2)
        jobs += JT(C, 1, "P4", "rev_p4_paired", f"p4_citadel__sir{s}", NEW2, rx_ov("citadel") + a1(s) + ["run.save_params=true"])
    for a in (0.25, 0.75):   # A4 at 6 PGD steps: seeds 12-14 (E2), with the jamming controls
        jobs += JT(C, 1, "P3refdeg", "rev_p3_refdeg", f"p3_a4_a{a:g}__sir0", NEW3,
                   rx_ov("citadel") + RND + ["attack.type=a4", f"attack.a4_alpha={a}", "attack.sir_db=0", "attack.pgd_steps=6"])
        jobs += J(C, 1, "P3refdeg", "rev_p3_refdeg", f"p3_jamctl_a{a:g}__sir0", NEW3,
                  rx_ov("citadel") + RND + ["attack.type=data_jam", f"attack.sir_db={-10 * math.log10(1 - a):.3f}"])
    jobs += JT(C, 1, "B2", "rev2_a4_pgd20", "b2_a4_a0.25_pgd20__sir0", T5,   # B2 at full strength: 20 PGD steps
               rx_ov("citadel") + RND + ["attack.type=a4", "attack.a4_alpha=0.25", "attack.sir_db=0", "attack.pgd_steps=20"])
    cells = {"wb_sir-10": a1(-10), "wb_sir10": a1(10), "tr_sir0": a1(0) + ["attack.knowledge=transfer"],
             "jam": ["attack.type=data_jam", "attack.sir_db=0"]}
    for rx in P1RX:   # E2: the other headline cells get seeds 13-14 (5 seeds)
        for cell, cov in cells.items():
            jobs += JT(C, 1, "P1", "rev_p1", f"p1_{rx}__{cell}", NEW2, rx_ov(rx) + RND + cov)
    # ===== cloud, tier 2 =====================================================================
    for rx in ("citadel", "online_deepsic", "lmmse"):   # D4: 8 x 32
        jobs += JT(C, 2, "D4", "rev2_arrays", f"d4_{rx}_8x32__sir0", T5, rx_ov(rx) + ["channel.n_user=8", "channel.n_ant=32"] + RND + a1(0))
    for rx in ["lmmse", "lmmse_robust", "rollback_allgates", "l2sp_deepsic", "ema_deepsic", "ewc_deepsic", "dd_deepsic",
               "cotta_deepsic", "eata_deepsic", "drift_deepsic", "titans_single", "medbn_deepsic"]:   # E2 for C1-C4, C6, C7
        jobs += JT(C, 2, "P2", "rev_p2", f"p2_{rx}__wb_sir0", NEW3, rx_ov(rx) + RND + a1(0))
    for w in (1e-3, 1e-1, 1.0):
        jobs += JT(C, 2, "P2", "rev_p2", f"p2_l2sp_w{w:g}__wb_sir0", NEW3, rx_ov("l2sp_deepsic") + [f"receiver.reg_weight={w}"] + RND + a1(0))
    # ===== windows, tier 1 ===================================================================
    lite = ["attack.soft_gate=true", "attack.unroll_steps=10", "attack.pgd_steps=50", "attack.restarts=2", "attack.eot=2"]
    adaptive = {"unroll10": ["attack.unroll_steps=10"], "softgate": ["attack.soft_gate=true", "attack.unroll_steps=10"],
                "pgd100_r5": ["attack.pgd_steps=100", "attack.restarts=5"]}
    for tag, aov in adaptive.items():   # E2 for B4
        for s in (0, 10):
            jobs += JT(W, 1, "P3adapt", "rev_p3_adaptive", f"p3_citadel_{tag}__sir{s}", NEW3, rx_ov("citadel") + RND + a1(s) + aov)
    jobs += JT(W, 1, "P3adapt", "rev_p3_adaptive", "p3_citadel_strongest__sir0", NEW3, rx_ov("citadel") + RND + a1(0) + lite)
    jobs += JT(W, 1, "P3adapt", "rev_p3_adaptive", "p3_citadel_unroll50__sir0", NEW3, rx_ov("citadel") + RND + a1(0) + ["attack.unroll_steps=50"])
    jobs += JT(W, 1, "P3adapt", "rev_p3_adaptive", "p3_online_strongest__sir0", NEW3, rx_ov("online_deepsic") + RND + a1(0) + lite[1:])
    phys = {"M1": ["attack.attacker_antennas=1"], "M2": ["attack.attacker_antennas=2"]}
    for tag, pov in phys.items():   # E2 for B1
        for rx in ("citadel", "online_deepsic"):
            jobs += JT(W, 1, "P3phys", "rev_p3_phys", f"p3_{rx}_{tag}__sir0", NEW3, rx_ov(rx) + RND + a1(0) + pov)
    # B1 completed: full-rank physical attacker; CSI error now applied through the true channel (the
    # first campaign's CSI-error runs injected the perturbation designed for G_hat, see the attack code)
    for tag, pov in {"M4": ["attack.attacker_antennas=4"],
                     "M2_csi0.1": ["attack.attacker_antennas=2", "attack.attacker_csi_err=0.1"],
                     "M2_csi0.01": ["attack.attacker_antennas=2", "attack.attacker_csi_err=0.01"]}.items():
        for rx in ("citadel", "online_deepsic"):
            jobs += JT(W, 1, "B1", "rev2_phys", f"b1_{rx}_{tag}__sir0", T5, rx_ov(rx) + RND + a1(0) + pov)
    jobs += JT(W, 1, "P3know", "rev_p3_know", "p3_citadel_greybox__sir0", NEW3,
               rx_ov("citadel") + RND + a1(0) + ["attack.knowledge=transfer", "attack.surrogate=citadel"])
    for rx in ("citadel", "online_deepsic"):
        jobs += JT(W, 1, "P3know", "rev_p3_know", f"p3_{rx}_query__sir0", NEW3, rx_ov(rx) + RND + a1(0) + ["attack.knowledge=query"])
        jobs += JT(W, 1, "P3know", "rev_p3_know", f"p3_{rx}_sigbudget__sir0", NEW3, rx_ov(rx) + RND + a1(0) + ["attack.budget_ref=signal"])
    redraw = ["channel.abrupt_block=50", "channel.abrupt_type=redraw"]
    bases = (("citadel", rx_ov("citadel")), ("citadel_streak", rx_ov("citadel") + ["citadel.streak_k=5"]),
             ("online_deepsic", rx_ov("online_deepsic")), ("lmmse", ["receiver.type=lmmse"]))
    for rx, base in bases:   # B3/H4 as intended: poisoning strong enough to be rejected on every block, during a redraw
        jobs += J(W, 1, "B3", "rev2_deny_a1", f"b3_{rx}_redraw__none", T5, base + redraw + ["attack.type=none"])
        jobs += J(W, 1, "B3", "rev2_deny_a1", f"b3_{rx}_redraw__a1deny", T5,
                  base + redraw + ["attack.type=a1", "attack.sir_db=0", "attack.start_block=40", "attack.end_block=90"])
    for rx, base in bases:   # E2 for the original denial spoof (B3, D6)
        jobs += J(W, 1, "P3deny", "rev_p3_deny", f"p3_{rx}_redraw__none", NEW3, base + redraw + ["attack.type=none"])
        jobs += J(W, 1, "P3deny", "rev_p3_deny", f"p3_{rx}_redraw__deny", NEW3,
                  base + redraw + ["attack.type=deny", "attack.sir_db=10", "attack.start_block=40", "attack.end_block=90"])
        jobs += J(W, 1, "P3deny", "rev_p3_deny", f"p3_{rx}_snrdrop__none", NEW3,
                  base + ["channel.abrupt_block=50", "channel.abrupt_type=snr_drop", "attack.type=none"])
    for v, vov in (("citadel", []), ("citadel_peruser", ["citadel.per_user_gate=true"])):   # H7: per-user gating
        for atk, aov in (("a2", ["attack.type=a2", "attack.sir_db=0"]), ("a1", a1(0))):
            jobs += JT(W, 1, "H7", "rev2_peruser", f"h7_{v}__{atk}", T5, rx_ov("citadel") + vov + RND + aov)
    jobs += JT(W, 1, "H7", "rev2_peruser", "h7_online_deepsic__a2", T5, rx_ov("online_deepsic") + RND + ["attack.type=a2", "attack.sir_db=0"])
    # ===== windows, tier 2 ===================================================================
    ab = {"K1": ["citadel.levels=1", "citadel.periods=[1]", "citadel.consol_clip=[]"],
          "K2": ["citadel.levels=2", "citadel.periods=[1,8]", "citadel.consol_clip=[8.5]"],
          "nogate": ["citadel.gates=[]"], "g1": ["citadel.gates=[g1]"], "g2": ["citadel.gates=[g2]"], "g3": ["citadel.gates=[g3]"],
          "no_anchor": ["citadel.prox_lambda=0.0", "citadel.reanchor_beta=0.0"], "no_fallback": ["citadel.fallback_on_reject=false"],
          "no_select": ["citadel.crc_select=false"], "no_clip": ["citadel.consol_clip=[]"]}
    for tag, aov in ab.items():   # E2 for the ablations
        jobs += JT(W, 2, "P5", "rev_p5_ablate", f"p5_{tag}__wb_sir0", NEW3, rx_ov("citadel") + aov + RND + a1(0))
    for nd, npil in itertools.product((1000, 5000), (32, 100)):   # E2 for D1, D4, D5, D9
        for rx in ("citadel", "online_deepsic"):
            jobs += JT(W, 2, "P6", "rev_p6_blocklen", f"p6_{rx}_nd{nd}_np{npil}__sir0", NEW3,
                       rx_ov(rx) + [f"frame.data_bits={2 * nd}", f"frame.pilot_bits={2 * npil}"] + RND + a1(0))
    for rx in ("citadel", "online_deepsic", "lmmse"):
        jobs += JT(W, 2, "P6", "rev_p6_arrays", f"p6_{rx}_4x16__sir0", NEW3, rx_ov(rx) + ["channel.n_user=4", "channel.n_ant=16"] + RND + a1(0))
        jobs += JT(W, 2, "P6", "rev_p6_qam16", f"p6_{rx}_qam16__sir0", NEW3,
                   rx_ov(rx) + ["frame.modulation=QAM16", "receiver.hidden_base=16", "channel.snr_db=20", "frame.data_bits=100000",
                                "frame.pilot_bits=400"] + RND + a1(0))
    for tag, vov in {"steps30": ["citadel.fast_steps=30"], "last_layer": ["citadel.adaptable=last"]}.items():
        jobs += JT(W, 2, "P6", "rev_p6_deploy", f"p6_citadel_{tag}__sir0", NEW3, rx_ov("citadel") + vov + RND + a1(0))
    # ===== windows, tier 3: sensitivity at x0.75 and x1.5 (E5) and a two-setting grid ========
    sens = {"g1_slack": ("citadel.g1_tau", lambda m: 1 + 0.25 * m), "g3_slack": ("citadel.g3_tau", lambda m: 1 + 3 * m),
            "tighten": ("citadel.tighten_floor", lambda m: 1 - 0.3 * m), "soft_width": ("citadel.gate_kappa", lambda m: 0.1 * m),
            "prox_lambda": ("citadel.prox_lambda", lambda m: 0.5 * m), "delta": ("citadel.dgd_delta", lambda m: 0.1 * m),
            "crc_rel": ("citadel.g2_rel_slack", lambda m: 1.0 * m)}
    for m in (0.75, 1.5):
        for par, (key, f) in sens.items():
            jobs += JT(W, 3, "P7", "rev_p7_sens", f"p7_{par}_x{m:g}__wb_sir0", T1, rx_ov("citadel") + [f"{key}={f(m):g}"] + RND + a1(0))
        jobs += JT(W, 3, "P7", "rev_p7_sens", f"p7_eta3_x{m:g}__wb_sir0", T1,
                   rx_ov("citadel") + [f"citadel.level_lr=[1.0,{0.5 * m:g}]"] + RND + a1(0))
    for m1, m2 in itertools.product((0.5, 2.0), (0.5, 2.0)):   # grid: CRC slack x G1 slack (corners)
        jobs += JT(W, 3, "P7grid", "rev2_sens_grid", f"grid_crc{m1:g}_g1{m2:g}__wb_sir0", T1,
                   rx_ov("citadel") + [f"citadel.g2_rel_slack={1.0 * m1:g}", f"citadel.g1_tau={1 + 0.25 * m2:g}"] + RND + a1(0))
    return jobs


def rev2x_jobs() -> List[Job]:
    """New-feature experiments on the cloud (shards cloudx and cloudy, run next to the "cloud" driver).
    cloudx: the calibration of the abstain threshold and the tuning of the second backbone (seeds 0-2,
    rules in scripts/freeze_rev2.py, fixed before any test run of these features), and the coded UMi
    scene (NR LDPC + 38.901 UMi with the attacker at 35, 75 and 150 m; Citadel-Rx and the baselines
    keep their frozen settings). cloudy: the test runs that read configs/revision2_frozen_*.json."""
    X, Y = "cloudx", "cloudy"
    a1 = lambda s: ["attack.type=a1", f"attack.sir_db={s}"]
    jobs: List[Job] = []
    # ===== cloudx, tier 0: calibration and tuning on seeds 0-2 ================================
    jobs += J(X, 0, "H3cal", "rev2_abstain_cal", "h3cal_ratio__clean", CAL,
              rx_ov("citadel") + ["citadel.abstain=true", "citadel.abstain_mode=ratio", "citadel.abstain_z=1e9", "attack.type=none"])
    # abstain v3 (residual on CRC-verified symbols): calibrated by the same rule (scripts/freeze_rev2.py)
    jobs += J(X, 0, "H3cal", "rev2_abstain_cal", "h3cal_verified__clean", CAL,
              rx_ov("citadel") + ["citadel.abstain=true", "citadel.abstain_mode=verified", "citadel.abstain_z=1e9", "attack.type=none"])
    for ep, lr in itertools.product([30, 100, 300], [1e-3, 5e-3]):
        jobs += J(X, 0, "D8tune", "rev2_joint_tune", f"tune_joint_ep{ep}_lr{lr:g}", CAL,
                  ["receiver.type=online_deepsic", "receiver.backbone=joint", f"receiver.epochs={ep}", f"receiver.lr={lr}",
                   "attack.type=none"], kind="tune")
    # ===== cloudx, tier 1: NR LDPC coding over 38.901 UMi channels, attacker in the scene (D2, D3) =
    # d23_*: the first version, without NR scrambling (a constant detector output passed the check);
    # superseded by d23s_* below and dropped from the plan (configs/claims.json), kept for the record
    scene = ["channel.model=umi", "frame.coding=ldpc"]
    for d in (35, 75, 150):
        for rx in ("citadel", "online_deepsic", "crc_rollback", "lmmse"):
            jobs += JT(X, 1, "D23", "rev2_umi_ldpc", f"d23_{rx}_d{d}__phys", T5,
                       rx_ov(rx) + scene + RND + ["attack.type=a1", "attack.attacker_antennas=1", "attack.sir_from_geometry=true",
                                                 "attack.budget_ref=signal", f"attack.att_dist={d}"])
    scene_s = scene + ["frame.ldpc_scramble=true"]   # with NR data scrambling (TS 38.211 Sec. 6.3.1.1)
    for d in (35, 75, 150):
        for rx in ("citadel", "online_deepsic", "crc_rollback", "lmmse"):
            jobs += JT(X, 1, "D23s", "rev2_umi_ldpc_scr", f"d23s_{rx}_d{d}__phys", T5,
                       rx_ov(rx) + scene_s + RND + ["attack.type=a1", "attack.attacker_antennas=1", "attack.sir_from_geometry=true",
                                                   "attack.budget_ref=signal", f"attack.att_dist={d}"])
    # ===== cloudy, tier 1: test runs with the frozen abstain threshold and backbone tuning =======
    for a in (0.25, 0.75):   # H3 against A4
        jobs += JT(Y, 1, "H3", "rev2_abstain", f"h3_a4_a{a:g}_ratio__sir0", T5,
                   rx_ov("citadel") + ["@ABST"] + RND + ["attack.type=a4", f"attack.a4_alpha={a}", "attack.sir_db=0", "attack.pgd_steps=6"])
    jobs += JT(Y, 1, "H3", "rev2_abstain", "h3_a1_ratio__sir0", T5, rx_ov("citadel") + ["@ABST"] + RND + ["attack.type=a1", "attack.sir_db=0"])
    for tag, ch in (("redraw", ["channel.abrupt_block=50", "channel.abrupt_type=redraw"]),
                    ("snrdrop", ["channel.abrupt_block=50", "channel.abrupt_type=snr_drop"])):   # legitimate changes
        jobs += J(Y, 1, "H3", "rev2_abstain", f"h3_ratio_{tag}__none", T5, rx_ov("citadel") + ["@ABST"] + ch + ["attack.type=none"])
    # abstain v3: the test runs of the second version, repeated with the third (shard cloudy, run by the pool)
    for a in (0.25, 0.75):
        jobs += JT(Y, 1, "H3v", "rev2_abstain_v3", f"h3v_a4_a{a:g}__sir0", T5,
                   rx_ov("citadel") + ["@ABSTV"] + RND + ["attack.type=a4", f"attack.a4_alpha={a}", "attack.sir_db=0", "attack.pgd_steps=6"])
    jobs += JT(Y, 1, "H3v", "rev2_abstain_v3", "h3v_a1__sir0", T5, rx_ov("citadel") + ["@ABSTV"] + RND + ["attack.type=a1", "attack.sir_db=0"])
    for tag, ch in (("redraw", ["channel.abrupt_block=50", "channel.abrupt_type=redraw"]),
                    ("snrdrop", ["channel.abrupt_block=50", "channel.abrupt_type=snr_drop"])):
        jobs += J(Y, 1, "H3v", "rev2_abstain_v3", f"h3v_{tag}__none", T5, rx_ov("citadel") + ["@ABSTV"] + ch + ["attack.type=none"])
    # the same tests on seeds 15-19: the verified statistic was adopted after the second version's first test
    # runs (seeds 10-12) had been seen, so these seeds, untouched by any choice, are reported on their own too
    T15 = [15, 16, 17, 18, 19]
    for a in (0.25, 0.75):
        jobs += JT(Y, 1, "H3vx", "rev2_abstain_v3", f"h3v_a4_a{a:g}__sir0", T15,
                   rx_ov("citadel") + ["@ABSTV"] + RND + ["attack.type=a4", f"attack.a4_alpha={a}", "attack.sir_db=0", "attack.pgd_steps=6"])
    jobs += JT(Y, 1, "H3vx", "rev2_abstain_v3", "h3v_a1__sir0", T15, rx_ov("citadel") + ["@ABSTV"] + RND + ["attack.type=a1", "attack.sir_db=0"])
    for tag, ch in (("redraw", ["channel.abrupt_block=50", "channel.abrupt_type=redraw"]),
                    ("snrdrop", ["channel.abrupt_block=50", "channel.abrupt_type=snr_drop"])):
        jobs += J(Y, 1, "H3vx", "rev2_abstain_v3", f"h3v_{tag}__none", T15, rx_ov("citadel") + ["@ABSTV"] + ch + ["attack.type=none"])
    for rx in ("citadel", "online_deepsic", "crc_rollback"):   # D8: second backbone under A1 (shard cloudz)
        jobs += JT("cloudz", 1, "D8", "rev2_joint", f"d8_{rx}_joint__wb_sir0", T5,
                   ([*rx_ov("citadel")] if rx == "citadel" else [f"receiver.type={rx}", "@JOINT"]) + ["receiver.backbone=joint"]
                   + RND + ["attack.type=a1", "attack.sir_db=0"])
    # ===== drift detection and median-of-means with the tuned optimiser of online DeepSIC (C5; the
    # P2 runs used the receivers' reference 300 epochs / 5e-3 because ONLINE_BASED omitted them) ==
    for rx in ("drift_deepsic", "medbn_deepsic"):
        jobs += JT("cloudw", 1, "P2t", "rev2_p2_tuned", f"p2t_{rx}__wb_sir0", T5,
                   [f"receiver.type={rx}", "@BASE:online_deepsic"] + RND + a1(0))
    # ===== stretched SED profile for the larger arrays (audit D4; shard cloudw, run by a pool machine) ==
    for rx in ("citadel", "online_deepsic", "lmmse"):
        jobs += JT("cloudw", 1, "D4s", "rev2_arrays_stretch", f"d4s_{rx}_8x32s__sir0", T5,
                   rx_ov(rx) + ["channel.n_user=8", "channel.n_ant=32", "channel.sed_stretch=true"] + RND + a1(0))
        jobs += JT("cloudw", 1, "P6s", "rev2_arrays_stretch", f"p6s_{rx}_4x16s__sir0", T5,
                   rx_ov(rx) + ["channel.n_user=4", "channel.n_ant=16", "channel.sed_stretch=true"] + RND + a1(0))
    return jobs


def helper_jobs() -> List[Job]:
    """Campaign 4: a second cloud machine takes the jobs the Windows laptop reaches last (tiers 2-3)
    and the cloud machine's tier 2. The original assignees keep them in their lists: whichever
    machine gets to a job second finds the record (results arrive through the periodic git pull)
    and skips it, so nothing is lost if one machine stops."""
    out = []
    for j in rev2_jobs():
        if (j.shard == "windows" and j.tier >= 2) or (j.shard == "cloud" and j.tier == 2):
            out.append(Job("helper", j.tier, j.group, CLEAN_DIR["helper"] if j.clean_twin else j.out, j.name, j.seeds, j.ov,
                           clean_twin=j.clean_twin, kind=j.kind))
    # the most expensive first, so that the slower laptop is left with the cheap remainder
    order = {"D4": 0, "P2": 1, "P6": 2, "P5": 3, "P7": 4, "P7grid": 5}   # the cloud's tier 2 first
    out.sort(key=lambda j: order.get(j.group, 9))
    return out


def pool_jobs(shard: str) -> List[Tuple["Job", int]]:
    """Campaign 5: the runs configs/pool_assign.json gives this pool machine (written by
    scripts/assign_pool.py, which also claims them in configs/claims.json so that the machines that
    had them skip them), in the order assigned (longest first)."""
    want = [tuple(x) for x in json.load(open(POOL_ASSIGN))["assign"].get(shard, [])]
    by_lid = {}
    for j in rev2_jobs() + rev2x_jobs():
        by_lid.setdefault(j.lid, j)
    out = []
    for lid, s in want:
        j = by_lid[lid]
        out.append((Job(shard, j.tier, j.group, CLEAN_DIR[shard] if j.clean_twin else j.out, j.name, [s], j.ov,
                        clean_twin=j.clean_twin, kind=j.kind, parent=j.parent), s))
    return out


# ------------------------------------------------------------------------------------ settings
def resolve(job: Job, seed: int, fz_cit: Optional[dict], fz_base: Optional[dict]) -> Tuple[Tuple[str, str, int], List[str]]:
    ov: List[str] = []
    for o in job.ov:
        if o == "@ABST":
            ov += json.load(open(FZ_ABST))["overrides"]
        elif o == "@ABSTV":
            ov += json.load(open(FZ_ABSTV))["overrides"]
        elif o == "@JOINT":
            ov += json.load(open(FZ_JOINT))["overrides"]
        elif o == "@CIT":
            ov += fz_cit["citadel_overrides"]
        elif o.startswith("@BASE:"):
            ov += (fz_base or {}).get(o[6:], {}).get("overrides", [])
        else:
            ov.append(o)
    name = job.name
    if job.clean_twin:
        ov = [o for o in ov if not o.startswith("attack.")] + ["attack.type=none"]
        cfg = Config.from_yaml(CFG, ov)   # raises on an unknown setting
        nd = {k: v for k, v in cfg.nondefault().items() if not k.startswith("run.") or k == "run.save_params"}
        name = "clean_" + hashlib.sha1(json.dumps(nd, sort_keys=True, default=str).encode()).hexdigest()[:10]
    else:
        Config.from_yaml(CFG, ov)
    return (job.out, name, seed), ov + [f"run.name={name}", f"run.out_dir=results/{job.out}", "run.device=cpu"]


def _matches(r: dict, ov: List[str], seed: int) -> bool:
    probe = Config.from_yaml(CFG, ov)
    probe.channel.seed = seed
    return r.get("seed") == seed and probe.matches_record(r.get("config", {}), ignore=MATCH_IGNORE)


def _done_elsewhere(ov: List[str], seed: int) -> bool:
    """Calibration only: the same configuration and seed is already recorded in results/cal."""
    for fn in glob.glob(os.path.join(ROOT, "results", "cal", "*.json")):
        try:
            if _matches(json.load(open(fn)), ov, seed):
                return True
        except Exception:
            continue
    return False


# ------------------------------------------------------------------------------------ freezing
def _cal_records() -> List[dict]:
    recs = []
    for d in CAL_DIRS:
        for fn in sorted(glob.glob(os.path.join(ROOT, "results", d, "*.json"))):
            try:
                r = json.load(open(fn))
                r["_file"] = os.path.relpath(fn, ROOT)
                recs.append(r)
            except Exception:
                pass
    return recs


def freeze_citadel() -> Optional[dict]:
    """Pre-registered rule: lowest mean of (clean SER, A1 SIR 0 attack-window SER, COST2100 A1 SIR 0
    attack-window SER) over seeds 0-2, among candidates with clean false-rejection rate <= 2%."""
    import numpy as np
    recs = _cal_records()
    table = {}
    for tag, ov in CANDIDATES.items():
        cells = {}
        for cell, cov in CAL_CELLS.items():
            got = {}
            for s in CAL:
                hit = [r for r in recs if _matches(r, ["receiver.type=citadel"] + ov + cov, s)]
                if hit:
                    got[s] = hit[0]
            cells[cell] = got
        if all(len(cells[c]) == len(CAL) for c in CAL_CELLS):
            clean = [cells["clean"][s]["summary"]["ser_mean"] for s in CAL]
            a1 = [cells["a1"][s]["summary"]["ser_attack"] for s in CAL]
            cost = [cells["cost"][s]["summary"]["ser_attack"] for s in CAL]
            frej = [float(np.mean([b["gamma"] < 0.5 for b in cells["clean"][s]["blocks"] if b["block"] >= 5])) for s in CAL]
            table[tag] = {"score": float(np.mean([np.mean(clean), np.mean(a1), np.mean(cost)])), "clean_ser": float(np.mean(clean)),
                          "a1_sir0_window_ser": float(np.mean(a1)), "cost2100_sir0_window_ser": float(np.mean(cost)),
                          "clean_false_rejection": float(np.mean(frej)),
                          "records": {c: [cells[c][s]["_file"] for s in CAL] for c in CAL_CELLS}}
    if len(table) < len(CANDIDATES):
        print("calibration incomplete:", sorted(set(CANDIDATES) - set(table)), flush=True)
        return None
    admissible = {k: v for k, v in table.items() if v["clean_false_rejection"] <= 0.02}
    pool = admissible or table
    chosen = min(pool, key=lambda k: pool[k]["score"])
    fz = {"rule": "lowest mean of (clean SER, A1 SIR 0 window SER, COST2100 A1 SIR 0 window SER) on calibration seeds 0-2, "
                  "among candidates with clean false-rejection rate <= 2% (all candidates if none qualifies)",
          "seeds": CAL, "admissible": sorted(admissible), "candidates": table, "chosen": chosen,
          "citadel_overrides": CANDIDATES[chosen], "frozen_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    json.dump(fz, open(FZ_CIT, "w"), indent=1)
    print("Citadel-Rx frozen:", chosen, {k: round(v["score"], 5) for k, v in table.items()}, flush=True)
    return fz


def freeze_baselines() -> dict:
    """Pre-registered rule: lowest mean clean SER over seeds 0-2 (configurations with all seeds)."""
    import numpy as np
    best = {}
    for rx in ("online_deepsic", "meta_deepsic"):
        scores: Dict[tuple, Dict[int, float]] = {}
        for fn in glob.glob(os.path.join(ROOT, "results", "rev_cal_tune", f"tune_{rx}_*.json")):
            try:
                r = json.load(open(fn))
            except Exception:
                continue
            c = r["config"]["receiver"]
            if c["type"] == rx:
                scores.setdefault((c["epochs"], c["lr"], c["weight_decay"]), {})[r["seed"]] = r["summary"]["ser_mean"]
        full = {k: float(np.mean([v[s] for s in CAL])) for k, v in scores.items() if set(CAL) <= set(v)}
        if full:
            k = min(full, key=full.get)
            best[rx] = {"overrides": [f"receiver.epochs={k[0]}", f"receiver.lr={k[1]}", f"receiver.weight_decay={k[2]}"],
                        "cal_clean_ser": full[k],
                        "grid": {f"epochs={kk[0]} lr={kk[1]:g} wd={kk[2]:g}": v for kk, v in sorted(full.items())}}
        else:
            best[rx] = {"overrides": [], "note": "no complete tuning configuration; defaults used"}
    fz = {"rule": "lowest mean clean SER on calibration seeds 0-2", "seeds": CAL, **best,
          "frozen_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    json.dump(fz, open(FZ_BASE, "w"), indent=1)
    print("baselines frozen:", {k: v["overrides"] for k, v in best.items()}, flush=True)
    return fz


# ------------------------------------------------------------------------------------ git
GIT_LOCK = threading.Lock()
# never wait for a password: a git call without credentials fails at once instead of blocking
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")


def _run_git(args, timeout: int = 300, **kw):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, env=GIT_ENV, timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124)


def _git(*args, retries: int = 1) -> int:
    rc = 1
    for i in range(retries):
        rc = _run_git(list(args)).returncode
        if rc == 0:
            return 0
        time.sleep(2 ** (i + 1))
    return rc


def fetch_frozen_citadel() -> bool:
    """Laptop: take only configs/revision_frozen_citadel.json from GitHub (never the code)."""
    with GIT_LOCK:
        _run_git(["fetch", "-q", "origin", BRANCH], capture_output=True)
        rel = os.path.relpath(FZ_CIT, ROOT)
        r = _run_git(["checkout", f"origin/{BRANCH}", "--", rel], capture_output=True)
    return r.returncode == 0 and os.path.exists(FZ_CIT)


def push_results(shard: str) -> None:
    with GIT_LOCK:
        files = []
        for fn in glob.glob(os.path.join(ROOT, "results", "rev*_*", "*.json")):   # rev_* and rev2_*
            try:
                json.load(open(fn))   # only complete records
                files.append(os.path.relpath(fn, ROOT))
            except Exception:
                pass
        files += [os.path.relpath(f, ROOT) for f in (FZ_BASE, FZ_CIT, FZ_ABST, FZ_ABSTV, FZ_JOINT) if os.path.exists(f)]
        files += [os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(LOGS, f"{shard}*"))]
        for i in range(0, len(files), 200):
            _run_git(["add", "--", *files[i:i + 200]])
        if _run_git(["diff", "--cached", "--quiet"]).returncode != 0:
            n = len([f for f in files if f.startswith("results")])
            _run_git(["commit", "-q", "-m", f"Revision results ({shard} machine, {n} records)"])
        # -X ours: if two machines ever produced the same record (a job taken over by the helper machine
        # while its first assignee also ran it), keep this machine's; the other's clean twin stays unused
        if _git("pull", "-q", "--no-rebase", "--no-edit", "-X", "ours", "origin", BRANCH, retries=4) != 0:
            _run_git(["merge", "--abort"], capture_output=True)
            print("!! git pull failed; results are committed locally and will be pushed next time", flush=True)
            return
        ok = _git("push", "-q", "origin", f"HEAD:{BRANCH}", retries=3) == 0
        print(("pushed results to GitHub" if ok else
               "!! push failed (no GitHub login saved on this machine?): results stay committed here; in another terminal run "
               f"'git push origin HEAD:{BRANCH}' once and log in, the next automatic push then works") + f" ({time.strftime('%H:%M')})",
              flush=True)


# ------------------------------------------------------------------------------------ scheduler
class Campaign:
    def __init__(self, shard: str, workers: int, tier: int, wait_hours: float, push_every: float, min_free_mb: int,
                 cache_gb: float = 0.6, campaign: int = 1):
        self.shard, self.workers, self.wait_hours, self.push_every, self.min_free_mb = shard, workers, wait_hours, push_every, min_free_mb
        self.cache_gb = cache_gb
        self.campaign = campaign
        if campaign == 5:
            self.queue: List[Tuple[Job, int]] = pool_jobs(shard)
        elif campaign == 6:   # every run of the second campaign, its clean twins on this machine
            src = [Job(shard, j.tier, j.group, CLEAN_DIR[shard] if j.clean_twin else j.out, j.name, j.seeds, j.ov,
                       clean_twin=j.clean_twin, kind=j.kind, parent=j.parent) for j in rev2_jobs() + rev2x_jobs()
                   if j.tier <= tier and j.group not in ("H3", "D23")]   # superseded: second abstain version, unscrambled coded scene
            src.sort(key=lambda j: j.tier)
            self.queue = [(j, s) for j in src for s in j.seeds]
        else:
            src = helper_jobs() if campaign == 4 else (rev2x_jobs() if campaign == 3 else
                                                        (rev2_jobs() if campaign == 2 else calibration_jobs() + test_jobs()))
            jobs = [j for j in src if j.shard == shard and j.tier <= tier]
            if campaign == 4:
                jobs.sort(key=lambda j: {"D4": 0, "P2": 1, "P6": 2, "P5": 3, "P7": 4, "P7grid": 5}.get(j.group, 9))
            if campaign != 4:
                jobs.sort(key=lambda j: j.tier)   # stable: list order within a tier is the priority
            self.queue = [(j, s) for j in jobs for s in j.seeds]
        self.cal_kind = "cal" if shard == "cloud" else "tune"
        self.cal_left = sum(1 for j, _ in self.queue if j.kind == self.cal_kind)
        self.fz_cit = json.load(open(FZ_CIT)) if os.path.exists(FZ_CIT) else None
        self.fz_base = {} if shard == "cloud" else None   # the cloud runs no tuned baseline
        self.seen: set = set()
        self.lock = threading.Lock()
        self.done = self.failed = self.running = 0
        self.t0 = time.time()
        self.t_wait0: Optional[float] = None
        self.last_fetch = 0.0
        self.calibrated = False
        self._freezing = False
        if campaign in (2, 3, 4, 5, 6):   # settings were frozen by the first campaign's rules; nothing is calibrated again
            self.fz_cit, self.fz_base = json.load(open(FZ_CIT)), json.load(open(FZ_BASE))
            self.cal_left, self.calibrated = 0, True
        os.makedirs(LOGS, exist_ok=True)
        self.tasklog = open(os.path.join(LOGS, f"{shard}_tasks.jsonl"), "a")

    def _ready(self, job: Job) -> bool:
        if "cit" in job.needs and self.fz_cit is None:
            return False
        if "base" in job.needs and self.fz_base is None:
            return False
        # the second campaign's frozen feature settings (abstain, second backbone) arrive from GitHub
        return all(os.path.exists(FROZEN_FILE[n]) for n in job.needs & set(FROZEN_FILE))

    def _next(self):
        """Highest-priority runnable task; ('wait', None) when only blocked tasks remain; None when finished."""
        with self.lock:
            i = 0
            while i < len(self.queue):
                job, s = self.queue[i]
                if not self._ready(job):
                    i += 1
                    continue
                self.queue.pop(i)
                try:
                    key, ov = resolve(job, s, self.fz_cit, self.fz_base)
                except Exception as e:   # a setting this code does not know: skip the run, never guess
                    print(f"!! skipped {job.group} {job.name or 'clean twin'} s{s}: {e!r} (update the code: git pull)", flush=True)
                    if job.kind == self.cal_kind:
                        self.cal_left -= 1
                    continue
                skip = key in self.seen or (job.kind == "cal" and _done_elsewhere(ov[:-3], s))
                self.seen.add(key)
                if skip:
                    if job.kind == self.cal_kind:
                        self.cal_left -= 1
                    continue
                self.running += 1
                return job, s, key, ov
            busy_cal = self.cal_left > 0 or not self.calibrated
            return ("wait", None) if (self.queue or busy_cal and self.running) else None

    def _after_calibration(self) -> None:
        if self.shard == "laptop":
            fz = freeze_baselines()
            with self.lock:
                self.fz_base = fz
        else:
            fz = freeze_citadel()
            with self.lock:
                if fz is not None:
                    self.fz_cit = fz
                else:   # a calibration run failed: never guess the configuration
                    n = len(self.queue)
                    self.queue = [(j, s) for j, s in self.queue if "cit" not in j.needs]
                    print(f"!! calibration incomplete: {n - len(self.queue)} Citadel-Rx runs dropped; fix the failed run and restart",
                          flush=True)
        self.calibrated = True
        push_results(self.shard)   # the laptop picks the frozen Citadel-Rx file up from GitHub

    def _worker(self) -> None:
        while True:
            free_mb = shutil.disk_usage(ROOT).free // 2 ** 20
            if free_mb < self.min_free_mb:
                print(f"!! only {free_mb} MB of disk left: paused (free some space; it resumes by itself)", flush=True)
                time.sleep(120)
                continue
            with self.lock:
                trigger = self.cal_left == 0 and not self.calibrated and not self._freezing
                if trigger:
                    self._freezing = True
            if trigger:
                self._after_calibration()
            nxt = self._next()
            if nxt is None:
                return
            if nxt[0] == "wait":
                self._maybe_fetch()
                time.sleep(20)
                continue
            job, s, key, ov = nxt
            cmd = [sys.executable, RUN, CFG, "--quiet", "--seeds", str(s), "--set", *ov]
            env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1",
                       CITADEL_THREADS="1", CITADEL_PRETRAIN_CACHE=CACHE, CITADEL_PRETRAIN_CACHE_GB=str(self.cache_gb),
                       CITADEL_MACHINE=self.shard, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            t = time.time()
            r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT, encoding="utf-8", errors="replace")
            dt = time.time() - t
            with self.lock:
                self.running -= 1
                self.done += 1
                self.failed += r.returncode != 0
                if job.kind == self.cal_kind:
                    self.cal_left -= 1
                left = len(self.queue) + self.running
                el = time.time() - self.t0
                tail = (r.stdout.strip().splitlines() or [""])[-1][:140]
                print(f"[{self.done} done, ~{left} left | {el / 3600:.1f} h, ~{el / self.done * left / 3600:.1f} h to go at this pace] "
                      f"t{job.tier} {job.group} {key[1]} s{s} {'OK' if r.returncode == 0 else 'FAIL'} {dt / 60:.0f} min  {tail}"
                      + ("" if r.returncode == 0 else "\n" + r.stderr[-1500:]), flush=True)
                self.tasklog.write(json.dumps({"shard": self.shard, "tier": job.tier, "group": job.group, "out": key[0], "name": key[1],
                                               "seed": s, "ok": r.returncode == 0, "seconds": round(dt, 1),
                                               "finished": _dt.datetime.now(_dt.timezone.utc).isoformat()}) + "\n")
                self.tasklog.flush()

    def _maybe_fetch(self) -> None:
        if self.campaign == 5:   # pool: take only the frozen feature settings from GitHub, every 5 minutes
            if time.time() - self.last_fetch >= 300:
                self.last_fetch = time.time()
                with GIT_LOCK:
                    _run_git(["fetch", "-q", "origin", BRANCH], capture_output=True)
                    for f in FROZEN_FILE.values():
                        _run_git(["checkout", f"origin/{BRANCH}", "--", os.path.relpath(f, ROOT)], capture_output=True)
            return
        if self.shard != "laptop" or self.fz_cit is not None:
            return
        if self.t_wait0 is None:
            self.t_wait0 = time.time()
            print("waiting for configs/revision_frozen_citadel.json from the cloud machine (checked every 5 min)", flush=True)
        if time.time() - self.last_fetch < 300:
            return
        self.last_fetch = time.time()
        if fetch_frozen_citadel():
            fz = json.load(open(FZ_CIT))
            with self.lock:
                self.fz_cit = fz
            print("fetched the frozen Citadel-Rx settings:", fz["chosen"], fz["citadel_overrides"], flush=True)
        elif time.time() - self.t_wait0 > self.wait_hours * 3600:
            with self.lock:
                n = len(self.queue)
                self.queue = [(j, s) for j, s in self.queue if "cit" not in j.needs]
            print(f"!! no frozen Citadel-Rx settings after {self.wait_hours} h: dropped {n - len(self.queue)} Citadel-Rx runs", flush=True)

    def run(self) -> None:
        print(f"== {self.shard}: {len(self.queue)} runs queued (before de-duplication), {self.workers} workers, "
              f"pre-training cache {os.path.relpath(CACHE, ROOT)}", flush=True)
        stop = threading.Event()

        def pusher():
            while not stop.wait(self.push_every * 60):
                push_results(self.shard)

        threading.Thread(target=pusher, daemon=True).start()
        ths = [threading.Thread(target=self._worker) for _ in range(self.workers)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        stop.set()
        if self.campaign == 5:   # paired displacement on this machine, which holds the level snapshots
            snap = sorted({j.out for j, _ in pool_jobs(self.shard) if "run.save_params=true" in j.ov and not j.clean_twin})
            for folder in snap:
                r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "paired_disp.py"), os.path.join("results", folder),
                                    "--clean", os.path.join("results", CLEAN_DIR[self.shard]),
                                    "--out", os.path.join(LOGS, f"{self.shard}_paired_{folder}")], cwd=ROOT, capture_output=True, text=True)
                print(f"paired displacement {folder}: rc {r.returncode}\n{r.stdout[-3000:]}{r.stderr[-1500:]}", flush=True)
        print(f"== {self.shard} finished: {self.done} runs, {self.failed} failed, {(time.time() - self.t0) / 3600:.1f} h", flush=True)
        push_results(self.shard)


def dry(shard_filter: Optional[str], campaign: int = 1) -> None:
    fzc = {"citadel_overrides": CANDIDATES["rel_select_clip"]}
    fzb = {"online_deepsic": {"overrides": ["receiver.epochs=100"]}, "meta_deepsic": {"overrides": ["receiver.epochs=100"]}}
    if campaign == 2:
        fzc, fzb = json.load(open(FZ_CIT)), json.load(open(FZ_BASE))
    keys_by_shard: Dict[str, set] = {}
    shards = ("cloud", "windows") if campaign == 2 else ("laptop", "cloud")
    src = rev2_jobs() if campaign == 2 else calibration_jobs() + test_jobs()
    for shard in shards:
        jobs = sorted([j for j in src if j.shard == shard], key=lambda j: j.tier)
        seen, per = set(), {}
        for j in jobs:
            for s in j.seeds:
                key, ov = resolve(j, s, fzc, fzb)   # validates every setting
                if key in seen:
                    continue
                seen.add(key)
                per[(j.tier, j.group)] = per.get((j.tier, j.group), 0) + 1
        keys_by_shard[shard] = seen
        if shard_filter in (None, shard):
            print(f"{shard}: {len(seen)} runs")
            for (t, g), n in sorted(per.items()):
                print(f"   tier {t}  {g:10s} {n}")
    a, b = (keys_by_shard[x] for x in shards)
    both = a & b
    print("shared runs:", len(both))
    assert not both, "the two machines must not write the same files"
    if campaign == 1:
        outs = {k[0] for k in a} & {k[0] for k in b}
        print("shared folders:", sorted(outs) or "none")
        assert not outs, "the two machines must not write the same files"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", choices=["laptop", "cloud", "windows", "cloudx", "cloudy", "cloudz", "helper", "local"] +
                    [f"pool{i}" for i in range(1, 13)])
    ap.add_argument("--campaign", type=int, choices=[1, 2, 3, 4, 5, 6], default=1,
                    help="2 = the second revision campaign, 3 = its new-feature experiments (shards cloudx, cloudy), "
                         "4 = the helper machine, 5 = the pool machines (configs/pool_assign.json), "
                         "6 = the whole second campaign on one machine (--shard local)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tier", type=int, choices=[0, 1, 2, 3], default=3, help="run tiers up to this one (0: calibration and tuning only)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--push-only", action="store_true")
    ap.add_argument("--push-every", type=float, default=45.0, help="minutes between automatic pushes")
    ap.add_argument("--wait-hours", type=float, default=8.0, help="laptop: how long to wait for the Citadel-Rx freeze")
    ap.add_argument("--min-free-mb", type=int, default=400)
    ap.add_argument("--cache-gb", type=float, default=None, help="pre-training cache cap (default 0.6 laptop, 3 cloud)")
    args = ap.parse_args()
    os.chdir(ROOT)
    if args.dry:
        dry(args.shard, args.campaign)
        return
    if not args.shard:
        ap.error("--shard is required")
    if args.push_only:
        push_results(args.shard)
        return
    cache_gb = args.cache_gb if args.cache_gb is not None else (3.0 if args.shard.startswith(("cloud", "pool", "local")) or args.shard == "helper" else 0.6)
    Campaign(args.shard, args.workers, args.tier, args.wait_hours, args.push_every, args.min_free_mb, cache_gb, args.campaign).run()


if __name__ == "__main__":
    main()
