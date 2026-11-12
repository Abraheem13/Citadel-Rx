"""Citadel-Rx: continuum-memory test-time-learning receiver (proposal §2.5).

Memory levels. The adaptable parameter set A of the DeepSIC backbone is kept
in K copies θ^(1..K). θ^(1) (the *fast* level) detects and is updated on every
block from the pilots. Level k+1 is updated only every C_{k+1} blocks from the
*gated average* of level-k states over the period,

    θ^(k+1) ← θ^(k+1) + η^(k+1) ( Σ_b γ_b θ^(k)_b / Σ_b γ_b − θ^(k+1) ),     (Eq. 2.6')

which is Eq. (2.6) written with increments taken relative to the slow anchor:
a corrupted block that slipped through the gate owns at most its γ-share
(≈1/C_{k+1}) of the average, which is the 1/C_k factor of Theorem 2.1, and
with all-clean verdicts the slow level tracks the period-average of the fast
level so that anchoring to it costs nothing in the clean condition.

Re-anchoring (recovery). Either a jump θ^(1) ← (1−β)θ^(1) + βΠ(θ^(2..K)) at
every consolidation (CMS Eq. 72) or, by default, a proximal pull inside every
fast update, θ^(1) ← θ^(1) − η λ (θ^(1) − Π(θ^(2..K))), i.e. the fast level
minimises  L_pil + (λ/2)‖θ − Π‖²  — a contraction toward the uncorrupted slow
memory that pulls a poisoned fast state back once the attack stops.

Fast rule (Eq. 2.4, Delta Gradient Descent). W ← W (I − η δ φ φᵀ) − η ĝ with φ
the normalised mean input of the layer over the pilot batch and ĝ the
Adam-preconditioned (or plain) gradient. δ = 0 with the 'adam' rule recovers
the reference online DeepSIC.

Surprise (Eq. 2.5). S_b = ‖∇_A L_pil(θ^(1); P_b)‖² before adaptation,
r_b = clip(S_b / S̄_b, 1/c, c) with S̄ an EMA seeded on a short warm-up,
η_b = η_max · 2 r_b / (1 + r_b); the gate thresholds tighten with r_b.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import torch

from ..config import Config
from ..gates import GateController
from ..gates.physics import g1_residual
from .base import BlockOutput
from .deepsic import ParamDict, clone_params, param_dist
from .lmmse import ChannelTracker, estimate_noise_var, hard_from_probs, lmmse_soft_symbols, ls_channel_estimate
from .online import DeepSICReceiver


class CitadelRx(DeepSICReceiver):
    name = "citadel"

    def __init__(self, cfg: Config, device: torch.device, single_memory: bool = False):
        super().__init__(cfg, device)
        cc = cfg.citadel
        self.single = single_memory
        self.K = 1 if single_memory else cc.levels
        self.C = [1] if single_memory else list(cc.periods[: self.K])
        if len(self.C) != self.K or self.C[0] != 1:
            raise ValueError("periods must have `levels` entries and start with 1")
        self.A = self.core.adaptable_keys(cc.adaptable)
        self.rule = cc.fast_rule
        self.fast_steps = cc.fast_steps
        self.eta_max = cc.eta_max
        self.use_surprise = cc.surprise_lr
        self.s_ema_coef = cc.surprise_ema
        self.s_clamp = cc.surprise_clamp
        self.s_warmup = cc.surprise_warmup
        self.delta = cc.dgd_delta
        self.level_lr = [1.0] + list(cc.level_lr[: self.K - 1]) if self.K > 1 else [1.0]
        self.reanchor_mode = cc.reanchor_mode
        self.beta = cc.reanchor_beta
        self.prox_lambda = cc.prox_lambda
        w = np.array(cc.level_weights[: self.K - 1], dtype=float) if self.K > 1 else np.array([])
        self.level_w = (w / w.sum()) if w.size else w
        gates = [] if single_memory else cc.gates
        # G2 threshold from Proposition 2.3: a pass-rate ratio below (1 - slack)^L means the fast
        # level's SER exceeds the reference's by more than `slack`
        L = cfg.frame.crc_subblock_symbols
        g2_tau = cc.g2_tau if cc.g2_tau is not None else float((1.0 - cc.g2_ser_slack) ** L)
        g2_rel = None
        if cc.g2_slack_mode in ("relative", "derived"):
            g2_rel = {"L": L, "rel": cc.g2_rel_slack, "abs_min": cc.g2_abs_min_slack, "mode": cc.g2_slack_mode,
                      "z": cc.g2_derived_z}
        self.gate = GateController(gates, cc.gate_mode, cc.g1_tau, g2_tau, cc.g3_tau, cc.g3_quantile,
                                   cc.adaptive_thresholds, dof=self.n_ant * self.n_user, kappa=cc.gate_kappa,
                                   tighten_floor=cc.tighten_floor, g2_relative=g2_rel)
        self.cc = cc
        self.streak = 0
        self.ref_stats = {"pass": None, "pass_var": None, "res": None, "res_var": None}
        self.reject_action = cc.reject_action
        self.fallback = cc.fallback_on_reject
        self.noise_var = 10 ** (-0.1 * cfg.channel.snr_db)
        self.tracker = ChannelTracker(rho=1.0)
        self.levels: List[ParamDict] = [clone_params(self.params) for _ in range(self.K)]
        self.level_init: List[ParamDict] = [clone_params(self.params) for _ in range(self.K)]
        # buf[k]: (gamma, state) pairs of level-k states since the last consolidation into level k+1
        self.buf: List[List] = [[] for _ in range(self.K)]
        self.S_hist: List[float] = []
        self.S_ema: Optional[float] = None
        self.name = "titans_single" if single_memory else "citadel"

    # ---- lifecycle ----------------------------------------------------------
    def pretrain(self, blocks) -> None:
        super().pretrain(blocks)
        self.levels = [clone_params(self.params) for _ in range(self.K)]
        self.level_init = [clone_params(self.params) for _ in range(self.K)]
        self.tracker = ChannelTracker(rho=1.0)

    def set_channel_rho(self, rho: float) -> None:
        self.tracker.rho = rho

    def _anchor(self) -> Optional[ParamDict]:
        if self.K == 1:
            return None
        return {key: sum(float(w) * self.levels[k + 1][key] for k, w in enumerate(self.level_w)) for key in self.A}

    # ---- surprise -------------------------------------------------------------
    def _surprise(self, yf: torch.Tensor, idx: torch.Tensor) -> float:
        p = {k: (v.detach().clone().requires_grad_(True) if k in self.A else v) for k, v in self.params.items()}
        loss = self.core.detect_loss(p, yf, idx)
        grads = torch.autograd.grad(loss, [p[k] for k in self.A])
        return float(sum((g ** 2).sum() for g in grads).item())

    def _surprise_ratio(self, S: float) -> float:
        self.S_hist.append(S)
        if len(self.S_hist) <= self.s_warmup:
            self.S_ema = float(np.median(self.S_hist))
            return 1.0
        r = S / max(self.S_ema, 1e-12)
        r = float(np.clip(r, 1.0 / self.s_clamp, self.s_clamp))
        self.S_ema = self.s_ema_coef * self.S_ema + (1 - self.s_ema_coef) * S
        return r

    # ---- fast rule --------------------------------------------------------------
    def _fast_stage(self, p: ParamDict, q: int, X: torch.Tensor, idx: torch.Tensor, eta: float,
                    anchor: Optional[ParamDict], sample_w: Optional[torch.Tensor] = None) -> ParamDict:
        keys = [k for k in self.core.keys_for(q) if k in self.A]
        if not keys:
            return p
        p = dict(p)
        leaves = {k: p[k].detach().clone().requires_grad_(True) for k in keys}
        use_adam = self.rule in ("adam", "dgd")
        opt = torch.optim.Adam(list(leaves.values()), lr=eta) if use_adam else None
        use_delta = self.rule in ("dgd", "dgd_plain") and self.delta > 0
        use_prox = anchor is not None and self.reanchor_mode == "proximal" and self.prox_lambda > 0
        pp = dict(p)
        with torch.no_grad():
            phi1 = X.mean(dim=1)
            phi1 = phi1 / phi1.norm(dim=-1, keepdim=True).clamp_min(1e-9)
        for _ in range(self.fast_steps):
            pp.update(leaves)
            logits, h = self.core.module_forward(pp, q, X, return_hidden=True)
            tgt = idx.transpose(0, 1)
            ce = torch.nn.functional.cross_entropy(logits.reshape(-1, self.core.order), tgt.reshape(-1),
                                                   reduction="none").reshape(self.core.U, -1)
            ce = ce.mean(dim=1).sum() if sample_w is None else (ce * sample_w[None, :]).sum()
            grads = torch.autograd.grad(ce, list(leaves.values()))
            with torch.no_grad():
                if use_delta:
                    phi2 = h.mean(dim=1)
                    phi2 = phi2 / phi2.norm(dim=-1, keepdim=True).clamp_min(1e-9)
                    for k, t in leaves.items():
                        if k.endswith("fc1.w"):
                            t -= eta * self.delta * torch.einsum("uoi,ui,uj->uoj", t, phi1, phi1)
                        elif k.endswith("fc2.w"):
                            t -= eta * self.delta * torch.einsum("uoi,ui,uj->uoj", t, phi2, phi2)
                if use_prox:
                    for k, t in leaves.items():
                        t -= eta * self.prox_lambda * (t - anchor[k])
            if use_adam:
                opt.zero_grad(set_to_none=True)
                for t, g in zip(leaves.values(), grads):
                    t.grad = g
                opt.step()
            else:
                with torch.no_grad():
                    for t, g in zip(leaves.values(), grads):
                        t -= eta * g
        for k, t in leaves.items():
            p[k] = t.detach()
        return p

    def _fast_update(self, yf: torch.Tensor, idx: torch.Tensor, eta: float,
                     sample_w: Optional[torch.Tensor] = None, start: Optional[ParamDict] = None) -> ParamDict:
        anchor = self._anchor()
        p0 = self.params if start is None else start
        p = self.core.sequential_adapt(p0, yf, idx,
                                       lambda p, q, X, t: self._fast_stage(p, q, X, t, eta, anchor, sample_w))
        R = self.cc.fast_radius
        if R > 0:   # H1: the block's total update lies in a ball of radius R around its start
            d = param_dist(p, p0, self.A)
            if d > R:
                p = dict(p)
                for k in self.A:
                    p[k] = p0[k] + (p[k] - p0[k]) * (R / d)
        return p

    # ---- consolidation ------------------------------------------------------------
    def _consolidate(self, b: int) -> Dict[str, Any]:
        events = []
        for k in range(self.K - 1):
            if (b + 1) % self.C[k + 1] != 0 or not self.buf[k]:
                continue
            gs = np.array([g for g, _ in self.buf[k]], dtype=float)
            if self.cc.consol_mean == "normalized" and gs.sum() > 0:
                denom = float(gs.sum())          # convex combination of the buffered states
            else:
                denom = max(1.0, float(gs.sum()))  # first version: sub-normalised when sum gamma < 1
            mean_state = {key: sum(g * s[key] for g, s in self.buf[k]) / denom for key in self.A}
            eta_k = self.level_lr[k + 1]
            # with Σγ < 1 (everything rejected) the update is scaled down accordingly
            scale = eta_k * min(1.0, float(gs.sum()))
            # quantities of the extended retention bound (audit A2), logged for paired analysis
            radius = max(param_dist(st, mean_state, self.A) for _, st in self.buf[k])
            d_mean = param_dist(self.levels[k + 1], mean_state, self.A)
            incs = {key: scale * (mean_state[key] - self.levels[k + 1][key]) for key in self.A}
            inc_norm = float(np.sqrt(sum(float((v ** 2).sum().item()) for v in incs.values())))
            clip = self.cc.consol_clip[k] if k < len(self.cc.consol_clip) else 0.0
            clipped = clip > 0 and inc_norm > clip
            if clipped:   # H1: every consolidation moves level k+2 by at most `clip`
                incs = {key: v * (clip / inc_norm) for key, v in incs.items()}
            for key in self.A:
                self.levels[k + 1][key] = self.levels[k + 1][key] + incs[key]
            if k + 1 == self.K - 1 and self.cc.drift_guard > 0 and hasattr(self, "pretrained_params"):
                xi = self.cc.drift_guard   # H5: weak pull of the slowest level toward the pre-trained weights
                for key in self.A:
                    self.levels[k + 1][key] = self.levels[k + 1][key] - xi * (self.levels[k + 1][key] - self.pretrained_params[key])
            self.buf[k + 1].append((float(gs.mean()), clone_params(self.levels[k + 1])))
            self.buf[k] = []
            events.append({"level": k + 2, "block": b, "mean_gamma": float(gs.mean()),
                           "sum_gamma": float(gs.sum()), "inc_norm": inc_norm, "clipped": bool(clipped),
                           "w": [float(g / denom) for g in gs], "s": float(scale), "r": float(radius),
                           "d_to_mean": float(d_mean)})
        if events and self.reanchor_mode == "jump" and self.beta > 0:
            proj = self._anchor()
            for key in self.A:
                self.params[key] = (1 - self.beta) * self.params[key] + self.beta * proj[key]
        return {"consolidations": events}

    # ---- block ---------------------------------------------------------------------
    def _crc_pass(self, framer, idx: np.ndarray) -> np.ndarray:
        return framer.framer.check(framer.decided_bits_to_subblocks(idx))          # (n_sub, U)

    def _crc_select(self, framer, cands: List[np.ndarray]) -> (np.ndarray, Dict[str, float]):
        """H6: per (sub-block, user) output the first candidate whose CRC passes; if none
        passes, keep the first candidate (the gate's choice)."""
        L, n_sub = framer.framer.L, framer.n_sub
        out = cands[0].copy()
        done = self._crc_pass(framer, cands[0])
        for c in cands[1:]:
            ok = self._crc_pass(framer, c) & ~done
            if ok.any():
                js, us = np.nonzero(ok)
                for j, u in zip(js, us):
                    out[j * L:(j + 1) * L, u] = c[j * L:(j + 1) * L, u]
                done |= ok
        return out, {"crc_select_frac": float(done.mean())}

    def _revert_users(self, before: ParamDict, users: np.ndarray) -> None:
        """H7: restore the listed users' slices of every adaptable tensor (leading axis = user)."""
        self.params = dict(self.params)
        for k in self.A:
            t = self.params[k].clone()
            t[users] = before[k][users]
            self.params[k] = t

    def _abstain_check(self, pass_ref: Optional[float], r_mm: Optional[float], n_checks: int) -> bool:
        """H3: the reference itself is degraded (its CRC pass rate or LMMSE residual is far from its
        running level on accepted blocks), so neither the fast level nor the ratios can be trusted."""
        st, z = self.ref_stats, self.cc.abstain_z
        bad = False
        if pass_ref is not None and st["pass"] is not None:
            var = max(st["pass_var"] or 0.0, pass_ref * (1 - pass_ref) / max(n_checks, 1))
            bad |= pass_ref < st["pass"] - z * np.sqrt(var)
        if r_mm is not None and st["res"] is not None:
            bad |= r_mm > st["res"] + z * np.sqrt(max(st["res_var"] or 0.0, (0.05 * st["res"]) ** 2))
        return bool(bad)

    def _ref_symbols(self, framer, refs):
        """Per (sub-block or code block, user): the verified data symbol indices from the reference
        detections and a verified mask. CRC framing: the first reference whose CRC passes; LDPC: the
        re-encoded codeword of the first reference that decodes."""
        L, n_sub, U = framer.framer.L, framer.n_sub, self.n_user
        sym = np.zeros((n_sub * L, U), dtype=np.int64)
        ok_all = np.zeros((n_sub, U), dtype=bool)
        for idx in refs:
            if hasattr(framer.framer, "decode"):
                ok, cw = framer.framer.decode(framer.decided_bits_to_subblocks(idx))
                bits = framer.framer.scramble(cw.transpose(1, 0, 2).reshape(U, -1))   # (U, n_d * bps), as sent
                cand = self.mod.bits_to_indices(bits).T                        # (n_d, U)
            else:
                ok, cand = self._crc_pass(framer, idx), idx
            new = ok & ~ok_all
            if new.any():
                m = np.repeat(new, L, axis=0)                                  # (n_d, U)
                sym[m] = cand[m]
            ok_all |= ok
        return sym, ok_all

    def _coded_virtual_pass(self, framer, idx_nn, refs):
        """LDPC (audit D2): a code block's CRC after decoding tolerates raw symbol errors, so its pass
        rate is not the (1-p)^L of the G2 design rule. On the code blocks that decode under a reference,
        the transmitted symbols are known; each detector's raw SER on them, written as the pass rate
        (1 - SER)^L of a virtual L-symbol sub-block (L of the design rule), lets the gate tolerate
        SER_ref + delta exactly as with CRC sub-blocks. Returns ((F_nn, per user), (F_ref, per user),
        verified fraction), or None if nothing decodes."""
        sym, ok = self._ref_symbols(framer, refs)
        if not ok.any():
            return None
        L, Lg = framer.framer.L, self.cfg.frame.crc_subblock_symbols
        m = np.repeat(ok, L, axis=0)                                           # (n_d, U) verified symbols

        def vpass(idx):
            err = (idx != sym) & m
            n_u = np.maximum(m.sum(axis=0), 1)
            ser_u = err.sum(axis=0) / n_u
            ser = err.sum() / max(m.sum(), 1)
            return float((1 - ser) ** Lg), (1 - ser_u) ** Lg

        f_nn = vpass(idx_nn)
        refs_v = [vpass(i) for i in refs]
        f_ref = max(refs_v, key=lambda x: x[0])
        pu_ref = np.max(np.stack([x[1] for x in refs_v]), axis=0)
        return f_nn, (f_ref[0], pu_ref), float(ok.mean())

    def _verified_residual(self, framer, y_d, H, refs):
        """Mean squared residual of the linear model on the symbol slots whose decisions are verified
        for every user (abstain v3); None when fewer than 5% of the slots are verified."""
        from ..gates.physics import model_residual
        sym, ok = self._ref_symbols(framer, refs)
        slots = np.repeat(ok, framer.framer.L, axis=0).all(axis=1)
        frac = float(slots.mean())
        if frac < 0.05:
            return None, frac
        return model_residual(y_d[slots], sym[slots], H, self.mod), frac

    def _abstain_ratio(self, t: float, ema: float = 0.9):
        """H3, second and third versions. t = log(data residual of the reference / noise power estimated
        on the pilots). Both follow the noise level, so t stays near its running level under SNR changes;
        with the residual of hard LMMSE decisions (second version) t also follows the reference's
        decision errors and a redraw to a worse-conditioned channel moves it, with the residual on
        CRC-verified symbols (third version) it does not. An attacker's energy on the data raises it and
        energy on the pilots lowers it. Abstain when |t - level| > z max(sd, 0.1), with level and sd
        tracked on every block that is not abstained; after `abstain_refresh` consecutive abstentions
        the level is re-based, so the state cannot lock the receiver (the first version did)."""
        st, z = self.ref_stats, self.cc.abstain_z
        if st.get("t") is None or self.block_count < 3:
            if st.get("t") is None:
                st["t"], st["t_var"] = t, 0.0
            else:
                st["t_var"] = ema * st["t_var"] + (1 - ema) * (t - st["t"]) ** 2
                st["t"] = ema * st["t"] + (1 - ema) * t
            return False, 0.0
        dev = (t - st["t"]) / max(float(np.sqrt(st["t_var"])), 0.1)
        if abs(dev) > z:
            st["n_abst"] = st.get("n_abst", 0) + 1
            if st["n_abst"] >= self.cc.abstain_refresh:   # a lasting change: re-base
                st["t"], st["t_var"], st["n_abst"] = t, 0.0, 0
            return True, float(dev)
        st["n_abst"] = 0
        st["t_var"] = ema * st["t_var"] + (1 - ema) * (t - st["t"]) ** 2
        st["t"] = ema * st["t"] + (1 - ema) * t
        return False, float(dev)

    def _update_ref_stats(self, pass_ref: Optional[float], r_mm: Optional[float], ema: float = 0.9) -> None:
        st = self.ref_stats
        for key, v in (("pass", pass_ref), ("res", r_mm)):
            if v is None:
                continue
            if st[key] is None:
                st[key], st[key + "_var"] = v, 0.0
            else:
                st[key + "_var"] = ema * st[key + "_var"] + (1 - ema) * (v - st[key]) ** 2
                st[key] = ema * st[key] + (1 - ema) * v

    def process_block(self, b, y_p, idx_p, y_d, aux=None) -> BlockOutput:
        from ..gates.physics import model_residual
        aux = aux or {}
        cc = self.cc
        framer = aux.get("framer")
        has_crc = framer is not None and framer.framer.enabled
        yf_p, it_p, yf_d = self.to_feat(y_p), self.to_idx(idx_p), self.to_feat(y_d)
        stats: Dict[str, Any] = {}

        # 0. H1: the fast level starts every block from the anchor (so its state carries no memory)
        if cc.fast_init == "anchor" and self.K > 1:
            self.params = dict(self.params)
            self.params.update(clone_params(self._anchor()))

        # 1. surprise and self-generated learning rate
        S = self._surprise(yf_p, it_p)
        r = self._surprise_ratio(S)
        eta = self.eta_max * (2 * r / (1 + r)) if self.use_surprise else self.eta_max
        stats.update(surprise=S, surprise_ratio=r, eta=eta)

        # model-based reference and anchor detections (also used before adaptation by H2)
        need_ref = bool(self.gate.gates) or cc.crc_select or self.cfg.receiver.dd_weight > 0 or cc.streak_k > 0
        H = nv = idx_mm = probs_slow = idx_slow = fused = None
        if need_ref:
            s_p = self.mod.modulate_indices(idx_p)
            H_ls = ls_channel_estimate(y_p, s_p, self.noise_var)
            nv = estimate_noise_var(y_p, s_p, H_ls)
            fused = self.tracker.fuse(H_ls, nv, y_p.shape[0], accept=False)
            H = fused["H"]
            idx_mm = hard_from_probs(lmmse_soft_symbols(y_d, H, nv, self.mod))
            if self.K > 1:
                p_slow = dict(self.params)
                p_slow.update(self._anchor())
                with torch.no_grad():
                    probs_slow = self.core.detect(p_slow, yf_d)
                idx_slow = self.hard(probs_slow)

        # 2. fast update (H2: pilots plus CRC-verified data symbols)
        before = clone_params(self.params)
        yf_tr, it_tr, sw = yf_p, it_p, None
        if self.cfg.receiver.dd_weight > 0 and has_crc:
            with torch.no_grad():
                cand = [self.hard(self.core.detect(self.params, yf_d))] + [c for c in (idx_slow, idx_mm) if c is not None]
            ver = self.verified_data(yf_d, framer, cand, self.cfg.receiver.dd_max_symbols)
            if ver is not None:
                yv, iv = ver
                n_p, n_v = yf_p.shape[0], yv.shape[0]
                yf_tr, it_tr = torch.cat([yf_p, yv]), torch.cat([it_p, iv])
                sw = torch.cat([torch.full((n_p,), 1.0 / n_p), torch.full((n_v,), self.cfg.receiver.dd_weight / n_v)]).to(yf_p.device)
                stats["dd_symbols"] = int(n_v)
        self.params = self._fast_update(yf_tr, it_tr, eta, sample_w=sw)
        stats["fast_step_norm"] = param_dist(self.params, before, self.A)
        with torch.no_grad():
            stats["pilot_loss_post"] = float(self.core.detect_loss(self.params, yf_p, it_p).item())

        # 3. detect data with the fast level
        probs = self.detect(yf_d)
        idx_hat = self.hard(probs)

        # 4. gates (all statistics relative to the model-based reference on the same block)
        gamma, abstain, reject = 1.0, False, False
        if self.gate.gates:
            g1 = g1_residual(y_d, idx_hat, idx_mm, H, self.mod, idx_slow) if "g1" in self.gate.gates else None
            pass_nn = pass_mm = None
            ok_nn = ok_mm = ok_slow = None
            pu_nn = pu_ref = None                       # per-user pass rates for H7
            coded = has_crc and hasattr(framer.framer, "decode")
            if "g2" in self.gate.gates and has_crc:
                ok_nn, ok_mm = self._crc_pass(framer, idx_hat), self._crc_pass(framer, idx_mm)
                pass_nn, pass_mm = float(ok_nn.mean()), float(ok_mm.mean())
                stats["pass_lmmse"] = pass_mm
                if self.gate.g2_relative is not None:
                    self.gate.g2_relative["n"] = int(ok_nn.size)
                if idx_slow is not None:
                    ok_slow = self._crc_pass(framer, idx_slow)
                    stats["pass_slow"] = float(ok_slow.mean())
                    pass_mm = max(pass_mm, float(ok_slow.mean()))
                pu_nn = ok_nn.mean(axis=0)
                pu_ref = np.maximum(ok_mm.mean(axis=0), ok_slow.mean(axis=0) if ok_slow is not None else 0.0)
                if coded:
                    v = self._coded_virtual_pass(framer, idx_hat, [c for c in (idx_mm, idx_slow) if c is not None])
                    if v is not None:   # LDPC: raw SER on decoder-verified symbols as a virtual CRC-sub-block pass rate
                        (pass_nn, pu_nn), (pass_mm, pu_ref), n_ver = v
                        stats.update(vpass_nn=pass_nn, vpass_ref=pass_mm, verified_frac=n_ver)
            innov = fused["innov_norm"] if "g3" in self.gate.gates else None
            r_mm = model_residual(y_d, idx_mm, H, self.mod) if cc.abstain else None
            if cc.abstain and cc.abstain_mode == "verified" and nv is not None and has_crc:
                # abstain v3: the residual of the reference on symbols whose decisions are verified by the
                # CRC (decision errors excluded), over the noise power estimated on the pilots
                r_v, frac = self._verified_residual(framer, y_d, H, [c for c in (idx_mm, idx_slow) if c is not None])
                t = float(np.log(max(r_v if r_v is not None else r_mm, 1e-12) / max(float(nv), 1e-12)))
                abstain, dev = self._abstain_ratio(t)
                stats["abstain_t"], stats["abstain_dev"], stats["abstain_verified"] = t, dev, frac
            elif cc.abstain and cc.abstain_mode == "ratio" and r_mm is not None and nv is not None:
                # data residual of the reference over the pilot-estimated noise power: both follow the
                # noise and the fading, an attacker's energy on the data or on the pilots moves one of them
                t = float(np.log(max(r_mm, 1e-12) / max(float(nv), 1e-12)))
                abstain, dev = self._abstain_ratio(t)
                stats["abstain_t"], stats["abstain_dev"] = t, dev
            elif cc.abstain and self.gate.n_accepted >= 3:
                abstain = self._abstain_check(pass_mm, r_mm, ok_nn.size if ok_nn is not None else 1)
            g2_block = None if cc.per_user_gate else pass_nn
            verdict = self.gate.evaluate(g1, g2_block, pass_mm if g2_block is not None else None, innov, r)
            gamma = verdict.gamma
            if cc.per_user_gate and pu_nn is not None:
                v_u = self.gate.g2_user_verdicts(pu_nn, pu_ref, ok_nn.shape[0], r)
                stats["verdict_g2_user"] = [float(v) for v in v_u]
            if abstain:
                gamma, reject = 0.0, True
                stats["abstain"] = True
            else:
                accepted = self.gate.update_clean(verdict, g1, pass_nn, pass_mm)
                if accepted:  # a rejected block must not raise the reference it is tested against
                    self.tracker.commit(fused["innov"])
                    if cc.abstain_mode != "ratio":
                        self._update_ref_stats(pass_mm, r_mm)
            reject = reject or gamma < 0.5
            stats.update({f"gate_{k}": v for k, v in verdict.stats.items()})
            stats.update({f"verdict_{k}": v for k, v in verdict.verdicts.items()})
            stats.update(pass_nn=pass_nn, pass_mm=pass_mm, innov_norm=fused["innov_norm"])
            # 4b. a rejected block: the fast update is not trusted. Discard it (revert / snap to the
            #     slow projection) and, if enabled, detect the data with the slow projection instead.
            if reject and self.K > 1:
                anchor = self._anchor()
                if self.reject_action == "revert":
                    self.params = before
                elif self.reject_action == "anchor":
                    self.params = dict(self.params)
                    self.params.update(anchor)
                if self.fallback and probs_slow is not None:
                    probs, idx_hat = probs_slow, idx_slow
                    stats["fallback"] = True
            elif reject and self.K == 1:
                # single level: the only uncorrupted state is the last accepted one (rollback)
                if self.reject_action != "keep":
                    self.params = before
                if self.fallback:
                    with torch.no_grad():
                        probs = self.core.detect(before, yf_d)
                    idx_hat = self.hard(probs)
                    stats["fallback"] = True
            elif cc.per_user_gate and "verdict_g2_user" in stats:
                bad = np.where(np.array(stats["verdict_g2_user"]) < 0.5)[0]
                if bad.size:   # H7: only the users whose CRC test fails revert and fall back
                    self._revert_users(before, bad)
                    fb = idx_slow if idx_slow is not None else self.hard(self.core.detect(before, yf_d))
                    idx_hat = idx_hat.copy()
                    idx_hat[:, bad] = fb[:, bad]
                    stats["users_reverted"] = [int(u) for u in bad]

            # H4: a streak of rejections is either a legitimate abrupt change or denial of adaptation.
            # Re-fit from the anchor on CRC-verified data only and accept it if it verifies better.
            self.streak = self.streak + 1 if reject else 0
            if reject and cc.streak_k > 0 and self.streak >= cc.streak_k and has_crc and self.K > 1:
                cand = [c for c in (idx_hat, idx_slow, idx_mm) if c is not None]
                ver = self.verified_data(yf_d, framer, cand, max(self.cfg.receiver.dd_max_symbols, 400))
                if ver is not None:
                    yv, iv = ver
                    start = dict(self.params)
                    start.update(clone_params(self._anchor()))
                    p_rec = self._fast_update(yv, iv, self.eta_max, start=start)
                    with torch.no_grad():
                        idx_rec = self.hard(self.core.detect(p_rec, yf_d))
                    pass_rec = float(self._crc_pass(framer, idx_rec).mean())
                    stats["recovery_pass"] = pass_rec
                    if pass_rec > (pass_mm or 0.0):
                        self.params = p_rec
                        idx_hat, gamma, reject = idx_rec, 0.5, False
                        self.streak = 0
                        stats["recovered"] = True

        # H6: per sub-block CRC selection among the gate's choice, the anchor and LMMSE
        if cc.crc_select and has_crc:
            idx_hat, sel = self._crc_select(framer, [c for c in (idx_hat, idx_slow, idx_mm) if c is not None])
            stats.update(sel)
        stats["gamma"] = gamma

        # 5. store the gated state and consolidate / re-anchor (an abstained block is not stored)
        if self.K > 1 and not abstain:
            self.buf[0].append((gamma, clone_params(self.params)))
            stats.update(self._consolidate(b))
        elif self.K > 1:
            stats.update(self._consolidate(b))
        self.levels[0] = clone_params(self.params)
        for k in range(self.K):
            stats[f"level{k + 1}_disp"] = param_dist(self.levels[k], self.level_init[k], self.A)
        if self.K > 1:
            stats["fast_to_slow"] = param_dist(self.levels[0], self.levels[1], self.A)
        self.block_count += 1
        return BlockOutput(probs_data=probs, idx_hat=idx_hat, stats=stats)

    def level_snapshot(self, k: int) -> Dict[str, np.ndarray]:
        return {key: self.levels[k][key].detach().cpu().numpy() for key in self.A}

    def attack_surface(self) -> Dict[str, Any]:
        d = super().attack_surface()
        d.update({"keys": self.A, "lr": self.eta_max, "gate": self.gate, "noise_var": self.noise_var})
        return d
