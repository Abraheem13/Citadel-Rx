"""One plotting style for every manuscript figure (serif text matching IEEEtran, vector output)."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["STIXGeneral", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "lines.linewidth": 1.1, "lines.markersize": 3,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.handlelength": 1.8, "legend.columnspacing": 1.0,
    "figure.dpi": 200, "savefig.dpi": 300, "pdf.fonttype": 42,
})

# receiver colours (colour-blind safe), used identically in every figure
C = {"citadel": "#0072B2", "online_deepsic": "#D55E00", "meta_deepsic": "#7B4F9D", "lmmse": "#6E6E6E",
     "drift_deepsic": "#009E73", "medbn_deepsic": "#CC79A7", "titans_single": "#E69F00"}
L = {"citadel": "Citadel-Rx", "online_deepsic": "Online DeepSIC", "meta_deepsic": "Meta-DeepSIC",
     "lmmse": "LMMSE", "drift_deepsic": "Drift-detection", "medbn_deepsic": "MedBN-style",
     "titans_single": "Single-memory Titans"}
OUT = "docs/figures"


def panel_title(ax, text):
    ax.set_title(text, loc="left", fontsize=8, pad=4)


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(f"{OUT}/{name}.png", bbox_inches="tight", pad_inches=0.02)
