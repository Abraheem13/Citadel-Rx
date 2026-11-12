#!/usr/bin/env python3
"""Add the files a machine holds that are not on GitHub to the `snapshots` branch.

A machine that ran part of a campaign keeps files that never reach the main branch: the level
snapshots (`*.levels.npz`, ignored by .gitignore and too large for GitHub as single files), the
pretrained-weight cache (`cache/`), and whatever else is untracked, ignored or modified in its clone
(figures and tables it generated from its own snapshots, console logs, partial records). This script
stores all of them on the `snapshots` branch under `machines/<machine>/`, the large ones cut into parts
of 90 MB, writes `manifests/<machine>.json` (size, sha256 and parts of every file) and pushes. It never
changes the clone it reads from, and it does not download the files that are already on the branch.

One command, from anywhere (python3 or python):

    python3 archive_machine.py --machine pool4 --repo /path/to/Citradel-Rx          # add --dry to only list

In a clone of main the same script is scripts/archive_machine_snapshots.py and --repo defaults to that
clone. On a machine that has only the clone, fetch the script from the branch without downloading the
branch:

    git init -q snaparch && cd snaparch \
      && git remote add origin https://github.com/abraheemrashid99-sys/Citradel-Rx \
      && git fetch -q --depth 1 --filter=blob:none origin snapshots \
      && git show FETCH_HEAD:tools/archive_machine.py > archive_machine.py

The script works in a staging directory of its own (a small git repository next to the clone, or the
current directory if that already is one with the remote `origin`), which it removes when everything is
verified on the branch.

How it works: every file (or part) is written as a git blob with `git hash-object`; the tree of the
branch tip is read into a private index (only tree objects are needed, the blobs of the other machines
stay on GitHub), the new entries are added, and the resulting commit is pushed on top of the tip. If
another machine pushed in between, the push is rejected; the script then fetches the new tip, rebuilds
the commit on it (the paths of two machines never overlap) and pushes again. Files are pushed in groups
of at most 400 MB; the manifest goes in with the last group, so a manifest on the branch means that all
of its files are there. At the end the script reads the branch back and checks every blob.

Running it again on the same machine adds what is new: the manifest keeps the files stored earlier even
if they are no longer in the clone, a file restored from another machine's archive is not stored twice,
and a file whose content changed since it was stored stops the run unless --replace is given.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

BRANCH = "snapshots"
PART = 90 * 2 ** 20            # GitHub refuses files over 100 MB
GROUP = 400 * 2 ** 20          # bytes per push
SKIP = ["*/__pycache__/*", "__pycache__/*", "*.pyc", ".pytest_cache/*", "*/.pytest_cache/*", ".venv/*", "*.egg-info/*",
        "paper/main.aux", "paper/main.log", "paper/main.out", "paper/build.log", ".DS_Store", "*/.DS_Store",
        "*.restoring", ".git/*"]
FAST = ["-c", "core.compression=0", "-c", "core.looseCompression=0", "-c", "pack.window=0", "-c", "gc.auto=0",
        "-c", "http.postBuffer=1048576000"]


WORK = None                    # the staging repository; set in main()


def git(*args, cwd=None, data=None, check=True, env=None, quiet=True):
    r = subprocess.run(["git", *FAST, *args], cwd=cwd or WORK, input=data, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE if quiet else None)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args[:3])} ... failed:\n{(r.stderr or b'').decode(errors='replace')}")
    return r


def rmtree(path: str) -> None:
    """Remove a directory tree; git marks its object files read-only, which stops a plain rmtree on Windows."""
    def fix(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


def skip(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in SKIP)


def inventory(repo: str) -> tuple[list[str], list[str]]:
    """Every file of the clone that is not exactly what its HEAD commit holds: untracked, ignored, modified
    or staged. Also returns the entries that cannot be stored (nested repositories, symbolic links)."""
    out, left = set(), set()
    for args in (["ls-files", "-z", "--others"], ["ls-files", "-z", "--modified"],
                 ["diff-index", "--cached", "--name-only", "-z", "HEAD"]):
        for rel in git(*args, cwd=repo).stdout.decode().split("\0"):
            if not rel or skip(rel) or skip(rel.rstrip("/") + "/x"):
                continue
            full = os.path.join(repo, rel)
            if os.path.islink(full) or os.path.isdir(full):
                left.add(rel)
            elif os.path.isfile(full):
                out.add(rel)
    return sorted(out), sorted(left)


def kind_and_path(rel: str, machine: str) -> tuple[str, str]:
    if rel.endswith(".levels.npz"):
        return "snapshot", rel                               # goes back next to its JSON record
    if rel.startswith("cache/"):
        return "pretrain_cache", rel                         # goes back into cache/ (only on request, per machine)
    return "machine_file", f"results_archive/{machine}/{rel}"   # never read by the analysis


def fetch_tip() -> str:
    for attempt in range(5):
        r = git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", BRANCH, check=False)
        if r.returncode == 0:
            return git("rev-parse", "FETCH_HEAD").stdout.decode().strip()
        time.sleep(2 * 2 ** attempt)
    sys.exit("cannot fetch the snapshots branch:\n" + r.stderr.decode(errors="replace"))


def commit_on(tip: str, entries: dict[str, str], message: str) -> str | None:
    """A commit whose tree is the tree of `tip` plus `entries` (stored path -> blob); None if nothing changes."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, "index"))
        git("read-tree", tip, env=env)
        info = "".join(f"100644 {sha}\t{path}\0" for path, sha in sorted(entries.items()))
        git("update-index", "-z", "--index-info", data=info.encode(), env=env)
        tree = git("write-tree", "--missing-ok", env=env).stdout.decode().strip()
    if tree == git("rev-parse", f"{tip}^{{tree}}").stdout.decode().strip():
        return None
    if git("config", "--bool", "commit.gpgsign", check=False).stdout.decode().strip() == "true":
        r = git("commit-tree", tree, "-p", tip, "-S", "-m", message, check=False)   # sign as `git commit` would here
        if r.returncode == 0:
            return r.stdout.decode().strip()
        print("   signing the commit failed, committing unsigned", flush=True)
    return git("commit-tree", tree, "-p", tip, "-m", message).stdout.decode().strip()


def push_group(entries: dict[str, str], message: str) -> str:
    """Put `entries` on the branch, whatever the other machines push meanwhile. Returns the new tip."""
    last = ""
    for attempt in range(12):
        tip = fetch_tip()
        commit = commit_on(tip, entries, message)
        if commit is None:
            return tip                                       # already there (a re-run)
        r = git("push", "-q", "origin", f"{commit}:refs/heads/{BRANCH}", check=False)
        if r.returncode == 0:
            return commit
        last = r.stderr.decode(errors="replace")
        if any(w in last for w in ("403", "Permission", "denied", "Authentication failed", "could not read Username")):
            sys.exit("the push was refused (no permission to write to the repository from here):\n" + last)
        print(f"   push not accepted (attempt {attempt + 1}): {last.strip().splitlines()[-1] if last.strip() else '?'}; retrying", flush=True)
        time.sleep(min(60, 3 * 2 ** attempt))
    sys.exit("push failed 12 times:\n" + last)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--machine", required=True, help="the name of this machine, e.g. pool4, helper, windows")
    here = os.path.dirname(os.path.abspath(__file__))
    default_repo = os.path.dirname(here) if os.path.isdir(os.path.join(os.path.dirname(here), "citadel_rx")) else None
    ap.add_argument("--repo", default=default_repo, required=default_repo is None,
                    help="the clone of Citradel-Rx on this machine (read only)")
    ap.add_argument("--workdir", default=None, help="staging directory (default: next to the clone)")
    ap.add_argument("--dry", action="store_true", help="list what would be stored and stop")
    ap.add_argument("--replace", action="store_true",
                    help="store the current content of files that changed since this machine stored them")
    ap.add_argument("--trailer", default="", help="text appended to the commit messages (attribution lines)")
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    if not os.path.exists(os.path.join(repo, ".git")):
        sys.exit(f"{repo} is not a git clone")
    if not all(c.isalnum() or c in "-_" for c in args.machine) or args.machine == "cloud":
        sys.exit("--machine: letters, digits, - and _ only (and not 'cloud', the coordinating machine)")

    global WORK
    real = lambda d: os.path.normcase(os.path.realpath(d))          # a symlinked or differently cased path is the same place
    inside = lambda d: real(d) == real(repo) or real(d).startswith(real(repo) + os.sep)
    out = lambda *a, cwd: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    url = out("remote", "get-url", "origin", cwd=repo).stdout.strip()
    norm = lambda u: re.sub(r"\.git$", "", u.strip().rstrip("/").lower())
    same = lambda u: bool(u.strip()) and norm(u) == norm(url)
    cwd = os.getcwd()
    default = os.path.join(os.path.dirname(os.path.realpath(repo)), f".snaparch_{args.machine}")
    if args.workdir:
        WORK = os.path.abspath(args.workdir)
    elif (os.path.isdir(os.path.join(cwd, ".git")) and not inside(cwd) and url
          and same(out("remote", "get-url", "origin", cwd=cwd).stdout.strip())
          and out("rev-parse", "-q", "--verify", "HEAD", cwd=cwd).returncode != 0):
        WORK = cwd            # an empty staging repository of this project, made as in the docstring: no commit checked out
    else:
        WORK = default
    ours = real(WORK) == real(default)                               # removed once all is verified
    if inside(WORK):
        sys.exit("the staging directory must be outside the clone")
    if not git("branch", "-r", "--contains", "HEAD", cwd=repo, check=False).stdout.strip():
        print("WARNING: the clone has commits that are on no remote branch; push them, this script only stores "
              "files that are untracked, ignored or modified", flush=True)

    files, left = inventory(repo)
    for rel in left:
        print(f"NOT STORED (a nested repository or a symbolic link; store its content separately): {rel}", flush=True)
    total = sum(os.path.getsize(os.path.join(repo, f)) for f in files)
    print(f"{args.machine}: {len(files)} files not on GitHub, {total / 2 ** 20:.0f} MB "
          f"(HEAD {git('rev-parse', '--short', 'HEAD', cwd=repo).stdout.decode().strip()})", flush=True)
    if args.dry or not files:
        for f in files:
            print(f"  {os.path.getsize(os.path.join(repo, f)):>11d}  {kind_and_path(f, args.machine)[0]:14s} {f}")
        return

    if not os.path.isdir(os.path.join(WORK, ".git")):
        if not url:
            sys.exit(f"{repo} has no remote 'origin'")
        os.makedirs(WORK, exist_ok=True)
        git("init", "-q", ".")
        git("remote", "add", "origin", url)
    for key in ("user.name", "user.email"):                         # the clone's identity, if only the clone has one
        if not out("config", key, cwd=WORK).stdout.strip() and out("config", key, cwd=repo).stdout.strip():
            git("config", key, out("config", key, cwd=repo).stdout.strip())
    if git("var", "GIT_COMMITTER_IDENT", check=False).returncode != 0:
        sys.exit('git does not know who you are; run:  git config --global user.name "Your Name"  and  '
                 'git config --global user.email "you@example.com"  and start again')

    # what the branch already holds: this machine's earlier manifest, and the files of the other machines
    tip = fetch_tip()
    names = [n for n in git("ls-tree", "-r", "--name-only", "-z", tip, "--", "MANIFEST.json", "manifests").stdout.decode().split("\0") if n]
    earlier, elsewhere = {}, {}
    for n in names:
        for e in json.loads(git("cat-file", "blob", f"{tip}:{n}").stdout.decode()):
            if e.get("machine") == args.machine and n == f"manifests/{args.machine}.json":
                earlier[e["source"]] = e
            else:
                elsewhere[(e["path"], e["sha256"])] = e.get("machine", "?")
    digest = {}
    for rel in files:
        h = hashlib.sha256()
        with open(os.path.join(repo, rel), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                h.update(chunk)
        digest[rel] = h.hexdigest()
    restored = [rel for rel in files if (rel, digest[rel]) in elsewhere]
    for rel in restored:
        print(f"already archived by {elsewhere[(rel, digest[rel])]} (a restored copy), not stored again: {rel}", flush=True)
    files = [rel for rel in files if rel not in restored]
    changed = [rel for rel in files if rel in earlier and earlier[rel]["sha256"] != digest[rel]]
    if changed and not args.replace:
        sys.exit(f"{len(changed)} files changed since {args.machine} stored them, e.g. {changed[:3]}.\n"
                 "If this is another machine, give it another --machine name. If the new content should replace the stored "
                 "one, run again with --replace (the stored version stays in the history of the branch).")
    total = sum(os.path.getsize(os.path.join(repo, f)) for f in files)
    if not files and not earlier:
        print("nothing left to store: every file is already archived")
        if ours:
            rmtree(WORK)
        return

    manifest, blobs = [], []                                 # blobs: (stored path, blob sha, bytes)
    for rel in files:
        src = os.path.join(repo, rel)
        size = os.path.getsize(src)
        kind, dest = kind_and_path(rel, args.machine)
        stored = f"machines/{args.machine}/{rel}"
        h, parts, read = hashlib.sha256(), [], 0
        with open(src, "rb") as f:
            for i in range(max(1, -(-size // PART))):        # one blob for a small (or empty) file, else 90 MB parts
                data = f.read(PART)
                h.update(data)
                read += len(data)
                p = stored if size <= PART else f"{stored}.part{i:02d}"
                sha = git("hash-object", "-w", "--stdin", data=data).stdout.decode().strip()
                parts.append(p)
                blobs.append((p, sha, len(data)))
            if read != size or f.read(1) or h.hexdigest() != digest[rel]:
                sys.exit(f"{rel} changed while it was read; nothing pushed")
        manifest.append({"path": dest, "kind": kind, "machine": args.machine, "source": rel, "bytes": size,
                         "sha256": h.hexdigest(), "parts": parts})
    kept = [e for src, e in sorted(earlier.items()) if src not in set(files)]
    manifest += kept
    mpath = f"manifests/{args.machine}.json"
    msha = git("hash-object", "-w", "--stdin", data=(json.dumps(manifest, indent=1) + "\n").encode()).stdout.decode().strip()

    groups, cur, cur_bytes = [], {}, 0
    for p, sha, n in sorted(blobs, key=lambda b: (b[2] > 2 ** 20, b[0])):   # small files first
        if cur and cur_bytes + n > GROUP:
            groups.append(cur)
            cur, cur_bytes = {}, 0
        cur[p] = sha
        cur_bytes += n
    cur[mpath] = msha
    groups.append(cur)

    trailer = ("\n\n" + args.trailer.replace("\\n", "\n")) if args.trailer else ""
    for g, entries in enumerate(groups):
        mb = sum(n for p, _, n in blobs if p in entries) / 2 ** 20
        print(f"pushing group {g + 1}/{len(groups)}: {len(entries)} files, {mb:.0f} MB ...", flush=True)
        push_group(entries, f"{args.machine}: files not on main, group {g + 1} of {len(groups)}\n\n"
                            f"Level snapshots, pretrained-weight cache and other untracked or ignored files of the machine\n"
                            f"{args.machine}; manifests/{args.machine}.json lists them with size, sha256 and parts.{trailer}")

    tip = fetch_tip()
    want = dict((p, sha) for p, sha, _ in blobs)
    want[mpath] = msha
    listing = git("ls-tree", "-r", "-z", tip, "--", f"machines/{args.machine}", mpath).stdout.decode().split("\0")
    have = {line.split("\t", 1)[1]: line.split()[2] for line in listing if line}
    missing = [p for p, sha in want.items() if have.get(p) != sha] + [p for e in kept for p in e["parts"] if p not in have]
    if missing:
        sys.exit(f"NOT VERIFIED: {len(missing)} files are not on the branch as expected, e.g. {missing[:3]}")
    kinds = {}
    for m in manifest:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    if ours:
        rmtree(WORK)
    if kept:
        print(f"{len(kept)} files stored earlier and no longer in the clone stay in the manifest")
    print(f"VERIFIED {args.machine}: {len(manifest)} files ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}), "
          f"{total / 2 ** 20:.0f} MB in {len(blobs)} blobs on {BRANCH} at {tip[:12]}")


if __name__ == "__main__":
    main()
