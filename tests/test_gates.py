import numpy as np

from citadel_rx.gates import GateController
from citadel_rx.gates.physics import g1_residual
from citadel_rx.modulation import Modulation
from citadel_rx.receivers.lmmse import ChannelTracker


def test_g2_rejects_when_pass_rate_collapses_relative_to_lmmse():
    gc = GateController(["g2"], "min", 1.25, 0.72, 4.0, 0.999, adaptive=False, dof=16)
    for _ in range(5):  # clean history: neural and LMMSE pass rates comparable
        v = gc.evaluate(None, 0.6, 0.55, None)
        gc.update_clean(v, None, 0.6, 0.55)
    assert gc.evaluate(None, 0.6, 0.55, None).gamma > 0.9
    # the channel got worse for both -> still accepted
    assert gc.evaluate(None, 0.2, 0.18, None).gamma > 0.9
    # only the neural receiver collapsed -> rejected
    assert gc.evaluate(None, 0.1, 0.55, None).gamma < 0.1


def test_g1_ratio_is_near_one_for_correct_decisions_and_large_for_wrong():
    rng = np.random.default_rng(0)
    mod = Modulation("QPSK")
    H = np.exp(-np.abs(np.arange(4)[:, None] - np.arange(4)[None, :]))
    idx = rng.integers(0, 4, size=(2000, 4))
    y = mod.modulate_indices(idx) @ H.T + 0.1 * (rng.standard_normal((2000, 4)) + 1j * rng.standard_normal((2000, 4)))
    assert abs(g1_residual(y, idx, idx, H, mod) - 1.0) < 1e-9
    wrong = (idx + rng.integers(1, 4, size=idx.shape)) % 4
    assert g1_residual(y, wrong, idx, H, mod) > 5


def test_g3_innovation_flags_implausible_jump():
    tr = ChannelTracker(rho=0.99)
    H0 = np.exp(-np.abs(np.arange(4)[:, None] - np.arange(4)[None, :]))
    rng = np.random.default_rng(1)
    normals = []
    for _ in range(10):
        out = tr.fuse(H0 + 0.02 * rng.standard_normal(H0.shape), noise_var=0.1, n_p=100)
        normals.append(out["innov_norm"])
    jump = tr.fuse(H0 * 1.8, noise_var=0.1, n_p=100)["innov_norm"]
    assert jump > 5 * max(normals[1:])
