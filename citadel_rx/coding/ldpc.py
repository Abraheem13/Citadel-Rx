"""NR channel coding of the data part (reviewer audit D2).

Every code block carries `k - 24` payload bits and a CRC-24A (3GPP TS 38.212 Sec. 5.1) and is
encoded with the 5G LDPC code (TS 38.212 Sec. 5.3.2, base graph chosen by the standard's rule, rate
matching to `n` bits) by Sionna's `LDPC5GEncoder` (Sionna PHY 2.2, PyTorch). check() decodes
hard symbol decisions (belief propagation, 20 iterations, channel LLR magnitude 3 for every bit)
and returns the CRC verdict per code block and user, in the place of the CRC-8 sub-blocks: the
receivers' gates, the CRC selection and the BLER then work on decoded code blocks.
"""
from __future__ import annotations

import numpy as np
import torch


class LDPCFramer:
    def __init__(self, k: int, n: int, bits_per_symbol: int, num_iter: int = 20, llr_mag: float = 3.0,
                 scramble: bool = False, n_id: int = 1):
        # importing Sionna seeds torch's global generator from OS entropy: keep the run's RNG state
        state = torch.get_rng_state()
        import sionna.phy
        sionna.phy.config.seed = 0
        from sionna.phy.fec.crc import CRCDecoder, CRCEncoder
        from sionna.phy.fec.ldpc import LDPC5GDecoder, LDPC5GEncoder
        torch.set_rng_state(state)
        if n % bits_per_symbol:
            raise ValueError("coded bits per code block must fill whole symbols")
        self.enabled = True
        self.r, self.k, self.n, self.bps = 24, k, n, bits_per_symbol
        self.L = n // bits_per_symbol           # symbols per code block
        self.sub_bits = n
        self.payload_bits = k - 24
        self.llr_mag = llr_mag
        self.crc = CRCEncoder("CRC24A")
        self.crc_dec = CRCDecoder(self.crc)
        self.enc = LDPC5GEncoder(k, n)
        self.dec = LDPC5GDecoder(self.enc, num_iter=num_iter, hard_out=True, return_infobits=True)
        self.scrambled, self.n_id, self._scr = scramble, n_id, {}

    def scramble(self, bits: np.ndarray) -> np.ndarray:
        """bits (n_user, n_bits) of every user's code blocks in transmission order -> XOR with the
        NR PUSCH scrambling sequence of user u (TS 38.211 Sec. 6.3.1.1: length-31 Gold sequence of
        Sec. 5.2.1, c_init = n_RNTI 2^15 + n_ID, n_RNTI = u + 1). Its own inverse; identity when off."""
        if not self.scrambled:
            return bits
        key = bits.shape
        if key not in self._scr:
            from sionna.phy.nr.utils import generate_prng_seq
            self._scr[key] = np.stack([generate_prng_seq(bits.shape[1], ((u + 1) << 15) + self.n_id)
                                       for u in range(bits.shape[0])]).astype(np.int64)
        return np.bitwise_xor(np.asarray(bits, dtype=np.int64), self._scr[key])

    def frame(self, payload: np.ndarray) -> np.ndarray:
        """payload (n_cb, n_user, k - 24) -> coded bits (n_cb, n_user, n)."""
        with torch.no_grad():
            c = self.enc(self.crc(torch.as_tensor(payload, dtype=torch.float32)))
        return c.numpy().astype(np.int64)

    def n_subblocks(self, data_bits: int) -> int:
        return data_bits // self.n

    def check(self, decided_bits: np.ndarray) -> np.ndarray:
        """decided bits (n_cb, n_user, n) -> CRC pass after LDPC decoding (n_cb, n_user)."""
        return self.decode(decided_bits)[0]

    def decode(self, decided_bits: np.ndarray):
        """-> (CRC pass (n_cb, n_user), re-encoded codewords of the decoded blocks (n_cb, n_user, n))."""
        b = torch.as_tensor(decided_bits, dtype=torch.float32)
        state = torch.get_rng_state()
        with torch.no_grad():
            u = self.dec((2.0 * b - 1.0) * self.llr_mag)      # logit convention: positive = bit 1
            _, ok = self.crc_dec(u)
            cw = self.enc(u)
        torch.set_rng_state(state)
        return ok.squeeze(-1).numpy().astype(bool), cw.numpy().astype(np.int64)
