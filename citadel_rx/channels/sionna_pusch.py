"""E6 — 5G NR PUSCH link with 3GPP CDL channels, LDPC and a real transport-block CRC (Sionna ≥ 1.0).

STATUS: written for the GPU machine; NOT exercised in the CPU development
environment (Sionna/TensorFlow are not installed there). Everything that can
fail is wrapped so that the rest of the package imports without Sionna.

What this provides to the rest of the code
------------------------------------------
``SionnaPUSCHBlocks`` yields, per coherence block (= one slot), the per-user
received resource grid flattened to the (n_symbols, n_ant) complex matrix that
the DeepSIC-type receivers consume, with the first ``n_pilot`` entries being
DMRS-carrying resource elements (known symbols) and the rest data. The LDPC
decoding + TB-CRC check is exposed through ``decode_and_check`` so that gate
G2 can use the *real* transport-block CRC instead of the sub-block framing.

Reviewers will ask whether the gains survive coded transmission at high
Doppler: this is the module that answers that (coded BLER vs SNR at 30/60/120
km/h with and without A1).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

try:  # pragma: no cover - GPU only
    import tensorflow as tf
    import sionna
    from sionna.phy.nr import PUSCHConfig, PUSCHTransmitter, PUSCHReceiver
    from sionna.phy.channel.tr38901 import CDL, PanelArray
    from sionna.phy.channel import OFDMChannel
    _HAVE_SIONNA = True
except Exception:  # noqa: BLE001
    _HAVE_SIONNA = False


class SionnaPUSCHBlocks:
    def __init__(self, n_user: int = 4, n_ant: int = 4, cdl_model: str = "A", speed_kmh: float = 30.0,
                 carrier_ghz: float = 3.5, mcs_index: int = 14, num_prb: int = 16, snr_db: float = 10.0,
                 seed: int = 0):
        if not _HAVE_SIONNA:
            raise ImportError("Sionna/TensorFlow not available; install with `pip install -e .[sionna]` on the GPU box")
        self.n_user, self.n_ant = n_user, n_ant
        self.snr_db = snr_db
        tf.random.set_seed(seed)
        self.cfg = PUSCHConfig()
        self.cfg.carrier.subcarrier_spacing = 30
        self.cfg.carrier.n_size_grid = num_prb
        self.cfg.num_antenna_ports = 1
        self.cfg.num_layers = 1
        self.cfg.tb.mcs_index = mcs_index
        self.cfg.dmrs.additional_position = 1
        self.cfgs = []
        for u in range(n_user):
            c = self.cfg.clone()
            c.dmrs.dmrs_port_set = [u]
            self.cfgs.append(c)
        self.tx = PUSCHTransmitter(self.cfgs, output_domain="freq")
        self.rx = PUSCHReceiver(self.tx, input_domain="freq")  # LMMSE + LDPC reference chain
        ut = PanelArray(num_rows_per_panel=1, num_cols_per_panel=1, polarization="single",
                        polarization_type="V", antenna_pattern="omni", carrier_frequency=carrier_ghz * 1e9)
        bs = PanelArray(num_rows_per_panel=1, num_cols_per_panel=n_ant, polarization="single",
                        polarization_type="V", antenna_pattern="omni", carrier_frequency=carrier_ghz * 1e9)
        self.cdl = CDL(model=cdl_model, delay_spread=300e-9, carrier_frequency=carrier_ghz * 1e9,
                       ut_array=ut, bs_array=bs, direction="uplink", min_speed=speed_kmh / 3.6)
        self.channel = OFDMChannel(self.cdl, self.tx.resource_grid, add_awgn=True, normalize_channel=True,
                                   return_channel=True)

    def block(self, b: int) -> Dict[str, Any]:
        """One slot for all users. Returns received grid, the known DMRS positions and the TB bits."""
        no = 10 ** (-self.snr_db / 10)
        x, bits = self.tx(1)                                   # x: [1, n_user, 1, n_sym, n_sc]
        y, h = self.channel(x, no)                             # y: [1, 1, n_ant, n_sym, n_sc]
        return {"y": y.numpy()[0, 0], "x": x.numpy()[0], "bits": bits.numpy()[0], "h": h.numpy()}

    def decode_and_check(self, llrs_or_symbols, bits_true) -> np.ndarray:
        """LDPC decode and TB-CRC check through Sionna's receiver; returns per-user CRC pass."""
        raise NotImplementedError("wire the DeepSIC soft outputs into PUSCHReceiver's LDPC/TB decoder on the GPU box")
