"""Modular drift-detection receiver (after Uzlaner, Raviv, Shlezinger, Todros, TWC 2025).

The receiver adapts a user's modules only when a per-user drift statistic
fires. We use the pilot cross-entropy of the *current* model on the new block,
standardised by a running mean/std of past values (a CUSUM-free, one-sided
z-test); the reference paper's detectors are posterior/statistics-based per
module and this is the simplest faithful stand-in. The first block always
trains. This is the "adapt less" defence in the proposal's baseline table.
"""
from __future__ import annotations

from typing import Any, Dict

import torch

from ..config import Config
from .online import DeepSICReceiver, adam_train_stage


class DriftDeepSIC(DeepSICReceiver):
    name = "drift_deepsic"

    def __init__(self, cfg: Config, device: torch.device):
        super().__init__(cfg, device)
        self.thr = cfg.receiver.drift_threshold
        self.mean = None
        self.var = None
        self.alpha = 0.9

    def _per_user_pilot_loss(self, yf, idx) -> torch.Tensor:
        with torch.no_grad():
            probs = self.core.detect(self.params, yf)
            logp = torch.log(probs.clamp_min(1e-12))
            nll = -logp.gather(-1, idx.unsqueeze(-1)).squeeze(-1)   # (n, U)
            return nll.mean(dim=0)                                    # (U,)

    def adapt(self, b: int, yf: torch.Tensor, idx: torch.Tensor) -> Dict[str, Any]:
        loss_u = self._per_user_pilot_loss(yf, idx)
        if self.mean is None:
            mask = torch.ones_like(loss_u)
            z = torch.zeros_like(loss_u)
        else:
            std = torch.sqrt(self.var.clamp_min(1e-8))
            z = (loss_u - self.mean) / std
            mask = (z > self.thr).float()
        if mask.sum() > 0:
            self.params = self.core.sequential_adapt(
                self.params, yf, idx,
                lambda p, q, X, t: adam_train_stage(self.core, p, q, X, t, self.lr, self.epochs, user_mask=mask))
        # update statistics with the post-adaptation loss so the baseline tracks "healthy" values
        post = self._per_user_pilot_loss(yf, idx)
        if self.mean is None:
            self.mean, self.var = post.clone(), torch.full_like(post, 0.05)
        else:
            self.mean = self.alpha * self.mean + (1 - self.alpha) * post
            self.var = self.alpha * self.var + (1 - self.alpha) * (post - self.mean) ** 2
        return {"drift_mask": mask.cpu().tolist(), "drift_z": z.cpu().tolist(),
                "retrained_users": int(mask.sum().item())}
