"""DeepMIMO ray-traced user trajectories (E4 drift spoofing, E8 channel prediction).

STATUS: adapter written against the DeepMIMO v3 Python API; NOT exercised in
the CPU development environment (scenario files are several GB and must be
downloaded on the GPU machine: https://www.deepmimo.net , scenarios O1_3p5 /
I3_60). Falls back with a clear error when the package or scenario is absent.

The adapter turns a user trajectory (a sequence of user indices along a row of
the scenario grid) into the (n_ant, n_user) block channel matrices the runner
expects, so that A2's "physically implausible jump" is tested against spatially
consistent drift rather than against an AR(1) toy.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

try:  # pragma: no cover - GPU/data only
    import DeepMIMO  # noqa: N811
    _HAVE_DEEPMIMO = True
except Exception:  # noqa: BLE001
    _HAVE_DEEPMIMO = False


class DeepMIMOTrajectoryChannel:
    def __init__(self, scenario: str = "O1_3p5", dataset_folder: str = "./deepmimo_scenarios", n_ant: int = 4,
                 n_user: int = 4, user_rows: Optional[List[int]] = None, step: int = 1, seed: int = 0):
        if not _HAVE_DEEPMIMO:
            raise ImportError("DeepMIMO not installed; `pip install DeepMIMO` and download the scenario on the GPU box")
        params = DeepMIMO.default_params()
        params["scenario"] = scenario
        params["dataset_folder"] = dataset_folder
        params["num_paths"] = 10
        params["active_BS"] = np.array([1])
        params["user_row_first"] = (user_rows or [1000])[0]
        params["user_row_last"] = (user_rows or [1000, 1200])[-1]
        params["bs_antenna"]["shape"] = np.array([n_ant, 1, 1])
        params["ue_antenna"]["shape"] = np.array([1, 1, 1])
        params["OFDM"]["subcarriers"] = 64
        params["OFDM"]["subcarriers_limit"] = 1
        self.data = DeepMIMO.generate_data(params)
        ch = self.data[0]["user"]["channel"]              # (n_users_total, n_ant, 1, n_sc)
        self.h_all = ch[:, :, 0, 0]                        # narrowband (n_users_total, n_ant)
        self.n_ant, self.n_user, self.step = n_ant, n_user, step
        rng = np.random.default_rng(seed)
        n_total = self.h_all.shape[0]
        self.start = rng.integers(0, n_total - 1, size=n_user)

    def state_matrix(self, b: int) -> np.ndarray:
        idx = (self.start + b * self.step) % self.h_all.shape[0]
        H = self.h_all[idx].T                              # (n_ant, n_user) complex
        H = H / np.sqrt(np.mean(np.abs(H) ** 2) + 1e-12)   # unit average gain
        return H
