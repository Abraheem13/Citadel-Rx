"""v3 model-based detectors, the pilot-domain guard and the piecewise attack schedule."""
import numpy as np
import torch

from citadel_rx.config import Config
from citadel_rx.eval import run_experiment
from citadel_rx.modulation import Modulation
from citadel_rx.receivers.modelbased import detect_kbest, detect_ml, detect_mmse_sic, detect_lmmse


def _scene(mod_name="QPSK", n=600, N=4, U=4, snr_db=12.0, seed=0, real=False):
    rng = np.random.default_rng(seed)
    mod = Modulation(mod_name)
    H = rng.standard_normal((N, U)) + (0 if real else 1j * rng.standard_normal((N, U)))
    H /= np.sqrt(2 * N)
    H += np.eye(N, U)
    idx = rng.integers(0, mod.order, size=(n, U))
    nv = 10 ** (-snr_db / 10)
    y = mod.modulate_indices(idx) @ H.T + np.sqrt(nv / 2) * (rng.standard_normal((n, N)) + 1j * rng.standard_normal((n, N)))
    return mod, H, idx, y, nv


def test_kbest_with_large_k_equals_ml():
    mod, H, idx, y, nv = _scene()
    ml = detect_ml(y, H, mod)
    kb = detect_kbest(y, H, mod, K=256)        # keeps every hypothesis: exact ML
    assert np.array_equal(ml, kb)


def test_detector_ordering_on_a_hard_channel():
    mod, H, idx, y, nv = _scene(n=4000, snr_db=8.0, seed=3)
    err = lambda d: float((d != idx).any(axis=1).mean())
    e_ml, e_kb = err(detect_ml(y, H, mod)), err(detect_kbest(y, H, mod, K=16))
    e_sic, e_lin = err(detect_mmse_sic(y, H, nv, mod)), err(detect_lmmse(y, H, nv, mod))
    assert e_ml <= e_kb + 0.01 and e_kb <= e_sic + 0.01 and e_sic <= e_lin + 0.01


def test_kbest_16qam_runs_and_beats_lmmse():
    mod, H, idx, y, nv = _scene("QAM16", n=2000, snr_db=20.0, seed=1)
    err = lambda d: float((d != idx).any(axis=1).mean())
    assert err(detect_kbest(y, H, mod, K=16)) <= err(detect_lmmse(y, H, nv, mod))


def _tiny(**kw):
    cfg = Config()
    for o in ["frame.n_blocks=8", "frame.data_bits=2048", "receiver.type=model", "receiver.pretrain=false",
              "attack.start_block=3", "attack.end_block=6", "run.device=cpu"] + [f"{k}={v}" for k, v in kw.items()]:
        cfg.set(o)
    return cfg


def test_guard_rejects_poisoned_pilots_and_accepts_clean():
    torch.set_num_threads(1)
    clean = run_experiment(_tiny(**{"receiver.guard": "true"}), seed=1, save=False, verbose=False)
    assert all(b["gamma"] == 1.0 for b in clean["blocks"])
    att = run_experiment(_tiny(**{"receiver.guard": "true", "attack.type": "deny", "attack.sir_db": "0"}),
                         seed=1, save=False, verbose=False)
    assert all(b["gamma"] == 0.0 for b in att["blocks"] if b.get("attacked"))
    unguarded = run_experiment(_tiny(**{"attack.type": "deny", "attack.sir_db": "0"}), seed=1, save=False, verbose=False)
    w = [b["block"] for b in att["blocks"] if b.get("attacked")]
    assert np.mean([att["blocks"][i]["ser"] for i in w]) < np.mean([unguarded["blocks"][i]["ser"] for i in w])


def test_perfect_csi_ignores_pilot_attack():
    a = run_experiment(_tiny(**{"receiver.csi": "perfect", "attack.type": "deny", "attack.sir_db": "0"}), seed=2,
                       save=False, verbose=False)
    c = run_experiment(_tiny(**{"receiver.csi": "perfect"}), seed=2, save=False, verbose=False)
    assert [b["ser"] for b in a["blocks"]] == [b["ser"] for b in c["blocks"]]


def test_attack_schedule_segments():
    cfg = _tiny(**{"attack.type": "deny", "attack.sir_db": "0",
                   "attack.schedule": "[{start: 1, end: 3, sir_db: 20}, {start: 5, end: 7, sir_db: 0}]"})
    rec = run_experiment(cfg, seed=3, save=False, verbose=False)
    att = {b["block"]: b for b in rec["blocks"] if b.get("attacked")}
    assert sorted(att) == [1, 2, 5, 6]
    assert att[1]["segment"] == 0 and att[5]["segment"] == 1
    assert att[1]["eps"] < att[5]["eps"] / 5          # 20 dB weaker budget in the first segment
    assert rec["summary"]["attack_window"] == [1, 7]
