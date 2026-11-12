"""Meta-DeepSIC (Raviv, Park, Simeone, Eldar, Shlezinger, TWC 2023).

Reference flow (``Trainer.evaluate`` + ``MetaDeepSICTrainer``):
  * a buffer of past pilot blocks is kept;
  * every ``meta_every`` blocks the *saved* (meta) detector is meta-trained with
    MAML on (support, query) = (all but last block, all but first block) pairs
    from the buffer, META_LR = 0.01 inner step, Adam outer step, 300 epochs;
  * after the first ``meta_every`` blocks, each block's online training starts
    from a copy of the saved detector rather than from the previous block.
The buffer is capped to keep the cost bounded; the reference keeps everything.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import torch

from ..config import Config
from .deepsic import ParamDict, clone_params
from .online import DeepSICReceiver, adam_train_stage


class MetaDeepSIC(DeepSICReceiver):
    name = "meta_deepsic"

    def __init__(self, cfg: Config, device: torch.device, buffer_cap: int = 20):
        super().__init__(cfg, device)
        rc = cfg.receiver
        self.meta_lr = rc.meta_lr
        self.meta_every = rc.meta_every
        self.meta_epochs = rc.meta_epochs
        self.buffer_cap = buffer_cap
        self.buf_y: List[torch.Tensor] = []
        self.buf_idx: List[torch.Tensor] = []
        self.saved: ParamDict = clone_params(self.params)

    def pretrain(self, blocks) -> None:
        super().pretrain(blocks)
        self.saved = clone_params(self.params)

    # ---- MAML stage trainer ----------------------------------------------
    def _maml_stage(self, p: ParamDict, q: int, X: torch.Tensor, idx: torch.Tensor,
                    n_support: int) -> ParamDict:
        """X holds the concatenated buffer; support = first n_support samples, query = the rest,
        exactly the reference split (support idx [0, T-P), query idx [P, T))."""
        stage_keys = self.core.keys_for(q)
        leaves = [p[k].detach().clone().requires_grad_(True) for k in stage_keys]
        opt = torch.optim.Adam(leaves, lr=self.lr)
        pp = dict(p)
        T = X.shape[1]
        P = T - n_support  # query offset
        sup = slice(0, n_support)
        qry = slice(P, T)
        for _ in range(self.meta_epochs):
            for k, t in zip(stage_keys, leaves):
                pp[k] = t
            loss_s = self.core.stage_loss(pp, q, X[:, sup], idx[sup])
            grads = torch.autograd.grad(loss_s, leaves, create_graph=True)
            fast = dict(pp)
            for k, t, g in zip(stage_keys, leaves, grads):
                fast[k] = t - self.meta_lr * g
            loss_q = self.core.stage_loss(fast, q, X[:, qry], idx[qry])
            meta_grads = torch.autograd.grad(loss_q, leaves)
            opt.zero_grad(set_to_none=True)
            for t, g in zip(leaves, meta_grads):
                t.grad = g
            opt.step()
        out = dict(p)
        for k, t in zip(stage_keys, leaves):
            out[k] = t.detach()
        return out

    def _meta_train(self) -> None:
        yf = torch.cat(self.buf_y, dim=0)
        idx = torch.cat(self.buf_idx, dim=0)
        n_p = self.buf_y[-1].shape[0]
        n_support = yf.shape[0] - n_p
        self.saved = self.core.sequential_adapt(
            self.saved, yf, idx, lambda p, q, X, t: self._maml_stage(p, q, X, t, n_support))

    # ---- per block ----------------------------------------------------------
    def adapt(self, b: int, yf: torch.Tensor, idx: torch.Tensor) -> Dict[str, Any]:
        self.buf_y.append(yf.detach())
        self.buf_idx.append(idx.detach())
        if len(self.buf_y) > self.buffer_cap:
            self.buf_y.pop(0)
            self.buf_idx.pop(0)
        stats: Dict[str, Any] = {"meta_step": False}
        if b > 0 and b % self.meta_every == 0 and len(self.buf_y) >= 2:
            self._meta_train()
            stats["meta_step"] = True
        if b >= self.meta_every:
            self.params = clone_params(self.saved)
        self.params = self.core.sequential_adapt(
            self.params, yf, idx,
            lambda p, q, X, t: adam_train_stage(self.core, p, q, X, t, self.lr, self.epochs,
                                                weight_decay=self.cfg.receiver.weight_decay))
        return stats
