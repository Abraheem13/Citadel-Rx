#!/usr/bin/env python
"""Revision campaign for the reviewer audit, in priority order, resumable, one command.

Phase A (calibration, seeds 0-2, never reported as results)
  A1  tune online DeepSIC and Meta-DeepSIC on clean blocks over epochs x lr x weight decay (C5)
  A2  Citadel-Rx candidate configurations on clean, A1 SIR 0 and COST2100 A1 SIR 0
  ->  configs/revision_frozen.json is written by a PRE-REGISTERED rule:
      baselines: lowest mean clean SER over the calibration seeds;
      Citadel-Rx: lowest mean of (clean SER, A1 window SER, COST2100 window SER) among candidates
      whose clean false-rejection rate is at most 2%.
Phase B (test, fresh seeds 10-19; nothing is tuned here)
  P1 headline grid, 10 seeds, randomised attack window, matched clean runs (E2, E3)
  P2 remaining and new baselines, 5 seeds (C1-C4, C6, C7)
  P3 attacks built against the defence: adaptive sweep (B4), reference degradation (B2),
     denial + abrupt change (B3, D6), physical rank-M attacker (B1), grey-box and query (B6),
     signal-referenced budget (B8)
  P4 paired displacement with snapshots (E7, A2)
  P5 ablations on test seeds (C1 K=1 fix and all components)
  P6 block length (D1), arrays N>U (D4), 16-QAM (D5), 30-step / last-layer variants (D9)
  P7 hyperparameter sensitivity (E5)
  P8 optimised slow drift over 1000 blocks (B5) and 2000-block clean horizon (D7)
Every attacked job gets a matched clean job (same settings except attack.*), so excess SER
(attacked minus clean on the same blocks) is available everywhere.

    python scripts/revision_campaign.py --workers 8            # runs everything (resumes)
    python scripts/revision_campaign.py --phase A --workers 8  # calibration only
    python scripts/revision_campaign.py --dry                  # list the jobs
    python scripts/revision_campaign.py --only P1 P3 --workers 8
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "scripts", "run_experiment.py")
CFG = os.path.join(ROOT, "configs", "e3_a1_defence.yaml")
FROZEN = os.path.join(ROOT, "configs", "revision_frozen.json")
CAL_SEEDS = [0, 1, 2]
TEST10 = list(range(10, 20))
TEST5 = list(range(10, 15))
TEST3 = list(range(10, 13))
KAPPA = "[8.5,4.5]"      # clean p99 of the consolidation increments (levels 2, 3), measured on calibration runs

CITADEL_CANDIDATES = {
    "rel_select_clip": ["citadel.g2_slack_mode=relative", "citadel.crc_select=true", f"citadel.consol_clip={KAPPA}", "citadel.consol_mean=normalized"],
    "derived_select_clip": ["citadel.g2_slack_mode=derived", "citadel.crc_select=true", f"citadel.consol_clip={KAPPA}", "citadel.consol_mean=normalized"],
    "rel_select_clip_anchorstart": ["citadel.g2_slack_mode=relative", "citadel.crc_select=true", f"citadel.consol_clip={KAPPA}", "citadel.consol_mean=normalized",
                                    "citadel.fast_init=anchor", "citadel.fast_radius=13"],
}
REFERENCE_CITADEL = ["citadel.g2_slack_mode=relative"]     # the submitted configuration, for comparison

Job = Tuple[str, str, List[int], List[str]]   # (phase, out_dir, seeds, overrides incl. run.name)


def job(phase: str, out: str, name: str, seeds: List[int], ov: List[str]) -> List[Job]:
    return [(phase, out, seeds, ov + [f"run.name={name}", f"run.out_dir=results/{out}", "run.device=cpu"])]


def with_clean_twin(phase: str, out: str, name: str, seeds: List[int], ov: List[str]) -> List[Job]:
    """An attacked job plus its matched clean job (identical except attack.*). Clean twins live in
    one shared folder and are named by a hash of their settings, so identical clean
    configurations are run once and shared by every attack that needs them."""
    import hashlib
    clean_ov = sorted(o for o in ov if not o.startswith("attack.")) + ["attack.type=none"]
    h = hashlib.sha1(" ".join(clean_ov).encode()).hexdigest()[:10]
    return job(phase, out, name, seeds, ov) + job(phase, "rev_clean", f"clean_{h}", seeds, clean_ov)


# ------------------------------------------------------------------------------------ phase A
def phase_a() -> List[Job]:
    jobs: List[Job] = []
    for rx, ep, lr, wd in itertools.product(["online_deepsic", "meta_deepsic"], [30, 100, 300], [1e-3, 5e-3], [0.0, 1e-4]):
        jobs += job("A", "rev_cal_tune", f"tune_{rx}_ep{ep}_lr{lr:g}_wd{wd:g}", CAL_SEEDS,
                    [f"receiver.type={rx}", f"receiver.epochs={ep}", f"receiver.lr={lr}", f"receiver.weight_decay={wd}",
                     "attack.type=none"])
    cells = {"clean": ["attack.type=none"], "a1": ["attack.type=a1", "attack.sir_db=0"],
             "cost": ["channel.model=cost2100", "attack.type=a1", "attack.sir_db=0"]}
    for tag, ov in list(CITADEL_CANDIDATES.items()) + [("reference", REFERENCE_CITADEL)]:
        for cell, cov in cells.items():
            jobs += job("A", "rev_cal_citadel", f"cand_{tag}__{cell}", CAL_SEEDS, ["receiver.type=citadel"] + ov + cov)
    return jobs


def _records(folder: str) -> List[dict]:
    out = []
    for fn in glob.glob(os.path.join(ROOT, "results", folder, "*.json")):
        try:
            out.append(json.load(open(fn)))
        except Exception:
            pass
    return out


def freeze() -> Dict:
    """The pre-registered selection rule. Writes configs/revision_frozen.json."""
    import numpy as np
    tune = _records("rev_cal_tune")
    best = {}
    for rx in ("online_deepsic", "meta_deepsic"):
        scores = {}
        for r in tune:
            c = r["config"]["receiver"]
            if c["type"] != rx:
                continue
            key = (c["epochs"], c["lr"], c["weight_decay"])
            scores.setdefault(key, []).append(r["summary"]["ser_mean"])
        full = {k: float(np.mean(v)) for k, v in scores.items() if len(v) == len(CAL_SEEDS)}
        if full:
            k = min(full, key=full.get)
            best[rx] = {"overrides": [f"receiver.epochs={k[0]}", f"receiver.lr={k[1]}", f"receiver.weight_decay={k[2]}"],
                        "cal_clean_ser": full[k], "grid": {str(kk): v for kk, v in full.items()}}
    cal = _records("rev_cal_citadel")
    table = {}
    for tag in CITADEL_CANDIDATES:
        vals, frej = [], []
        for cell, metric in (("clean", "ser_mean"), ("a1", "ser_attack"), ("cost", "ser_attack")):
            rs = [r for r in cal if r["name"] == f"cand_{tag}__{cell}"]
            if len(rs) < len(CAL_SEEDS):
                break
            vals.append(float(np.mean([r["summary"][metric] for r in rs])))
            if cell == "clean":
                frej = [float(np.mean([b["gamma"] < 0.5 for b in r["blocks"] if b["block"] >= 5])) for r in rs]
        if len(vals) == 3:
            table[tag] = {"score": float(np.mean(vals)), "clean": vals[0], "a1": vals[1], "cost": vals[2],
                          "false_rej_clean": float(np.mean(frej))}
    admissible = {k: v for k, v in table.items() if v["false_rej_clean"] <= 0.02} or table
    chosen = min(admissible, key=lambda k: admissible[k]["score"]) if admissible else "rel_select_clip"
    frozen = {"rule": "baselines: min mean clean SER on seeds 0-2; Citadel: min mean of (clean, A1 SIR0, COST2100 SIR0) "
                      "SER on seeds 0-2 subject to clean false rejection <= 2%",
              "baselines": best, "citadel_candidates": table, "citadel_chosen": chosen,
              "citadel_overrides": CITADEL_CANDIDATES[chosen]}
    json.dump(frozen, open(FROZEN, "w"), indent=1)
    print(json.dumps({"chosen": chosen, "candidates": table, "baselines": {k: v["overrides"] for k, v in best.items()}}, indent=1))
    return frozen


# ------------------------------------------------------------------------------------ phase B
def phase_b(fz: Dict) -> List[Job]:
    CIT = ["receiver.type=citadel"] + fz["citadel_overrides"]
    tuned = {rx: v["overrides"] for rx, v in fz.get("baselines", {}).items()}
    RND = ["attack.start_mode=random"]
    rx_ov = lambda rx: (CIT if rx == "citadel" else
                        [f"receiver.type={rx}"] + tuned.get("online_deepsic" if rx == "online_select" else rx, []))
    jobs: List[Job] = []

    # P1 headline: 10 seeds, randomised window, matched clean runs (E2, E3)
    for rx in ["citadel", "online_deepsic", "meta_deepsic", "crc_rollback", "online_select"]:
        cells = {f"wb_sir{s}": ["attack.type=a1", "attack.knowledge=whitebox", f"attack.sir_db={s}"] for s in (-10, 0, 10)}
        cells["tr_sir0"] = ["attack.type=a1", "attack.knowledge=transfer", "attack.sir_db=0"]
        cells["jam"] = ["attack.type=data_jam", "attack.sir_db=0"]
        for cell, cov in cells.items():
            jobs += with_clean_twin("P1", "rev_p1", f"p1_{rx}__{cell}", TEST10, rx_ov(rx) + RND + cov)

    # P2 remaining and new baselines, 5 seeds (C1-C4, C6, C7)
    for rx in ["lmmse", "lmmse_robust", "drift_deepsic", "medbn_deepsic", "titans_single", "rollback_allgates",
               "l2sp_deepsic", "ema_deepsic", "ewc_deepsic", "dd_deepsic", "cotta_deepsic", "eata_deepsic"]:
        for cell, cov in {"wb_sir0": ["attack.type=a1", "attack.sir_db=0"], "wb_sir10": ["attack.type=a1", "attack.sir_db=10"],
                          "tr_sir0": ["attack.type=a1", "attack.knowledge=transfer", "attack.sir_db=0"]}.items():
            jobs += with_clean_twin("P2", "rev_p2", f"p2_{rx}__{cell}", TEST5, [f"receiver.type={rx}"] + RND + cov)
    for w in (1e-3, 1e-2, 1e-1, 1.0):   # L2-SP weight sweep (C2)
        jobs += with_clean_twin("P2", "rev_p2", f"p2_l2sp_w{w:g}__wb_sir0", TEST5,
                                ["receiver.type=l2sp_deepsic", f"receiver.reg_weight={w}", "attack.type=a1", "attack.sir_db=0"] + RND)

    # P3 attacks built against the defence
    strongest = ["attack.soft_gate=true", "attack.unroll_steps=10", "attack.pgd_steps=100", "attack.restarts=5", "attack.eot=4"]
    adaptive = {"unroll2": ["attack.unroll_steps=2"], "unroll10": ["attack.unroll_steps=10"], "unroll50": ["attack.unroll_steps=50"],
                "pgd100_r5": ["attack.pgd_steps=100", "attack.restarts=5"],
                "softgate": ["attack.soft_gate=true", "attack.unroll_steps=10"], "strongest": strongest}
    for tag, aov in adaptive.items():
        for s in (0, 10):
            jobs += with_clean_twin("P3", "rev_p3_adaptive", f"p3_citadel_{tag}__sir{s}", TEST5,
                                    CIT + RND + ["attack.type=a1", f"attack.sir_db={s}"] + aov)
    for s in (0, 10):
        jobs += with_clean_twin("P3", "rev_p3_adaptive", f"p3_online_strongest__sir{s}", TEST5,
                                rx_ov("online_deepsic") + RND + ["attack.type=a1", f"attack.sir_db={s}"] + strongest[1:])
    for a, s, ab in itertools.product((0.25, 0.5, 0.75), (0, 10), (False, True)):   # B2 reference degradation
        extra = ["citadel.abstain=true"] if ab else []
        jobs += with_clean_twin("P3", "rev_p3_refdeg", f"p3_a4_a{a:g}{'_abstain' if ab else ''}__sir{s}", TEST5,
                                CIT + extra + RND + ["attack.type=a4", f"attack.a4_alpha={a}", f"attack.sir_db={s}"])
    import math
    for a, s in itertools.product((0.25, 0.5, 0.75), (0, 10)):   # jamming-only control at the same data power
        jobs += job("P3", "rev_p3_refdeg", f"p3_jamctl_a{a:g}__sir{s}", TEST5,
                    CIT + RND + ["attack.type=data_jam", f"attack.sir_db={s - 10 * math.log10(1 - a):.3f}"])
    abrupt = {"redraw": ["channel.abrupt_block=50", "channel.abrupt_type=redraw"],
              "snrdrop": ["channel.abrupt_block=50", "channel.abrupt_type=snr_drop"]}
    for sc, cov in abrupt.items():   # B3 denial of adaptation + D6 abrupt change
        for rx, extra in (("citadel", []), ("citadel_streak", ["citadel.streak_k=5"]), ("online_deepsic", []), ("lmmse", [])):
            base = (CIT + extra) if rx.startswith("citadel") else rx_ov(rx)
            jobs += job("P3", "rev_p3_deny", f"p3_{rx}_{sc}__none", TEST5, base + cov + ["attack.type=none"])
            jobs += job("P3", "rev_p3_deny", f"p3_{rx}_{sc}__deny", TEST5,
                        base + cov + ["attack.type=deny", "attack.sir_db=10", "attack.start_block=40", "attack.end_block=90"])
    phys = {"M1": ["attack.attacker_antennas=1"], "M2": ["attack.attacker_antennas=2"], "M4": ["attack.attacker_antennas=4"],
            "M2_csi0.01": ["attack.attacker_antennas=2", "attack.attacker_csi_err=0.01"],
            "M2_csi0.1": ["attack.attacker_antennas=2", "attack.attacker_csi_err=0.1"]}
    for tag, pov in phys.items():   # B1 physical attacker
        for rx in ("citadel", "online_deepsic"):
            jobs += with_clean_twin("P3", "rev_p3_phys", f"p3_{rx}_{tag}__sir0", TEST5, rx_ov(rx) + RND + ["attack.type=a1", "attack.sir_db=0"] + pov)
    for s in (0, 10):   # B6 grey-box (Citadel surrogate from another seed) and query attacker
        jobs += with_clean_twin("P3", "rev_p3_know", f"p3_citadel_greybox__sir{s}", TEST5,
                                CIT + RND + ["attack.type=a1", "attack.knowledge=transfer", "attack.surrogate=citadel", f"attack.sir_db={s}"])
        for rx in ("citadel", "online_deepsic"):
            jobs += with_clean_twin("P3", "rev_p3_know", f"p3_{rx}_query__sir{s}", TEST5,
                                    rx_ov(rx) + RND + ["attack.type=a1", "attack.knowledge=query", f"attack.sir_db={s}"])
    for rx in ("citadel", "online_deepsic"):   # B8 signal-referenced budget
        jobs += with_clean_twin("P3", "rev_p3_know", f"p3_{rx}_sigbudget__sir0", TEST5,
                                rx_ov(rx) + RND + ["attack.type=a1", "attack.sir_db=0", "attack.budget_ref=signal"])

    # P4 paired displacement with snapshots (E7, A2)
    for s in (0, 10):
        jobs += with_clean_twin("P4", "rev_p4_paired", f"p4_citadel__sir{s}", TEST5,
                                CIT + ["attack.type=a1", f"attack.sir_db={s}", "run.save_params=true"])

    # P5 ablations on test seeds, final configuration (C1 fix included)
    ab = {"full": [], "K1": ["citadel.levels=1", "citadel.periods=[1]", "citadel.consol_clip=[]"],
          "K2": ["citadel.levels=2", "citadel.periods=[1,8]", "citadel.consol_clip=[8.5]"],
          "K4": ["citadel.levels=4", "citadel.periods=[1,4,16,64]", "citadel.consol_clip=[8.5,6,4.5]"],
          "misaligned": ["citadel.periods=[1,3,7]"], "nogate": ["citadel.gates=[]"], "g1": ["citadel.gates=[g1]"],
          "g2": ["citadel.gates=[g2]"], "g3": ["citadel.gates=[g3]"], "last_only": ["citadel.adaptable=last"],
          "plain_gd": ["citadel.fast_rule=gd"], "adam_no_delta": ["citadel.fast_rule=adam"], "fixed_eta": ["citadel.surprise_lr=false"],
          "no_anchor": ["citadel.prox_lambda=0.0", "citadel.reanchor_beta=0.0"],
          "jump_anchor": ["citadel.reanchor_mode=jump", "citadel.reanchor_beta=0.25"], "no_fallback": ["citadel.fallback_on_reject=false"],
          "reject_keep": ["citadel.reject_action=keep"], "no_select": ["citadel.crc_select=false"], "no_clip": ["citadel.consol_clip=[]"]}
    for tag, aov in ab.items():
        jobs += with_clean_twin("P5", "rev_p5_ablate", f"p5_{tag}__wb_sir0", TEST5, CIT + aov + RND + ["attack.type=a1", "attack.sir_db=0"])

    # P6 block length (D1), arrays (D4), 16-QAM (D5), deployable variants (D9)
    for nd, npil in itertools.product((1000, 5000, 25000), (32, 100, 200)):
        for rx in ("citadel", "online_deepsic"):
            jobs += with_clean_twin("P6", "rev_p6_blocklen", f"p6_{rx}_nd{nd}_np{npil}__sir0", TEST3,
                                    rx_ov(rx) + [f"frame.data_bits={2 * nd}", f"frame.pilot_bits={2 * npil}", "attack.type=a1", "attack.sir_db=0"] + RND)
    for U, N in ((4, 16), (8, 32)):
        for rx in ("citadel", "online_deepsic", "meta_deepsic", "lmmse"):
            jobs += with_clean_twin("P6", "rev_p6_arrays", f"p6_{rx}_{U}x{N}__sir0", TEST3,
                                    rx_ov(rx) + [f"channel.n_user={U}", f"channel.n_ant={N}", "attack.type=a1", "attack.sir_db=0"] + RND)
    for rx in ("citadel", "online_deepsic", "lmmse"):
        jobs += with_clean_twin("P6", "rev_p6_qam16", f"p6_{rx}_qam16__sir0", TEST3,
                                rx_ov(rx) + ["frame.modulation=QAM16", "receiver.hidden_base=16", "channel.snr_db=20",
                                             "frame.data_bits=100000", "frame.pilot_bits=400", "attack.type=a1", "attack.sir_db=0"] + RND)
    for tag, vov in {"steps30": ["citadel.fast_steps=30"], "last_layer": ["citadel.adaptable=last"]}.items():
        jobs += with_clean_twin("P6", "rev_p6_deploy", f"p6_citadel_{tag}__sir0", TEST3, CIT + vov + RND + ["attack.type=a1", "attack.sir_db=0"])

    # P7 hyperparameter sensitivity, one at a time at x0.5, x0.75, x1.5, x2 (E5)
    sens = {"g1_slack": [f"citadel.g1_tau={1 + 0.25 * m}" for m in (0.5, 0.75, 1.5, 2)],
            "g3_slack": [f"citadel.g3_tau={1 + 3 * m}" for m in (0.5, 0.75, 1.5, 2)],
            "tighten": [f"citadel.tighten_floor={1 - 0.3 * m}" for m in (0.5, 0.75, 1.5, 2)],
            "soft_width": [f"citadel.gate_kappa={0.1 * m}" for m in (0.5, 0.75, 1.5, 2)],
            "prox_lambda": [f"citadel.prox_lambda={0.5 * m}" for m in (0.5, 0.75, 1.5, 2)],
            "eta3": [f"citadel.level_lr=[1.0,{0.5 * m}]" for m in (0.5, 0.75, 1.5, 2)],
            "delta": [f"citadel.dgd_delta={0.1 * m}" for m in (0.5, 0.75, 1.5, 2)],
            "crc_rel": [f"citadel.g2_rel_slack={1.0 * m}" for m in (0.5, 0.75, 1.5, 2)]}
    for par, vals in sens.items():
        for i, v in enumerate(vals):
            jobs += with_clean_twin("P7", "rev_p7_sens", f"p7_{par}_x{(0.5, 0.75, 1.5, 2)[i]}__wb_sir0", TEST3[:2],
                                    CIT + [v] + RND + ["attack.type=a1", "attack.sir_db=0"])
    for g1, rel in itertools.product((1.125, 1.25, 1.5, 2.0), (0.5, 1.0, 2.0, 4.0)):
        jobs += job("P7", "rev_p7_heat", f"p7_heat_g1{g1:g}_rel{rel:g}__wb_sir0", TEST3[:2],
                    CIT + [f"citadel.g1_tau={g1}", f"citadel.g2_rel_slack={rel}"] + RND + ["attack.type=a1", "attack.sir_db=0"])
        jobs += job("P7", "rev_p7_heat", f"p7_heat_g1{g1:g}_rel{rel:g}__clean", TEST3[:2],
                    CIT + [f"citadel.g1_tau={g1}", f"citadel.g2_rel_slack={rel}", "attack.type=none"])

    # P8 long horizons: optimised slow drift over 1000 blocks (B5) and 2000 clean blocks (D7)
    for e, dg in ((0.05, False), (0.2, False), (0.5, False), (0.2, True), (0.5, True)):
        extra = ["citadel.drift_guard=0.05"] if dg else []
        jobs += with_clean_twin("P8", "rev_p8_drift", f"p8_a3star_e{e:g}{'_guard' if dg else ''}__long", TEST3,
                                CIT + extra + ["frame.n_blocks=1000", "attack.type=a3star", f"attack.a3_eps_small={e}",
                                               "attack.start_block=30", "attack.end_block=930", "run.save_params=true"])
    for rx, fad in itertools.product(("citadel", "online_deepsic"), ("cosine", "jakes")):
        jobs += job("P8", "rev_p8_horizon", f"p8_{rx}_{fad}__h2000", [10], rx_ov(rx) + [f"channel.fading={fad}", "frame.n_blocks=2000", "attack.type=none"])
    return dedupe(jobs)


def dedupe(jobs: List[Job]) -> List[Job]:
    seen, out = set(), []
    for j in jobs:
        key = (j[1], tuple(sorted(o for o in j[3] if not o.startswith("run.name="))), tuple(j[2]))
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


# ------------------------------------------------------------------------------------ runner
def expand(jobs: List[Job]) -> List[Tuple[str, List[str]]]:
    cmds = []
    for phase, out, seeds, ov in jobs:
        for s in seeds:
            cmds.append((phase, [sys.executable, RUN, CFG, "--quiet", "--seeds", str(s), "--set", *ov]))
    return cmds


def run_all(cmds, workers: int) -> None:
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", CITADEL_THREADS="1")
    done = [0]

    def one(c):
        r = subprocess.run(c[1], capture_output=True, text=True, env=env, cwd=ROOT)
        done[0] += 1
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        print(f"[{done[0]}/{len(cmds)}] {c[0]} " + ("OK  " if r.returncode == 0 else "FAIL") + " " + tail
              + ("" if r.returncode == 0 else "\n" + r.stderr[-1500:]), flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, cmds))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--phase", choices=["A", "B", "all"], default="all")
    ap.add_argument("--only", nargs="*", default=None, help="phase-B groups to run, e.g. P1 P3")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    if args.phase in ("A", "all"):
        ja = expand(phase_a())
        print(f"Phase A: {len(ja)} runs")
        if not args.dry:
            run_all(ja, args.workers)
            freeze()
    if args.phase in ("B", "all"):
        if not os.path.exists(FROZEN):
            if args.dry:
                fz = {"citadel_overrides": CITADEL_CANDIDATES["rel_select_clip"], "baselines": {}}
            else:
                fz = freeze()
        else:
            fz = json.load(open(FROZEN))
        jb = phase_b(fz)
        if args.only:
            jb = [j for j in jb if j[0] in args.only]
        cmds = expand(jb)
        groups = {}
        for p, _ in cmds:
            groups[p] = groups.get(p, 0) + 1
        print("Phase B:", len(cmds), "runs", groups)
        if not args.dry:
            run_all(cmds, args.workers)


if __name__ == "__main__":
    main()
