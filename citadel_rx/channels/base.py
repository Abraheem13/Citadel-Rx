"""Block-fading uplink MIMO channel models.

System model (proposal §2.3.1):  y_b[n] = H_b s_b[n] + q_b(.) + n_b[n],
H_b ∈ R^{N_r x U} (real-valued magnitudes as in the reference code; complex
QPSK symbols pass through a real gain matrix, which is exactly the reference
DeepSIC setting), q_b = tanh(0.5 .) when ``linear`` is False.

Fading modes
------------
cosine : the reference deterministic per-user fading, periods (51,39,33,21)
         blocks, depth 0.8..1.0 (exactly `SEDChannel._add_fading`).
jakes  : AR(1) Gauss-Markov block correlation  H_{b+1} = rho H_b + sqrt(1-rho^2) W_b
         around the SED mean, rho = J0(2 pi f_D T_b).
static : no variation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.special import j0

from ..config import ChannelConfig

_SED_FADE_PERIODS = np.array([51, 39, 33, 21])
_SED_FADE_DEPTH = 0.8
_COST_SCALING = 0.25
_COST_FRAMES = 25
_COST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "resources", "cost2100_channel")


@dataclass
class ChannelState:
    H: np.ndarray            # (n_ant, n_user)
    noise_var: float         # per real dimension total (reference convention)
    rho: float               # block-to-block correlation (prior for G3)
    G: Optional[np.ndarray] = None   # (n_ant, 1) attacker channel of the block (UMi scene, audit D3)


class BlockFadingChannel:
    def __init__(self, cfg: ChannelConfig, is_complex: bool, cost_dir: Optional[str] = None):
        self.cfg = cfg
        self.n_user = cfg.n_user
        self.n_ant = cfg.n_ant
        self.is_complex = is_complex
        self.rng = np.random.default_rng(cfg.seed + 1000)
        self.cost_dir = cost_dir or _COST_DIR
        self._H_prev: Optional[np.ndarray] = None
        self._abrupt_H: Optional[np.ndarray] = None
        self.H_mean = self._sed_mean()
        self.rho = 1.0
        if cfg.fading in ("jakes", "complex_gm"):
            self.rho = float(j0(2 * np.pi * cfg.jakes_fd_tb))
        # complex_gm draws from its own generator, so the noise stream of self.rng is that of the other modes
        self.h_rng = np.random.default_rng(cfg.seed + 2000)
        self._los: Optional[np.ndarray] = None
        self._G: Optional[np.ndarray] = None

    # ---- channel matrices --------------------------------------------
    def _sed_mean(self) -> np.ndarray:
        rows = np.arange(self.n_ant)[:, None] * (self.n_user / self.n_ant if getattr(self.cfg, "sed_stretch", False) else 1.0)
        cols = np.arange(self.n_user)[None, :]
        return np.exp(-np.abs(rows - cols)).astype(np.float64)

    def _synthetic(self, b: int) -> np.ndarray:
        H = self.H_mean.copy()
        mode = self.cfg.fading
        if mode == "cosine":
            # reference periods for the first four users; further users (8x8) get co-prime periods
            periods = np.concatenate([_SED_FADE_PERIODS, np.array([47, 29, 43, 23, 37, 19, 41, 17])])[: self.n_user]
            fade = _SED_FADE_DEPTH + (1 - _SED_FADE_DEPTH) * np.cos(2 * np.pi * b / periods)
            H = H * fade[None, :]
        elif mode == "jakes":
            if self._H_prev is None:
                dev = self.rng.standard_normal(H.shape) * 0.1
            else:
                dev = self.rho * (self._H_prev - self.H_mean) + np.sqrt(1 - self.rho ** 2) * 0.1 * self.rng.standard_normal(H.shape)
            H = self.H_mean + dev
        elif mode == "complex_gm":
            if not self.is_complex:
                raise ValueError("fading=complex_gm needs a complex modulation")
            if self._los is None:   # per-seed line-of-sight phases
                self._los = self.H_mean * np.exp(2j * np.pi * self.h_rng.random(H.shape))
            W = self.H_mean * (self.h_rng.standard_normal(H.shape) + 1j * self.h_rng.standard_normal(H.shape)) / np.sqrt(2)
            self._G = W if self._G is None else self.rho * self._G + np.sqrt(1 - self.rho ** 2) * W
            K = float(self.cfg.rician_k)
            H = np.sqrt(K / (K + 1)) * self._los + np.sqrt(1 / (K + 1)) * self._G
        elif mode == "static":
            pass
        else:
            raise ValueError(f"unknown fading mode {mode}")
        self._H_prev = H
        return H

    def _cost2100(self, b: int) -> np.ndarray:
        # Reference convention: y = h @ s with h rows taken from h_i.mat, i.e. row i is the gain
        # vector seen at receive antenna i across users; diagonal pinned to 1, off-diagonal x0.25.
        import scipy.io
        H = np.empty((self.n_ant, self.n_user))
        folder = 1 + (b // _COST_FRAMES)
        folder = ((folder - 1) % 8) + 1  # 8 folders x 25 frames = 200 distinct blocks, then wrap
        for i in range(1, self.n_ant + 1):
            path = os.path.join(self.cost_dir, f"{folder}", f"h_{i}.mat")
            h_row = scipy.io.loadmat(path)["norm_channel"][b % _COST_FRAMES, : self.n_user]
            H[i - 1] = _COST_SCALING * h_row
        d = min(self.n_user, self.n_ant)
        H[np.arange(d), np.arange(d)] = 1.0
        self._H_prev = H
        return H

    def _umi(self, b: int):
        if not hasattr(self, "_umi_data"):
            fn = os.path.join(os.path.dirname(self.cost_dir), "umi", f"umi_N{self.n_ant}_U{self.n_user}_s{self.cfg.seed}.npz")
            if not os.path.exists(fn):
                raise FileNotFoundError(f"{fn}: run scripts/make_umi_channels.py first")
            z = np.load(fn)
            self._umi_data = z["H"]
            self._umi_att = {k[3:]: z[k] for k in z.files if k.startswith("G_d")}      # distance -> (T, N, 1)
            self._umi_sir = {k[5:]: float(z[k]) for k in z.files if k.startswith("sir_d")}
            try:   # t_block etc.: recorded with every run (scripts/make_umi_channels.py)
                import json
                self.umi_meta = {k: v for k, v in json.loads(str(z["meta"])).items() if k in ("t_block", "fc", "speed_kmh", "target_db")}
            except Exception:
                self.umi_meta = {}
        H = self._umi_data
        if b >= H.shape[0]:
            raise ValueError("more blocks than the UMi drop holds")
        return H[b], None

    def umi_attacker(self, dist: float):
        """(per-block attacker channels (T, N, 1), geometric SIR in dB, rms norm of G) at this distance."""
        if not hasattr(self, "_umi_att"):
            self._umi(0)
        key = f"{dist:g}"
        if key not in self._umi_att:
            raise ValueError(f"no attacker at {dist:g} m in this drop (have {sorted(self._umi_att)})")
        G = self._umi_att[key]
        return G, self._umi_sir[key], float(np.sqrt(np.mean(np.sum(np.abs(G) ** 2, axis=(1, 2)))))

    def state(self, b: int) -> ChannelState:
        G = None
        ab = getattr(self.cfg, "abrupt_block", -1)
        if (self.cfg.fading == "complex_gm" and self.cfg.abrupt_type == "redraw" and ab is not None and ab >= 0
                and b >= ab and self._abrupt_H is None):
            # complex_gm: a redraw is a new drop of the same family (new line-of-sight phases, new scattering)
            arng = np.random.default_rng(self.cfg.seed + 5150)
            self._los = self.H_mean * np.exp(2j * np.pi * arng.random(self.H_mean.shape))
            self._G = None
            self._abrupt_H = self._los
        if self.cfg.model == "synthetic":
            H = self._synthetic(b)
        elif self.cfg.model == "umi":
            H, G = self._umi(b)
        elif self.cfg.model == "cost2100":
            H = self._cost2100(b)
        else:
            raise ValueError(f"unknown channel model {self.cfg.model}")
        snr = self.cfg.snr_db
        if ab is not None and ab >= 0 and b >= ab:
            # audit D6/B3: an abrupt change the receiver must follow (with no attack present)
            if self.cfg.abrupt_type == "redraw" and self.cfg.fading == "complex_gm":
                pass                                     # drawn above, inside the channel process
            elif self.cfg.abrupt_type == "redraw":
                if self._abrupt_H is None:
                    arng = np.random.default_rng(self.cfg.seed + 5150)
                    self._abrupt_H = self.H_mean * (0.5 + arng.random(self.H_mean.shape))
                H = H + (self._abrupt_H - self.H_mean)
            elif self.cfg.abrupt_type == "snr_drop":
                snr = snr - self.cfg.abrupt_snr_drop_db
        noise_var = 10 ** (-0.1 * snr)
        return ChannelState(H=H, noise_var=noise_var, rho=self.rho, G=G)

    # ---- transmission -------------------------------------------------
    def transmit(self, s: np.ndarray, st: ChannelState, rng: Optional[np.random.Generator] = None) -> np.ndarray:
        """s: (n_sym, n_user) complex or real -> y: (n_sym, n_ant)."""
        rng = rng or self.rng
        conv = s @ st.H.T
        var = st.noise_var
        if self.is_complex:
            w = np.sqrt(var) / 2 * (rng.standard_normal(conv.shape) + 1j * rng.standard_normal(conv.shape))
        else:
            w = np.sqrt(var) * rng.standard_normal(conv.shape)
        y = conv + w
        if not self.cfg.linear:
            y = np.tanh(0.5 * y)
        return y

    def apply_nonlinearity(self, y_lin: np.ndarray) -> np.ndarray:
        return y_lin if self.cfg.linear else np.tanh(0.5 * y_lin)

    # ---- v3 receiver front-end ------------------------------------------
    @property
    def has_frontend(self) -> bool:
        c = self.cfg
        return bool(getattr(c, "iq_eps", 0) or getattr(c, "iq_phi_deg", 0) or getattr(c, "pa_sat", 0) or getattr(c, "adc_bits", 0))

    def frontend(self, y: np.ndarray, st: ChannelState) -> np.ndarray:
        """IQ imbalance -> LNA saturation (Rapp) -> uniform ADC, applied to what reaches the antennas (users'
        signals, noise and any attack). AGC: the level is the block's mean received power per antenna,
        P = mean_n sum_u |H_nu|^2 + E|w|^2, so pilots and data of a block see the same gain. Identity when
        no impairment is configured."""
        if not self.has_frontend:
            return y
        c = self.cfg
        cplx = np.iscomplexobj(y)
        P = float(np.mean(np.sum(np.abs(st.H) ** 2, axis=1))) + (st.noise_var / 2 if cplx else st.noise_var)
        rms = np.sqrt(P)
        if cplx and (c.iq_eps or c.iq_phi_deg):
            g, ph = 1.0 + c.iq_eps, np.deg2rad(c.iq_phi_deg)
            k1, k2 = (1 + g * np.exp(-1j * ph)) / 2, (1 - g * np.exp(1j * ph)) / 2
            y = k1 * y + k2 * np.conj(y)
        if c.pa_sat > 0:
            A, p = c.pa_sat * rms, c.pa_p
            r = np.abs(y)
            gain = 1.0 / (1.0 + (r / A) ** (2 * p)) ** (1.0 / (2 * p))
            y = y * gain
        if c.adc_bits > 0:
            levels = 2 ** int(c.adc_bits)
            clip = c.adc_clip * (rms / np.sqrt(2) if cplx else rms)
            step = 2 * clip / levels

            def q(x):
                return (np.clip(np.floor(x / step), -levels // 2, levels // 2 - 1) + 0.5) * step
            y = q(y.real) + 1j * q(y.imag) if cplx else q(y)
        return y


def make_channel(cfg: ChannelConfig, is_complex: bool) -> BlockFadingChannel:
    return BlockFadingChannel(cfg, is_complex)
