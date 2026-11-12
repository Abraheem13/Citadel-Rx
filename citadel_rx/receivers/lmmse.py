"""Model-based LMMSE channel estimation and detection.

Used (i) as the "adapt nothing" baseline receiver and (ii) inside the gates:
G1 needs a channel estimate and model-based soft decisions, G3 needs the
innovation of the channel estimate against the Jakes/AR(1) prior.

Channel estimate from known pilots S (n_p, U) and observations Y (n_p, N):
    H_ls   = (S^H S + sigma^2 I)^{-1} S^H Y          (regularised LS, rows = users)
    H_hat  = H_ls^T                                   (N, U)
Prior fusion (one-step Kalman predictor with scalar innovation variance):
    H_pred = rho * H_prev ;  H_fused = H_pred + K (H_hat - H_pred).
Detection: per-symbol linear MMSE equaliser then nearest constellation point.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import torch

from ..config import Config
from ..modulation import Modulation
from .base import BlockOutput, Receiver


def ls_channel_estimate(y_p: np.ndarray, s_p: np.ndarray, noise_var: float) -> np.ndarray:
    """Regularised least squares. y_p (n_p, N), s_p (n_p, U) -> H (N, U)."""
    S = s_p
    G = S.conj().T @ S + noise_var * np.eye(S.shape[1])
    H = np.linalg.solve(G, S.conj().T @ y_p)       # (U, N)
    return H.T


def robust_channel_estimate(y_p: np.ndarray, s_p: np.ndarray, noise_var: float, kind: str,
                            iters: int = 5, trim: float = 0.2) -> np.ndarray:
    """Robust LS (audit C7): Huber IRLS or trimmed LS on the per-pilot-symbol residual norms."""
    H = ls_channel_estimate(y_p, s_p, noise_var)
    for _ in range(iters):
        r = np.linalg.norm(y_p - s_p @ H.T, axis=1)                       # (n_p,)
        scale = 1.4826 * np.median(r) + 1e-12
        if kind == "huber":
            c = 1.345 * scale
            w = np.where(r <= c, 1.0, c / np.maximum(r, 1e-12))
        elif kind == "trim":
            w = (r <= np.quantile(r, 1 - trim)).astype(float)
        else:
            raise ValueError(kind)
        Sw = s_p * w[:, None]
        G = Sw.conj().T @ s_p + noise_var * np.eye(s_p.shape[1])
        H = np.linalg.solve(G, Sw.conj().T @ y_p).T
    return H


def estimate_noise_var(y_p: np.ndarray, s_p: np.ndarray, H: np.ndarray) -> float:
    r = y_p - s_p @ H.T
    return float(np.mean(np.abs(r) ** 2))


def lmmse_soft_symbols(y: np.ndarray, H: np.ndarray, noise_var: float, mod: Modulation) -> np.ndarray:
    """Per-symbol-vector LMMSE equalisation followed by posterior over the constellation.
    Returns probs (n, U, order)."""
    N, U = H.shape
    sigma2 = noise_var
    # symbol energy is 1 for both BPSK and QPSK conventions used here
    W = np.linalg.solve(H.conj().T @ H + sigma2 * np.eye(U), H.conj().T)   # (U, N)
    x_hat = y @ W.T                                                        # (n, U)
    # post-equalisation gain and residual variance per user
    HW = W @ H                                                             # (U, U)
    mu = np.real(np.diag(HW))                                              # (U,)
    nu = np.maximum(mu - mu ** 2, 1e-6)                                    # unbiased residual var approx
    c = mod.constellation()                                                # (order,)
    d2 = np.abs(x_hat[:, :, None] - mu[None, :, None] * c[None, None, :]) ** 2
    logits = -d2 / nu[None, :, None]
    logits -= logits.max(axis=-1, keepdims=True)
    p = np.exp(logits)
    return p / p.sum(axis=-1, keepdims=True)


def hard_from_probs(p: np.ndarray) -> np.ndarray:
    return p.argmax(axis=-1)


@dataclass
class ChannelTracker:
    """Keeps the previous channel estimate and fuses with an AR(1) prior."""
    rho: float
    H_prev: Optional[np.ndarray] = None
    innov_var_ema: Optional[float] = None
    ema: float = 0.9
    warmup: int = 3          # first accepted innovations seed the reference with their maximum
    n_commit: int = 0

    def fuse(self, H_hat: np.ndarray, noise_var: float, n_p: int, accept: bool = True) -> Dict[str, Any]:
        """Returns the fused estimate and the innovation energy normalised by its *running level*
        (floored by the physical expectation: AR(1) process variance + LS estimation noise).
        The running level is only updated on accepted blocks (``accept``), so a poisoned or
        spoofed block cannot inflate the reference it is tested against."""
        est_var = noise_var / max(n_p, 1)            # LS estimation noise per entry (unit-energy pilots)
        if self.H_prev is None:
            self.H_prev = H_hat
            return {"H": H_hat, "innov": 0.0, "innov_norm": 0.0, "pred": H_hat, "expected": 0.0}
        H_pred = self.rho * self.H_prev
        innov = H_hat - H_pred
        innov_energy = float(np.sum(np.abs(innov) ** 2))
        n_entries = innov.size
        proc_var = (1 - self.rho ** 2) * float(np.mean(np.abs(self.H_prev) ** 2)) if self.rho < 1 else 0.0
        expected = n_entries * (proc_var + est_var) + 1e-9
        if self.innov_var_ema is None:
            self.innov_var_ema = max(innov_energy, expected)
        normalised = innov_energy / max(expected, self.innov_var_ema)
        K = (proc_var + 1e-9) / (proc_var + est_var + 1e-9) if self.rho < 1 else 1.0
        H_fused = H_pred + K * innov
        if accept:
            self.commit(innov_energy)
        self.H_prev = H_fused
        return {"H": H_fused, "innov": innov_energy, "innov_norm": normalised, "pred": H_pred,
                "expected": expected}

    def commit(self, innov_energy: float) -> None:
        """Fold an accepted block's innovation energy into the running reference level."""
        self.n_commit += 1
        if self.innov_var_ema is None:
            self.innov_var_ema = innov_energy
        elif self.n_commit <= self.warmup:
            self.innov_var_ema = max(self.innov_var_ema, innov_energy)
        else:
            self.innov_var_ema = self.ema * self.innov_var_ema + (1 - self.ema) * innov_energy


class LMMSEReceiver(Receiver):
    """Adapt-nothing model-based floor."""

    def __init__(self, cfg: Config, device: torch.device):
        super().__init__(cfg, device)
        self.noise_var = 10 ** (-0.1 * cfg.channel.snr_db)
        self.tracker = ChannelTracker(rho=1.0)

    def process_block(self, b, y_p, idx_p, y_d, aux=None) -> BlockOutput:
        s_p = self.mod.modulate_indices(idx_p)
        kind = self.cfg.receiver.robust_ls
        H = ls_channel_estimate(y_p, s_p, self.noise_var) if kind == "none" else \
            robust_channel_estimate(y_p, s_p, self.noise_var, kind)
        nv = estimate_noise_var(y_p, s_p, H)
        probs = lmmse_soft_symbols(y_d, H, nv, self.mod)
        pt = torch.as_tensor(probs, dtype=torch.float32, device=self.device)
        return BlockOutput(probs_data=pt, idx_hat=hard_from_probs(probs), stats={"noise_var_hat": nv})


class MLReceiver(LMMSEReceiver):
    """Exhaustive maximum-likelihood detection with the regularized LS channel estimate of the pilots
    (a model-based reference: no adaptation, no memory). Per-user posteriors are max-log marginals,
    p(s_u = c) proportional to exp(-min over the other users' symbols of ||y - H s||^2 / nv)."""

    def process_block(self, b, y_p, idx_p, y_d, aux=None) -> BlockOutput:
        import itertools
        s_p = self.mod.modulate_indices(idx_p)
        H = ls_channel_estimate(y_p, s_p, self.noise_var)
        nv = max(float(estimate_noise_var(y_p, s_p, H)), 1e-12)
        U, order = H.shape[1], self.mod.order
        hyp = np.array(list(itertools.product(range(order), repeat=U)))      # (order^U, U)
        S = self.mod.modulate_indices(hyp)                                   # (order^U, U)
        Y0 = S @ H.T                                                          # (order^U, N) noiseless outputs
        n = y_d.shape[0]
        logp = np.empty((n, U, order))
        idx = np.empty((n, U), dtype=int)
        for a in range(0, n, 2048):
            yb = y_d[a:a + 2048]
            d = (np.abs(yb[:, None, :] - Y0[None, :, :]) ** 2).sum(axis=2) / nv   # (n_b, order^U)
            idx[a:a + 2048] = hyp[np.argmin(d, axis=1)]
            for u in range(U):
                for c in range(order):
                    logp[a:a + 2048, u, c] = -d[:, hyp[:, u] == c].min(axis=1)
        logp -= logp.max(axis=2, keepdims=True)
        probs = np.exp(logp)
        probs /= probs.sum(axis=2, keepdims=True)
        pt = torch.as_tensor(probs, dtype=torch.float32, device=self.device)
        return BlockOutput(probs_data=pt, idx_hat=idx, stats={"noise_var_hat": nv})
