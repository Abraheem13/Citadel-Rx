"""Pilot-poisoning adversaries (proposal §2.4).

All attacks add a perturbation E to the received pilot block Y_p (and optionally
the data block) under an l2 budget ‖E‖_F ≤ ε per block. The budget is set
either explicitly or from a signal-to-interference ratio
    SIR = 10 log10( ‖Y_p^clean‖_F² / ‖E‖_F² ),
i.e. the attacker's energy relative to the legitimate users' energy over the
same symbols. 0 dB means the attacker spends as much energy as all users
together.

A1 — availability poisoning (Wu et al. 2024).  The attacker unrolls the
victim's adaptation map with a differentiable gradient-descent surrogate,
    θ⁺(E) = Adapt(θ; Y_p + E, S_p),
and maximises the detection loss of θ⁺ on a *clean query set* (the clean pilot
observations, which share the block's channel) by projected gradient ascent.
White-box: θ is the victim's current fast level. Transfer: θ is the attacker's
own surrogate receiver, trained on the pilots it observed over the air.

A2 — targeted drift spoofing. Maximise the loss of one user u* and penalise
the loss of the others, so the receiver "forgets" u* only.

A3 — boiling frog. With a small budget on every block, push θ⁺ toward a bad
basin θ_bad (the receiver adapted to a spoofed channel H + ΔH) while keeping
the clean query loss low so decision-based gates (G2) keep passing. Aims at the
slow levels through many consolidations.

adaptive — gate-aware A1: adds a differentiable penalty on the G1 residual
ratio computed from θ⁺'s soft symbols so that the poisoned fast state still
looks physically consistent.

data_jam — not a poisoning attack: Gaussian noise of the same energy on the
data symbols. The fair "is poisoning worse than jamming at equal power" control.

Revision attacks (reviewer audit):
a4 (B2) — reference degradation: the per-symbol power is split, a fraction a4_alpha on the
    pilots (poison) and the rest on the data (aimed at the reference detectors), and both parts
    are optimised jointly for the error rate of what the receiver emits.
deny (B3) — denial of adaptation: a weak, fixed channel-estimate spoof E = S_p Delta^T that trips
    the gates on every block, to freeze the receiver when the channel changes.
a3star (B5) — optimised slow drift: A3's spoofed basin, larger budgets, and a soft-gate term
    that keeps every block accepted.
soft_gate / restarts / eot / unroll_steps (B4) — the adaptive white-box: the attacker sees the
    exact thresholds and EMA states, differentiates through soft versions of the gates (BPDA)
    and maximises P(accept) x loss of the emitted decisions, averaged over noise draws.
attacker_antennas (B1) — E = G X_a with an N x M attacker channel G (optionally with CSI error).
knowledge = transfer with surrogate = citadel (B6) — a Citadel-Rx surrogate from another seed.
knowledge = query (B6) — no gradients: an NES search across blocks driven by the victim's
    per-block NACK count (HARQ feedback).
budget_ref = signal (B8) — the budget is defined against the users' noise-free energy.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

from ..config import AttackConfig, Config
from ..modulation import Modulation
from ..receivers.deepsic import DeepSICCore, ParamDict, clone_params
from ..receivers.lmmse import ls_channel_estimate
from ..receivers.online import OnlineDeepSIC


def feat(y: np.ndarray, device) -> torch.Tensor:
    f = np.concatenate([y.real, y.imag], axis=1) if np.iscomplexobj(y) else y
    return torch.as_tensor(np.ascontiguousarray(f), dtype=torch.float32, device=device)


def unfeat(f: torch.Tensor, is_complex: bool) -> np.ndarray:
    a = f.detach().cpu().numpy()
    if is_complex:
        n = a.shape[1] // 2
        return a[:, :n] + 1j * a[:, n:]
    return a


class Attacker:
    def __init__(self, cfg: Config, device: torch.device, rng: np.random.Generator):
        self.cfg = cfg
        self.ac: AttackConfig = cfg.attack
        self.device = device
        self.rng = rng
        self.mod = Modulation(cfg.frame.modulation)
        self.surrogate: Optional[OnlineDeepSIC] = None
        self.h_a: Optional[np.ndarray] = None
        self.theta_bad: Optional[ParamDict] = None
        self._surrogate_cfg = None
        self.start, self.end = self.ac.start_block, self.ac.end_block
        self.schedule = [dict(s) for s in (getattr(self.ac, "schedule", None) or [])]
        if self.schedule:   # v3 piecewise schedule: the window spans all segments, no random start
            self.start = int(min(s["start"] for s in self.schedule))
            self.end = int(max(s["end"] for s in self.schedule))
        elif self.ac.start_mode == "random" and self.ac.type != "none":
            wrng = np.random.default_rng(cfg.channel.seed + 9090)
            self.start = int(wrng.integers(self.ac.random_lo, self.ac.random_hi + 1))
            self.end = self.start + (self.ac.end_block - self.ac.start_block)
        self.G: Optional[np.ndarray] = None
        self.G_hat: Optional[np.ndarray] = None
        self.block_state = None          # set by the runner every block (UMi scene: st.G)
        self.sir_override: Optional[float] = None
        self.g_rms: Optional[float] = None
        self.q_mean: Optional[np.ndarray] = None
        self.q_last: Optional[np.ndarray] = None
        self.q_base: Optional[float] = None
        self.deny_dir: Optional[np.ndarray] = None
        self.frames = None

    @property
    def window(self) -> Tuple[int, int]:
        return self.start, self.end

    # ---- schedule and budget ------------------------------------------------
    def active(self, b: int) -> bool:
        if self.ac.type == "none":
            return False
        if not (self.start <= b < self.end):
            return False
        if self.schedule and self._segment(b) is None:
            return False
        if self.ac.rho_blk < 1.0:
            return bool(self.rng.random() < self.ac.rho_blk)
        return True

    def budget(self, y_clean: np.ndarray, small: bool = False, signal: Optional[np.ndarray] = None) -> float:
        if self.ac.eps is not None and not small:
            return float(self.ac.eps)
        sir = self.ac.sir_db if self.sir_override is None else self.sir_override
        ref = signal if (self.ac.budget_ref == "signal" and signal is not None) else y_clean
        energy = float(np.sum(np.abs(ref) ** 2))
        eps = np.sqrt(energy * 10 ** (-sir / 10))
        st = self.block_state
        if self.sir_override is not None and st is not None and getattr(st, "G", None) is not None:
            # UMi scene: unit-energy symbols at a user's maximum power through the attacker's own channel
            # (G is in the users' power-control units), so the SIR of each block follows the physics
            eps = float(np.sqrt(y_clean.shape[0]) * np.linalg.norm(st.G))
        if small:
            eps = float(self.ac.a3_eps_small) * np.sqrt(energy)
        return float(eps)

    # ---- transfer surrogate -----------------------------------------------------
    def _ensure_surrogate(self) -> OnlineDeepSIC:
        if self.surrogate is None:
            import copy
            scfg = copy.deepcopy(self.cfg)
            scfg.channel.seed = self.cfg.channel.seed + 999
            if self.ac.knowledge == "transfer" and self.ac.surrogate == "citadel":
                # grey-box (B6): the defence and its configuration are known, its weights are not
                from ..receivers import make_receiver
                from ..eval.runner import pretraining_blocks
                from ..frames import FrameGenerator
                scfg.receiver.type = "citadel"
                self.surrogate = make_receiver(scfg, self.device)
                self.surrogate.pretrain(pretraining_blocks(scfg, FrameGenerator(scfg)))
            else:
                scfg.receiver.type = "online_deepsic"
                self.surrogate = OnlineDeepSIC(scfg, self.device)
        return self.surrogate

    def _noisy(self, y: np.ndarray) -> np.ndarray:
        return y + np.sqrt(10 ** (-0.1 * self.cfg.channel.snr_db) / 2) * (
            self.rng.standard_normal(y.shape) + (1j * self.rng.standard_normal(y.shape) if np.iscomplexobj(y) else 0))

    def observe_clean(self, b: int, y_p: np.ndarray, idx_p: np.ndarray, y_d: Optional[np.ndarray] = None,
                      frames=None) -> None:
        """The attacker (a transmitter in range) listens to the pilots and trains its surrogate."""
        self.frames = frames
        if self.ac.type == "none" or self.ac.knowledge != "transfer":
            return
        sur = self._ensure_surrogate()
        # the attacker hears the pilots through its own noisy link
        y_obs = self._noisy(y_p)
        if self.ac.surrogate == "citadel" and y_d is not None:
            sur.process_block(b, y_obs, idx_p, self._noisy(y_d), aux={"framer": frames})
        else:
            sur.adapt(b, sur.to_feat(y_obs), sur.to_idx(idx_p))

    def feedback(self, b: int, crc_pass: Optional[np.ndarray], attacked: bool) -> None:
        """Query attacker (B6): the victim's per-block NACK fraction is the only signal it gets."""
        if self.ac.knowledge != "query" or not attacked or crc_pass is None or self.q_last is None:
            return
        nack = 1.0 - float(np.mean(crc_pass))
        if self.q_base is None:
            self.q_base = nack
        adv = nack - self.q_base
        self.q_base = 0.8 * self.q_base + 0.2 * nack
        self.q_mean = self.q_mean + self.ac.query_lr * adv * self.q_last
        self.q_mean = self.q_mean / max(np.linalg.norm(self.q_mean), 1e-12)

    # ---- rank-1 projection ----------------------------------------------------------
    def _ensure_G(self, n_ant: int) -> None:
        st = self.block_state
        if st is not None and getattr(st, "G", None) is not None:   # UMi scene: the block's true channel
            self.G = self.G_hat = st.G
            if self.ac.attacker_csi_err > 0:
                z = self.rng.standard_normal(st.G.shape) + 1j * self.rng.standard_normal(st.G.shape)
                self.G_hat = st.G + np.sqrt(self.ac.attacker_csi_err / 2) * z * np.linalg.norm(st.G) / np.sqrt(st.G.size)
            return
        if self.G is None:
            grng = np.random.default_rng(self.cfg.channel.seed + 31337)
            M = self.ac.attacker_antennas
            self.G = grng.standard_normal((n_ant, M)) / np.sqrt(n_ant)
            self.G_hat = self.G + np.sqrt(self.ac.attacker_csi_err) * grng.standard_normal(self.G.shape) / np.sqrt(n_ant) \
                if self.ac.attacker_csi_err > 0 else self.G.copy()

    def _through_true_channel(self, E: np.ndarray) -> np.ndarray:
        """B1 with CSI error: the attacker designs its transmit signal X_a = pinv(G_hat) E for the channel
        it believes in; what reaches the receiver is G X_a (the first revision injected E itself, so the
        CSI error had no effect beyond the choice of subspace)."""
        if self.ac.attacker_antennas <= 0 or self.ac.attacker_csi_err <= 0 or self.G is None or self.G_hat is None:
            return E
        Gh = self.G_hat
        T = self.G @ np.linalg.solve(Gh.conj().T @ Gh, Gh.conj().T)        # (N, N): E -> G pinv(G_hat) E
        return E @ T.T

    def _project_structure(self, E: torch.Tensor, is_complex: bool) -> torch.Tensor:
        if self.ac.attacker_antennas > 0:
            # B1: the received perturbation lies in the column space of the attacker's channel as
            # the attacker believes it to be (G_hat); the true G is applied at injection time
            n = E.shape[1] // (2 if is_complex else 1)
            self._ensure_G(n)
            Gh = self.G_hat
            P = Gh @ np.linalg.solve(Gh.conj().T @ Gh, Gh.conj().T)        # (N, N) projector on span(G_hat)
            e = unfeat(E, is_complex)
            return feat(e @ P.T, E.device)
        if self.ac.attacker_channel != "rank1":
            return E
        if self.h_a is None:
            n = E.shape[1] // (2 if is_complex else 1)
            h = self.rng.standard_normal(n) + (1j * self.rng.standard_normal(n) if is_complex else 0)
            self.h_a = h / np.linalg.norm(h)
        e = unfeat(E, is_complex)
        coef = e @ self.h_a.conj()                      # (n,)
        e_proj = np.outer(coef, self.h_a)
        return feat(e_proj, E.device)

    # ---- objectives ---------------------------------------------------------------------
    def _objective(self, core: DeepSICCore, theta_plus: ParamDict, yf_q: torch.Tensor, it_q: torch.Tensor,
                   y_d_feat: Optional[torch.Tensor], H: Optional[np.ndarray]) -> torch.Tensor:
        t = self.ac.type
        probs = core.detect(theta_plus, yf_q)
        logp = torch.log(probs.clamp_min(1e-12))
        nll = -logp.gather(-1, it_q.unsqueeze(-1)).squeeze(-1)          # (n, U)
        per_user = nll.mean(dim=0)
        if t in ("a1", "adaptive", "a4"):
            obj = per_user.sum()
            if t == "adaptive" and y_d_feat is not None and H is not None:
                obj = obj - self.ac.gate_aware_weight * self._g1_soft(core, theta_plus, y_d_feat, H)
            return obj
        if t == "a2":
            u = self.ac.target_user
            others = [v for v in range(per_user.shape[0]) if v != u]
            return per_user[u] - self.ac.a2_lambda * per_user[others].sum()
        if t in ("a3", "a3star"):
            assert self.theta_bad is not None
            dist = sum(((theta_plus[k] - self.theta_bad[k]) ** 2).sum() for k in self.theta_bad)
            return -dist - self.ac.a2_lambda * per_user.sum()
        if t == "deny":
            return per_user.sum()
        raise ValueError(t)

    @staticmethod
    def _soft_pass(probs: torch.Tensor, idx_true: torch.Tensor, L: int) -> torch.Tensor:
        """Soft CRC pass rate: mean over (sub-block, user) of prod_l P(correct symbol)."""
        pc = probs.gather(-1, idx_true.unsqueeze(-1)).squeeze(-1).clamp_min(1e-12)   # (n, U)
        n_sub = pc.shape[0] // L
        logp = torch.log(pc[: n_sub * L]).reshape(n_sub, L, -1).sum(dim=1)            # (n_sub, U)
        return torch.exp(logp).mean()

    def _soft_gamma(self, core, theta_plus, gate, ctx) -> torch.Tensor:
        """BPDA view of the victim's gates (B4): the exact thresholds and EMA states, with the
        hard steps replaced by the victim's own soft steps and the CRC by a soft pass rate."""
        if gate is None or not gate.gates:
            return torch.ones((), device=self.device)
        vs = []
        kappa = gate.kappa
        th = gate.thresholds(1.0)
        if "g2" in gate.gates and ctx.get("idx_d_sub") is not None:
            probs = core.detect(theta_plus, ctx["yd_sub"])
            pn = self._soft_pass(probs, ctx["idx_d_sub"], ctx["L"])
            s = pn / max(ctx["pass_ref"], 0.02) / max(gate.clean_g2_ema or 1.0, 1e-9)
            tau = th["g2"]
            if gate.g2_relative is not None and gate.g2_relative.get("mode") == "derived":
                tau = gate.g2_tau_derived(ctx["pass_ref"])
            elif gate.g2_relative is not None:
                Lc = gate.g2_relative["L"]
                p_ref = 1.0 - float(np.clip(ctx["pass_ref"], 1e-9, 1.0)) ** (1.0 / Lc)
                delta = max(gate.g2_relative["abs_min"], gate.g2_relative["rel"] * p_ref)
                tau = float(((1.0 - min(p_ref + delta, 0.999)) / max(1.0 - p_ref, 1e-9)) ** Lc)
            vs.append(torch.sigmoid((s - tau) / max(kappa * tau, 1e-9)))
        if "g1" in gate.gates and ctx.get("H") is not None:
            r_nn = self._g1_soft(core, theta_plus, ctx["yd_sub"], ctx["H"])
            s = r_nn / max(ctx["r_ref"], 1e-12) / max(gate.clean_g1_ema or 1.0, 1e-9)
            vs.append(torch.sigmoid((th["g1"] - s) / max(kappa * th["g1"], 1e-9)))
        if not vs:
            return torch.ones((), device=self.device)
        return torch.stack(vs).min()

    def _g1_soft(self, core: DeepSICCore, theta: ParamDict, y_d_feat: torch.Tensor, H: np.ndarray) -> torch.Tensor:
        """Differentiable G1 residual with posterior-mean soft symbols (attacker's view)."""
        probs = core.detect(theta, y_d_feat)                            # (n, U, order)
        c = self.mod.constellation_torch(y_d_feat.device)               # (order, 2|1)
        s_soft = probs @ c                                              # (n, U, 2|1)
        Hr = torch.as_tensor(np.real(H), dtype=torch.float32, device=y_d_feat.device)   # (N, U)
        Hi = torch.as_tensor(np.imag(H), dtype=torch.float32, device=y_d_feat.device)
        if self.mod.is_complex:
            sr, si = s_soft[..., 0], s_soft[..., 1]
            yr = sr @ Hr.T - si @ Hi.T
            yi = sr @ Hi.T + si @ Hr.T
            y_hat = torch.cat([yr, yi], dim=1)
        else:
            y_hat = s_soft[..., 0] @ Hr.T
        # mean over slots of the squared residual per receive antenna, |.|^2 summed over the real and
        # imaginary parts: the scale of physics.model_residual, which the receiver's G1 uses. (Records
        # written before this fix averaged over the 2N real coordinates, half the receiver's scale for
        # complex modulation; they stay in results/rev_p3_adaptive, see docs/G1_SOFT_FIX.md.)
        return ((y_d_feat - y_hat) ** 2).sum(dim=1).mean() / H.shape[0]

    def _soft_ctx(self, t, y_p, y_d, idx_p, idx_d, H, noise_var, framer, victim, core) -> Optional[Dict[str, Any]]:
        if idx_d is None or framer is None or not framer.framer.enabled:
            return None
        from ..gates.physics import model_residual
        from ..receivers.lmmse import hard_from_probs, lmmse_soft_symbols
        L, n_sub = framer.framer.L, framer.n_sub
        nsel = n_sub if (t == "a4" or self.ac.data_subblocks <= 0 or self.ac.data_subblocks >= n_sub) else self.ac.data_subblocks
        subs = np.arange(n_sub) if nsel >= n_sub else np.sort(self.rng.choice(n_sub, size=nsel, replace=False))
        rows = (subs[:, None] * L + np.arange(L)[None, :]).reshape(-1)
        nv = float(np.mean(np.abs(y_p - self.mod.modulate_indices(idx_p) @ H.T) ** 2))
        idx_mm = hard_from_probs(lmmse_soft_symbols(y_d, H, nv, self.mod))
        chk = lambda i: float(framer.framer.check(framer.decided_bits_to_subblocks(i)).mean())
        pass_ref = chk(idx_mm)
        if hasattr(victim, "_anchor") and getattr(victim, "K", 1) > 1:
            p_sl = dict(victim.params); p_sl.update(victim._anchor())
            with torch.no_grad():
                idx_sl = victim.hard(core.detect(p_sl, feat(y_d, self.device)))
            pass_ref = max(pass_ref, chk(idx_sl))
        return {"L": L, "rows": rows, "yd_sub": feat(y_d[rows], self.device),
                "idx_d_sub": torch.as_tensor(idx_d[rows], dtype=torch.long, device=self.device),
                "pass_ref": pass_ref, "H": H, "r_ref": model_residual(y_d[rows], idx_mm[rows], H, self.mod)}

    # ---- main entry ---------------------------------------------------------------------
    def _segment(self, b: int) -> Optional[Dict[str, Any]]:
        for s in self.schedule:
            if int(s["start"]) <= b < int(s["end"]):
                return s
        return None

    def craft(self, b: int, y_p: np.ndarray, idx_p: np.ndarray, y_d: np.ndarray, receiver,
              noise_var: float, idx_d: Optional[np.ndarray] = None, H_true: Optional[np.ndarray] = None,
              framer=None) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """One block of the attack. With a schedule, the segment covering block b replaces the attack.*
        settings it names for this block only (the attacker's state, e.g. its surrogate, is shared)."""
        seg = self._segment(b) if self.schedule else None
        if seg is None:
            return self._craft(b, y_p, idx_p, y_d, receiver, noise_var, idx_d, H_true, framer)
        import dataclasses
        base = self.ac
        ov = {k: v for k, v in seg.items() if k not in ("start", "end")}
        unknown = set(ov) - {f.name for f in dataclasses.fields(base)}
        if unknown:
            raise KeyError(f"unknown attack setting(s) in the schedule: {sorted(unknown)}")
        self.ac = dataclasses.replace(base, **ov)
        try:
            y_p2, y_d2, stats = self._craft(b, y_p, idx_p, y_d, receiver, noise_var, idx_d, H_true, framer)
        finally:
            self.ac = base
        stats["segment"] = self.schedule.index(seg)
        return y_p2, y_d2, stats

    def _craft(self, b: int, y_p: np.ndarray, idx_p: np.ndarray, y_d: np.ndarray, receiver,
               noise_var: float, idx_d: Optional[np.ndarray] = None, H_true: Optional[np.ndarray] = None,
               framer=None) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        stats: Dict[str, Any] = {"attacked": False}
        if not self.active(b):
            return y_p, y_d, stats
        t = self.ac.type
        is_complex = np.iscomplexobj(y_p)
        stats["attacked"] = True
        framer = framer or self.frames
        # noise-free users' energy, for the signal-referenced budget (audit B8)
        sig_p = self.mod.modulate_indices(idx_p) @ H_true.T if H_true is not None else None
        sig_d = self.mod.modulate_indices(idx_d) @ H_true.T if (H_true is not None and idx_d is not None) else None

        if t == "data_jam":
            eps = self.budget(y_d, signal=sig_d)
            E = self.rng.standard_normal(y_d.shape) + (1j * self.rng.standard_normal(y_d.shape) if is_complex else 0)
            E = E / np.linalg.norm(E) * eps
            stats["eps"] = eps
            return y_p, y_d + E, stats

        if t == "deny":   # B3: fixed channel-estimate spoof E = S_p Delta^T that trips the gates every block
            eps = self.budget(y_p, signal=sig_p)
            if self.deny_dir is None:
                d = self.rng.standard_normal((y_p.shape[1], idx_p.shape[1]))
                self.deny_dir = d / np.linalg.norm(d)
            E = self.mod.modulate_indices(idx_p) @ self.deny_dir.T
            E = E / np.linalg.norm(E) * eps
            stats.update(eps=eps, e_norm=float(np.linalg.norm(E)))
            return y_p + E, y_d, stats

        if self.ac.knowledge == "query":   # B6: gradient-free NES across blocks on the victim's NACK feedback
            eps = self.budget(y_p, signal=sig_p)
            def _unit():
                z = self.rng.standard_normal(y_p.shape) + (1j * self.rng.standard_normal(y_p.shape) if is_complex else 0)
                return z / np.linalg.norm(z)
            if self.q_mean is None:
                self.q_mean = _unit()
            self.q_last = _unit()
            d = self.q_mean + self.ac.query_sigma * self.q_last
            E = d / np.linalg.norm(d) * eps
            if self.ac.attacker_antennas > 0:
                E = unfeat(self._project_structure(feat(E, self.device), is_complex), is_complex)
                E = self._through_true_channel(E / max(np.linalg.norm(E), 1e-12) * eps)
            stats.update(eps=eps, e_norm=float(np.linalg.norm(E)), knowledge_used="query")
            return y_p + E, y_d, stats

        # victim or surrogate model. A receiver without a differentiable adaptation map (LMMSE)
        # is attacked through the surrogate even in "white-box" mode, so every row of the
        # SIR table carries a perturbation of the same budget.
        surf = receiver.attack_surface() if self.ac.knowledge != "transfer" else {}
        victim_for_gate, gate = receiver, None
        if self.ac.knowledge == "transfer" or not surf:
            sur = self._ensure_surrogate()
            if self.ac.knowledge != "transfer":  # surrogate must still learn from the clean pilots
                sur.adapt(b, sur.to_feat(y_p), sur.to_idx(idx_p))
            if self.ac.knowledge == "transfer" and self.ac.surrogate == "citadel":
                ssurf = sur.attack_surface()   # grey-box (B6): defence known, weights unknown
                core, theta, keys, lr = ssurf["core"], ssurf["params"], ssurf["keys"], ssurf["lr"]
                victim_for_gate, gate = sur, ssurf.get("gate")
            else:
                core, theta, keys, lr = sur.core, sur.params, list(sur.params.keys()), sur.lr
            stats["knowledge_used"] = "transfer"
        else:
            core, theta, keys, lr = surf["core"], surf["params"], surf["keys"], surf["lr"]
            gate = surf.get("gate")
            stats["knowledge_used"] = "whitebox"
        theta = clone_params(theta)

        eps = self.budget(y_p, small=(t in ("a3", "a3star")), signal=sig_p)
        if t == "a4":   # reference degradation (B2): sqrt(alpha) of the budget goes on the pilots
            eps = float(np.sqrt(self.ac.a4_alpha)) * self.budget(y_p, signal=sig_p)
        yf_p = feat(y_p, self.device)
        it_p = torch.as_tensor(idx_p, dtype=torch.long, device=self.device)
        y_d_feat = feat(y_d, self.device) if t == "adaptive" else None
        want_H = t in ("adaptive", "a3", "a3star", "a4") or self.ac.soft_gate
        H = ls_channel_estimate(y_p, self.mod.modulate_indices(idx_p), noise_var) if want_H else None

        if t in ("a3", "a3star") and self.theta_bad is None:
            # spoofed channel: rotate / scale the user gains so the bad basin is well separated
            H_bad = H * (1.0 + 0.5 * self.rng.standard_normal(H.shape))
            s_p = self.mod.modulate_indices(idx_p)
            y_bad = s_p @ H_bad.T
            y_bad = y_bad + np.sqrt(noise_var / 2) * (self.rng.standard_normal(y_bad.shape) + 1j * self.rng.standard_normal(y_bad.shape)) \
                if is_complex else y_bad + np.sqrt(noise_var) * self.rng.standard_normal(y_bad.shape)
            with torch.enable_grad():
                tb = core.functional_adapt(theta, feat(y_bad, self.device), it_p, lr=lr, steps=self.ac.unroll_steps * 5,
                                           keys=keys, create_graph=False)
            self.theta_bad = {k: tb[k].detach() for k in keys}

        # context for the adaptive objective: the attacker that knows the defence (B4) maximises the
        # error rate of the *emitted* decisions weighted by a soft probability of being accepted
        # (BPDA through the gates); the reference-degradation attacker (B2) additionally perturbs the
        # data so the model-based references used by the gates degrade with the fast level.
        use_soft = (self.ac.soft_gate or t in ("a4", "a3star")) and gate is not None and gate.gates
        ctx = self._soft_ctx(t, y_p, y_d, idx_p, idx_d, H, noise_var, framer, victim_for_gate, core) if use_soft else None
        eps_d = (float(np.sqrt(1.0 - self.ac.a4_alpha)) * self.budget(y_d, signal=sig_d)) if (t == "a4" and ctx) else 0.0

        E = torch.zeros_like(yf_p, requires_grad=True)
        alpha = self.ac.pgd_alpha * eps
        best_obj, best_E, best_Ed = -np.inf, torch.zeros_like(yf_p), None
        n_restart = max(1, self.ac.restarts)
        for ri in range(n_restart):
            if ri > 0:   # B4: random restarts
                z = torch.randn(yf_p.shape, generator=torch.Generator().manual_seed(7 * b + ri))
                E = (z / z.norm().clamp_min(1e-12) * eps).to(self.device).requires_grad_(True)
            Ed = torch.zeros_like(ctx["yd_sub"]).requires_grad_(True) if eps_d > 0 else None
            for _ in range(self.ac.pgd_steps):
                leaves = [E] + ([Ed] if Ed is not None else [])
                obj = self._attack_obj(core, theta, yf_p, it_p, E, Ed, y_d_feat, H, gate, ctx, b, noise_var)
                grads = torch.autograd.grad(obj, leaves)
                with torch.no_grad():
                    if obj.item() > best_obj:
                        best_obj, best_E = obj.item(), E.detach().clone()
                        best_Ed = Ed.detach().clone() if Ed is not None else None
                    E = self._pgd_step(E, grads[0], alpha, eps, is_complex)
                    if Ed is not None:
                        Ed = Ed + grads[1] / grads[1].norm().clamp_min(1e-12) * (self.ac.pgd_alpha * eps_d)
                        nd = Ed.norm()
                        Ed = (Ed * (eps_d / nd) if nd > eps_d else Ed).detach().requires_grad_(True)
        E_np = self._through_true_channel(unfeat(best_E, is_complex))
        stats.update(eps=eps, obj=float(best_obj), e_norm=float(np.linalg.norm(E_np)))
        y_p_adv = y_p + E_np
        y_d_adv = y_d
        if best_Ed is not None and ctx is not None:   # write the optimised data perturbation back
            y_d_adv = y_d.copy()
            y_d_adv[ctx["rows"]] = y_d[ctx["rows"]] + unfeat(best_Ed, is_complex)
            stats["eps_d"] = float(eps_d)
        elif self.ac.where in ("pilots_data", "all"):
            eps_d = self.budget(y_d, signal=sig_d)
            Ed = self.rng.standard_normal(y_d.shape) + (1j * self.rng.standard_normal(y_d.shape) if is_complex else 0)
            y_d_adv = y_d + Ed / np.linalg.norm(Ed) * eps_d
        if self.ac.oracle_scales and idx_d is not None and hasattr(receiver, "process_block"):
            y_p_adv = self._oracle_select(b, y_p, idx_p, y_p_adv, y_d_adv, receiver, framer, idx_d, stats)
        return y_p_adv, y_d_adv, stats

    def _oracle_select(self, b, y_p, idx_p, y_p_adv, y_d_adv, receiver, framer, idx_d, stats) -> np.ndarray:
        """Exact-gate attacker. The optimised pilot perturbation E is scaled by each factor of
        attack.oracle_scales, every candidate is processed by an exact copy of the victim receiver
        (adaptation, references, gates with their thresholds and running statistics, fallback and CRC
        selection), and the candidate whose emitted decisions have the highest SER on the true data is
        sent (ties: the larger perturbation); with oracle_mode = accepted, the highest SER among the
        candidates the gates accept, if any (a poisoning attacker). The data part, if any, is kept. The random-number states
        are restored after every trial, so the trials do not change the run."""
        import copy
        import random
        E = y_p_adv - y_p
        best, trials = None, []
        for s in self.ac.oracle_scales:
            st = (torch.get_rng_state(), np.random.get_state(), random.getstate())
            rx = copy.deepcopy(receiver)
            out = rx.process_block(b, y_p + s * E, idx_p, y_d_adv, aux={"framer": framer, "state": self.block_state})
            torch.set_rng_state(st[0]); np.random.set_state(st[1]); random.setstate(st[2])
            ser = float((out.idx_hat != idx_d).any(axis=1).mean())
            g = out.stats.get("gamma")
            trials.append((float(s), ser, None if g is None else float(g)))
        acc = [t for t in trials if t[2] is None or t[2] >= 0.5]
        pool = acc if (self.ac.oracle_mode == "accepted" and acc) else trials
        for t in pool:   # first maximum: the larger perturbation on ties (scales in decreasing order)
            if best is None or t[1] > best[1] + 1e-12:
                best = t
        stats.update(oracle_scale=best[0], oracle_ser=best[1], oracle_gamma=best[2],
                     oracle_n_accepted=int(sum(1 for t in trials if t[2] is None or t[2] >= 0.5)),
                     oracle_n=len(trials))
        return y_p + best[0] * E

    def _pgd_step(self, E, g, alpha, eps, is_complex):
        E_new = self._project_structure(E + g / g.norm().clamp_min(1e-12) * alpha, is_complex)
        nrm = E_new.norm()
        if nrm > eps:
            E_new = E_new * (eps / nrm)
        return E_new.detach().requires_grad_(True)

    def _attack_obj(self, core, theta, yf_p, it_p, E, Ed, y_d_feat, H, gate, ctx, b, noise_var):
        """One evaluation of the attacker's objective, averaged over `eot` noise draws (B4)."""
        total = 0.0
        for k in range(max(1, self.ac.eot)):
            yin = yf_p + E
            if self.ac.eot > 1:
                gg = torch.Generator().manual_seed(10007 * b + k)
                yin = yin + (np.sqrt(noise_var / 2) * torch.randn(yin.shape, generator=gg)).to(yin.device)
            theta_plus = core.functional_adapt(theta, yin, it_p, lr=self.ac.unroll_lr,
                                                steps=self.ac.unroll_steps, keys=list(theta.keys()), create_graph=True)
            if ctx is not None:   # output-level objective behind the soft gates
                total = total + self._soft_objective(core, theta_plus, ctx, Ed, gate)
            else:
                total = total + self._objective(core, theta_plus, yf_p, it_p, y_d_feat, H)
        return total / max(1, self.ac.eot)

    def _soft_objective(self, core, theta_plus, ctx, Ed, gate) -> torch.Tensor:
        """Error rate of the emitted decisions times the soft probability the block is accepted."""
        yd = ctx["yd_sub"] if Ed is None else ctx["yd_sub"] + Ed
        probs = core.detect(theta_plus, yd)
        nll = -torch.log(probs.gather(-1, ctx["idx_d_sub"].unsqueeze(-1)).squeeze(-1).clamp_min(1e-12)).mean()
        p_acc = self._soft_gamma(core, theta_plus, gate, {**ctx, "yd_sub": yd})
        return nll * p_acc + self.ac.gate_aware_weight * (p_acc - 1.0)


def make_attacker(cfg: Config, device: torch.device, seed: int) -> Attacker:
    return Attacker(cfg, device, np.random.default_rng(seed + 4242))
