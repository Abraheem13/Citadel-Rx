#!/usr/bin/env python
"""One command on the Windows laptop (cmd or PowerShell, inside the repository folder):

    py -3.12 scripts\\run_windows.py

It (1) updates the code from GitHub, (2) creates the Python environment .venv the first time (CPU
PyTorch and the requirements), (3) runs the tests, (4) runs the Windows part of the second revision
campaign with the laptop kept awake, pushing results to GitHub every 45 minutes, and (5) pushes at
the end. Every run is resumable: after any interruption (crash, Ctrl-C, restart) run the same
command again; finished runs are skipped.

Options:  --workers N   parallel runs (default: from the free memory, at most 4)
          --tier T      1 = the most important runs only, 2 = + ablations and scenarios, 3 = all (default)
          --setup-only  stop after the environment is ready
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import os
import shutil
import subprocess
import sys

BRANCH = "claude/fervent-cray-ah5drn"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VPY = os.path.join(ROOT, ".venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(ROOT, ".venv", "bin", "python")
LOG = None


def say(msg: str) -> None:
    print(msg, flush=True)
    if LOG:
        LOG.write(msg + "\n")
        LOG.flush()


def run(cmd, check=False, quiet=False, env=None) -> int:
    """Run a command, copying its output to the screen and the log file."""
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", env=env)
    for line in p.stdout:
        if not quiet:
            say(line.rstrip("\n"))
    rc = p.wait()
    if check and rc != 0:
        say(f"!! command failed ({rc}): {' '.join(cmd)}")
        sys.exit(1)
    return rc


def free_memory_mb() -> int:
    if os.name != "nt":
        return 8000

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return int(m.ullAvailPhys // 2 ** 20)


def keep_awake() -> None:
    """Stop Windows from sleeping while this script runs (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)."""
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)


def git(*args, check=False) -> int:
    return run(["git", *args], check=check)


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--tier", type=int, choices=[1, 2, 3], default=3)
    ap.add_argument("--setup-only", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)
    os.makedirs("logs", exist_ok=True)
    LOG = open(os.path.join("logs", f"windows_{dt.datetime.now():%Y%m%d_%H%M%S}.log"), "a", encoding="utf-8")
    say(f"== Citadel-Rx revision, Windows part   {dt.datetime.now()}")
    say(f"   Python {sys.version.split()[0]}, {os.cpu_count()} logical processors, {free_memory_mb()} MB of memory free")
    if shutil.which("git") is None:
        say("!! git is not installed: run  winget install -e --id Git.Git  then open a new terminal and try again")
        sys.exit(1)

    # ---- 1. code ------------------------------------------------------------------------------
    cur = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if cur != BRANCH:
        git("fetch", "origin", BRANCH, check=True)
        git("checkout", BRANCH, check=True)
    for key, val in (("user.email", "windows@citadel-rx.invalid"), ("user.name", "Citadel-Rx windows")):
        if subprocess.run(["git", "config", key], cwd=ROOT, capture_output=True).returncode != 0:
            git("config", key, val)
    if git("pull", "--no-rebase", "--no-edit", "origin", BRANCH) != 0:
        say("   (git pull failed: continuing with the local copy)")
    say("   code version: " + subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                             text=True).stdout.strip())
    say("   checking that this laptop can push results to GitHub (a browser window may ask you to sign in to")
    say("   GitHub: use the account abraheemrashid99-sys)")
    if git("push", "origin", f"HEAD:{BRANCH}") == 0:
        say("   push access OK")
    else:
        say("!! this laptop cannot push to GitHub yet: the runs still start and their results are kept here.")
        say(f"   Fix the login (run: git push origin HEAD:{BRANCH}); the next automatic push then sends everything.")

    # ---- 2. disk and Python environment -------------------------------------------------------
    free_mb = shutil.disk_usage(ROOT).free // 2 ** 20
    say(f"   free disk: {free_mb} MB")
    if not os.path.exists(VPY):
        if free_mb < 3000:
            say("!! about 3 GB of free disk is needed for the environment (PyTorch); free some space and re-run")
            sys.exit(1)
        if sys.version_info < (3, 10):
            say("!! Python 3.10 or newer is needed: winget install -e --id Python.Python.3.12, then py -3.12 scripts\\run_windows.py")
            sys.exit(1)
        say(f"   creating .venv with Python {sys.version.split()[0]} (a few minutes the first time)")
        run([sys.executable, "-m", "venv", ".venv"], check=True)
        run([VPY, "-m", "pip", "install", "-q", "--upgrade", "pip"])
        run([VPY, "-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
        run([VPY, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    if run([VPY, "-c", "import torch, numpy, scipy, yaml; print('   torch', torch.__version__, '| numpy', numpy.__version__)"]) != 0:
        say("!! the environment is broken: delete the .venv folder and run the same command again")
        sys.exit(1)
    with open(os.path.join("logs", "windows_env.txt"), "w", encoding="utf-8") as f:
        f.write(subprocess.run([VPY, "-m", "pip", "freeze"], cwd=ROOT, capture_output=True, text=True).stdout)
    if args.setup_only:
        say("== environment ready (--setup-only)")
        return

    # ---- 3. tests -------------------------------------------------------------------------------
    say("== tests (a few minutes)")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if run([VPY, "-m", "pytest", "tests", "-q"], env=env) != 0:
        # a platform quirk in a test should not cost a day: the campaign continues, and this log is
        # pushed with the results so the failure can be checked
        say(f"!! some tests failed (above); the campaign continues and this log ({LOG.name}) is pushed for checking")

    # ---- 4. campaign ----------------------------------------------------------------------------
    keep_awake()
    mem = free_memory_mb()
    workers = args.workers or max(1, min(4, (mem - 1500) // 900))
    say(f"== campaign: {workers} parallel runs ({mem} MB of memory free), tiers up to {args.tier}")
    say("   keep the laptop plugged in; closing other programs frees memory for more parallel runs")
    if workers < 2:
        say("   (only one run at a time: close the browser and other programs and restart for more)")
    run([VPY, os.path.join("scripts", "revision_fast.py"), "--campaign", "2", "--shard", "windows",
         "--workers", str(workers), "--tier", str(args.tier), "--min-free-mb", "1000"], env=env)

    # ---- 5. final push --------------------------------------------------------------------------
    run([VPY, os.path.join("scripts", "revision_fast.py"), "--shard", "windows", "--push-only"], env=env)
    say(f"== finished {dt.datetime.now()}. Results are on GitHub (branch {BRANCH}).")


if __name__ == "__main__":
    main()
