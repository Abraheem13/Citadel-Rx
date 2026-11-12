#!/usr/bin/env python
"""Create and check the Python environment of the v3 campaign (docs/ROADMAP_9of10.md).

Run it with the system Python 3.12 (3.11 also works; Sionna 2.2 needs >= 3.11), from the repository
root:

    Windows:  py -3.12 scripts\\v3\\setup_env.py
    Linux:    python3.12 scripts/v3/setup_env.py

It
  1. creates .venv (left alone if it already passes the checks; --fresh rebuilds it);
  2. installs PyTorch 2.9.1 from the CUDA 12.8 index (the RTX 50 series, compute capability 12.0,
     needs CUDA >= 12.8 builds) or the CPU build with --cpu;
  3. installs requirements-v3.txt (Sionna 2.2 among them) and this package in editable mode;
  4. checks that PyTorch sees the GPU and can run a forward and backward pass on it, and that the
     Sionna 5G LDPC encoder and decoder import;
  5. writes the exact package versions to logs/v3/env_<machine>.txt (the lock file of this machine).

Nothing outside the repository folder is changed.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENV = os.path.join(ROOT, ".venv")
TORCH = "2.9.1"
CUDA_INDEX = "https://download.pytorch.org/whl/cu128"
CPU_INDEX = "https://download.pytorch.org/whl/cpu"

CHECK = r"""
import json, platform, sys
out = {"python": sys.version.split()[0], "platform": platform.platform()}
import numpy, scipy, torch
out.update(numpy=numpy.__version__, scipy=scipy.__version__, torch=torch.__version__,
           torch_cuda=torch.version.cuda, cuda_available=torch.cuda.is_available())
if torch.cuda.is_available():
    d = torch.device("cuda")
    out["gpu"] = torch.cuda.get_device_name(0)
    out["capability"] = list(torch.cuda.get_device_capability(0))
    out["gpu_mem_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1)
    w = torch.randn(4, 256, 16, device=d, requires_grad=True)       # a stacked DeepSIC-like layer
    x = torch.randn(4, 1000, 16, device=d)
    y = torch.relu(torch.einsum("uoi,uni->uno", w, x)).sum()
    y.backward()
    torch.cuda.synchronize()
    out["gpu_kernel_ok"] = bool(torch.isfinite(w.grad).all().item())
import sionna.phy
from sionna.phy.fec.ldpc import LDPC5GEncoder, LDPC5GDecoder
enc = LDPC5GEncoder(520, 1000); dec = LDPC5GDecoder(enc, num_iter=5, hard_out=True, return_infobits=True)
u = torch.randint(0, 2, (2, 520)).float()
ok = bool((dec((2.0 * enc(u) - 1.0) * 3.0) == u).all().item())
out.update(sionna=getattr(sionna.phy, "__version__", "2.x"), ldpc_roundtrip_ok=ok)
import citadel_rx
out["citadel_rx"] = citadel_rx.__version__
print("CHECK_JSON " + json.dumps(out))
"""


def vpy() -> str:
    return os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")


def run(cmd, **kw) -> int:
    print("   $ " + " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT, **kw)


def check(cpu: bool) -> dict:
    if not os.path.exists(vpy()):
        return {}
    r = subprocess.run([vpy(), "-c", CHECK], cwd=ROOT, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("CHECK_JSON "):
            return json.loads(line[len("CHECK_JSON "):])
    print(r.stdout[-2000:] + r.stderr[-3000:])
    return {}


def healthy(info: dict, cpu: bool) -> bool:
    if not info or not info.get("ldpc_roundtrip_ok"):
        return False
    return cpu or bool(info.get("gpu_kernel_ok"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", action="store_true", help="CPU build of PyTorch (machines without an NVIDIA GPU)")
    ap.add_argument("--fresh", action="store_true", help="delete .venv and rebuild it")
    ap.add_argument("--machine", default=os.environ.get("CITADEL_MACHINE", "ws5080"),
                    help="name of this machine in the run records (default ws5080)")
    a = ap.parse_args()

    print(f"== Citadel-Rx v3 environment   ({platform.platform()}, Python {sys.version.split()[0]})")
    if sys.version_info < (3, 11):
        print("!! Python >= 3.11 is needed (Sionna 2.2). Install Python 3.12 from python.org and run:"
              "  py -3.12 scripts\\v3\\setup_env.py")
        return 1
    if platform.architecture()[0] != "64bit":
        print("!! a 64-bit Python is needed")
        return 1

    if a.fresh and os.path.isdir(VENV):
        print("   removing .venv (--fresh)")
        shutil.rmtree(VENV)
    info = check(a.cpu)
    if healthy(info, a.cpu):
        print("   .venv already passes every check; nothing to install")
    else:
        if not os.path.exists(vpy()):
            if run([sys.executable, "-m", "venv", VENV]) != 0:
                print("!! could not create .venv")
                return 1
        steps = [
            [vpy(), "-m", "pip", "install", "--upgrade", "pip", "wheel"],
            [vpy(), "-m", "pip", "install", f"torch=={TORCH}", "--index-url", CPU_INDEX if a.cpu else CUDA_INDEX],
            [vpy(), "-m", "pip", "install", "-r", "requirements-v3.txt"],
            [vpy(), "-m", "pip", "install", "--no-deps", "-e", "."],
        ]
        for s in steps:
            if run(s) != 0:
                print("!! the step above failed; send the output above")
                return 1
        info = check(a.cpu)

    print("== checks")
    for k, v in info.items():
        print(f"   {k:18s} {v}")
    if not healthy(info, a.cpu):
        if not a.cpu and info and not info.get("cuda_available"):
            print("!! PyTorch does not see the GPU: update the NVIDIA driver (>= 570 for CUDA 12.8), then"
                  " run this script again with --fresh")
        else:
            print("!! the environment is not usable; send this output")
        return 1

    os.makedirs(os.path.join(ROOT, "logs", "v3"), exist_ok=True)
    lock = os.path.join(ROOT, "logs", "v3", f"env_{a.machine}.txt")
    freeze = subprocess.run([vpy(), "-m", "pip", "freeze", "--exclude-editable"], cwd=ROOT, capture_output=True, text=True).stdout
    with open(lock, "w") as f:
        f.write("# " + json.dumps(info) + "\n" + freeze)
    print(f"== environment ready; versions written to {os.path.relpath(lock, ROOT)}")
    act = r".venv\Scripts\activate" if os.name == "nt" else "source .venv/bin/activate"
    print(f"   next:  {act}   then   python scripts{os.sep}v3{os.sep}phase0.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
