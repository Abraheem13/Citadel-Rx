"""Experiment configuration.

A single dataclass tree, loadable from YAML, hashable for run records.
Defaults reproduce the reference Meta-DeepSIC setting (TWC 2023 code,
`LINEAR_SYNTH_QPSK.yaml`): 4x4 QPSK, 200 pilot bits, 50 000 data bits per
block, SNR 10 dB, cosine fading on the SED channel.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ChannelConfig:
    model: str = "synthetic"          # synthetic | cost2100 | umi
    n_user: int = 4
    n_ant: int = 4
    linear: bool = True               # False -> tanh(0.5 y) PA nonlinearity
    fading: str = "cosine"            # cosine (reference) | jakes | static
    jakes_fd_tb: float = 0.05         # normalised Doppler f_D * T_b for 'jakes'
    snr_db: float = 10.0
    seed: int = 0
    # abrupt change (audit D6/B3): from `abrupt_block` on, the channel is redrawn or the SNR drops
    abrupt_block: int = -1            # -1 disables
    abrupt_type: str = "redraw"       # redraw | snr_drop
    abrupt_snr_drop_db: float = 6.0
    # SED profile exp(-|i - j|) concentrates user j's energy on the antennas next to index j, so with
    # N > U only about U + 3 antennas carry it (audit D4: an "8 x 32" array is then nearly 8 x 11).
    # True: exp(-|i U / N - j|), the same profile stretched over the whole array
    sed_stretch: bool = False


@dataclass
class FrameConfig:
    modulation: str = "QPSK"          # BPSK | QPSK | QAM16
    pilot_bits: int = 200             # pilot bits per user per block (reference: 200)
    data_bits: int = 50000            # data bits per user per block (reference: 50 000)
    n_blocks: int = 100
    # CRC framing of the data part (used by gate G2 and the BLER metric)
    crc_bits: int = 8                 # 0 disables CRC framing
    crc_subblock_symbols: int = 32    # symbols per CRC-protected sub-block
    # NR channel coding of the data (audit D2): "crc" = CRC-8 sub-blocks; "ldpc" = code blocks with
    # CRC-24A and 5G LDPC (base graph 2), decoded from the symbol decisions
    coding: str = "crc"
    ldpc_k: int = 520                 # information bits per code block, CRC-24A included
    ldpc_n: int = 1000                # coded bits per code block
    # NR data scrambling of the coded bits (TS 38.211 Sec. 6.3.1.1, c_init = n_RNTI 2^15 + n_ID, one
    # RNTI per user). Without it the all-zero codeword, whose CRC-24A is zero, passes the check, so a
    # detector that outputs one constant symbol "decodes"; the first coded-scene runs had this flaw.
    ldpc_scramble: bool = False


@dataclass
class ReceiverConfig:
    type: str = "citadel"             # lmmse | online_deepsic | meta_deepsic | drift_deepsic |
                                      # titans_single | medbn_deepsic | citadel
    iterations: int = 3               # DeepSIC SIC iterations Q
    hidden_base: int = 64
    backbone: str = "deepsic"         # deepsic | joint (fully connected joint-symbol detector, audit D8)
    joint_hidden: int = 512           # hidden width of the joint backbone
    lr: float = 5e-3
    epochs: int = 300                 # online epochs per block (reference: 300)
    optimizer: str = "adam"
    pretrain: bool = True             # joint pre-training on many channel realisations
    pretrain_blocks: int = 1
    pretrain_bits: int = 5000
    pretrain_snrs: List[float] = field(default_factory=lambda: [2, 4, 6, 8, 10, 12, 14, 16])
    pretrain_epochs: int = 300
    # meta
    meta_lr: float = 0.01
    meta_every: int = 5
    meta_epochs: int = 300
    # drift detection
    drift_threshold: float = 2.0
    # median-of-means robust gradient (was labelled "MedBN-style")
    robust_groups: int = 4
    # baselines requested in the audit (C2-C5, C7)
    weight_decay: float = 0.0         # Adam weight decay (C5 tuning)
    reg: str = "none"                 # none | l2sp | ewc : pull toward the pre-trained weights (C2)
    reg_weight: float = 0.0
    ema_beta: float = 0.0             # >0: detect with an EMA (mean-teacher) copy of the weights (C2, CoTTA)
    restore_p: float = 0.0            # CoTTA-style stochastic restore of this fraction of weights per block (C4)
    entropy_filter: float = 0.0       # EATA-style: revert the block's update if mean data entropy > this x ln(order) (C4)
    dd_weight: float = 0.0            # >0: also adapt on CRC-verified data symbols with this loss weight (C3/H2)
    dd_max_symbols: int = 400         # cap on verified data symbols used per block
    robust_ls: str = "none"           # LMMSE channel estimate: none | huber | trim (C7)
    crc_select: bool = False          # per (sub-block, user) CRC selection between this receiver and LMMSE
                                      # (the comparator for Citadel-Rx's H6 selection gain)
    # v3: model-based receivers (receiver.type=model; receivers/modelbased.py)
    detector: str = "lmmse"           # lmmse | ml | kbest | mmse_sic
    csi: str = "ls"                   # ls (regularised LS from the pilots) | perfect (true channel and noise power)
    kbest_k: int = 16                 # survivors per layer of the K-best tree search
    guard: bool = False               # pilot-domain test (noise inflation and channel innovation) with fallback
                                      # to the last accepted channel estimate and CRC selection between the two
    guard_quantile: float = 0.9999    # chi-square quantile of the noise-inflation test
    guard_innov_tau: float = 4.0      # innovation energy relative to its running level on accepted blocks
    guard_refresh: int = 10           # consecutive rejections after which the estimate is re-based (legit change)


@dataclass
class CitadelConfig:
    levels: int = 3
    periods: List[int] = field(default_factory=lambda: [1, 8, 32])
    adaptable: str = "all"            # all | last | mask
    fast_rule: str = "dgd"            # dgd | gd | adam
    fast_steps: int = 300             # fast-level steps per block
    eta_max: float = 5e-3
    surprise_lr: bool = True
    surprise_ema: float = 0.9
    level_lr: List[float] = field(default_factory=lambda: [1.0, 0.5, 0.25])  # eta^(k) for k>=2 (index k-1)
    reanchor_mode: str = "proximal"   # jump (Eq. 72 re-anchor at consolidation) | proximal (per-block pull)
    reanchor_beta: float = 0.25       # jump weight
    prox_lambda: float = 0.5          # proximal pull strength (fraction of eta) toward the slow projection
    level_weights: List[float] = field(default_factory=lambda: [0.5, 0.5])  # Pi weights over slow levels
    gates: List[str] = field(default_factory=lambda: ["g1", "g2", "g3"])
    gate_mode: str = "min"            # min (all gates must pass) | product | max (any) | any_hard
    g1_tau: float = 1.25              # residual ratio threshold (relative to the clean EMA)
    g2_tau: Optional[float] = None    # explicit CRC pass-rate ratio threshold; None -> derived from g2_ser_slack
    g2_ser_slack: float = 0.01        # tolerated SER excess over the reference; tau2 = (1 - slack)^L (Prop. 2.3)
    g2_slack_mode: str = "absolute"   # absolute: slack = g2_ser_slack | relative: slack = max(g2_abs_min_slack,
                                      #   g2_rel_slack * SER_ref) with SER_ref inferred from the reference pass rate
    g2_rel_slack: float = 1.0         # relative mode: tolerate at most (1 + rel) x the reference per-symbol SER (p_ref ~ 0.01 at the
                                      #   linear 10 dB point, ~1e-4 on COST2100; the floor covers the CRC statistical resolution)
    g2_abs_min_slack: float = 0.002   # relative mode: floor on the slack (about 5 sd of the pass fraction at n=781, L=32)
    g3_tau: float = 4.0               # innovation energy relative to its running level
    g3_quantile: float = 0.999        # chi-square floor for the innovation test
    adaptive_thresholds: bool = True
    tighten_floor: float = 0.7        # thresholds shrink at most to this fraction of their slack under surprise
    surprise_clamp: float = 8.0       # surprise ratio clipped to [1/c, c]
    surprise_warmup: int = 5          # blocks used to seed the surprise EMA
    reject_action: str = "revert"     # what happens to the fast level on a rejected block: keep | revert | anchor
    fallback_on_reject: bool = True   # detect the data of a rejected block with the slow projection instead
    dgd_delta: float = 0.1            # scale of the delta-rule decay term
    gate_kappa: float = 0.1           # soft-step width as a fraction of each threshold (E5 sensitivity)
    g2_derived_z: float = 5.0         # g2_slack_mode=derived: delta = max(z * sigma_F(p_ref), rho * p_ref) (A7)
    # method upgrades (audit H1-H7)
    fast_init: str = "carry"          # carry | anchor : start every block's fast level from the anchor (H1)
    fast_radius: float = 0.0          # >0: project the block's total fast update onto a ball of this radius (H1)
    consol_clip: List[float] = field(default_factory=list)  # per slow level: clip each consolidation increment (H1)
    consol_mean: str = "legacy"       # legacy: gated mean divided by max(1, sum gamma), as in the first version, which
    #                                   pulls a level toward the origin when sum gamma < 1 | normalized: divided by
    #                                   sum gamma, so every consolidation is a convex combination (Lemma 1)
    abstain: bool = False             # reference-degradation abstain state (H3)
    abstain_z: float = 4.0
    # "legacy": pass fraction or residual of the reference against statistics of accepted blocks (the
    # first revision; it locks on clean runs). "ratio": log(data residual of the reference / pilot
    # noise estimate) against its level tracked on every non-abstained block, re-based after
    # abstain_refresh consecutive abstentions so that a lasting change cannot lock the receiver.
    # "verified": the same with the residual taken only on CRC-verified symbols (decision errors of a
    # worse-conditioned channel do not move it; the second version abstained after legitimate redraws)
    abstain_mode: str = "legacy"
    abstain_refresh: int = 20
    streak_k: int = 0                 # >0: recovery after this many consecutive rejections (H4)
    drift_guard: float = 0.0          # pull of the slowest level toward the pre-trained weights per consolidation (H5)
    crc_select: bool = False          # per sub-block CRC selection among fast, anchor and LMMSE decisions (H6)
    per_user_gate: bool = False       # gate, revert and fall back per user with per-user CRC statistics (H7)


@dataclass
class AttackConfig:
    type: str = "none"                # none | a1 | a2 | a3 | adaptive
    knowledge: str = "whitebox"       # whitebox | transfer
    sir_db: float = 0.0               # perturbation power relative to signal power
    eps: Optional[float] = None       # explicit l2 budget per block (overrides sir_db)
    where: str = "pilots"             # pilots | pilots_data | all
    rho_blk: float = 1.0              # fraction of attacked blocks
    start_block: int = 20
    end_block: int = 60
    pgd_steps: int = 20
    pgd_alpha: float = 0.25           # step as a fraction of eps
    unroll_steps: int = 1             # adaptation steps unrolled by the attacker
    unroll_lr: float = 5e-3
    target_user: int = 0              # A2
    a2_lambda: float = 1.0
    a3_eps_small: float = 0.05
    surrogate_blocks: int = 10        # transfer: blocks of pilots observed by the attacker
    attacker_channel: str = "direct"  # direct | rank1
    gate_aware_weight: float = 1.0    # adaptive attacker: penalty on gate statistics
    # audit B1/B8: physical attacker and budget reference
    attacker_antennas: int = 0        # >0: E = G X_a with G (N x M) from the channel family (rank-M physical attacker)
    attacker_csi_err: float = 0.0     # variance of the attacker's error on G (imperfect CSI)
    sir_from_geometry: bool = False   # UMi: the budget follows the attacker's position (audit D3), not sir_db
    att_dist: float = 75.0            # UMi: attacker distance from the base station (m), one of the drop's distances
    budget_ref: str = "received"      # received (noise included) | signal (noise-free users' energy)
    # audit B2: reference degradation (joint pilot + data)
    a4_alpha: float = 0.5             # fraction of per-symbol power spent on the pilots
    data_subblocks: int = 64          # data sub-blocks the attacker optimises over (soft CRC objective)
    # audit B4: adaptive strength
    restarts: int = 1                 # random restarts of PGD
    eot: int = 1                      # noise draws averaged in the objective (expectation over transformation)
    soft_gate: bool = False           # BPDA/soft-gate output objective: maximise P(accept) x loss of emitted decisions
    # audit B5: optimised slow drift (a3star) uses a3_eps_small and the soft-gate penalty
    # audit B6: transfer surrogate and query attacker
    surrogate: str = "online_deepsic" # surrogate receiver type for knowledge=transfer (online_deepsic | citadel)
    query_sigma: float = 0.3          # query attacker: exploration noise of the NES search
    query_lr: float = 0.5
    # audit E3: randomised attack window
    start_mode: str = "fixed"         # fixed | random
    random_lo: int = 10
    random_hi: int = 50
    # exact-gate attacker: the optimised perturbation is scaled by each factor, every candidate is run
    # through an exact copy of the victim receiver (its gates, thresholds, references, fallback and CRC
    # selection), and the one whose emitted decisions have the highest SER on the block is sent
    oracle_scales: Optional[List[float]] = None
    oracle_mode: str = "max_ser"      # max_ser: highest SER on the block | accepted: highest SER among the
                                      # candidates the gates accept (poisoning), else highest SER
    # v3: piecewise attack schedule. Each segment {"start": b0, "end": b1, ...} attacks blocks b0 <= b < b1
    # with the attack.* settings it names replaced (e.g. sir_db, soft_gate, oracle_scales); empty = the
    # single window start_block..end_block (or the random window). Used by the ratchet attack (Phase 1c).
    schedule: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RunConfig:
    name: str = "debug"
    out_dir: str = "results"
    device: str = "auto"
    seeds: List[int] = field(default_factory=lambda: [0])
    log_every: int = 10
    save_params: bool = False


@dataclass
class Config:
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    frame: FrameConfig = field(default_factory=FrameConfig)
    receiver: ReceiverConfig = field(default_factory=ReceiverConfig)
    citadel: CitadelConfig = field(default_factory=CitadelConfig)
    attack: AttackConfig = field(default_factory=AttackConfig)
    run: RunConfig = field(default_factory=RunConfig)

    # ---- serialisation -------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()[:12]

    def nondefault(self) -> Dict[str, Any]:
        """Flattened {section.key: value} of every entry that differs from the dataclass default."""
        return _nondefault(self.to_dict(), Config().to_dict())

    def matches_record(self, record_config: Dict[str, Any], ignore=("run.out_dir", "run.device", "run.seeds")) -> bool:
        """True if a saved record's config describes the same experiment: every non-default entry of
        either side agrees, with keys absent from the record (added to the code later) taken at their
        default. This keeps old records valid when new options are added with a default value."""
        a = {k: v for k, v in self.nondefault().items() if k not in ignore}
        b = {k: v for k, v in _nondefault(record_config, Config().to_dict()).items() if k not in ignore}
        return a == b

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Config":
        return _dc_from_dict(cls, d)

    @classmethod
    def from_yaml(cls, path: str, overrides: Optional[List[str]] = None) -> "Config":
        with open(path) as f:
            d = yaml.safe_load(f) or {}
        cfg = cls.from_dict(d)
        for ov in overrides or []:
            cfg.set(ov)
        return cfg

    def set(self, assignment: str) -> None:
        """Apply a dotted override such as ``attack.sir_db=5``."""
        key, _, raw = assignment.partition("=")
        node: Any = self
        parts = key.strip().split(".")
        for p in parts[:-1]:
            node = getattr(node, p)
        current = getattr(node, parts[-1])
        setattr(node, parts[-1], _coerce(raw.strip(), current))

    @property
    def bits_per_symbol(self) -> int:
        return 1 if self.frame.modulation.upper() == "BPSK" else 2

    @property
    def pilot_symbols(self) -> int:
        return self.frame.pilot_bits // self.bits_per_symbol

    @property
    def data_symbols(self) -> int:
        return self.frame.data_bits // self.bits_per_symbol


def _nondefault(d: Dict[str, Any], ref: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (d or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and isinstance(ref.get(k), dict):
            out.update(_nondefault(v, ref[k], key + "."))
        elif k not in ref or v != ref[k]:
            out[key] = v
    return out


def _dc_from_dict(cls, d):
    if not is_dataclass(cls):
        return d
    import typing
    hints = typing.get_type_hints(cls)   # resolves the string annotations of `from __future__ import annotations`
    kwargs = {}
    names = {f.name for f in fields(cls)}
    for k, v in (d or {}).items():
        if k not in names:
            raise KeyError(f"Unknown config key '{k}' for {cls.__name__}")
        t = hints.get(k)
        if isinstance(t, type) and is_dataclass(t):
            kwargs[k] = _dc_from_dict(t, v)
        else:
            kwargs[k] = v
    return cls(**kwargs)


def _coerce(raw: str, current: Any) -> Any:
    if isinstance(current, bool):
        return raw.lower() in ("1", "true", "yes")
    if isinstance(current, int) and not isinstance(current, bool):
        return int(float(raw))
    if isinstance(current, float):
        return float(raw)
    if isinstance(current, list):
        return yaml.safe_load(raw)
    if current is None:
        return yaml.safe_load(raw)
    return raw
