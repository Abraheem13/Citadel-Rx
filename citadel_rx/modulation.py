"""BPSK / QPSK modulation, matching the reference DeepSIC code conventions.

QPSK: bits (b0, b1) -> ((-1)^b0 + j (-1)^b1) / sqrt(2);  symbol index = b0 + 2 b1.
BPSK: bit b -> 1 - 2b;                                     symbol index = b.
"""
from __future__ import annotations

import numpy as np
import torch

_SQRT2 = np.sqrt(2.0)


_GRAY2 = np.array([0, 1, 3, 2])          # 2-bit Gray code: level index -> amplitude index (-3,-1,+1,+3)
_PAM4 = np.array([-3.0, -1.0, 3.0, 1.0]) / np.sqrt(10.0)   # unit-energy 16-QAM per real axis, Gray-mapped


class Modulation:
    def __init__(self, name: str):
        self.name = name.upper()
        if self.name in ("16QAM", "QAM16"):
            self.name = "QAM16"
        if self.name not in ("BPSK", "QPSK", "QAM16"):
            raise ValueError(f"unsupported modulation {name}")
        self.bits_per_symbol = {"BPSK": 1, "QPSK": 2, "QAM16": 4}[self.name]
        self.order = 2 ** self.bits_per_symbol
        self.is_complex = self.name in ("QPSK", "QAM16")

    # ---- bits <-> symbol indices ------------------------------------
    def bits_to_indices(self, bits: np.ndarray) -> np.ndarray:
        """bits: (..., n_bits) -> indices (..., n_bits / bps). Index = sum_k b_k 2^k."""
        if self.name == "BPSK":
            return bits.astype(np.int64)
        bps = self.bits_per_symbol
        b = bits.reshape(*bits.shape[:-1], -1, bps)
        w = (2 ** np.arange(bps)).astype(np.int64)
        return (b * w).sum(-1).astype(np.int64)

    def indices_to_bits(self, idx: np.ndarray) -> np.ndarray:
        if self.name == "BPSK":
            return idx.astype(np.int64)
        bps = self.bits_per_symbol
        bitsel = [(idx // (2 ** k)) % 2 for k in range(bps)]
        return np.stack(bitsel, axis=-1).reshape(*idx.shape[:-1], -1).astype(np.int64)

    # ---- indices -> constellation points -------------------------------
    def constellation(self) -> np.ndarray:
        idx = np.arange(self.order)
        return self.modulate_indices(idx)

    def modulate_indices(self, idx: np.ndarray) -> np.ndarray:
        if self.name == "BPSK":
            return (1 - 2 * idx).astype(np.float64)
        if self.name == "QPSK":
            b0 = idx % 2
            b1 = idx // 2
            return ((-1.0) ** b0 + 1j * (-1.0) ** b1) / _SQRT2
        # 16-QAM: bits (b0,b1) select the I level (Gray), (b2,b3) the Q level
        i_lvl = (idx % 2) + 2 * ((idx // 2) % 2)
        q_lvl = ((idx // 4) % 2) + 2 * ((idx // 8) % 2)
        return _PAM4[_GRAY2[i_lvl]] + 1j * _PAM4[_GRAY2[q_lvl]]

    def modulate_bits(self, bits: np.ndarray) -> np.ndarray:
        return self.modulate_indices(self.bits_to_indices(bits))

    # ---- torch helpers -----------------------------------------------
    def constellation_torch(self, device=None) -> torch.Tensor:
        c = self.constellation()
        if self.is_complex:
            return torch.tensor(np.stack([c.real, c.imag], -1), dtype=torch.float32, device=device)
        return torch.tensor(c, dtype=torch.float32, device=device).unsqueeze(-1)

    def hard_decide(self, probs: torch.Tensor) -> torch.Tensor:
        """probs: (..., order) -> symbol index with the largest posterior."""
        return probs.argmax(dim=-1)

    def soft_symbol(self, probs: torch.Tensor) -> torch.Tensor:
        """Posterior-mean constellation point. probs (..., order) -> (..., 2 or 1)."""
        c = self.constellation_torch(probs.device)
        return probs @ c
