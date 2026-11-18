"""Job lists of the v3 phases (docs/ROADMAP_9of10.md). A job is one configuration run on a list of seeds;
an attacked job carries a clean twin (the same settings with attack.* removed, run on the same machine).

Settings carried over from the second campaign and frozen there by pre-registered rules on seeds 0-2:
  @CIT            configs/revision_frozen_citadel.json   (relative CRC slack, CRC selection, clip, normalized mean)
  @BASE:<rx>      configs/revision_frozen_baselines.json (online / Meta-DeepSIC optimiser settings)
Every receiver built on online DeepSIC uses the online DeepSIC setting, as in the second campaign.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

T20 = list(range(20, 30))      # v3 test seeds (roadmap rule 1); 10-19 are retired
CAL = [0, 1, 2]                # calibration seeds
ONLINE_BASED = {"online_deepsic", "online_select", "crc_rollback", "rollback_allgates", "l2sp_deepsic", "ema_deepsic",
                "ewc_deepsic", "dd_deepsic", "cotta_deepsic", "eata_deepsic", "drift_deepsic", "medbn_deepsic", "titans_single"}
RND = ["attack.start_mode=random"]


def a1(sir) -> List[str]:
    return ["attack.type=a1", f"attack.sir_db={sir}"]


def rx(name: str) -> List[str]:
    if name == "citadel":
        return ["receiver.type=citadel", "@CIT"]
    if name == "meta_deepsic":
        return ["receiver.type=meta_deepsic", "@BASE:meta_deepsic"]
    if name == "frozen_deepsic":       # pre-trained DeepSIC that never adapts (as scripts/extra_baselines.py)
        return ["receiver.type=online_deepsic", "@BASE:online_deepsic", "receiver.epochs=0"]
    if name == "frozen_select":        # the same, with per-sub-block CRC selection against LMMSE (roadmap 1a)
        return ["receiver.type=online_select", "@BASE:online_deepsic", "receiver.epochs=0"]
    if name.startswith("cls_"):         # v3 Citadel-LS: multi-rate verified channel-estimate memory (Phase 3)
        return ["receiver.type=citadel_ls", f"receiver.detector={name[4:]}", "@CIT", "receiver.guard_noise_ref=calibrated"]
    if name in ("ml_never", "ml_crc", "ml_count", "lmmse_never", "lmmse_crc"):   # single-state model-based guards
        det, mode = name.split("_")   # Phase 3: the same offline noise calibration as Citadel-LS (fairness)
        return (rx(f"model_{det}_guard") + ([] if mode == "count" else [f"receiver.guard_rebase={mode}"])
                + ["receiver.guard_noise_ref=calibrated"])
    if name == "citadel_ccv":          # Phase 4: conditioned on the verified channel estimate
        return rx("citadel_cc") + ["receiver.cond_source=verified"]
    if name in ("kbest_never", "kbest_crc", "kbest_count"):   # K-best guards (8 x 32)
        mode = name.split("_")[1]
        return (["receiver.type=model", "receiver.detector=kbest", "receiver.guard=true", "receiver.guard_noise_ref=calibrated"]
                + ([] if mode == "count" else [f"receiver.guard_rebase={mode}"]))
    if name.endswith("_cc"):           # v3 channel-conditioned backbone (receivers/conditioning.py)
        base = {"online_cc": "online_deepsic", "frozen_cc": "frozen_deepsic", "citadel_cc": "citadel"}[name]
        return rx(base) + ["receiver.cond=lmmse"]
    if name.startswith("model_"):      # model_<detector>[_perfect][_guard]
        parts = name.split("_")[1:]
        det = parts[0] if parts[0] != "mmse" else "mmse_sic"
        ov = ["receiver.type=model", f"receiver.detector={det}"]
        if "perfect" in parts:
            ov.append("receiver.csi=perfect")
        if "guard" in parts:
            ov.append("receiver.guard=true")
        return ov
    if name in ONLINE_BASED:
        return [f"receiver.type={name}", "@BASE:online_deepsic"]
    return [f"receiver.type={name}"]


@dataclass
class Job:
    group: str                  # experiment id of the roadmap (1a, 1b, ...)
    name: str                   # run name (also the record file prefix)
    seeds: List[int]
    ov: List[str]               # dotted overrides on configs/e3_a1_defence.yaml (placeholders @CIT, @BASE:...)
    twin: bool = True           # also run the matched clean twin
    priority: int = 0           # lower runs first
    stage: str = "all"          # cal: calibration runs; test: needs the settings frozen from the cal stage
    tags: List[str] = field(default_factory=list)


def phase1() -> List[Job]:
    J: List[Job] = []
    # 1a: does a receiver that never adapts, with CRC selection against LMMSE, match Citadel-Rx? Re-baselines
    # Citadel-Rx, online DeepSIC and CRC-Rollback on the new seeds and this machine.
    for r in ("citadel", "online_deepsic", "frozen_deepsic", "frozen_select", "crc_rollback"):
        J.append(Job("1a", f"v3p1a_{r}__wb_sir0", T20, rx(r) + RND + a1(0), priority=0))
    # 1b: cold start. The gates accept their first three blocks and seed their reference statistics from
    # them, and the slow levels are still the pre-trained weights. Control: the same attack on blocks 40-80.
    fixed = lambda s, e: ["attack.start_mode=fixed", f"attack.start_block={s}", f"attack.end_block={e}"]
    soft = ["attack.soft_gate=true", "attack.unroll_steps=10"]
    J.append(Job("1b", "v3p1b_citadel_cold__a1_sir0", T20, rx("citadel") + a1(0) + fixed(0, 40), priority=1))
    J.append(Job("1b", "v3p1b_citadel_warm__a1_sir0", T20, rx("citadel") + a1(0) + fixed(40, 80), priority=1))
    J.append(Job("1b", "v3p1b_citadel_cold__soft_sir0", T20, rx("citadel") + a1(0) + soft + fixed(0, 40), priority=2))
    # 1c: ratchet. Blocks 10-50: soft-gate perturbations, each scaled by the largest factor an exact copy
    # of the receiver accepts (exact-gate attacker, accepted mode), so the gates' running statistics move;
    # blocks 50-90: plain A1 at SIR 0 dB. Control: the burst alone.
    ratchet = ('attack.schedule=[{start: 10, end: 50, sir_db: 10, soft_gate: true, unroll_steps: 10, '
               'oracle_scales: [1.0, 0.5, 0.25, 0.12, 0.06], oracle_mode: accepted}, {start: 50, end: 90, sir_db: 0}]')
    J.append(Job("1c", "v3p1c_citadel_ratchet__sir0", T20, rx("citadel") + a1(0) + [ratchet], priority=3))
    J.append(Job("1c", "v3p1c_citadel_burst__sir0", T20, rx("citadel") + a1(0) + fixed(50, 90), priority=3))
    # 1d: model-based defenses (pilot-domain guard with fallback) and 1e: model-based detectors, LS CSI,
    # under A1 (crafted on the online DeepSIC surrogate, as for every receiver without an adaptation map)
    for det in ("lmmse", "ml", "kbest", "mmse"):
        for g in ("", "_guard"):
            J.append(Job("1d" if g else "1e", f"v3p1_model_{det}{g}__wb_sir0", T20, rx(f"model_{det}{g}") + RND + a1(0), priority=1))
    # a channel-estimate spoof S_p Z^T (lies in the pilots' column space, so only the innovation test sees it)
    spoof = ["attack.type=deny", "attack.sir_db=0"]
    for r in ("citadel", "model_lmmse", "model_lmmse_guard", "model_ml_guard", "online_deepsic"):
        J.append(Job("1d", f"v3p1d_{r}__spoof_sir0", T20, rx(r) + RND + spoof, priority=2))
    # perfect-CSI genie references (a pilot attack cannot reach them; clean runs only)
    for det in ("lmmse", "ml", "kbest", "mmse"):
        J.append(Job("1e", f"v3p1e_model_{det}_perfect__clean", T20, rx(f"model_{det}_perfect") + ["attack.type=none"],
                     twin=False, priority=2))
    # 1f: 16-QAM at the reference width (hidden = 64 x order = 1024); the second campaign used 256
    q16 = ["frame.modulation=QAM16", "receiver.hidden_base=64", "channel.snr_db=20", "frame.data_bits=100000",
           "frame.pilot_bits=400"]
    for r in ("citadel", "online_deepsic", "model_lmmse", "model_kbest"):
        J.append(Job("1f", f"v3p1f_{r}_qam16w__sir0", T20[:5], rx(r) + q16 + RND + a1(0), priority=4))
    # 1R: regime scan for Phase 2, CALIBRATION seeds 0-2, clean runs only. Where do adapting deep receivers
    # beat ML detection with the LS estimate? The main regime of the paper is chosen from these runs by the
    # rule in docs/v3/PHASE1.md (fixed before the runs). Every R1-R5 regime uses the seed-varying complex
    # Rician Gauss-Markov channel and ensemble pre-training on 32 draws that exclude every test channel.
    for reg, rov in REGIMES.items():
        for r in ("online_deepsic", "citadel", "frozen_deepsic", "model_lmmse", "model_ml", "model_kbest"):
            J.append(Job("1R", f"v3p1R_{reg}_{r}__clean", CAL, rx(r) + rov + ["attack.type=none"], twin=False, priority=-1))
    return J


CGM = ["channel.fading=complex_gm", "channel.jakes_fd_tb=0.01", "channel.rician_k=1.0",
       "receiver.pretrain_draws=32", "receiver.pretrain_draw_bits=2000"]
REGIMES = {
    "R0sed": [],                                                         # the benchmark of the paper (reference)
    "R1cgm": CGM,                                                        # complex, seed-varying, linear front-end
    "R2adc3": CGM + ["channel.adc_bits=3"],                              # 3-bit ADCs
    "R3sat": CGM + ["channel.pa_sat=0.7"],                               # LNA saturation at 0.7 x rms
    "R4iq": CGM + ["channel.iq_eps=0.15", "channel.iq_phi_deg=15"],      # IQ imbalance
    "R5np32": CGM + ["frame.pilot_bits=64"],                             # 32 pilot symbols per block
}


REGIMES2 = {**{k: v for k, v in REGIMES.items() if k != "R0sed"},
            "R6adc2": CGM + ["channel.adc_bits=2"],                                  # 2-bit ADCs
            "R7sat": CGM + ["channel.pa_sat=0.4"],                                    # hard saturation
            "R8hw": CGM + ["channel.adc_bits=3", "channel.pa_sat=0.7", "channel.iq_eps=0.15",
                           "channel.iq_phi_deg=15"]}                                  # combined hardware
FIXES = {"base": [], "F1": ["citadel.consol_mean=vote"], "F2": ["citadel.gate_warmup=prior"],
         "F1F2": ["citadel.consol_mean=vote", "citadel.gate_warmup=prior"]}
T30 = [30, 31, 32, 33, 34]


def phase2() -> List[Job]:
    J: List[Job] = []
    fixed = lambda s, e: ["attack.start_mode=fixed", f"attack.start_block={s}", f"attack.end_block={e}"]
    # ---- cal stage (seeds 0-2) ----------------------------------------------------------------
    # 2R: regime scan with the channel-conditioned backbone (rule in docs/v3/PHASE2.md)
    for reg, rov in REGIMES2.items():
        for r in ("online_cc", "citadel_cc", "frozen_cc", "model_lmmse", "model_ml", "model_kbest"):
            J.append(Job("2R", f"v3p2R_{reg}_{r}__clean", CAL, rx(r) + rov + ["attack.type=none"], twin=False,
                         priority=0, stage="cal"))
    # 2F: the cold-start fixes on SED; cells: warm A1 (random window), cold A1 (blocks 0-39), with clean twins
    for tag, fov in FIXES.items():
        J.append(Job("2F", f"v3p2F_{tag}_warm__a1_sir0", CAL, rx("citadel") + fov + RND + a1(0), priority=0, stage="cal"))
        J.append(Job("2F", f"v3p2F_{tag}_cold__a1_sir0", CAL, rx("citadel") + fov + a1(0) + fixed(0, 40), priority=0,
                     stage="cal"))
    # ---- test stage ---------------------------------------------------------------------------
    # 2F test: the fix frozen by scripts/v3/freeze.py against the frozen first-version settings, fresh seeds 30-34
    for tag, fov in (("base", []), ("fix", ["@FIX"])):
        J.append(Job("2Ft", f"v3p2Ft_{tag}_warm__a1_sir0", T30, rx("citadel") + fov + RND + a1(0), priority=1, stage="test"))
        J.append(Job("2Ft", f"v3p2Ft_{tag}_cold__a1_sir0", T30, rx("citadel") + fov + a1(0) + fixed(0, 40), priority=1,
                     stage="test"))
    # 2G: stronger model-based guards on SED, test seeds 20-29 (Citadel-Rx's runs are in Phase 1, 1a and 1d)
    spoof = ["attack.type=deny", "attack.sir_db=0"]
    for det in ("ml", "lmmse"):
        for mode in ("never", "crc"):
            g = rx(f"model_{det}_guard") + [f"receiver.guard_rebase={mode}"]
            J.append(Job("2G", f"v3p2G_{det}_{mode}__wb_sir0", T20, g + RND + a1(0), priority=2, stage="test"))
            J.append(Job("2G", f"v3p2G_{det}_{mode}__spoof_sir0", T20, g + RND + spoof, priority=2, stage="test"))
    # legitimate redraw at block 50, no attack: what each guard costs when the channel really changes
    red = ["channel.abrupt_block=50", "channel.abrupt_type=redraw", "attack.type=none"]
    for name, ov in (("citadel", rx("citadel")), ("online_deepsic", rx("online_deepsic")), ("ml", rx("model_ml")),
                     ("ml_count", rx("model_ml_guard")),
                     ("ml_never", rx("model_ml_guard") + ["receiver.guard_rebase=never"]),
                     ("ml_crc", rx("model_ml_guard") + ["receiver.guard_rebase=crc"])):
        J.append(Job("2G", f"v3p2G_redraw_{name}__clean", T20, ov + red, twin=False, priority=2, stage="test"))
    return J


LS = ["attack.type=ls", "attack.sir_db=0"]
LS_SG = LS + ["attack.soft_gate=true"]
SPOOF = ["attack.type=deny", "attack.sir_db=0"]
SPOOF_REDRAW = ["channel.abrupt_block=50", "channel.abrupt_type=redraw", "attack.type=deny", "attack.sir_db=10",
                "attack.start_mode=fixed", "attack.start_block=40", "attack.end_block=90"]
GUARDED = ("cls_ml", "ml_never", "ml_crc", "ml_count")


def phase3() -> List[Job]:
    """Capture-lock grid (test seeds 20-29) in the main regime R7 and on SED, and the large-scale scan
    (calibration seeds 0-2). Rules: docs/v3/PHASE3.md."""
    J: List[Job] = []
    # 3D: the dichotomy grid. R7: the main regime by the rule of Phase 2 (largest r); R4: the largest r among the
    # regimes where CRC verification has resolution for every user (docs/v3/PHASE3.md, verifiability condition).
    for reg in ("R4iq", "R7sat"):
        for r in ("citadel_cc", "online_cc", "cls_ml", "ml", "ml_never", "ml_crc", "ml_count"):
            deep = r.endswith("_cc")
            cells = {"ls": RND + LS, "spoof": RND + SPOOF, "spoofredraw": SPOOF_REDRAW}
            if deep:
                cells["a1"] = RND + a1(0)
            if r in GUARDED:
                cells["lssg"] = RND + LS_SG
            for c, cov in cells.items():
                J.append(Job("3D", f"v3p3D_{reg[:2]}_{r}__{c}", T20, rx(r) + REGIMES2[reg] + cov,
                             priority=(0 if reg == "R4iq" else 1) + (2 if deep else 0)))
    # 3S: the same dichotomy on the SED benchmark (Phase 1/2 hold A1, spoof and redraw for the guards)
    for r in ("cls_ml", "ml_never", "ml_crc", "citadel"):
        cells = {"ls": RND + LS, "spoofredraw": SPOOF_REDRAW}
        if r in GUARDED:
            cells["lssg"] = RND + LS_SG
        if r == "cls_ml":
            cells.update(a1=RND + a1(0), spoof=RND + SPOOF)
        for c, cov in cells.items():
            J.append(Job("3S", f"v3p3S_{r}__{c}", T20, rx(r) + cov, priority=2))
    # 3L: large-scale scan, 8 x 32, calibration seeds 0-2, clean, 60 blocks; ML is infeasible, K-best (K = 32)
    big = ["channel.n_user=8", "channel.n_ant=32", "channel.sed_stretch=true", "frame.n_blocks=60",
           "receiver.pretrain_draws=16", "receiver.pretrain_epochs=100"]   # pre-training capped for cost (8 x 32)
    mods = {"qpsk": [], "qam16": ["frame.modulation=QAM16", "receiver.hidden_base=64", "channel.snr_db=20",
                                  "frame.data_bits=40000", "frame.pilot_bits=400", "receiver.pretrain_draw_bits=4000"]}
    for mod, mov in mods.items():
        for reg in ("R1cgm", "R7sat", "R8hw"):
            for r in ("online_cc", "citadel_cc", "frozen_cc", "model_kbest", "model_mmse", "model_lmmse"):
                extra = ["receiver.kbest_k=32"] if r == "model_kbest" else []
                J.append(Job("3L", f"v3p3L_{reg}{mod}_{r}__clean", CAL, rx(r) + REGIMES2[reg] + big + mov + extra +
                             ["attack.type=none"], twin=False, priority=4, stage="cal"))
    return J


FIX4 = ["citadel.gamma_floor=1e-6", "frame.crc_scramble=true"]   # Phase 4 fixes, in every Phase 4 run
BIG = ["channel.n_user=8", "channel.n_ant=32", "channel.sed_stretch=true", "receiver.pretrain_draws=16",
       "receiver.pretrain_epochs=100", "receiver.kbest_k=32"]
UMI = ["channel.model=umi", "frame.coding=ldpc", "frame.ldpc_scramble=true", "attack.type=a1", "attack.attacker_antennas=1",
       "attack.sir_from_geometry=true", "attack.budget_ref=signal"]
T10_14 = [10, 11, 12, 13, 14]     # the UMi drops in resources/umi (seeds 10-14)


def phase4() -> List[Job]:
    """Rules: docs/v3/PHASE4.md."""
    J: List[Job] = []
    # 4X: the 47 Phase 3 runs hit by the two bugs, re-run with the fixes (new clean twins: the framing changed)
    for reg in ("R4iq", "R7sat"):
        for c, cov in (("a1", RND + a1(0)), ("ls", RND + LS)):
            J.append(Job("4X", f"v3p4X_{reg[:2]}_citadel_cc__{c}", T20, rx("citadel_cc") + REGIMES2[reg] + cov + FIX4, priority=1))
    J.append(Job("4X", "v3p4X_SED_citadel__ls", T20, rx("citadel") + RND + LS + FIX4, priority=1))
    # 4U: the coded 5G scene of the second campaign (UMi drops, NR LDPC with scrambling, rank-1 attacker at 35/75/150 m):
    # Citadel-Rx with the fix (its records were all hit by bug 1), and the verified-conditioned receiver (tests the
    # paper's phase-rotation explanation: the conditioning gives the network the block's channel)
    for d in (35, 75, 150):
        for r in ("citadel", "citadel_ccv", "online_cc"):
            J.append(Job("4U", f"v3p4U_{r}_d{d}__phys", T10_14, rx(r) + UMI + [f"attack.att_dist={d}", "citadel.gamma_floor=1e-6"],
                         priority=0))
    # 4V: the capture-lock grid in the main large-scale setting (R8 combined hardware, QPSK, 8 x 32), test seeds 20-29
    R8 = REGIMES2["R8hw"]
    for r in ("citadel_ccv", "citadel_cc", "online_cc", "cls_kbest", "kbest", "kbest_crc", "kbest_never"):
        deep = r.endswith("_cc") or r.endswith("_ccv")
        cells = {"ls": RND + LS, "spoof": RND + SPOOF, "spoofredraw": SPOOF_REDRAW}
        if deep:
            cells["a1"] = RND + a1(0)
        if r in ("cls_kbest", "kbest_crc", "kbest_never"):
            cells["lssg"] = RND + LS_SG
        for c, cov in cells.items():
            J.append(Job("4V", f"v3p4V_{r}__{c}", T20, rx(r) + R8 + BIG + cov + FIX4, priority=2 if deep else 0))
    # 4T: two-sided noise test in R4 against the gate-aware LS attack (Phase 3 observation 4)
    for r in ("cls_ml", "ml_crc"):
        for tag, tov in (("one", []), ("two", ["receiver.guard_two_sided=true"])):
            J.append(Job("4T", f"v3p4T_{r}_{tag}__lssg", T20, rx(r) + REGIMES2["R4iq"] + RND + LS_SG + tov + FIX4, priority=0))
    return J


PHASES = {1: phase1, 2: phase2, 3: phase3, 4: phase4}
