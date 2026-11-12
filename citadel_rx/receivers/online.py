"""Online DeepSIC (reference: `online_deepsic`) and the shared machinery for all
DeepSIC-based receivers: Adam stage training, joint pre-training, detection.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import torch

from ..config import Config
from .base import BlockOutput, Receiver
from .deepsic import DeepSICCore, ParamDict, clone_params


def adam_train_stage(core: DeepSICCore, p: ParamDict, q: int, X: torch.Tensor, idx: torch.Tensor,
                     lr: float, epochs: int, user_mask: Optional[torch.Tensor] = None,
                     grad_transform: Optional[Callable[[List[torch.Tensor]], List[torch.Tensor]]] = None,
                     keys: Optional[List[str]] = None, weight_decay: float = 0.0,
                     sample_w: Optional[torch.Tensor] = None,
                     reg: Optional[Callable[[Dict[str, torch.Tensor]], torch.Tensor]] = None) -> ParamDict:
    """Train the U stacked modules of stage q with a fresh Adam (reference behaviour:
    a new optimiser per module per block). ``user_mask`` (U,) in {0,1} restricts the
    update to drifted users; ``grad_transform`` lets robust variants replace the
    gradient (median-of-means etc.)."""
    stage_keys = [k for k in core.keys_for(q) if (keys is None or k in keys)]
    p = dict(p)
    leaves = [p[k].detach().clone().requires_grad_(True) for k in stage_keys]
    opt = torch.optim.Adam(leaves, lr=lr, weight_decay=weight_decay)
    pp = dict(p)
    for _ in range(epochs):
        for k, t in zip(stage_keys, leaves):
            pp[k] = t
        ce = core.stage_loss(pp, q, X, idx, reduction="none")         # (U, n)
        per_user = ce.mean(dim=1) if sample_w is None else (ce * sample_w[None, :]).sum(dim=1)
        if user_mask is not None:
            per_user = per_user * user_mask
        loss = per_user.sum()
        if reg is not None:
            loss = loss + reg({k: t for k, t in zip(stage_keys, leaves)})
        if grad_transform is None:
            opt.zero_grad(set_to_none=True)
            loss.backward()
        else:
            grads = grad_transform(_per_group_grads(core, pp, q, X, idx, stage_keys, leaves, user_mask))
            opt.zero_grad(set_to_none=True)
            for t, g in zip(leaves, grads):
                t.grad = g
        opt.step()
    for k, t in zip(stage_keys, leaves):
        p[k] = t.detach()
    return p


def _per_group_grads(core, pp, q, X, idx, stage_keys, leaves, user_mask, groups: int = 4):
    """Gradients computed on ``groups`` disjoint pilot sub-batches (for robust aggregation)."""
    n = X.shape[1]
    perm = torch.randperm(n, device=X.device)
    out = []
    for g in range(groups):
        sel = perm[g::groups]
        ce = core.stage_loss(pp, q, X[:, sel], idx[sel], reduction="none").mean(dim=1)
        if user_mask is not None:
            ce = ce * user_mask
        grads = torch.autograd.grad(ce.sum(), leaves, retain_graph=g < groups - 1)
        out.append(grads)
    return out


class DeepSICReceiver(Receiver):
    """Base for every DeepSIC-backed receiver. Subclasses override ``adapt``."""

    name = "deepsic"

    def __init__(self, cfg: Config, device: torch.device):
        super().__init__(cfg, device)
        rc = cfg.receiver
        if rc.backbone == "joint":
            from .deepsic import JointCore
            self.core = JointCore(self.n_user, self.n_ant, self.mod.order, self.mod.is_complex, rc.joint_hidden, device)
        else:
            self.core = DeepSICCore(self.n_user, self.n_ant, self.mod.order, self.mod.is_complex,
                                    rc.iterations, rc.hidden_base, device)
        g = torch.Generator(device="cpu").manual_seed(cfg.channel.seed)
        self.params: ParamDict = self.core.init_params(generator=g if device.type == "cpu" else None)
        self.lr = rc.lr
        self.epochs = rc.epochs
        self.block_count = 0

    # ---- joint pre-training ----------------------------------------------
    def pretrain(self, blocks: List[Tuple[np.ndarray, np.ndarray]]) -> None:
        """Reference `joint_*`: train sequentially on each pre-training block
        (many SNRs / channel realisations), with pretrain_epochs."""
        for y, idx in blocks:
            yf, it = self.to_feat(y), self.to_idx(idx)
            self.params = self.core.sequential_adapt(
                self.params, yf, it,
                lambda p, q, X, t: adam_train_stage(self.core, p, q, X, t, self.lr, self.cfg.receiver.pretrain_epochs))
        self.pretrained_params = clone_params(self.params)
        if self.cfg.receiver.reg == "ewc":
            self._compute_fisher(blocks)

    # ---- regularisers of the audit baselines (C2) -------------------------
    def _reg_fn(self):
        rc = self.cfg.receiver
        if rc.reg == "none" or rc.reg_weight <= 0 or not hasattr(self, "pretrained_params"):
            return None
        lam, p0 = rc.reg_weight, self.pretrained_params
        if rc.reg == "l2sp":       # Li et al., ICML 2018: (lam/2) ||theta - theta_0||^2
            return lambda leaves: 0.5 * lam * sum(((t - p0[k]) ** 2).sum() for k, t in leaves.items())
        if rc.reg == "ewc":        # Kirkpatrick et al., PNAS 2017: (lam/2) sum F (theta - theta_0)^2
            F = self.fisher
            return lambda leaves: 0.5 * lam * sum((F[k] * (t - p0[k]) ** 2).sum() for k, t in leaves.items())
        raise ValueError(rc.reg)

    def _compute_fisher(self, blocks) -> None:
        """Diagonal empirical Fisher of the end-to-end detection loss on the pre-training data."""
        F = {k: torch.zeros_like(v) for k, v in self.params.items()}
        for y, idx in blocks:
            p = {k: v.detach().clone().requires_grad_(True) for k, v in self.params.items()}
            loss = self.core.detect_loss(p, self.to_feat(y), self.to_idx(idx))
            grads = torch.autograd.grad(loss, list(p.values()))
            for k, g in zip(p.keys(), grads):
                F[k] += g.detach() ** 2 / len(blocks)
        mean = torch.mean(torch.cat([f.reshape(-1) for f in F.values()]))
        self.fisher = {k: f / mean.clamp_min(1e-12) for k, f in F.items()}   # unit-mean scaling

    def _train_fn(self, sample_w: Optional[torch.Tensor] = None):
        rc = self.cfg.receiver
        reg = self._reg_fn()
        return lambda p, q, X, t: adam_train_stage(self.core, p, q, X, t, self.lr, self.epochs,
                                                   weight_decay=rc.weight_decay, sample_w=sample_w, reg=reg)

    # ---- per block ------------------------------------------------------
    def adapt(self, b: int, yf: torch.Tensor, idx: torch.Tensor, sample_w: Optional[torch.Tensor] = None) -> Dict[str, Any]:
        self.params = self.core.sequential_adapt(self.params, yf, idx, self._train_fn(sample_w))
        return {}

    def detect(self, yf: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            p = getattr(self, "ema_params", None) if self.cfg.receiver.ema_beta > 0 else None
            return self.core.detect(p if p is not None else self.params, yf)

    def verified_data(self, yf_d: torch.Tensor, framer, candidates: List[np.ndarray], max_symbols: int):
        """CRC-verified data labels (audit C3/H2): the symbols of every (sub-block, user) whose CRC
        passes under at least one candidate decision. A sub-block passes for one user only, so the
        label of the other users at those symbol slots is taken from the same candidate, and a
        symbol slot is kept only if every user's sub-block passed under some candidate."""
        if framer is None or not framer.framer.enabled or max_symbols <= 0:
            return None
        L = framer.framer.L
        n_sub = framer.n_sub
        U = self.n_user
        label = np.full((n_sub, U, L), -1, dtype=np.int64)
        for idx in candidates:
            ok = framer.framer.check(framer.decided_bits_to_subblocks(idx))      # (n_sub, U)
            blk = idx[: n_sub * L].reshape(n_sub, L, U).transpose(0, 2, 1)       # (n_sub, U, L)
            fill = ok[:, :, None] & (label < 0)
            label = np.where(fill, blk, label)
        full = (label >= 0).all(axis=1)                                          # (n_sub, L)
        sub_ok = np.where(full.all(axis=1))[0]
        if sub_ok.size == 0:
            return None
        rng = np.random.default_rng(self.block_count + 17)
        n_take = max(1, min(sub_ok.size, max_symbols // L))
        chosen = np.sort(rng.choice(sub_ok, size=n_take, replace=False))
        rows = (chosen[:, None] * L + np.arange(L)[None, :]).reshape(-1)
        lab = label[chosen].transpose(0, 2, 1).reshape(-1, U)                    # (n_take*L, U)
        return yf_d[torch.as_tensor(rows, device=yf_d.device)], torch.as_tensor(lab, device=yf_d.device)

    def process_block(self, b, y_p, idx_p, y_d, aux=None) -> BlockOutput:
        aux = aux or {}
        rc = self.cfg.receiver
        yf_p, it_p, yf_d = self.to_feat(y_p), self.to_idx(idx_p), self.to_feat(y_d)
        stats: Dict[str, Any] = {}
        yf_train, it_train, sample_w = yf_p, it_p, None
        if rc.dd_weight > 0:   # decision-directed on CRC-verified data, labels from the pre-adaptation decisions
            with torch.no_grad():
                cand = [self.hard(self.detect(yf_d))]
            ver = self.verified_data(yf_d, aux.get("framer"), cand, rc.dd_max_symbols)
            if ver is not None:
                yv, iv = ver
                n_p, n_v = yf_p.shape[0], yv.shape[0]
                yf_train, it_train = torch.cat([yf_p, yv]), torch.cat([it_p, iv])
                sample_w = torch.cat([torch.full((n_p,), 1.0 / n_p), torch.full((n_v,), rc.dd_weight / n_v)]).to(yf_p.device)
                stats["dd_symbols"] = int(n_v)
        before = clone_params(self.params)
        stats.update(self.adapt(b, yf_train, it_train, sample_w) if sample_w is not None else (self.adapt(b, yf_train, it_train) or {}))
        if rc.entropy_filter > 0:   # EATA-style sample (block) filtering on the data predictions
            with torch.no_grad():
                pr = self.core.detect(self.params, yf_d)
                ent = float((-(pr * torch.log(pr.clamp_min(1e-12))).sum(-1)).mean().item())
            stats["data_entropy"] = ent
            if ent > rc.entropy_filter * float(np.log(self.mod.order)):
                self.params = before
                stats["filtered"] = True
        if rc.restore_p > 0 and hasattr(self, "pretrained_params"):   # CoTTA-style stochastic restore
            g = torch.Generator(device="cpu").manual_seed(1000 + self.block_count)
            for k in self.params:
                m = (torch.rand(self.params[k].shape, generator=g) < rc.restore_p).to(self.params[k].device)
                self.params[k] = torch.where(m, self.pretrained_params[k], self.params[k])
        if rc.ema_beta > 0:   # mean teacher used for detection
            if not hasattr(self, "ema_params"):
                self.ema_params = clone_params(self.params)
            else:
                for k in self.params:
                    self.ema_params[k] = rc.ema_beta * self.ema_params[k] + (1 - rc.ema_beta) * self.params[k]
        with torch.no_grad():
            stats["pilot_loss_post"] = float(self.core.detect_loss(self.params, yf_p, it_p).item())
        probs = self.detect(yf_d)
        idx_hat = self.hard(probs)
        framer = aux.get("framer")
        if rc.crc_select and framer is not None and framer.framer.enabled:
            # comparator for Citadel-Rx's H6: per (sub-block, user), keep this receiver's decisions if
            # their CRC passes, otherwise take LMMSE's if those pass
            from .lmmse import estimate_noise_var, hard_from_probs, lmmse_soft_symbols, ls_channel_estimate
            s_p = self.mod.modulate_indices(idx_p)
            nv0 = 10 ** (-0.1 * self.cfg.channel.snr_db)
            H = ls_channel_estimate(y_p, s_p, nv0)
            idx_mm = hard_from_probs(lmmse_soft_symbols(y_d, H, estimate_noise_var(y_p, s_p, H), self.mod))
            L = framer.framer.L
            ok_nn = framer.framer.check(framer.decided_bits_to_subblocks(idx_hat))
            ok_mm = framer.framer.check(framer.decided_bits_to_subblocks(idx_mm))
            take = ok_mm & ~ok_nn
            if take.any():
                idx_hat = idx_hat.copy()
                for j, u in zip(*np.nonzero(take)):
                    idx_hat[j * L:(j + 1) * L, u] = idx_mm[j * L:(j + 1) * L, u]
            stats["crc_select_frac"] = float((ok_nn | ok_mm).mean())
        self.block_count += 1
        return BlockOutput(probs_data=probs, idx_hat=idx_hat, stats=stats)

    # ---- attacker view ---------------------------------------------------
    def attack_surface(self) -> Dict[str, Any]:
        return {"core": self.core, "params": self.params, "keys": list(self.params.keys()),
                "lr": self.lr}


class OnlineDeepSIC(DeepSICReceiver):
    name = "online_deepsic"
