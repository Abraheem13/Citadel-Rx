"""Numerical evaluation of Theorem 2.1 / Corollary 2.2 (targets).

adversary_term(k)  = rho_blk * eps * G * (1 - p_rej_k) / C_k           (per-block, Eq. 2.7)
certificate(W)     = eta_K * rho_blk * eps * G * (1 - p_rej_K) * W / C_K   (Eq. 2.8)

The Lipschitz constant G of the gradient in the input is *measured* from the
receiver (``estimate_input_lipschitz``) rather than assumed, so that the
certificate plotted against E5 is a number the code can actually produce.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch


def adversary_term(C: np.ndarray, p_rej: float, rho_blk: float = 1.0, eps: float = 1.0, G: float = 1.0) -> np.ndarray:
    return rho_blk * eps * G * (1 - p_rej) / np.asarray(C, dtype=float)


def certificate(W: np.ndarray, C_K: int, eta_K: float, p_rej: float, rho_blk: float, eps: float, G: float) -> np.ndarray:
    return eta_K * rho_blk * eps * G * (1 - p_rej) * np.asarray(W, dtype=float) / C_K


def estimate_input_lipschitz(core, params: Dict[str, torch.Tensor], yf: torch.Tensor, idx: torch.Tensor,
                             keys: List[str], n_probe: int = 8, radius: float = 0.1,
                             seed: int = 0) -> float:
    """Finite-difference estimate of  sup ‖∇_θ L(θ; y + e) − ∇_θ L(θ; y)‖ / ‖e‖  over random
    directions e of norm ``radius`` (a lower bound on the true G, reported as such)."""
    g = torch.Generator(device="cpu").manual_seed(seed)
    p = {k: (v.detach().clone().requires_grad_(True) if k in keys else v) for k, v in params.items()}

    def grad_at(y):
        loss = core.detect_loss(p, y, idx)
        gs = torch.autograd.grad(loss, [p[k] for k in keys])
        return torch.cat([x.reshape(-1) for x in gs])

    g0 = grad_at(yf)
    best = 0.0
    for _ in range(n_probe):
        e = torch.randn(yf.shape, generator=g).to(yf.device)
        e = e / e.norm() * radius
        g1 = grad_at(yf + e)
        best = max(best, float((g1 - g0).norm().item() / radius))
    return best


def figure_adversary_term(out_path: str = "figures/fig_adversary_term.png") -> None:
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = 2 ** np.arange(0, 9)
    plt.figure(figsize=(5, 3.2))
    for p, lab, m in ((0.0, "no gate ($p^{rej}=0$)", "o"), (0.5, "G1 residual gate ($p^{rej}=0.5$)", "s"),
                      (0.95, "G2 CRC gate ($p^{rej}=0.95$)", "^")):
        plt.plot(C, adversary_term(C, p), marker=m, label=lab)
    plt.xscale("log", base=2)
    plt.xlabel("level period $C_k$ (blocks)")
    plt.ylabel("adversary term, normalised")
    plt.legend(fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=200)


if __name__ == "__main__":
    figure_adversary_term()


def estimate_adaptation_lipschitz(rx, yf: torch.Tensor, idx: torch.Tensor, eta: float, n_probe: int = 4,
                                  radius_in: float = 0.05, radius_par: float = 0.05, seed: int = 0):
    """Finite-difference constants of the *block adaptation map* Φ(θ; y) = fast level after one
    block of adaptation on pilots y, as implemented by ``rx._fast_update``:

      G_adapt = sup_e ‖Φ(θ; y+e) − Φ(θ; y)‖ / ‖e‖      (input sensitivity, ‖e‖ = radius_in·‖y‖)
      L_theta = sup_d ‖Φ(θ+d; y) − Φ(θ; y)‖ / ‖d‖      (parameter contraction, ‖d‖ = radius_par·‖θ_A‖)
      L_a     = sup_d ‖Φ(θ; y; a+d) − Φ(θ; y; a)‖ / ‖d‖  (sensitivity to the slow anchor a)

    All are lower bounds of the true suprema (random probes); L_theta + L_a < 1 certifies that the
    paired fast trajectories forget a displacement geometrically (Lemma 1 in docs/THEORY.md).
    Returns (G_adapt, L_theta, L_a)."""
    g = torch.Generator(device="cpu").manual_seed(seed)
    keys = rx.A
    base = {k: v.detach().clone() for k, v in rx.params.items()}
    flat = lambda p: torch.cat([p[k].reshape(-1) for k in keys])

    anchor0 = rx._anchor()

    def phi(params, y, anchor=None):
        rx.params = {k: v.detach().clone() for k, v in params.items()}
        a = anchor0 if anchor is None else anchor
        out = rx.core.sequential_adapt(rx.params, y, idx, lambda p, q, X, t: rx._fast_stage(p, q, X, t, eta, a))
        rx.params = {k: v.detach().clone() for k, v in base.items()}
        return flat(out)

    p0 = phi(base, yf)
    G, L, La = 0.0, 0.0, 0.0
    for _ in range(n_probe):
        e = torch.randn(yf.shape, generator=g).to(yf.device)
        e = e / e.norm() * (radius_in * yf.norm())
        G = max(G, float((phi(base, yf + e) - p0).norm() / e.norm()))
        d = {k: torch.randn(base[k].shape, generator=g).to(base[k].device) for k in keys}
        dn = torch.sqrt(sum((v ** 2).sum() for v in d.values()))
        scale = radius_par * flat(base).norm() / dn
        pert = dict(base)
        for k in keys:
            pert[k] = base[k] + scale * d[k]
        L = max(L, float((phi(pert, yf) - p0).norm() / (scale * dn)))
        if anchor0 is not None:
            da = {k: anchor0[k] + scale * d[k] for k in keys}
            La = max(La, float((phi(base, yf, da) - p0).norm() / (scale * dn)))
    return G, L, La


def estimate_input_gain_ascent(rx, yf: torch.Tensor, idx: torch.Tensor, eta: float, n_probe: int = 20,
                               ascent: int = 10, radius_in: float = 0.05, step: float = 0.5, seed: int = 0):
    """Stronger estimate of G_Phi (audit A6): from each of `n_probe` random directions, a
    finite-difference hill climb of `ascent` steps searches for the input direction of largest
    gain of the block adaptation map. Returns all per-probe maxima so callers can report the
    maximum and an upper quantile. Still a lower bound of the true supremum, but a much tighter
    one than independent random probes."""
    g = torch.Generator(device="cpu").manual_seed(seed)
    keys = rx.A
    base = {k: v.detach().clone() for k, v in rx.params.items()}
    flat = lambda p: torch.cat([p[k].reshape(-1) for k in keys])
    anchor0 = rx._anchor() if hasattr(rx, "_anchor") else None

    def phi(y):
        rx.params = {k: v.detach().clone() for k, v in base.items()}
        out = rx.core.sequential_adapt(rx.params, y, idx, lambda p, q, X, t: rx._fast_stage(p, q, X, t, eta, anchor0))
        rx.params = {k: v.detach().clone() for k, v in base.items()}
        return flat(out)

    p0 = phi(yf)
    r = radius_in * yf.norm()
    gains = []
    for _ in range(n_probe):
        d = torch.randn(yf.shape, generator=g).to(yf.device)
        d = d / d.norm()
        best = float((phi(yf + r * d) - p0).norm() / r)
        for _ in range(ascent):
            z = torch.randn(yf.shape, generator=g).to(yf.device)
            cand = d + step * z / z.norm()
            cand = cand / cand.norm()
            val = float((phi(yf + r * cand) - p0).norm() / r)
            if val > best:
                best, d = val, cand
        gains.append(best)
    return gains
