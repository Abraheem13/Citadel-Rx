"""Functional DeepSIC backbone.

DeepSIC (Shlezinger, Fu, Eldar, TWC 2021) runs Q soft-interference-cancellation
iterations; in iteration q the detector of user u is a small MLP whose input is
the received vector together with the other users' soft symbols from iteration
q-1. The reference implementation keeps U*Q independent `nn.Module`s and trains
each with its own Adam loop. Here all U modules of one iteration are *stacked*
along a leading user axis so the whole receiver is a flat dict of tensors:

    params["q{q}.fc1.w"] : (U, hidden, F_in)
    params["q{q}.fc1.b"] : (U, hidden)
    params["q{q}.fc2.w"] : (U, order, hidden)
    params["q{q}.fc2.b"] : (U, order)

Per-user gradients never mix (the loss is a sum over users), so this is
numerically the same receiver as the reference, but every operation that the
project needs — level copies, re-anchoring, Delta Gradient Descent, MAML and
unrolled poisoning — becomes a pure function of a parameter dict.

Architecture and hyper-parameters match the reference exactly:
    hidden = 64 * order, F_in = (2 or 1) * N_r + (order - 1) * (U - 1), ReLU.
"""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Tuple

import torch
import torch.nn.functional as F

ParamDict = Dict[str, torch.Tensor]


def clone_params(p: ParamDict, requires_grad: bool = False) -> ParamDict:
    out = {}
    for k, v in p.items():
        t = v.detach().clone()
        if requires_grad:
            t.requires_grad_(True)
        out[k] = t
    return out


def detach_params(p: ParamDict) -> ParamDict:
    return {k: v.detach() for k, v in p.items()}


def param_norm(p: ParamDict, keys: Optional[Iterable[str]] = None) -> float:
    keys = list(keys) if keys is not None else list(p.keys())
    return float(torch.sqrt(sum((p[k].detach() ** 2).sum() for k in keys)).item())


def param_dist(a: ParamDict, b: ParamDict, keys: Optional[Iterable[str]] = None) -> float:
    keys = list(keys) if keys is not None else list(a.keys())
    return float(torch.sqrt(sum(((a[k].detach() - b[k].detach()) ** 2).sum() for k in keys)).item())


class DeepSICCore:
    def __init__(self, n_user: int, n_ant: int, order: int, is_complex: bool, iterations: int,
                 hidden_base: int, device: torch.device):
        self.U = n_user
        self.N = n_ant
        self.order = order
        self.Q = iterations
        self.F_rx = (2 if is_complex else 1) * n_ant
        self.F_in = self.F_rx + (order - 1) * (n_user - 1)
        self.hidden = hidden_base * order
        self.device = device
        # index of "other users" for every user: (U, U-1)
        others = [[v for v in range(n_user) if v != u] for u in range(n_user)]
        self.others = torch.tensor(others, dtype=torch.long, device=device)

    # ---- parameters --------------------------------------------------
    def init_params(self, generator: Optional[torch.Generator] = None) -> ParamDict:
        p: ParamDict = {}
        for q in range(self.Q):
            w1 = torch.empty(self.U, self.hidden, self.F_in, device=self.device)
            w2 = torch.empty(self.U, self.order, self.hidden, device=self.device)
            for u in range(self.U):  # same init law as nn.Linear (kaiming uniform, a=sqrt(5))
                torch.nn.init.kaiming_uniform_(w1[u], a=5 ** 0.5, generator=generator)
                torch.nn.init.kaiming_uniform_(w2[u], a=5 ** 0.5, generator=generator)
            b1 = (torch.rand(self.U, self.hidden, device=self.device, generator=generator) * 2 - 1) / self.F_in ** 0.5
            b2 = (torch.rand(self.U, self.order, device=self.device, generator=generator) * 2 - 1) / self.hidden ** 0.5
            p[f"q{q}.fc1.w"], p[f"q{q}.fc1.b"] = w1, b1
            p[f"q{q}.fc2.w"], p[f"q{q}.fc2.b"] = w2, b2
        return p

    def keys_for(self, q: int) -> List[str]:
        return [f"q{q}.fc1.w", f"q{q}.fc1.b", f"q{q}.fc2.w", f"q{q}.fc2.b"]

    def adaptable_keys(self, mode: str) -> List[str]:
        if mode == "all":
            return [k for q in range(self.Q) for k in self.keys_for(q)]
        if mode == "last":
            return [k for q in range(self.Q) for k in self.keys_for(q) if ".fc2." in k]
        if mode == "first":
            return [k for q in range(self.Q) for k in self.keys_for(q) if ".fc1." in k]
        raise ValueError(mode)

    # ---- forward ---------------------------------------------------------
    def build_input(self, y_feat: torch.Tensor, probs_prev: torch.Tensor) -> torch.Tensor:
        """y_feat (n, F_rx), probs_prev (n, U, order) -> X (U, n, F_in)."""
        n = y_feat.shape[0]
        # other users' posteriors without the first class (reference convention)
        oth = probs_prev[:, self.others, 1:]                     # (n, U, U-1, order-1)
        oth = oth.reshape(n, self.U, -1).transpose(0, 1)          # (U, n, (U-1)(order-1))
        y_rep = y_feat.unsqueeze(0).expand(self.U, n, self.F_rx)
        return torch.cat([y_rep, oth], dim=-1)

    def module_forward(self, p: ParamDict, q: int, X: torch.Tensor,
                       return_hidden: bool = False):
        """X (U, n, F_in) -> logits (U, n, order)."""
        h = torch.relu(torch.einsum("uoi,uni->uno", p[f"q{q}.fc1.w"], X) + p[f"q{q}.fc1.b"][:, None, :])
        logits = torch.einsum("uoh,unh->uno", p[f"q{q}.fc2.w"], h) + p[f"q{q}.fc2.b"][:, None, :]
        if return_hidden:
            return logits, h
        return logits

    def initial_probs(self, n: int) -> torch.Tensor:
        return torch.full((n, self.U, self.order), 1.0 / self.order, device=self.device)

    def detect(self, p: ParamDict, y_feat: torch.Tensor, iterations: Optional[int] = None) -> torch.Tensor:
        """Full SIC inference. Returns posteriors (n, U, order)."""
        Q = self.Q if iterations is None else iterations
        probs = self.initial_probs(y_feat.shape[0])
        for q in range(Q):
            X = self.build_input(y_feat, probs)
            logits = self.module_forward(p, q, X)
            probs = torch.softmax(logits, dim=-1).transpose(0, 1)  # (n, U, order)
        return probs

    # ---- training data per iteration ---------------------------------------
    def one_hot(self, idx: torch.Tensor) -> torch.Tensor:
        return F.one_hot(idx, self.order).float()

    def stage_inputs(self, p: ParamDict, y_feat: torch.Tensor, idx: torch.Tensor,
                     q: int, probs_prev: Optional[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        """Inputs for training stage q. Stage 0 uses the true symbols of the other users
        (reference: ``_initialize_probs``), later stages use the posteriors of the
        previously trained stage. Returns X (U, n, F_in) and probs for the next stage."""
        if q == 0:
            probs_in = self.one_hot(idx)                       # (n, U, order)
        else:
            probs_in = probs_prev
        X = self.build_input(y_feat, probs_in)
        return X, probs_in

    def stage_loss(self, p: ParamDict, q: int, X: torch.Tensor, idx: torch.Tensor,
                   reduction: str = "mean") -> torch.Tensor:
        """Sum over users of per-user mean CE (so each user's module gets its own mean-CE gradient)."""
        logits = self.module_forward(p, q, X)                   # (U, n, order)
        tgt = idx.transpose(0, 1)                               # (U, n)
        ce = F.cross_entropy(logits.reshape(-1, self.order), tgt.reshape(-1), reduction="none")
        ce = ce.reshape(self.U, -1)
        if reduction == "none":
            return ce
        return ce.mean(dim=1).sum()

    def next_stage_probs(self, p: ParamDict, q: int, y_feat: torch.Tensor,
                         probs_prev: torch.Tensor) -> torch.Tensor:
        """Posteriors produced by stage q given inputs built from probs_prev (reference
        ``calculate_posteriors`` starts from uniform priors at training time)."""
        X = self.build_input(y_feat, probs_prev)
        with torch.no_grad():
            return torch.softmax(self.module_forward(p, q, X), dim=-1).transpose(0, 1)

    def sequential_adapt(self, p: ParamDict, y_feat: torch.Tensor, idx: torch.Tensor,
                         train_stage: Callable[[ParamDict, int, torch.Tensor, torch.Tensor], ParamDict]) -> ParamDict:
        """Reference training flow: stage 0 on true labels, stage q on the posteriors from
        stage q-1 (computed with uniform priors), each stage trained by ``train_stage``."""
        X, _ = self.stage_inputs(p, y_feat, idx, 0, None)
        p = train_stage(p, 0, X, idx)
        probs = self.initial_probs(y_feat.shape[0])
        for q in range(1, self.Q):
            probs = self.next_stage_probs(p, q - 1, y_feat, probs)
            X, _ = self.stage_inputs(p, y_feat, idx, q, probs)
            p = train_stage(p, q, X, idx)
        return p

    # ---- differentiable adaptation (for MAML and for the attacker) ----------
    def functional_adapt(self, p: ParamDict, y_feat: torch.Tensor, idx: torch.Tensor,
                         lr: float, steps: int, keys: Optional[List[str]] = None,
                         create_graph: bool = True) -> ParamDict:
        """Plain gradient-descent adaptation of ``steps`` steps per stage, differentiable
        w.r.t. ``y_feat`` and ``p``. Used as the attacker's model of the victim's
        adaptation map and as the inner loop of MAML."""
        keys = keys or list(p.keys())
        p = dict(p)
        for k in keys:  # leaves must be differentiable even when the caller passes plain tensors
            if not p[k].requires_grad:
                p[k] = p[k].detach().requires_grad_(True)

        def train_stage(pp: ParamDict, q: int, X: torch.Tensor, tgt: torch.Tensor) -> ParamDict:
            stage_keys = [k for k in self.keys_for(q) if k in keys]
            for _ in range(steps):
                loss = self.stage_loss(pp, q, X, tgt)
                grads = torch.autograd.grad(loss, [pp[k] for k in stage_keys], create_graph=create_graph)
                pp = dict(pp)
                for k, g in zip(stage_keys, grads):
                    pp[k] = pp[k] - lr * g
            return pp

        # the sequential flow needs grad-tracked posteriors between stages, so re-implement
        # without the no_grad in next_stage_probs
        X, _ = self.stage_inputs(p, y_feat, idx, 0, None)
        p = train_stage(p, 0, X, idx)
        probs = self.initial_probs(y_feat.shape[0])
        for q in range(1, self.Q):
            Xp = self.build_input(y_feat, probs)
            probs = torch.softmax(self.module_forward(p, q - 1, Xp), dim=-1).transpose(0, 1)
            X = self.build_input(y_feat, probs)
            p = train_stage(p, q, X, idx)
        return p

    def detect_loss(self, p: ParamDict, y_feat: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
        """End-to-end CE of the final SIC posteriors (differentiable)."""
        probs = self.detect(p, y_feat)
        logp = torch.log(probs.clamp_min(1e-12))
        return F.nll_loss(logp.reshape(-1, self.order), idx.reshape(-1))

    def ser(self, probs: torch.Tensor, idx: torch.Tensor) -> float:
        """Reference SER: fraction of symbol *vectors* with at least one user wrong."""
        hard = probs.argmax(-1)
        return float((hard != idx).any(dim=1).float().mean().item())


class JointCore(DeepSICCore):
    """Second backbone (audit D8): a fully connected detector that classifies the joint symbol vector
    of all users from the received vector, with no interference cancellation (the "FullyCon" class of
    data-driven detectors [Samuel et al. 2019; O'Shea and Hoydis 2017]). It has the DeepSICCore
    interface with one stage and one network whose classes are the order^U joint symbols, so every
    receiver, gate, consolidation rule and attack runs on it unchanged; detect() returns the per-user
    marginal posteriors. Joint symbol index: user 0 is the most significant digit."""

    def __init__(self, n_user: int, n_ant: int, order: int, is_complex: bool, hidden: int, device: torch.device):
        super().__init__(1, n_ant, order ** n_user, is_complex, 1, 1, device)
        self.U_real, self.M = n_user, order
        self.hidden = hidden
        self.F_in = self.F_rx                       # no other users' posteriors as inputs
        self.others = torch.zeros((1, 0), dtype=torch.long, device=device)
        w = order ** torch.arange(n_user - 1, -1, -1, device=device)
        self.place = w                               # digit weights
        digits = (torch.arange(self.order, device=device)[:, None] // w[None, :]) % order    # (classes, U)
        self.marg = F.one_hot(digits, order).float()                                           # (classes, U, M)

    def joint(self, idx: torch.Tensor) -> torch.Tensor:
        """per-user indices (n, U) -> joint index (n, 1)"""
        return (idx.long() * self.place[None, :]).sum(dim=1, keepdim=True)

    def build_input(self, y_feat: torch.Tensor, probs_prev: torch.Tensor) -> torch.Tensor:
        return y_feat.unsqueeze(0)                                                             # (1, n, F_rx)

    def detect(self, p: ParamDict, y_feat: torch.Tensor, iterations: Optional[int] = None) -> torch.Tensor:
        logits = self.module_forward(p, 0, self.build_input(y_feat, None))[0]                 # (n, classes)
        return torch.einsum("nc,cum->num", torch.softmax(logits, dim=-1), self.marg)           # (n, U, M)

    def stage_inputs(self, p: ParamDict, y_feat: torch.Tensor, idx: torch.Tensor, q: int,
                     probs_prev: Optional[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.build_input(y_feat, None), None

    def sequential_adapt(self, p, y_feat, idx, train_stage):
        return train_stage(p, 0, self.build_input(y_feat, None), self.joint(idx))

    def functional_adapt(self, p: ParamDict, y_feat: torch.Tensor, idx: torch.Tensor, lr: float, steps: int,
                         keys: Optional[List[str]] = None, create_graph: bool = True) -> ParamDict:
        keys = keys or list(p.keys())
        p = dict(p)
        for k in keys:
            if not p[k].requires_grad:
                p[k] = p[k].detach().requires_grad_(True)
        X, tgt = self.build_input(y_feat, None), self.joint(idx)
        stage_keys = [k for k in self.keys_for(0) if k in keys]
        for _ in range(steps):
            loss = self.stage_loss(p, 0, X, tgt)
            grads = torch.autograd.grad(loss, [p[k] for k in stage_keys], create_graph=create_graph)
            p = dict(p)
            for k, g in zip(stage_keys, grads):
                p[k] = p[k] - lr * g
        return p

    def stage_loss(self, p: ParamDict, q: int, X: torch.Tensor, idx: torch.Tensor, reduction: str = "mean") -> torch.Tensor:
        if idx.shape[-1] != 1:            # per-user labels given: map to the joint symbol
            idx = self.joint(idx)
        return super().stage_loss(p, q, X, idx, reduction)

    def detect_loss(self, p: ParamDict, y_feat: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
        probs = self.detect(p, y_feat)
        logp = torch.log(probs.clamp_min(1e-12))
        return F.nll_loss(logp.reshape(-1, self.M), idx.reshape(-1))
