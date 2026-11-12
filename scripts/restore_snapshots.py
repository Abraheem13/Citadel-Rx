#!/usr/bin/env python
"""Put the level snapshots and the pretrained-weight caches of the revision back into a clone.

The files are too large for the main branch (GitHub accepts at most 100 MB per file), so they live on
the branch `snapshots` of this repository, the large ones cut into parts of 90 MB. MANIFEST.json (the
cloud machine) and manifests/<machine>.json (every other machine) on that branch list every file with
its size, its sha256, its parts and the machine that wrote it. This script downloads the parts it needs,
joins them, checks the sha256 of every file and writes it to its place. A file that is already in place
with the right sha256 is left alone; a different file found in that place is kept beside it as
<name>.local; a download whose sha256 does not match the manifest is an error and is not written.

    python scripts/restore_snapshots.py                  # in a clone of main: every level snapshot
    python scripts/restore_snapshots.py --list           # only list what is on the branch
    python scripts/restore_snapshots.py --machine pool4  # only the snapshots of one machine
    python scripts/restore_snapshots.py --only pretrain_cache --machine cloud
    python restore_snapshots.py --to /path/to/Citradel-Rx    # in a checkout of the snapshots branch

What is restored, by kind:
  snapshot        results/<folder>/<record>.levels.npz, next to its JSON record (the default)
  pretrain_cache  cache/pretrain/<key>.pt; every machine made its own, so name the machine (--machine)
  machine_file    other files a machine held that are not on main (figures and tables it drew from its
                  own snapshots, logs); written to results_archive/<machine>/, which the analysis never reads

Nothing in the paper needs these files (see docs/SNAPSHOTS.md): with the snapshots in place, `make paper`
gives the same numbers, because scripts/paired_disp.py recomputes the stored displacements from them.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BRANCH = "snapshots"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def rmtree(path: str) -> None:
    """Remove a directory tree; git marks its object files read-only, which stops a plain rmtree on Windows."""
    def fix(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


def _inside(rel: str) -> bool:
    """A relative path that stays inside the folder it is joined to (a manifest must never write elsewhere)."""
    parts = rel.split("/")
    return bool(rel) and not rel.startswith("/") and "\\" not in rel and ":" not in rel and all(p not in ("", ".", "..") for p in parts)


def load_manifests(src: str) -> list[dict]:
    out = []
    for p in [os.path.join(src, "MANIFEST.json")] + sorted(glob.glob(os.path.join(glob.escape(src), "manifests", "*.json"))):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                out += json.load(f)
    for m in out:
        if not _inside(m["path"]) or not all(_inside(q) for q in m["parts"]):
            sys.exit(f"refusing a manifest entry with a path outside the repository: {m['path']!r}")
    return out


def select(manifest: list[dict], only: str | None, machine: str | None) -> list[dict]:
    kind = only or "snapshot"
    sel = [m for m in manifest if m["kind"] == kind and machine in (None, m.get("machine"))]
    if kind == "pretrain_cache" and machine is None:
        sys.exit("every machine made its own caches for the same folder: name one, e.g. --only pretrain_cache --machine cloud")
    seen, out = {}, []
    for m in sel:                    # two machines never hold the same record; if they ever do, keep the first
        if m["path"] in seen:
            if seen[m["path"]] != m["sha256"]:
                print(f"warning: {m['path']} is on the branch twice with different content; kept the copy of the first machine")
            continue
        seen[m["path"]] = m["sha256"]
        out.append(m)
    return out


def run(*cmd, cwd=None) -> bool:
    return subprocess.run(cmd, cwd=cwd).returncode == 0


NOCONV = ["-c", "core.autocrlf=false", "-c", "core.eol=lf"]   # the files must come out byte for byte (Git for Windows converts text by default)


def _sparse(tmp: str, paths: list[str]) -> None:
    """Limit the checkout of tmp to the manifests and `paths` (one anchored pattern per file)."""
    esc = lambda p: "/" + "".join("\\" + c if c in "*?[\\!# " else c for c in p)
    info = os.path.join(tmp, ".git", "info")
    os.makedirs(info, exist_ok=True)
    with open(os.path.join(info, "sparse-checkout"), "w", encoding="utf-8", newline="\n") as f:
        f.write("/.gitattributes\n/MANIFEST.json\n/manifests/*.json\n" + "".join(esc(p) + "\n" for p in paths))


def download(url: str, tmp: str, want) -> None:
    """Fetch the branch into tmp: first only the manifests, then only the parts that `want` selects (a partial
    clone with a sparse checkout). If this git cannot do that, the whole branch."""
    partial = run("git", "clone", "-q", *NOCONV, "--depth", "1", "--single-branch", "--branch", BRANCH,
                  "--filter=blob:none", "--no-checkout", url, tmp)
    if partial:
        _sparse(tmp, [])
        partial = (run("git", "config", "core.sparseCheckout", "true", cwd=tmp)
                   and run("git", "config", "core.sparseCheckoutCone", "false", cwd=tmp)
                   and run("git", "checkout", "-q", BRANCH, cwd=tmp))
    if partial:
        sel = want(load_manifests(tmp))
        parts = [p for m in sel for p in m["parts"]]
        if parts:
            need = 2 * sum(m["bytes"] for m in sel) + 2 ** 29   # the download holds every part twice until it is joined
            free = shutil.disk_usage(tmp).free
            if free < need:
                sys.exit(f"not enough free space in {os.path.dirname(tmp)}: about {need / 2 ** 30:.1f} GB needed, "
                         f"{free / 2 ** 30:.1f} GB free. Restore one machine at a time (--machine), or free some space.")
            print(f"downloading {len(parts)} files of the branch '{BRANCH}' ({sum(m['bytes'] for m in sel) / 2 ** 20:.0f} MB) ...", flush=True)
            _sparse(tmp, parts)
            if not run("git", "read-tree", "-mu", "HEAD", cwd=tmp):
                partial = False
    if not partial:
        if os.path.isdir(tmp):
            rmtree(tmp)
        print(f"downloading the whole branch '{BRANCH}' (several GB) ...", flush=True)
        if not run("git", "clone", "-q", *NOCONV, "--depth", "1", "--single-branch", "--branch", BRANCH, url, tmp):
            sys.exit(f"download failed (it needs free space in {os.path.dirname(tmp)}; is the repository reachable?)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", default=None, help="a checkout of the snapshots branch (default: download it)")
    ap.add_argument("--to", dest="dst", default=None, help="the clone to restore into (default: this repository)")
    ap.add_argument("--only", choices=["snapshot", "pretrain_cache", "machine_file"], default=None,
                    help="the kind of file to restore (default: snapshot)")
    ap.add_argument("--machine", default=None, help="only the files written by this machine (cloud, pool1, ...)")
    ap.add_argument("--list", action="store_true", help="list the files of the branch and stop")
    args = ap.parse_args()

    on_branch = os.path.exists(os.path.join(HERE, "MANIFEST.json"))
    src = args.src or (HERE if on_branch else None)
    dst = args.dst or (None if on_branch else os.path.dirname(HERE))
    if dst is None and not args.list:
        sys.exit("give the clone to restore into: --to /path/to/Citradel-Rx")
    want = (lambda man: [m for m in man if args.only in (None, m["kind"]) and args.machine in (None, m.get("machine"))]) \
        if args.list else (lambda man: select(man, args.only, args.machine))
    tmp = None
    try:
        if src is None:
            r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=dst or HERE, capture_output=True, text=True)
            url = r.stdout.strip()
            if not url:
                sys.exit("cannot read the git remote 'origin' here" + (": " + r.stderr.strip() if r.stderr.strip() else "")
                         + "\nclone the snapshots branch yourself and pass it with --from")
            try:      # next to the clone: the system temp directory is often too small for several GB
                tmp = tempfile.mkdtemp(prefix=".citadel_snapshots_", dir=os.path.dirname(os.path.abspath(dst)) if dst else None)
            except OSError:
                tmp = tempfile.mkdtemp(prefix="citadel_snapshots_")
            download(url, tmp, (lambda man: []) if args.list else want)
            src = tmp
        todo = want(load_manifests(src))
        if args.list:
            for m in todo:
                print(f"{m['bytes'] / 2 ** 20:8.1f} MB  {m['kind']:14s} {m.get('machine', ''):8s} {m['path']}")
            print(f"{len(todo)} files, {sum(m['bytes'] for m in todo) / 2 ** 20:.0f} MB")
            return
        if not todo:
            sys.exit("nothing on the branch matches")
        written = kept = 0
        for m in todo:
            out = os.path.join(dst, *m["path"].split("/"))
            if os.path.exists(out) and os.path.getsize(out) == m["bytes"] and sha256(out) == m["sha256"]:
                kept += 1
                continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            part = out + ".restoring"
            h = hashlib.sha256()
            try:
                with open(part, "wb") as w:
                    for p in m["parts"]:
                        q = os.path.join(src, *p.split("/"))
                        if not os.path.exists(q):
                            sys.exit(f"{p} is missing from {src}: the checkout of the snapshots branch is incomplete")
                        with open(q, "rb") as f:
                            for chunk in iter(lambda: f.read(1 << 22), b""):
                                h.update(chunk)
                                w.write(chunk)
                        if tmp:
                            os.remove(q)             # our own download: free the space as soon as a part is joined
                if h.hexdigest() != m["sha256"] or os.path.getsize(part) != m["bytes"]:
                    sys.exit(f"sha256 mismatch for {m['path']}: the download is damaged, nothing written for this file")
                if os.path.exists(out):              # a different file is already there (a re-run on this machine?): keep it
                    if os.path.exists(out + ".local"):
                        sys.exit(f"{m['path']} and {m['path']}.local both exist and differ from the archive; move one away first")
                    os.replace(out, out + ".local")
                    print(f"kept the different file that was there as {m['path']}.local")
                os.replace(part, out)
            finally:
                if os.path.exists(part):
                    os.remove(part)
            written += 1
            print(f"restored {m['path']} ({m['bytes'] / 2 ** 20:.0f} MB)", flush=True)
        print(f"{written} files restored, {kept} already in place, all sha256 verified")
    finally:
        if tmp and os.path.isdir(tmp):
            rmtree(tmp)


if __name__ == "__main__":
    main()
