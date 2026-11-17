"""Channel conditioning of the DeepSIC input (v3, roadmap section 0b, pillar P2).

receiver.cond = "lmmse": every symbol's input to the DeepSIC modules is the received vector y followed by
the LMMSE estimate of the users' symbols computed with the block's own LS channel estimate,

    H_b = [(S^H S + sigma0^2 I)^{-1} S^H Y_p]^T,  sigma_b^2 = ||Y_p - S H_b^T||_F^2 / (N_p N),
    x_hat = (H_b^H H_b + sigma_b^2 I)^{-1} H_b^H y,

stacked as real and imaginary parts (2N + 2U features instead of 2N). The network then sees the channel
of the block it detects, so one pre-training over many channel draws gives a usable start on a channel
it has never seen (a plain DeepSIC pre-trained that way is at SER 0.999; Phase 1 report, 1R), and test-
time adaptation is left with what the linear model misses (impairments, interference structure).

Security consequence: the pilots now reach the receiver twice, as training labels' inputs and through
the conditioning of every data symbol. The white-box attacker differentiates through both
(`cond_features_torch`, `ls_torch`, used by attacks/pilot_poisoning.py).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import torch


def ls_np(y_p: np.ndarray, s_p: np.ndarray, reg: float) -> Tuple[np.ndarray, float]:
    S = s_p.astype(complex)
    G = S.conj().T @ S + reg * np.eye(S.shape[1])
    H = np.linalg.solve(G, S.conj().T @ y_p).T                              # (N, U)
    nv = float(np.mean(np.abs(y_p - S @ H.T) ** 2))
    return H, nv


def lmmse_np(y: np.ndarray, H: np.ndarray, nv: float) -> np.ndarray:
    U = H.shape[1]
    W = np.linalg.solve(H.conj().T @ H + max(nv, 1e-9) * np.eye(U), H.conj().T)   # (U, N)
    return y @ W.T                                                          # (n, U)


def cond_features_np(y: np.ndarray, H: np.ndarray, nv: float) -> np.ndarray:
    x = lmmse_np(y.astype(complex), H, nv)
    return np.concatenate([y.real, y.imag, x.real, x.imag], axis=1).astype(np.float32)


# ---- torch (differentiable, for the attacker) -------------------------------------------------
def to_complex(yf: torch.Tensor) -> torch.Tensor:
    n = yf.shape[1] // 2
    return torch.complex(yf[:, :n], yf[:, n:])


def ls_torch(yf_p: torch.Tensor, s_p: np.ndarray, reg: float) -> Tuple[torch.Tensor, torch.Tensor]:
    """yf_p (n, 2N) real features of the (possibly perturbed) pilots -> H (N, U) complex, noise power."""
    Y = to_complex(yf_p).to(torch.complex128)
    S = torch.as_tensor(np.asarray(s_p, dtype=complex), dtype=torch.complex128, device=yf_p.device)
    G = S.conj().T @ S + reg * torch.eye(S.shape[1], dtype=torch.complex128, device=yf_p.device)
    H = torch.linalg.solve(G, S.conj().T @ Y).T
    nv = torch.mean(torch.abs(Y - S @ H.T) ** 2)
    return H, nv


def cond_features_torch(yf: torch.Tensor, H: torch.Tensor, nv: torch.Tensor) -> torch.Tensor:
    """yf (n, 2N) real features -> (n, 2N + 2U) conditioned features, differentiable in yf, H and nv."""
    Y = to_complex(yf).to(torch.complex128)
    U = H.shape[1]
    eye = torch.eye(U, dtype=torch.complex128, device=yf.device)
    W = torch.linalg.solve(H.conj().T @ H + torch.clamp(nv, min=1e-9) * eye, H.conj().T)
    x = Y @ W.T
    return torch.cat([yf, x.real.to(yf.dtype), x.imag.to(yf.dtype)], dim=1)
