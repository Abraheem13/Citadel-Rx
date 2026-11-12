"""CRC framing of the data part of a block.

The data bits of each user are cut into sub-blocks of ``L`` symbols; the last
``r`` bits of every sub-block are a CRC over the preceding payload bits. The
receiver re-computes the CRC on its hard decisions, so the fraction of passing
sub-blocks is a label-free statistic that is a smooth function of the
post-adaptation SER (Proposition 2.3 in the proposal):

    P(pass | SER p, L symbols) ≈ (1 - p)^L + 2^{-r} (1 - (1-p)^L).

Polynomials follow the 3GPP conventions where a matching length exists.
"""
from __future__ import annotations

import numpy as np

_POLY = {
    8: 0x9B,       # gCRC8 of 3GPP TS 36.212 (LTE) Sec. 5.1.1: x^8+x^7+x^4+x^3+x+1
    11: 0x621,     # 3GPP CRC-11
    16: 0x1021,    # 3GPP CRC-16
    24: 0x864CFB,  # 3GPP CRC-24A
}


class CRC:
    def __init__(self, n_bits: int):
        if n_bits not in _POLY:
            raise ValueError(f"no polynomial for CRC-{n_bits}")
        self.r = n_bits
        self.poly = _POLY[n_bits]
        self._table = self._build_table()

    def _build_table(self) -> np.ndarray:
        # bit-serial table over 8-bit chunks
        tbl = np.zeros(256, dtype=np.uint64)
        top = 1 << (self.r - 1)
        mask = (1 << self.r) - 1
        for i in range(256):
            c = i << (self.r - 8) if self.r >= 8 else i
            for _ in range(8):
                if c & top:
                    c = ((c << 1) ^ self.poly) & mask
                else:
                    c = (c << 1) & mask
            tbl[i] = c
        return tbl

    def compute(self, bits: np.ndarray) -> np.ndarray:
        """bits: (..., n) 0/1 -> crc bits (..., r), MSB first."""
        bits = np.asarray(bits, dtype=np.int64)
        lead = bits.shape[:-1]
        flat = bits.reshape(-1, bits.shape[-1])
        out = np.zeros((flat.shape[0], self.r), dtype=np.int64)
        mask = (1 << self.r) - 1
        top = 1 << (self.r - 1)
        for row in range(flat.shape[0]):
            c = 0
            for b in flat[row]:
                if ((c & top) != 0) != (b == 1):
                    c = ((c << 1) ^ self.poly) & mask
                else:
                    c = (c << 1) & mask
            for k in range(self.r):
                out[row, k] = (c >> (self.r - 1 - k)) & 1
        return out.reshape(*lead, self.r)

    def check(self, bits_with_crc: np.ndarray) -> np.ndarray:
        """Return boolean pass array over the leading dims."""
        payload = bits_with_crc[..., : -self.r]
        crc = bits_with_crc[..., -self.r:]
        return np.all(self.compute(payload) == crc, axis=-1)


class CRCFramer:
    """Insert CRCs into a per-user data bit stream and verify decisions."""

    def __init__(self, crc_bits: int, subblock_symbols: int, bits_per_symbol: int):
        self.enabled = crc_bits > 0
        self.r = crc_bits
        self.L = subblock_symbols
        self.bps = bits_per_symbol
        self.sub_bits = self.L * self.bps
        if self.enabled:
            if self.r >= self.sub_bits:
                raise ValueError("CRC longer than sub-block")
            self.crc = CRC(crc_bits)
        self.payload_bits = self.sub_bits - (self.r if self.enabled else 0)

    def frame(self, payload: np.ndarray) -> np.ndarray:
        """payload: (n_sub, n_user, payload_bits) -> (n_sub, n_user, sub_bits)."""
        if not self.enabled:
            return payload
        crc = self.crc.compute(payload)
        return np.concatenate([payload, crc], axis=-1)

    def n_subblocks(self, data_bits: int) -> int:
        return data_bits // self.sub_bits

    def check(self, decided_bits: np.ndarray) -> np.ndarray:
        """decided_bits: (n_sub, n_user, sub_bits) -> pass (n_sub, n_user)."""
        if not self.enabled:
            raise RuntimeError("CRC framing disabled")
        return self.crc.check(decided_bits)

    @staticmethod
    def theoretical_pass_rate(ser: float, L: int, r: int) -> float:
        q = (1.0 - ser) ** L
        return q + (2.0 ** (-r)) * (1.0 - q)
