"""Model-based detectors and a model-based pilot-poisoning defense (v3, roadmap Phase 1d/1e).

receiver.type = "model" selects

  receiver.detector  lmmse     linear MMSE equalisation, nearest point (as receivers/lmmse.py)
                     ml        exhaustive maximum likelihood over all order^U symbol vectors
                     kbest     K-best breadth-first tree search on the QR decomposition (K = kbest_k)
                     mmse_sic  ordered MMSE successive interference cancellation (V-BLAST order:
                               highest post-MMSE SINR first)
  receiver.csi       ls        regularised least squares from the (possibly poisoned) pilots
                     perfect   the true channel and noise power of the block (a genie bound; a pilot
                               attack cannot reach it)
  receiver.guard     True      pilot-domain test with fallback (below)

Guard. The pilots give the LS estimate H_ls and the residual noise power
    s2_b = ||Y_p - S_p H_ls^T||_F^2 / (N (N_p - U)),
an unbiased estimate of the per-entry noise power. Two statistics are tested against references that
change only on accepted blocks:
    noise inflation   s2_b / s2_ref  >  chi2_{q}(d) / d,   d = N (N_p - U) (x2 for complex),
    innovation        ||H_ls - H_acc||_F^2 / max(I_ref, expected) > guard_innov_tau,
with s2_ref initialised from the nominal noise power of the configured SNR (not from the first,
possibly poisoned, block) and I_ref the running innovation level (expected = estimation noise
d_H s2_ref / N_p). A perturbation outside the column space of S_p inflates s2; one inside it (a
channel spoof S_p Delta^T) moves H_ls and shows in the innovation. On rejection the block is detected
with the last accepted estimate H_acc, and per (sub-block, user) the first CRC-passing of the
decisions with H_acc and with H_ls is kept (H_ls first when accepted). After guard_refresh
consecutive rejections the references are re-based on the current block, so a lasting legitimate
change cannot lock the receiver.
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch
from scipy.stats import chi2

from ..config import Config
from .base import BlockOutput, Receiver
from .lmmse import hard_from_probs, lmmse_soft_symbols, ls_channel_estimate


# --------------------------------------------------------------------------------------- detectors
def _nearest(x: np.ndarray, const: np.ndarray) -> np.ndarray:
    return np.argmin(np.abs(x[..., None] - const) ** 2, axis=-1)


def detect_lmmse(y: np.ndarray, H: np.ndarray, nv: float, mod) -> np.ndarray:
    return hard_from_probs(lmmse_soft_symbols(y, H, nv, mod))


def detect_ml(y: np.ndarray, H: np.ndarray, mod, chunk: int = 1024) -> np.ndarray:
    U, order = H.shape[1], mod.order
    hyp = np.array(list(itertools.product(range(order), repeat=U)))           # (order^U, U)
    Y0 = mod.modulate_indices(hyp) @ H.T                                       # (order^U, N)
    out = np.empty((y.shape[0], U), dtype=np.int64)
    step = max(1, int(chunk * 256 / len(hyp)))
    for a in range(0, y.shape[0], step):
        d = (np.abs(y[a:a + step, None, :] - Y0[None]) ** 2).sum(axis=2)
        out[a:a + step] = hyp[np.argmin(d, axis=1)]
    return out


def detect_kbest(y: np.ndarray, H: np.ndarray, mod, K: int = 16) -> np.ndarray:
    """K-best on y = H s + w: H = QR (N >= U), z = Q^H y, layers searched from the last user to the first;
    at every layer each survivor is extended by every constellation point and the K smallest partial
    metrics ||z_i - sum_{j>=i} R_ij s_j||^2 are kept."""
    N, U = H.shape
    if N < U:
        raise ValueError("K-best needs at least as many antennas as users")
    Q, R = np.linalg.qr(H.astype(complex))                                     # Q (N, U), R (U, U)
    z = y.astype(complex) @ Q.conj()                                           # (n, U) = (Q^H y)^T
    const = mod.constellation().astype(complex)
    M, n = const.size, y.shape[0]
    surv = np.zeros((n, 1, U), dtype=np.int64)                                 # symbol indices, layers > i filled
    metric = np.zeros((n, 1))
    for i in range(U - 1, -1, -1):
        s_sel = const[surv[:, :, i + 1:]] if i + 1 < U else np.zeros((n, surv.shape[1], 0))
        interf = (s_sel * R[i, i + 1:][None, None, :]).sum(axis=2)            # (n, k)
        cand = np.abs(z[:, i, None, None] - interf[:, :, None] - R[i, i] * const[None, None, :]) ** 2  # (n, k, M)
        tot = (metric[:, :, None] + cand).reshape(n, -1)                       # (n, k*M)
        k = surv.shape[1]
        keep = min(K, k * M)
        sel = np.argpartition(tot, keep - 1, axis=1)[:, :keep] if keep < k * M else np.tile(np.arange(k * M), (n, 1))
        parent, sym = sel // M, sel % M
        surv = np.take_along_axis(surv, parent[:, :, None], axis=1).copy()
        surv[:, :, i] = sym
        metric = np.take_along_axis(tot, sel, axis=1)
    best = np.argmin(metric, axis=1)
    return surv[np.arange(n), best]


def detect_mmse_sic(y: np.ndarray, H: np.ndarray, nv: float, mod) -> np.ndarray:
    """Ordered MMSE-SIC: detect the user with the highest post-MMSE SINR, cancel it, repeat."""
    N, U = H.shape
    const = mod.constellation().astype(complex)
    left = list(range(U))
    r = y.astype(complex).copy()
    out = np.empty((y.shape[0], U), dtype=np.int64)
    while left:
        Hl = H[:, left].astype(complex)
        G = Hl.conj().T @ Hl + nv * np.eye(len(left))
        Ginv = np.linalg.inv(G)
        W = Ginv @ Hl.conj().T                                                  # (u, N)
        sinr = 1.0 / np.maximum(np.real(np.diag(Ginv)) * nv, 1e-12) - 1.0
        k = int(np.argmax(sinr))
        u = left[k]
        mu = np.real(W[k] @ Hl[:, k])
        xk = r @ W[k]                                                           # (n,)
        idx = _nearest(xk / max(mu, 1e-9), const)
        out[:, u] = idx
        r = r - np.outer(const[idx], H[:, u])
        left.pop(k)
    return out


def detect(kind: str, y: np.ndarray, H: np.ndarray, nv: float, mod, K: int) -> np.ndarray:
    if kind == "lmmse":
        return detect_lmmse(y, H, nv, mod)
    if kind == "ml":
        return detect_ml(y, H, mod)
    if kind == "kbest":
        return detect_kbest(y, H, mod, K)
    if kind == "mmse_sic":
        return detect_mmse_sic(y, H, nv, mod)
    raise ValueError(f"unknown detector {kind}")


# --------------------------------------------------------------------------------------- receiver
class ModelReceiver(Receiver):
    """Model-based detector with LS or perfect CSI, optionally guarded (see the module docstring)."""

    def __init__(self, cfg: Config, device: torch.device):
        super().__init__(cfg, device)
        rc = cfg.receiver
        self.kind, self.csi, self.K = rc.detector, rc.csi, rc.kbest_k
        self.guard = rc.guard
        self.name = f"model_{rc.detector}_{rc.csi}" + ("_guard" if rc.guard else "")
        self.noise_var = 10 ** (-0.1 * cfg.channel.snr_db)          # regulariser of the LS estimate (as LMMSE)
        cplx = self.mod.is_complex
        self.nv_nominal = self.noise_var / 2 if cplx else self.noise_var   # per-entry noise power (channels/base.py)
        self.s2_ref: Optional[float] = None
        self.I_ref: Optional[float] = None
        self.H_acc: Optional[np.ndarray] = None
        self.n_rej = 0

    def _thresholds(self, n_p: int) -> float:
        d = self.n_ant * max(n_p - self.n_user, 1) * (2 if self.mod.is_complex else 1)
        return float(chi2.ppf(self.cfg.receiver.guard_quantile, d) / d)

    def process_block(self, b, y_p, idx_p, y_d, aux=None) -> BlockOutput:
        aux = aux or {}
        s_p = self.mod.modulate_indices(idx_p)
        stats: Dict[str, Any] = {}
        if self.csi == "perfect":
            st = aux.get("state")
            if st is None:
                raise RuntimeError("perfect CSI needs the channel state (aux['state'])")
            H, nv = st.H, (st.noise_var / 2 if self.mod.is_complex else st.noise_var)
            idx = detect(self.kind, y_d, H, nv, self.mod, self.K)
            return self._out(idx, stats)
        H_ls = ls_channel_estimate(y_p, s_p, self.noise_var)
        n_p = y_p.shape[0]
        s2 = float(np.sum(np.abs(y_p - s_p @ H_ls.T) ** 2) / (self.n_ant * max(n_p - self.n_user, 1)))
        stats["noise_hat"] = s2
        if not self.guard:
            return self._out(detect(self.kind, y_d, H_ls, s2, self.mod, self.K), stats)

        # ---- guard ----
        if self.s2_ref is None:
            self.s2_ref = self.nv_nominal
        tau_s = self._thresholds(n_p)
        g_noise = s2 / max(self.s2_ref, 1e-12)
        expected = self.H_acc.size * self.s2_ref / n_p if self.H_acc is not None else 0.0
        if self.H_acc is None:
            g_innov, innov = 0.0, 0.0
        else:
            innov = float(np.sum(np.abs(H_ls - self.H_acc) ** 2))
            g_innov = innov / max(self.I_ref or 0.0, expected, 1e-12)
        accept = g_noise <= tau_s and g_innov <= self.cfg.receiver.guard_innov_tau
        rebase = False
        if not accept:
            self.n_rej += 1
            if self.n_rej >= self.cfg.receiver.guard_refresh or self.H_acc is None:
                accept, rebase = True, True          # a lasting change, or no accepted estimate yet
        stats.update(guard_noise=g_noise, guard_noise_tau=tau_s, guard_innov=g_innov, gamma=1.0 if accept else 0.0,
                     guard_rebase=rebase)
        idx_ls = detect(self.kind, y_d, H_ls, s2, self.mod, self.K)
        if accept:
            idx = idx_ls
            if self.H_acc is not None and not rebase:
                self.I_ref = innov if self.I_ref is None else 0.9 * self.I_ref + 0.1 * innov
            if rebase:
                self.I_ref = None
            self.s2_ref = s2 if rebase else 0.9 * self.s2_ref + 0.1 * s2
            self.H_acc = H_ls
            self.n_rej = 0
            cands = [idx_ls]
        else:
            idx = detect(self.kind, y_d, self.H_acc, self.s2_ref, self.mod, self.K)
            cands = [idx, idx_ls]
            stats["fallback"] = True
        framer = aux.get("framer")
        if framer is not None and framer.framer.enabled and len(cands) > 1:
            idx = self._crc_select(framer, cands)
        return self._out(idx, stats)

    @staticmethod
    def _crc_select(framer, cands):
        L = framer.framer.L
        out = cands[0].copy()
        done = framer.framer.check(framer.decided_bits_to_subblocks(cands[0]))
        for c in cands[1:]:
            ok = framer.framer.check(framer.decided_bits_to_subblocks(c)) & ~done
            for j, u in zip(*np.nonzero(ok)):
                out[j * L:(j + 1) * L, u] = c[j * L:(j + 1) * L, u]
            done |= ok
        return out

    def _out(self, idx: np.ndarray, stats: Dict[str, Any]) -> BlockOutput:
        probs = torch.nn.functional.one_hot(torch.as_tensor(idx, dtype=torch.long), self.mod.order).float().to(self.device)
        return BlockOutput(probs_data=probs, idx_hat=idx, stats=stats)
