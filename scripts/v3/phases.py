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
    return J


PHASES = {1: phase1}
