"""The soft-gate attacker's G1 residual must be on the receiver's scale (physics.model_residual).

With one-hot soft decisions the posterior-mean symbols equal the hard symbols, so the two residuals
must agree exactly; before the fix the attacker's value was half the receiver's for QPSK."""
import numpy as np
import torch

from citadel_rx.attacks.pilot_poisoning import Attacker, feat
from citadel_rx.config import Config
from citadel_rx.gates.physics import model_residual


class _OneHotCore:
    """Stands in for the DeepSIC core: returns one-hot probabilities of fixed decisions."""

    def __init__(self, idx: np.ndarray, order: int):
        self.p = torch.nn.functional.one_hot(torch.as_tensor(idx, dtype=torch.long), order).float()

    def detect(self, theta, y_feat):
        return self.p


def test_soft_g1_matches_receiver_scale():
    for modulation in ("QPSK", "BPSK"):
        cfg = Config()
        cfg.frame.modulation = modulation
        att = Attacker(cfg, torch.device("cpu"), np.random.default_rng(0))
        rng = np.random.default_rng(1)
        n, N, U = 64, 4, 4
        order = len(att.mod.constellation_torch(torch.device("cpu")))
        H = (rng.standard_normal((N, U)) + 1j * rng.standard_normal((N, U))) / np.sqrt(2 * N)
        idx = rng.integers(0, order, size=(n, U))
        y = att.mod.modulate_indices(idx) @ H.T
        y = y + 0.3 * (rng.standard_normal(y.shape) + 1j * rng.standard_normal(y.shape))
        if not att.mod.is_complex:
            H, y = H.real, y.real
        dec = rng.integers(0, order, size=(n, U))   # decisions that are not all correct
        soft = float(att._g1_soft(_OneHotCore(dec, order), None, feat(y, torch.device("cpu")), H))
        hard = model_residual(y, dec, H, att.mod)
        assert np.isclose(soft, hard, rtol=1e-5), (modulation, soft, hard)
