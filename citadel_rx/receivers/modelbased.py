"""Model-based detectors and a model-based pilot-poisoning defense (v3, roadmap Phase 1d/1e).

receiver.type = "model" selects

  receiver.detector  lmmse     linear MMSE equalisation, nearest point (as receivers/lmmse.py)
                     ml        exhaustive maximum likelihood over all order^U symbol vectors
                     kbest     K-best breadth-first tree search on the QR decomposition (K = kbest_k)
                     mmse_sic  ordered MMSE successive interference cancellation (V-BLAST order:
                               highest post-MMSE SINR first)
  receiver.csi       ls        regularised least squares from the (possibly poisoned) pilots
                     perfect   the true channel and noise power of the block (a genie bound; a pilot
                               attack cannot reach it)
  receiver.guard     True      pilot-domain test with fallback (below)

Guard. The pilots give the LS estimate H_ls and the residual noise power
    s2_b = ||Y_p - S_p H_ls^T||_F^2 / (N (N_p - U)),
an unbiased estimate of the per-entry noise power. Two statistics are tested against references that
change only on accepted blocks:
    noise inflation   s2_b / s2_ref  >  chi2_{q}(d) / d,   d = N (N_p - U) (x2 for complex),
    innovation        ||H_ls - H_acc||_F^2 / max(I_ref, expected) > guard_innov_tau,
with s2_ref initialised from the nominal noise power of the configured SNR (not from the first,
possibly poisoned, block) and I_ref the running innovation level (expected = estimation noise
d_H s2_ref / N_p). A perturbation outside the column space of S_p inflates s2; one inside it (a
channel spoof S_p Delta^T) moves H_ls and shows in the innovation. On rejection the block is detected
with the last accepted estimate H_acc, and per (sub-block, user) the first CRC-passing of the
decisions with H_acc and with H_ls is kept (H_ls first when accepted). After guard_refresh
consecutive rejections the references are re-based on the current block, so a lasting legitimate
change cannot lock the receiver.
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch
from scipy.stats import chi2

from ..config import Config
from .base import BlockOutput, Receiver
from .lmmse import hard_from_probs, lmmse_soft_symbols, ls_channel_estimate


# --------------------------------------------------------------------------------------- detectors
def _nearest(x: np.ndarray, const: np.ndarray) -> np.ndarray:
    return np.argmin(np.abs(x[..., None] - const) ** 2, axis=-1)


def detect_lmmse(y: np.ndarray, H: np.ndarray, nv: float, mod) -> np.ndarray:
    return hard_from_probs(lmmse_soft_symbols(y, H, nv, mod))


def detect_ml(y: np.ndarray, H: np.ndarray, mod, chunk: int = 1024) -> np.ndarray:
    U, order = H.shape[1], mod.order
    hyp = np.array(list(itertools.product(range(order), repeat=U)))           # (order^U, U)
    Y0 = mod.modulate_indices(hyp) @ H.T                                       # (order^U, N)
    out = np.empty((y.shape[0], U), dtype=np.int64)
    step = max(1, int(chunk * 256 / len(hyp)))
    for a in range(0, y.shape[0], step):
        d = (np.abs(y[a:a + step, None, :] - Y0[None]) ** 2).sum(axis=2)
        out[a:a + step] = hyp[np.argmin(d, axis=1)]
    return out


def detect_kbest(y: np.ndarray, H: np.ndarray, mod, K: int = 16) -> np.ndarray:
    """K-best on y = H s + w: H = QR (N >= U), z = Q^H y, layers searched from the last user to the first;
    at every layer each survivor is extended by every constellation point and the K smallest partial
    metrics ||z_i - sum_{j>=i} R_ij s_j||^2 are kept."""
    N, U = H.shape
    if N < U:
        raise ValueError("K-best needs at least as many antennas as users")
    Q, R = np.linalg.qr(H.astype(complex))                                     # Q (N, U), R (U, U)
    z = y.astype(complex) @ Q.conj()                                           # (n, U) = (Q^H y)^T
    const = mod.constellation().astype(complex)
    M, n = const.size, y.shape[0]
    surv = np.zeros((n, 1, U), dtype=np.int64)                                 # symbol indices, layers > i filled
    metric = np.zeros((n, 1))
    for i in range(U - 1, -1, -1):
        s_sel = const[surv[:, :, i + 1:]] if i + 1 < U else np.zeros((n, surv.shape[1], 0))
        interf = (s_sel * R[i, i + 1:][None, None, :]).sum(axis=2)            # (n, k)
        cand = np.abs(z[:, i, None, None] - interf[:, :, None] - R[i, i] * const[None, None, :]) ** 2  # (n, k, M)
        tot = (metric[:, :, None] + cand).reshape(n, -1)                       # (n, k*M)
        k = surv.shape[1]
        keep = min(K, k * M)
        sel = np.argpartition(tot, keep - 1, axis=1)[:, :keep] if keep < k * M else np.tile(np.arange(k * M), (n, 1))
        parent, sym = sel // M, sel % M
        surv = np.take_along_axis(surv, parent[:, :, None], axis=1).copy()
        surv[:, :, i] = sym
        metric = np.take_along_axis(tot, sel, axis=1)
    best = np.argmin(metric, axis=1)
    return surv[np.arange(n), best]


def detect_mmse_sic(y: np.ndarray, H: np.ndarray, nv: float, mod) -> np.ndarray:
    """Ordered MMSE-SIC: detect the user with the highest post-MMSE SINR, cancel it, repeat."""
    N, U = H.shape
    const = mod.constellation().astype(complex)
    left = list(range(U))
    r = y.astype(complex).copy()
    out = np.empty((y.shape[0], U), dtype=np.int64)
    while left:
        Hl = H[:, left].astype(complex)
        G = Hl.conj().T @ Hl + nv * np.eye(len(left))
        Ginv = np.linalg.inv(G)
        W = Ginv @ Hl.conj().T                                                  # (u, N)
        sinr = 1.0 / np.maximum(np.real(np.diag(Ginv)) * nv, 1e-12) - 1.0
        k = int(np.argmax(sinr))
        u = left[k]
        mu = np.real(W[k] @ Hl[:, k])
        xk = r @ W[k]                                                           # (n,)
        idx = _nearest(xk / max(mu, 1e-9), const)
        out[:, u] = idx
        r = r - np.outer(const[idx], H[:, u])
        left.pop(k)
    return out


def detect(kind: str, y: np.ndarray, H: np.ndarray, nv: float, mod, K: int) -> np.ndarray:
    if kind == "lmmse":
        return detect_lmmse(y, H, nv, mod)
    if kind == "ml":
        return detect_ml(y, H, mod)
    if kind == "kbest":
        return detect_kbest(y, H, mod, K)
    if kind == "mmse_sic":
        return detect_mmse_sic(y, H, nv, mod)
    raise ValueError(f"unknown detector {kind}")


# --------------------------------------------------------------------------------------- receiver
class ModelReceiver(Receiver):
    """Model-based detector with LS or perfect CSI, optionally guarded (see the module docstring)."""

    def __init__(self, cfg: Config, device: torch.device):
        super().__init__(cfg, device)
        rc = cfg.receiver
        self.kind, self.csi, self.K = rc.detector, rc.csi, rc.kbest_k
        self.guard = rc.guard
        self.name = f"model_{rc.detector}_{rc.csi}" + ("_guard" if rc.guard else "")
        self.noise_var = 10 ** (-0.1 * cfg.channel.snr_db)          # regulariser of the LS estimate (as LMMSE)
        cplx = self.mod.is_complex
        self.nv_nominal = self.noise_var / 2 if cplx else self.noise_var   # per-entry noise power (channels/base.py)
        self.s2_ref: Optional[float] = None
        self.I_ref: Optional[float] = None
        self.H_acc: Optional[np.ndarray] = None
        self.n_rej = 0

    def pretrain(self, blocks) -> None:
        """Offline noise calibration (receiver.guard_noise_ref = calibrated): the median LS residual power, per entry,
        of the pre-training draws at the configured SNR (the nearest SNR if none matches), each estimated from as
        many symbols as a block has pilots. Model mismatch of the front-end (IQ imbalance, saturation) then belongs
        to the reference, instead of looking like an attack."""
        rc = self.cfg.receiver
        if getattr(rc, "guard_noise_ref", "nominal") != "calibrated" or not blocks:
            return
        snrs = list(rc.pretrain_snrs)
        snr_of = [float(snrs[i % len(snrs)]) for i in range(len(blocks))]
        target = min(set(snr_of), key=lambda x: abs(x - self.cfg.channel.snr_db))
        n_p, vals = self.cfg.pilot_symbols, []
        for (y, idx), snr in zip(blocks, snr_of):
            if snr != target:
                continue
            s = self.mod.modulate_indices(idx[:n_p])
            H = ls_channel_estimate(y[:n_p], s, self.noise_var)
            vals.append(float(np.sum(np.abs(y[:n_p] - s @ H.T) ** 2) / (self.n_ant * max(n_p - self.n_user, 1))))
        if vals:
            self.s2_cal = float(np.median(vals))

    def _initial_s2_ref(self) -> float:
        return float(getattr(self, "s2_cal", None) or self.nv_nominal)

    def _thresholds(self, n_p: int) -> float:
        d = self.n_ant * max(n_p - self.n_user, 1) * (2 if self.mod.is_complex else 1)
        return float(chi2.ppf(self.cfg.receiver.guard_quantile, d) / d)

    def process_block(self, b, y_p, idx_p, y_d, aux=None) -> BlockOutput:
        aux = aux or {}
        s_p = self.mod.modulate_indices(idx_p)
        stats: Dict[str, Any] = {}
        if self.csi == "perfect":
            st = aux.get("state")
            if st is None:
                raise RuntimeError("perfect CSI needs the channel state (aux['state'])")
            H, nv = st.H, (st.noise_var / 2 if self.mod.is_complex else st.noise_var)
            idx = detect(self.kind, y_d, H, nv, self.mod, self.K)
            return self._out(idx, stats)
        H_ls = ls_channel_estimate(y_p, s_p, self.noise_var)
        n_p = y_p.shape[0]
        s2 = float(np.sum(np.abs(y_p - s_p @ H_ls.T) ** 2) / (self.n_ant * max(n_p - self.n_user, 1)))
        stats["noise_hat"] = s2
        if not self.guard:
            return self._out(detect(self.kind, y_d, H_ls, s2, self.mod, self.K), stats)

        # ---- guard ----
        if self.s2_ref is None:
            self.s2_ref = self._initial_s2_ref()
        tau_s = self._thresholds(n_p)
        g_noise = s2 / max(self.s2_ref, 1e-12)
        expected = self.H_acc.size * self.s2_ref / n_p if self.H_acc is not None else 0.0
        if self.H_acc is None:
            g_innov, innov = 0.0, 0.0
        else:
            innov = float(np.sum(np.abs(H_ls - self.H_acc) ** 2))
            g_innov = innov / max(self.I_ref or 0.0, expected, 1e-12)
        accept = g_noise <= tau_s and g_innov <= self.cfg.receiver.guard_innov_tau
        rebase = False
        idx_ls = detect(self.kind, y_d, H_ls, s2, self.mod, self.K)
        idx_acc = None
        mode = getattr(self.cfg.receiver, "guard_rebase", "count")
        framer = aux.get("framer")
        if not accept:
            self.n_rej += 1
            if self.H_acc is None:
                accept, rebase = True, True          # no accepted estimate yet
            elif mode == "count" and self.n_rej >= self.cfg.receiver.guard_refresh:
                accept, rebase = True, True          # a lasting change (or a lasting attack)
            elif mode == "crc" and framer is not None and framer.framer.enabled:
                idx_acc = detect(self.kind, y_d, self.H_acc, self.s2_ref, self.mod, self.K)
                f_ls = float(framer.framer.check(framer.decided_bits_to_subblocks(idx_ls)).mean())
                f_acc = float(framer.framer.check(framer.decided_bits_to_subblocks(idx_acc)).mean())
                stats.update(guard_pass_ls=f_ls, guard_pass_acc=f_acc)
                if f_ls >= f_acc:                    # verified against the protected estimate
                    accept, rebase = True, True
        stats.update(guard_noise=g_noise, guard_noise_tau=tau_s, guard_innov=g_innov, gamma=1.0 if accept else 0.0,
                     guard_rebase=rebase)
        if accept:
            idx = idx_ls
            if self.H_acc is not None and not rebase:
                self.I_ref = innov if self.I_ref is None else 0.9 * self.I_ref + 0.1 * innov
            if rebase:
                self.I_ref = None
            self.s2_ref = s2 if rebase else 0.9 * self.s2_ref + 0.1 * s2
            self.H_acc = H_ls
            self.n_rej = 0
            cands = [idx_ls]
        else:
            idx = idx_acc if idx_acc is not None else detect(self.kind, y_d, self.H_acc, self.s2_ref, self.mod, self.K)
            cands = [idx, idx_ls]
            stats["fallback"] = True
        if framer is not None and framer.framer.enabled and len(cands) > 1:
            idx = self._crc_select(framer, cands)
        return self._out(idx, stats)

    @staticmethod
    def _crc_select(framer, cands):
        L = framer.framer.L
        out = cands[0].copy()
        done = framer.framer.check(framer.decided_bits_to_subblocks(cands[0]))
        for c in cands[1:]:
            ok = framer.framer.check(framer.decided_bits_to_subblocks(c)) & ~done
            for j, u in zip(*np.nonzero(ok)):
                out[j * L:(j + 1) * L, u] = c[j * L:(j + 1) * L, u]
            done |= ok
        return out

    def _out(self, idx: np.ndarray, stats: Dict[str, Any]) -> BlockOutput:
        probs = torch.nn.functional.one_hot(torch.as_tensor(idx, dtype=torch.long), self.mod.order).float().to(self.device)
        return BlockOutput(probs_data=probs, idx_hat=idx, stats=stats)


# --------------------------------------------------------------------------------------- Citadel-LS
class CitadelLS(ModelReceiver):
    """Multi-rate verified memory of the channel estimate for a model-based detector (v3, Phase 3).

    The learner is the per-block LS channel estimate. Its persistent memory is two slow levels of
    estimates, H2 (period C2) and H3 (period C3), updated only by consolidation:

        H_k <- H_k + Pi_kappa( eta_k * (sum gamma / |B|) * (m - H_k) ),   m = sum gamma H_f / sum gamma,

    the vote rule (rejected blocks vote for the current memory), so a block that passes the gates owns at
    most 1/|B| of a full step whatever the other verdicts, and the clip kappa = ls_clip_frac * ||H_k||
    bounds every step (design bound). Gates, all relative to the protected memory (anchor H_a = H2, or the
    last accepted estimate before the first consolidation):
      noise  s2_f / s2_ref <= chi2_q(d)/d, with s2_ref from the configured SNR, then updated only by
             consolidation (never by a single block);
      CRC    F_u(H_f) >= tau2(F_u(H_a)) * F_u(H_a) for EVERY user u: the fast estimate's decisions pass nearly as
             many of user u's CRCs as the anchor's (tau2 from the relative-slack design rule of Citadel-Rx's G2,
             rho = 1, floor 2e-3), less a 3-sigma binomial margin of the pass-rate estimate over the n_sub
             sub-blocks. Per user, because a test pooled over the users is passed by an attacker that
             concentrates its damage on one user.
    Accepted blocks detect with H_f, rejected ones with H_a, and per (sub-block, user) the first CRC-passing
    of the candidates (H_f, H_a, H3 in the accepted order, H_a first when rejected) is emitted. A legitimate
    change passes (the fresh estimate verifies better than the stale anchor) and is consolidated within C2
    blocks; a lasting attack is rejected and leaks are diluted (no single-state capture).
    """

    def __init__(self, cfg: Config, device: torch.device):
        super().__init__(cfg, device)
        cc = cfg.citadel
        self.C2, self.C3 = int(cc.periods[1]), int(cc.periods[2])
        lr = list(cc.level_lr)
        self.eta2, self.eta3 = float(lr[0]), float(lr[1])
        self.clip = float(getattr(cc, "ls_clip_frac", 0.5))
        self.rel, self.abs_min = cc.g2_rel_slack, cc.g2_abs_min_slack
        self.L = cfg.frame.crc_subblock_symbols
        self.H2 = self.H3 = None
        self.H_last: Optional[np.ndarray] = None
        self.buf2, self.buf3 = [], []
        self.name = f"citadel_ls_{self.kind}"

    def _tau2(self, F_ref: float) -> float:
        p_ref = 1.0 - float(np.clip(F_ref, 1e-9, 1.0)) ** (1.0 / self.L)
        xi = max(self.abs_min, self.rel * p_ref)
        return float(((1.0 - min(p_ref + xi, 0.999)) / max(1.0 - p_ref, 1e-9)) ** self.L)

    def _step(self, H: Optional[np.ndarray], buf, eta: float) -> Optional[np.ndarray]:
        g = np.array([x[0] for x in buf], dtype=float)
        if g.sum() <= 0:
            return H
        m = sum(gi * Hi for gi, Hi in buf) / g.sum()
        if H is None:
            return m
        inc = eta * (g.sum() / len(g)) * (m - H)
        n, cap = np.linalg.norm(inc), self.clip * np.linalg.norm(H)
        if self.clip > 0 and n > cap:
            inc = inc * (cap / n)
        return H + inc

    def process_block(self, b, y_p, idx_p, y_d, aux=None) -> BlockOutput:
        aux = aux or {}
        framer = aux.get("framer")
        s_p = self.mod.modulate_indices(idx_p)
        H_f = ls_channel_estimate(y_p, s_p, self.noise_var)
        n_p = y_p.shape[0]
        s2 = float(np.sum(np.abs(y_p - s_p @ H_f.T) ** 2) / (self.n_ant * max(n_p - self.n_user, 1)))
        if self.s2_ref is None:
            self.s2_ref = self._initial_s2_ref()
        g_noise = s2 / max(self.s2_ref, 1e-12)
        noise_ok = g_noise <= self._thresholds(n_p)
        H_a = self.H2 if self.H2 is not None else self.H_last
        idx_f = detect(self.kind, y_d, H_f, s2, self.mod, self.K)
        stats: Dict[str, Any] = {"noise_hat": s2, "guard_noise": g_noise}
        has_crc = framer is not None and framer.framer.enabled
        chk = (lambda i: framer.framer.check(framer.decided_bits_to_subblocks(i))) if has_crc else None
        if H_a is None:                     # nothing protected yet: the first estimate that passes the noise test
            accept = noise_ok
            idx_a = None
        else:
            idx_a = detect(self.kind, y_d, H_a, self.s2_ref, self.mod, self.K)
            if has_crc:
                # per user: an attacker can concentrate its damage on one user, which a pass rate pooled over the
                # users hardly sees (Phase 3 smoke run, calibration seed 0); every user must verify
                ok_f, ok_a = chk(idx_f), chk(idx_a)                                   # (n_sub, U)
                f_f, f_a = ok_f.mean(axis=0), ok_a.mean(axis=0)
                n_sub = ok_f.shape[0]
                # threshold on user u's pass rate: tau2 * F_a minus a 3-sigma binomial margin of the estimate
                thr = [self._tau2(float(f_a[u])) * float(f_a[u]) - 3.0 * np.sqrt(f_a[u] * (1 - f_a[u]) / n_sub)
                       for u in range(len(f_a))]
                margin = [float(f_f[u] - thr[u]) for u in range(len(f_a))]
                worst = int(np.argmin(margin))
                stats.update(ls_pass_f=float(f_f.mean()), ls_pass_a=float(f_a.mean()), ls_margin_min=margin[worst],
                             ls_worst_user=worst, ls_pass_f_worst=float(f_f[worst]), ls_pass_a_worst=float(f_a[worst]))
                crc_ok = all(m >= 0 for m in margin)
            else:
                crc_ok = True
            accept = noise_ok and crc_ok
        gamma = 1.0 if accept else 0.0
        stats["gamma"] = gamma
        cands = [idx_f] + ([idx_a] if idx_a is not None else [])
        if not accept and idx_a is not None:
            cands = [idx_a, idx_f]
            stats["fallback"] = True
        if self.H3 is not None and has_crc:
            cands.append(detect(self.kind, y_d, self.H3, self.s2_ref, self.mod, self.K))
        idx = self._crc_select(framer, cands) if (has_crc and len(cands) > 1) else cands[0]
        # memory: the buffer of this period, consolidation by the vote rule
        if accept:
            self.H_last = H_f
        self.buf2.append((gamma, H_f, s2))
        if (b + 1) % self.C2 == 0 and self.buf2:
            prev = self.H2
            self.H2 = self._step(self.H2, [(g, H) for g, H, _ in self.buf2], self.eta2)
            gs = np.array([g for g, _, _ in self.buf2])
            if gs.sum() > 0:   # noise reference: vote rule on the accepted blocks' noise estimates
                m_s2 = sum(g * s for g, _, s in self.buf2) / gs.sum()
                self.s2_ref = self.s2_ref + self.eta2 * (gs.sum() / len(gs)) * (m_s2 - self.s2_ref)
            if self.H2 is not None:
                self.buf3.append((float(gs.mean()), self.H2.copy()))
            stats["consolidated"] = 2
            stats["h2_step"] = float(np.linalg.norm(self.H2 - prev)) if (prev is not None and self.H2 is not None) else None
            self.buf2 = []
        if (b + 1) % self.C3 == 0 and self.buf3:
            self.H3 = self._step(self.H3, self.buf3, self.eta3)
            self.buf3 = []
        return self._out(idx, stats)
