"""L67a: build a live-like twin of an S1 dataset -- same corpus, same rows, every BoardState passed through
``obs_contract.degrade`` (the measured live shift: recall/precision, side unknown 25%, no unit hp / deploy / age,
integer elixir, no king hp / opp elixir, conf redrawn, 0.45-tile position noise) BEFORE ``to_tokens``.

Rows, splits and targets are identical to the clean build (the split is a crc32 of the tag; row order is the
corpus file order), so a checkpoint's clean-vs-degraded scores are a paired comparison on the same states.

Moved from scratchpad/gauntlet/L67/build_degraded.py; behaviour unchanged (only the repo-root lookup moved).

usage (from the repo root):
  icebow\\.venv\\Scripts\\python.exe tools\\build_degraded.py icebow --corpus <corpus dir> --out <npz> [--seed 0] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline import dataset as ds                      # noqa: E402
from pipeline.obs_contract import degrade               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--corpus", type=Path, default=None)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    orig_add = ds._Rows.add
    n = {"rows": 0}

    def add(self, bs, **kw):
        n["rows"] += 1
        return orig_add(self, degrade(bs, rng), **kw)

    ds._Rows.add = add
    s = ds.build(a.deck, a.corpus, a.out, limit=a.limit)
    s["degraded_rows"] = n["rows"]
    s["degrade_seed"] = a.seed
    print(json.dumps(s, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
