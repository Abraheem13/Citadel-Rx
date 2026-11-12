"""Receiver interface used by the sequential block runner."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from ..config import Config
from ..modulation import Modulation


@dataclass
class BlockOutput:
    probs_data: torch.Tensor                 # (n_d, n_user, order) posteriors on the data part
    idx_hat: np.ndarray                      # (n_d, n_user) hard decisions
    stats: Dict[str, Any] = field(default_factory=dict)


class Receiver:
    """A receiver sees, per block b: the (possibly poisoned) pilot observations
    ``y_p`` with known pilot symbols, then the data observations ``y_d``.

    ``process_block`` must return posteriors and hard decisions for the data
    part. Receivers that gate on data-side statistics (Citadel-Rx) do their
    consolidation inside ``process_block`` after detection.
    """

    def __init__(self, cfg: Config, device: torch.device):
        self.cfg = cfg
        self.device = device
        self.mod = Modulation(cfg.frame.modulation)
        self.n_user = cfg.channel.n_user
        self.n_ant = cfg.channel.n_ant

    # ---- numpy <-> torch ---------------------------------------------
    def to_feat(self, y: np.ndarray) -> torch.Tensor:
        """Received (n, n_ant) complex/real -> (n, F) float32 features."""
        if np.iscomplexobj(y):
            f = np.concatenate([y.real, y.imag], axis=1)
        else:
            f = y
        return torch.as_tensor(np.ascontiguousarray(f), dtype=torch.float32, device=self.device)

    def to_idx(self, idx: np.ndarray) -> torch.Tensor:
        return torch.as_tensor(idx, dtype=torch.long, device=self.device)

    # ---- lifecycle -----------------------------------------------------
    def pretrain(self, blocks: List[Tuple[np.ndarray, np.ndarray]]) -> None:
        """Joint pre-training on a list of (y_pilot, idx_pilot) from many channel realisations."""

    def process_block(self, b: int, y_p: np.ndarray, idx_p: np.ndarray, y_d: np.ndarray,
                      aux: Optional[Dict[str, Any]] = None) -> BlockOutput:
        raise NotImplementedError

    def hard(self, probs: torch.Tensor) -> np.ndarray:
        return probs.argmax(dim=-1).cpu().numpy()

    # ---- hooks used by attacks -----------------------------------------
    def attack_surface(self) -> Dict[str, Any]:
        """What a white-box attacker gets: current adaptable parameters and a
        differentiable one-block adaptation map. Receivers without parametric
        adaptation return an empty dict."""
        return {}
