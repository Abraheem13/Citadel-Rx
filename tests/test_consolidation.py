"""Gated consolidation (Eq. (consol) and Lemma 1): with the normalized rule every consolidation is
a convex combination of the level's old state and the buffered states, also when the period's
verdict mass is below one; the first-version rule pulled the level toward the origin instead."""
import torch

from citadel_rx.config import Config
from citadel_rx.receivers import make_receiver


def _rx(rule, clip=None):
    cfg = Config()
    for o in ("receiver.type=citadel", f"citadel.consol_mean={rule}", "run.device=cpu"):
        cfg.set(o)
    if clip is not None:
        cfg.set(f"citadel.consol_clip={clip}")
    rx = make_receiver(cfg, torch.device("cpu"))
    full = lambda v: {k: torch.full_like(rx.params[k], v) for k in rx.A}
    rx.levels = [full(0.0), full(1.0), full(1.0)]
    rx.buf = [[(0.1, full(3.0)), (0.1, full(3.0))], [], []]   # two buffered fast states, sum gamma = 0.2
    return rx


def _value(rx, level):
    return {float(v.flatten()[0]) for v in rx.levels[level].values()}


def test_normalized_consolidation_is_convex_when_mass_below_one():
    rx = _rx("normalized")
    rx._consolidate(b=rx.C[1] - 1)          # level 2 consolidates at the end of its period
    # s = eta2 * min(1, 0.2) = 0.2 toward the normalized mean 3.0: 1 + 0.2 * (3 - 1) = 1.4
    assert all(abs(v - 1.4) < 1e-5 for v in _value(rx, 1))


def test_legacy_consolidation_leaves_the_convex_hull():
    rx = _rx("legacy")
    rx._consolidate(b=rx.C[1] - 1)
    # first version: mean 0.2 * 3.0 = 0.6, so 1 + 0.2 * (0.6 - 1) = 0.92 < 1 = min of old and buffered states
    assert all(abs(v - 0.92) < 1e-5 for v in _value(rx, 1))


def test_clip_bounds_every_consolidation_increment():
    rx = _rx("normalized", clip="[0.5,0.5]")
    before = {k: v.clone() for k, v in rx.levels[1].items()}
    ev = rx._consolidate(b=rx.C[1] - 1)["consolidations"][0]
    inc = torch.sqrt(sum(((rx.levels[1][k] - before[k]) ** 2).sum() for k in rx.A)).item()
    assert ev["clipped"] and abs(inc - 0.5) < 1e-4
