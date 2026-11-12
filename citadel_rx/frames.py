"""Block / frame generation: pilots + CRC-framed data for every user."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .coding import CRCFramer
from .config import Config
from .modulation import Modulation


@dataclass
class Block:
    index: int
    pilot_bits: np.ndarray     # (n_user, pilot_bits)
    data_bits: np.ndarray      # (n_user, n_sub * sub_bits)   (includes CRC bits)
    s_pilot: np.ndarray        # (n_p, n_user) constellation points
    s_data: np.ndarray         # (n_d, n_user)
    idx_pilot: np.ndarray      # (n_p, n_user) symbol indices
    idx_data: np.ndarray       # (n_d, n_user)


class FrameGenerator:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.mod = Modulation(cfg.frame.modulation)
        if getattr(cfg.frame, "coding", "crc") == "ldpc":
            from .coding.ldpc import LDPCFramer
            self.framer = LDPCFramer(cfg.frame.ldpc_k, cfg.frame.ldpc_n, self.mod.bits_per_symbol,
                                     scramble=getattr(cfg.frame, "ldpc_scramble", False))
        else:
            self.framer = CRCFramer(cfg.frame.crc_bits, cfg.frame.crc_subblock_symbols, self.mod.bits_per_symbol)
        self.n_user = cfg.channel.n_user
        self.n_sub = self.framer.n_subblocks(cfg.frame.data_bits)
        if self.n_sub == 0:
            raise ValueError("data_bits smaller than one CRC sub-block")
        self.rng = np.random.default_rng(cfg.channel.seed + 7)

    @property
    def n_pilot_symbols(self) -> int:
        return self.cfg.frame.pilot_bits // self.mod.bits_per_symbol

    @property
    def n_data_symbols(self) -> int:
        return self.n_sub * self.framer.L

    def make(self, b: int) -> Block:
        pilot_bits = self.rng.integers(0, 2, size=(self.n_user, self.cfg.frame.pilot_bits))
        payload = self.rng.integers(0, 2, size=(self.n_sub, self.n_user, self.framer.payload_bits))
        framed = self.framer.frame(payload)                                # (n_sub, n_user, sub_bits)
        data_bits = framed.transpose(1, 0, 2).reshape(self.n_user, -1)    # (n_user, n_d * bps)
        if hasattr(self.framer, "scramble"):                               # NR data scrambling (LDPC only)
            data_bits = self.framer.scramble(data_bits)
        idx_p = self.mod.bits_to_indices(pilot_bits).T                     # (n_p, n_user)
        idx_d = self.mod.bits_to_indices(data_bits).T                      # (n_d, n_user)
        return Block(
            index=b,
            pilot_bits=pilot_bits,
            data_bits=data_bits,
            s_pilot=self.mod.modulate_indices(idx_p),
            s_data=self.mod.modulate_indices(idx_d),
            idx_pilot=idx_p,
            idx_data=idx_d,
        )

    def decided_bits_to_subblocks(self, idx_hat: np.ndarray) -> np.ndarray:
        """idx_hat: (n_d, n_user) -> bits (n_sub, n_user, sub_bits) for CRC checking."""
        bits = self.mod.indices_to_bits(idx_hat.T)                          # (n_user, n_d*bps)
        if hasattr(self.framer, "scramble"):                               # descramble (LDPC only)
            bits = self.framer.scramble(bits)
        return bits.reshape(self.n_user, self.n_sub, self.framer.sub_bits).transpose(1, 0, 2)
