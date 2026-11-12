"""Citadel-Rx: continuum-memory test-time-learning receivers with certified
robustness to pilot poisoning.

Package layout
--------------
channels/   block-fading MIMO channel models (synthetic SED, COST2100, Jakes)
modulation  BPSK / QPSK mapping and symbol <-> bit utilities
coding/     CRC sub-block framing used by the CRC gate (G2)
receivers/  DeepSIC backbone (functional), online / meta / drift / LMMSE /
            single-memory Titans baselines, and the Citadel-Rx receiver
attacks/    A1 availability (white-box + transfer), A2 drift spoofing,
            A3 boiling-frog, and the gate-aware adaptive attacker
gates/      G1 model-residual, G2 CRC, G3 prior-likelihood
eval/       sequential block runner, metrics, JSON run records
theory/     numerical evaluation of the regret bound and certificate
"""

__version__ = "0.1.0"
