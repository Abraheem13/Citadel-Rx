#!/usr/bin/env bash
# The full experiment campaign (E1, E2, E3, E3snr, E4, E5, E7, ablations), 3 seeds each.
# Runs are independent processes; the receivers are tiny MLPs, so throughput comes from running
# many single-threaded processes in parallel, not from the GPU (GPU is used automatically when
# available, and matters for the 8x8 / Sionna configurations).
#
#   bash scripts/run_all.sh                 # everything, workers = half the CPU cores
#   WORKERS=12 bash scripts/run_all.sh e3   # one experiment, 12 parallel runs
#
# Each run writes results/<exp>/<name>_s<seed>_<hash>.json; re-running skips nothing (cheap) but
# records are keyed by config hash so duplicates are harmless. Expect 10–20 h for the whole
# campaign on a 16-core box; E3 alone is ~3 h.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export OMP_NUM_THREADS=1 CITADEL_THREADS=1
WORKERS=${WORKERS:-$(( $(nproc) / 2 ))}
SEEDS=${SEEDS:-"0 1 2"}
EXPS=${*:-"e3 e2 ablate e7 e1 e4 e3snr e5"}

mkdir -p logs
for e in $EXPS; do
  echo "=== $e  ($(date))" | tee -a logs/run_all.log
  python scripts/sweep.py "$e" --seeds $SEEDS --workers "$WORKERS" 2>&1 | tee -a "logs/sweep_$e.log"
done

echo "=== figures and tables ($(date))" | tee -a logs/run_all.log
python scripts/paper_numbers.py results/ --out figures/
python -m citadel_rx.theory.bound
echo "done. Now: bash scripts/push_results.sh"
