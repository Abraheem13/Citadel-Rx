#!/usr/bin/env bash
# One click on the MacBook. In the VS Code terminal, inside the repository folder:
#
#     bash scripts/run_laptop.sh
#
# It (1) updates the code from GitHub, (2) creates the Python environment .venv (first time only),
# (3) runs the tests, (4) runs the laptop part of the revision campaign with the Mac kept awake,
# pushing results to GitHub every 45 minutes, and (5) pushes at the end. Every run is resumable:
# after any interruption (crash, Ctrl-C, reboot) just run the same command again.
#
# Options:  WORKERS=8  (parallel runs; default 8 of the 10 cores)
#           TIER=3     (1 = only what the revised claims need, 2 = + remaining items, 3 = + sensitivity)
set -uo pipefail
cd "$(dirname "$0")/.."
# The whole script is one function, so bash has read all of it before step 1 runs `git pull`
# (which may replace this very file).
main() {
BRANCH="claude/fervent-cray-ah5drn"
WORKERS="${WORKERS:-8}"
TIER="${TIER:-3}"
mkdir -p logs
LOG="logs/laptop_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "== Citadel-Rx revision, laptop part   $(date)"
echo "   machine: $(uname -sm), $(sysctl -n hw.ncpu 2>/dev/null || nproc) cores"

# ---- 1. code -------------------------------------------------------------------------------
if [ "$(git rev-parse --abbrev-ref HEAD)" != "$BRANCH" ]; then
  git fetch origin "$BRANCH" && git checkout "$BRANCH" || { echo "!! cannot switch to branch $BRANCH"; exit 1; }
fi
git config user.email >/dev/null || git config user.email "laptop@citadel-rx.invalid"
git config user.name  >/dev/null || git config user.name  "Citadel-Rx laptop"
git pull --no-rebase --no-edit origin "$BRANCH" || echo "   (git pull failed: continuing with the local copy)"
echo "   code version: $(git rev-parse --short HEAD)"
# GitHub login for the automatic pushes: the repository is public, so reading needs none, but
# pushing does. Ask for it once now, while you are watching; it is remembered afterwards.
if [ -z "$(git config --get credential.helper)" ]; then
  if git credential-osxkeychain 2>&1 | grep -qi usage; then git config credential.helper osxkeychain
  else git config credential.helper "cache --timeout=172800"; fi
fi
echo "   checking that this machine can push results to GitHub. If asked: your GitHub user name, then a"
echo "   personal access token as the password (github.com > Settings > Developer settings > Personal access"
echo "   tokens > Fine-grained, repository Citradel-Rx, Contents: Read and write)."
if git push origin "HEAD:$BRANCH"; then
  echo "   push access OK"
else
  echo "!! this machine cannot push to GitHub yet: the runs still start and their results are kept here."
  echo "   Fix the login (run: git push origin HEAD:$BRANCH), the next automatic push then sends everything."
fi

# ---- 2. disk and Python environment ---------------------------------------------------------
# ignore personal pip settings (a pip.conf with "user = true" breaks virtual environments)
export PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1
unset PIP_USER PIP_TARGET PIP_PREFIX PIP_REQUIRE_VIRTUALENV PYTHONPATH PYTHONHOME
free_mb=$(df -m . | awk 'NR==2 {print $4}')
echo "   free disk: ${free_mb} MB"
if [ -d .venv ] && ! .venv/bin/python -c "import torch, numpy, scipy, yaml" 2>/dev/null; then
  echo "   removing an incomplete .venv"; rm -rf .venv
fi
if [ ! -d .venv ]; then
  # the active conda Python first; prefer one that already has numpy/scipy/matplotlib (then only
  # PyTorch is installed)
  cands=""
  if [ -n "${CONDA_PREFIX:-}" ] && [ -x "${CONDA_PREFIX}/bin/python" ]; then cands="${CONDA_PREFIX}/bin/python"; fi
  cands="$cands python3 python3.12 python3.11 python3.13 python"
  PY=""; PY_SITE=""
  for c in $cands; do
    command -v "$c" >/dev/null 2>&1 || continue
    "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || continue
    if [ "$(uname -s)" = "Darwin" ] && [ "$("$c" -c 'import platform; print(platform.machine())')" != "arm64" ]; then continue; fi
    [ -z "$PY" ] && PY="$c"
    if [ -z "$PY_SITE" ] && "$c" -c 'import numpy, scipy, matplotlib, yaml' 2>/dev/null; then PY_SITE="$c"; fi
  done
  if [ -z "$PY" ]; then
    echo "!! no native Python >= 3.10 found. With conda:  conda create -y -n py311 python=3.11 && conda activate py311  then re-run."
    exit 1
  fi
  SITE=""; need_mb=1400
  if [ -n "$PY_SITE" ]; then PY="$PY_SITE"; SITE="--system-site-packages"; need_mb=1000; fi
  if [ "$free_mb" -lt "$need_mb" ]; then
    echo "!! about $need_mb MB of free disk is needed (now $free_mb MB). Free space, for example:"
    echo "     conda clean -a -y ; pip cache purge ; rm -rf ~/Library/Caches/pip ; empty the Bin"
    exit 1
  fi
  echo "   creating .venv with $PY ($("$PY" --version 2>&1))${SITE:+, reusing its numpy/scipy/matplotlib}"
  mode=""
  if "$PY" -m venv $SITE .venv && .venv/bin/python -m pip --version >/dev/null 2>&1; then
    mode=venv
  else
    echo "   the standard venv failed; its pip bootstrap reports:"
    [ -x .venv/bin/python ] && .venv/bin/python -m ensurepip --default-pip 2>&1 | tail -6
    rm -rf .venv
    # fallback 1: a venv without pip, filled by the pip of the base Python (pip >= 22.3)
    if "$PY" -m pip --version >/dev/null 2>&1 && "$PY" -m venv $SITE --without-pip .venv \
       && "$PY" -m pip --python .venv/bin/python --version >/dev/null 2>&1; then
      mode=basepip
      echo "   using a venv without its own pip, filled by $PY -m pip"
    else
      rm -rf .venv
      # fallback 2: a conda environment in .venv
      if command -v conda >/dev/null 2>&1 && conda create -y -q -p "$PWD/.venv" python=3.12 pip; then
        mode=venv
        echo "   using a conda environment in .venv"
      fi
    fi
  fi
  case "$mode" in
    venv)    .venv/bin/python -m pip install -q --no-cache-dir --upgrade pip || true
             .venv/bin/python -m pip install --no-cache-dir -r requirements.txt || { echo "!! pip install failed"; rm -rf .venv; exit 1; } ;;
    basepip) "$PY" -m pip --python .venv/bin/python install --no-cache-dir -r requirements.txt || { echo "!! pip install failed"; rm -rf .venv; exit 1; } ;;
    *)       echo "!! could not create a Python environment; send the lines above"; exit 1 ;;
  esac
fi
PYV=.venv/bin/python
"$PYV" -c "import torch, numpy, scipy, yaml; print('   torch', torch.__version__, '| numpy', numpy.__version__, '| scipy', scipy.__version__)" \
  || { echo "!! the environment is broken: delete the .venv folder and re-run"; exit 1; }
{ "$PYV" -m pip freeze 2>/dev/null || "$PYV" -c "import importlib.metadata as m; print('\\n'.join(sorted(f'{d.metadata[\"Name\"]}=={d.version}' for d in m.distributions())))"; } > logs/laptop_env.txt 2>/dev/null   # package versions, pushed with the results
# pre-training cache: as large as the disk allows (0.1-0.6 GB), keeping 0.8 GB free for the runs
free_mb=$(df -m . | awk 'NR==2 {print $4}')
CACHE_GB=$(awk -v f="$free_mb" 'BEGIN { c = (f - 800) / 1024; if (c > 0.6) c = 0.6; if (c < 0.1) c = 0.1; printf "%.2f", c }')
echo "   free disk after setup: ${free_mb} MB; pre-training cache up to ${CACHE_GB} GB"
if [ "$free_mb" -lt 1000 ]; then
  echo "!! less than 1 GB free: free some space first (the drift runs write about 150 MB of level"
  echo "   snapshots each, and runs pause below 400 MB). For example: rm -rf cache ; conda clean -a -y ;"
  echo "   empty the Bin; restarting the Mac also releases its swap files."
  exit 1
fi
if [ "${SETUP_ONLY:-0}" = "1" ]; then echo "== environment ready (SETUP_ONLY=1)"; exit 0; fi

# ---- 3. tests --------------------------------------------------------------------------------
echo "== tests (a few minutes)"
"$PYV" -m pytest tests -q -x || { echo "!! tests failed: stop here and send this log ($LOG)"; exit 1; }

# ---- 4. campaign -----------------------------------------------------------------------------
echo "== campaign: $WORKERS parallel runs, tiers up to $TIER (keep the Mac on power, lid open)"
AWAKE=""
command -v caffeinate >/dev/null 2>&1 && AWAKE="caffeinate -ims"
$AWAKE "$PYV" scripts/revision_fast.py --shard laptop --workers "$WORKERS" --tier "$TIER" --cache-gb "$CACHE_GB"

# ---- 4b. paired displacement of the drift runs: needs the level snapshots, which stay on this Mac
if ls results/rev_p8_drift/*.levels.npz >/dev/null 2>&1; then
  echo "== paired displacement of the drift runs"
  "$PYV" scripts/paired_disp.py results/rev_p8_drift --clean results/rev_clean --out docs/figures/fig_rev_p8_drift \
    || echo "!! paired displacement failed: send this output"
fi

# ---- 5. final push ---------------------------------------------------------------------------
"$PYV" scripts/revision_fast.py --shard laptop --push-only
echo "== finished $(date). Results are on GitHub (branch $BRANCH)."
}
main "$@"
exit $?
