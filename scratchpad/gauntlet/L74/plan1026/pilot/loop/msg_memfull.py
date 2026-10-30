"""MEM-FULL: a compare.py message whose learner weights carry memory_e_max / memory_board_snap exactly as rl_royale's
learner sends them (the init widened by model_gen.GenModel.mem_full: zero snapshot columns, buffer mem.full); base, jobs
and every other tensor unchanged. Run from the repo root (imports pipeline).

    python msg_memfull.py MSG.pkl OUT.pkl [--e-max 256] [--snap 1] [--jobs N]
"""
from __future__ import annotations

import argparse
import io
import pickle
from pathlib import Path


def main(argv=None) -> int:
    import torch
    from pipeline import rl_royale as R
    from pipeline.model_gen import GenModel
    ap = argparse.ArgumentParser()
    ap.add_argument("msg")
    ap.add_argument("out")
    ap.add_argument("--e-max", type=int, default=256)
    ap.add_argument("--snap", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=0)
    a = ap.parse_args(argv)
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    msd = torch.load(io.BytesIO(sd), map_location="cpu")
    extra = {k: msd.pop(k) for k in list(msd) if k.startswith((R.ABILITY_SD, R.POSTURE_SD))}
    g = base["gen"]
    net = GenModel(d=int(base["d"]), layers=int(base["layers"]), d_c=int(g["d_c"]), n_cards=len(g["card_vocab"]),
                   feature_version=int(g.get("feature_version", 1)))
    net.load_state_dict(msd)
    net.mem_full(a.e_max, bool(a.snap))
    out = {**net.state_dict(), **extra}
    assert set(out) == set(msd) | set(extra) | {"mem.full"}, sorted(set(out) ^ (set(msd) | set(extra)))
    buf = io.BytesIO()
    torch.save(out, buf)
    Path(a.out).write_bytes(pickle.dumps((base, update, buf.getvalue(), jobs[:a.jobs] if a.jobs else jobs)))
    print(f"mem.full {out['mem.full'].tolist()}, ev_in {tuple(out['mem.ev_in.weight'].shape)}, jobs {len(jobs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
