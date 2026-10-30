"""LOOP-INT: one LOOP-SRV PolicyServer process (pipeline/policy_server.py) for the fast loop's producers. Models: the
learner (architecture from ``--learner`` = the run's init checkpoint; weights from the watch dir, written per update by
fastloop / bench: DIR/learner.v{V:08d}.pt + DIR/learner.latest) and every frozen opponent checkpoint (``--opp``, served
under its repo-relative path). fp32 (TF32 off: the lead's ruling), eager by default.

usage: python serve.py --listen /dev/shm/loop/srv0.sock --device cuda:0 --watch DIR --learner PATH [--opp PATH ...]
       [--block-max 512 --max-batch 2048 --mode eager|graphs]
Writes LISTEN.ready when it accepts producers; stats every 30 s to LISTEN.stats.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path[:0] = [str(REPO)]

# the producer's row block (producer.Rows + ID_SPLIT, after GenPolicy.row's zeroing): key -> (trailing shape, dtype)
ROW = {"tok": ((64, 14), "<f4"), "mask": ((64,), "|b1"), "sc": ((70,), "<f4"), "past": ((3, 5), "<f4"),
       "hand_card": ((4,), "<i8"), "hand_form": ((4,), "<i8"), "next_card": ((), "<i8"), "next_form": ((), "<i8"),
       "deck_card": ((8,), "<i8"), "deck_form": ((8,), "<i8"), "hand_slot": ((4,), "<i8"), "slot_card": ((9,), "<i8"),
       "slot_form": ((9,), "<i8"), "unit_form": ((64,), "|i1"), "opp_past": ((3, 5), "<f4"),
       "opp_cycle": ((8, 4), "<f4"), "projectiles": ((64, 8), "<f4"), "effects": ((32, 6), "<f4"),
       "own_ability": ((8, 7), "<f4"), "cue": ((64, 22), "<f4"),
       "tgt": ((64, 8), "<f4"), "tgt_idx": ((64,), "<i8")}                  # TARGET-OBS (CfTgt)


def spec_for(model) -> dict:
    from pipeline import e1_eval as E
    from pipeline import match_memory as MM
    o = MM.opts(getattr(model.model, "mem", None))      # MEM-FULL: the model's e_max / snap (absent = 128 / off)
    em, nf = o["e_max"], MM.F_SNAP if o["snap"] else MM.F
    row = {**ROW, "mem_ev": ((em, nf), "<f4"), "mem_mask": ((em,), "|b1"), "mem_card": ((em,), "<i8"),
           "mem_form": ((em,), "<i8"), "mem_summary": ((MM.S_V2,), "<f4"), "mem_answer": ((), "<i8")}   # CfMem rows
    return {k: row[k] for k in E.gen_row_keys(model.model)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", required=True)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--watch", required=True)
    ap.add_argument("--learner", required=True)
    ap.add_argument("--opp", nargs="*", default=[])
    ap.add_argument("--block-max", type=int, default=512)
    ap.add_argument("--max-batch", type=int, default=2048)
    ap.add_argument("--mode", default="eager")
    ap.add_argument("--no-learner", action="store_true", help="F2' shard: the frozen opponents only (--learner = arch only)")
    ap.add_argument("--mem-full", default="", help="MEM-FULL E_MAX,SNAP: the learner's memory_e_max / memory_board_snap "
                    "(rl_royale widens the init the same way: model_gen mem_full; absent = the init's layout)")
    a = ap.parse_args()
    from pipeline import e1_eval as E
    from pipeline.policy_server import PolicyServer
    models = []
    if not a.no_learner:
        pol, _ = E.load_policy(REPO / a.learner if not Path(a.learner).is_absolute() else a.learner, a.device)
        if a.mem_full:
            e_max, snap = (int(v) for v in a.mem_full.split(","))
            pol.model.mem_full(e_max, bool(snap))
        models.append({"name": "learner", "policy": pol, "spec": spec_for(pol), "block_max": a.block_max, "watch": a.watch})
    for p in a.opp:
        pol, _ = E.load_policy(REPO / p, a.device)
        if E.is_timing(pol):                             # P2 timing head: the producer forwards it in-process
            continue
        models.append({"name": p, "policy": pol, "spec": spec_for(pol), "block_max": a.block_max})
    Path(a.listen).parent.mkdir(parents=True, exist_ok=True)
    Path(a.listen).unlink(missing_ok=True)
    # graphs (ROLLOUT-SPEED): capture every model x copy x bucket NOW, before any producer or server thread runs (a
    # lazy capture mid-run raced the server's other threads / memory pressure and its failure poisoned the shared pool);
    # the warm rows' values do not matter (the graph is the shape's kernel sequence). eager: start() as before.
    warm = {m["name"]: {k: (np.ones if np.dtype(dt) == np.bool_ else np.zeros)((1, *shape), dt)
                        for k, (shape, dt) in m["spec"].items()} for m in models} if a.mode == "graphs" else None
    S = PolicyServer(models, device=a.device, max_batch=a.max_batch, mode=a.mode, listen=a.listen,
                     block_max=a.block_max).start(warm)
    Path(a.listen + ".ready").write_text("ok\n")
    while True:
        time.sleep(30)
        Path(a.listen + ".stats.json").write_text(json.dumps(S.stats, default=float))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
