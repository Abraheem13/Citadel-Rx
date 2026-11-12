"""JSON run records. Every number in the paper is regenerated from these."""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
from typing import Any, Dict


def git_commit() -> str:
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return subprocess.check_output(["git", "-C", root, "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _default(o):
    import numpy as np
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(f"not serialisable: {type(o)}")


def save_record(record: Dict[str, Any], out_dir: str, name: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    record = dict(record)
    record["saved_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    record["git_commit"] = git_commit()
    path = os.path.join(out_dir, f"{name}.json")
    tmp = path + ".part"   # write then rename, so an interrupted run never leaves a truncated record
    with open(tmp, "w") as f:
        json.dump(record, f, indent=1, default=_default)
    os.replace(tmp, path)
    return path


def load_records(out_dir: str):
    recs = []
    for fn in sorted(os.listdir(out_dir)):
        if fn.endswith(".json"):
            with open(os.path.join(out_dir, fn)) as f:
                recs.append(json.load(f))
    return recs
