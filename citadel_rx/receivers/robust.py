"""Vision-style robust-statistics TTA defence transplanted to the receiver.

MedBN (Park et al., CVPR 2024) protects test-time adaptation by replacing mean
batch statistics with medians. DeepSIC has no batch-norm; the closest faithful
transplant is a *median-of-means gradient*: the pilot batch is split into G
groups, per-group gradients are computed and aggregated coordinate-wise by the
median before the Adam step. It is the generic "robust aggregation" defence
that does not use channel physics; the paper's claim is that it does not
transfer well, which E3/E7 test.
"""
from __future__ import annotations

from typing import Any, Dict, List

import torch

from ..config import Config
from .online import DeepSICReceiver, adam_train_stage


def median_of_groups(group_grads: List[List[torch.Tensor]]) -> List[torch.Tensor]:
    out = []
    for i in range(len(group_grads[0])):
        stack = torch.stack([g[i] for g in group_grads], dim=0)
        out.append(stack.median(dim=0).values)
    return out


class MedBNDeepSIC(DeepSICReceiver):
    name = "medbn_deepsic"

    def adapt(self, b: int, yf: torch.Tensor, idx: torch.Tensor) -> Dict[str, Any]:
        self.params = self.core.sequential_adapt(
            self.params, yf, idx,
            lambda p, q, X, t: adam_train_stage(self.core, p, q, X, t, self.lr, self.epochs,
                                                grad_transform=median_of_groups))
        return {}
