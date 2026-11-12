from .base import Receiver, BlockOutput  # noqa: F401
from .deepsic import DeepSICCore, ParamDict  # noqa: F401


_BASELINE_DEFAULTS = {
    "l2sp_deepsic": {"reg": "l2sp", "reg_weight": 1e-2},       # weight swept in sweep.py
    "ewc_deepsic": {"reg": "ewc", "reg_weight": 1e-2},
    "ema_deepsic": {"ema_beta": 0.9},
    "dd_deepsic": {"dd_weight": 1.0},                          # CRC-verified decision-directed (C3)
    "cotta_deepsic": {"ema_beta": 0.9, "restore_p": 0.05},     # CoTTA-style teacher + stochastic restore (C4)
    "eata_deepsic": {"entropy_filter": 0.4, "reg": "ewc", "reg_weight": 1e-2},  # EATA-style filter + Fisher anchor (C4)
    "online_select": {"crc_select": True},                     # online DeepSIC + CRC selection with LMMSE (H6 comparator)
}


def make_receiver(cfg, device):
    t = cfg.receiver.type
    if t == "lmmse":
        from .lmmse import LMMSEReceiver
        return LMMSEReceiver(cfg, device)
    if t == "online_deepsic":
        from .online import OnlineDeepSIC
        return OnlineDeepSIC(cfg, device)
    if t in _BASELINE_DEFAULTS:
        # audit baselines built on online DeepSIC with one extra mechanism each; explicit
        # receiver.* overrides win over these defaults
        import copy
        from .online import OnlineDeepSIC
        from ..config import ReceiverConfig
        c = copy.deepcopy(cfg)
        ref = ReceiverConfig()
        for k, v in _BASELINE_DEFAULTS[t].items():
            if getattr(c.receiver, k) == getattr(ref, k):
                setattr(c.receiver, k, v)
        rx = OnlineDeepSIC(c, device)
        rx.name = t
        return rx
    if t == "ml":
        from .lmmse import MLReceiver
        return MLReceiver(cfg, device)
    if t == "lmmse_robust":
        import copy
        from .lmmse import LMMSEReceiver
        c = copy.deepcopy(cfg)
        if c.receiver.robust_ls == "none":
            c.receiver.robust_ls = "huber"
        rx = LMMSEReceiver(c, device)
        rx.name = t
        return rx
    if t == "meta_deepsic":
        from .meta import MetaDeepSIC
        return MetaDeepSIC(cfg, device)
    if t == "drift_deepsic":
        from .drift import DriftDeepSIC
        return DriftDeepSIC(cfg, device)
    if t == "medbn_deepsic":
        from .robust import MedBNDeepSIC
        return MedBNDeepSIC(cfg, device)
    if t == "titans_single":
        from .citadel import CitadelRx
        return CitadelRx(cfg, device, single_memory=True)
    if t == "citadel":
        from .citadel import CitadelRx
        return CitadelRx(cfg, device)
    if t in ("crc_rollback", "rollback_allgates"):
        # simplest receiver that uses the CRC (audit C1): online DeepSIC (plain Adam, fixed step,
        # no delta rule, no slow memory) + gate + rollback to the last accepted weights, which
        # also detect the data of a rejected block. crc_rollback uses G2 only; rollback_allgates
        # uses G1+G2+G3.
        import copy
        from .citadel import CitadelRx
        c = copy.deepcopy(cfg)
        c.citadel.levels, c.citadel.periods = 1, [1]
        c.citadel.fast_rule, c.citadel.surprise_lr, c.citadel.dgd_delta = "adam", False, 0.0
        c.citadel.prox_lambda, c.citadel.reanchor_beta = 0.0, 0.0
        c.citadel.eta_max, c.citadel.fast_steps = cfg.receiver.lr, cfg.receiver.epochs
        if t == "crc_rollback":
            c.citadel.gates = ["g2"]
        rx = CitadelRx(c, device)
        rx.name = t
        return rx
    raise ValueError(f"unknown receiver type {t}")
