#!/usr/bin/env python
"""Save the run records a machine holds that are not on GitHub, without touching the paper's numbers.

A laptop that ran part of a campaign (for example the Windows laptop of the second campaign, whose runs
were all also made by the cloud pool machines) may hold records in results/ that were never pushed.
Pushing them into results/ would let them replace records of the same name made by another machine, and
the analysis pairs every attacked run with the clean twin from its own machine, so the paper's numbers
could change. This script instead moves every new or changed file under results/ (and the machine's own
logs) into results_archive/<machine>/, which scripts/revision_numbers.py never reads, then pulls,
commits and pushes. Nothing is deleted: a file that differs from the one on GitHub is kept in the
archive next to the original.

Level snapshots (*.levels.npz) and the pretrained-weight cache are too large for main and are not
touched here: scripts/archive_machine_snapshots.py stores them, and anything else the clone holds
that is not on GitHub, on the branch `snapshots` (docs/SNAPSHOTS.md). Run it after this script.

    python scripts/archive_machine_results.py --machine windows        # on the laptop, in the repository
    python scripts/archive_machine_results.py --machine windows --dry  # list what would be archived
    python scripts/archive_machine_snapshots.py --machine windows      # then: snapshots, caches, the rest
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "main"
NEXT = ("level snapshots (*.levels.npz), the pretrain cache and other files that are not on GitHub are stored on the "
        "snapshots branch by:\n    python scripts/archive_machine_snapshots.py --machine {m} --dry    (list)\n"
        "    python scripts/archive_machine_snapshots.py --machine {m}          (store)")


def git(*args, check=True, capture=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=capture, text=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", required=True, help="a name for this machine, e.g. windows or mac")
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    status = git("status", "--porcelain", "--untracked-files=all", "--", "results", "logs").stdout.splitlines()
    paths = []
    for line in status:
        code, path = line[:2], line[3:].strip().strip('"')
        if code.strip() in ("??", "M", "A", "AM", "MM") and (path.endswith((".json", ".jsonl", ".log", ".md"))):
            paths.append(path)
    print(f"{len(paths)} new or changed files under results/ and logs/")
    if args.dry or not paths:
        for p in paths[:50]:
            print("  ", p)
        print(NEXT.format(m=args.machine))
        return
    dest_root = os.path.join("results_archive", args.machine)
    big = []
    for p in paths:
        dst = os.path.join(ROOT, dest_root, p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, p), dst)
        if os.path.getsize(dst) > 95 * 2 ** 20:   # GitHub refuses files over 100 MB
            big.append(dst)
        if git("ls-files", "--error-unmatch", p, check=False).returncode == 0:
            git("checkout", "--", p)               # tracked file changed here: restore it, the copy is archived
        else:
            os.remove(os.path.join(ROOT, p))        # untracked: now only in the archive
    git("pull", "--no-rebase", "--no-edit", "origin", args.branch, capture=False)
    keep = [os.path.relpath(b, ROOT) for b in big]
    for b in keep:
        print(f"   not pushed (over 100 MB, keep it locally or put it on Zenodo): {b}")
    add = [os.path.relpath(os.path.join(dp, f), ROOT) for dp, _, fs in os.walk(os.path.join(ROOT, dest_root)) for f in fs]
    add = [a for a in add if a not in keep]
    for i in range(0, len(add), 200):
        git("add", "-f", "--", *add[i:i + 200])
    git("commit", "-q", "-m", f"Archive of the run records held by the {args.machine} machine (not read by the analysis)", check=False)
    r = git("push", "origin", f"HEAD:{args.branch}", check=False, capture=False)
    print("pushed" if r.returncode == 0 else "push failed: log in to GitHub on this machine and run: git push origin HEAD:" + args.branch)
    print(NEXT.format(m=args.machine))


if __name__ == "__main__":
    main()
