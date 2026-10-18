"""Step d: the per-token CUE sidecar of a dataset_gen npz, from cue_drive.py outputs. The dataset is never modified (its
rocket-context artifact is hashed against it), so the no-cue twin trains on byte-identical rows.

    python scratchpad/gauntlet/L74/stepd/cue_sidecar.py --data icebow/data/pipeline/gen_dataset_v32_fv5.npz \
        --cues /workspace/stepd/cues --out /workspace/stepd/v32_cue.npz [--min-fid 0.9]

Per row (tick, side, play / wait): the SIM frame recorded at that exact tick (a play row prefers the pre-act play frame;
the native recorder's own ticks are recorded by cue_drive) -> if its SIM-vs-native body agreement fid >= --min-fid, the
row's unit tokens get the bodies' 22 cue floats through live_unit_state.align (= e1_eval.sim_cue_rows' token match,
verbatim: side + nearest position within 3 tiles, one body per token); else every token reads 0 (cue_known 0 = unknown,
exactly what a degraded live frame feeds).
Output: cue [n_tok, 22] uint8 (round(value x 255), aligned with the npz's ragged `tok`), status [n_rows] int8 (STATUS),
fid [n_rows] float16, meta (data sha256 + sizes + counts). train_gen --cue-data reads it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATUS = {0: "no_cue_file", 1: "no_frame_at_tick", 2: "below_min_fid", 3: "unused", 4: "attached"}
CUE_SCALE = 255.0
HEAD = 4                    # cue_drive body row: [team, x tiles, y tiles, hp_frac, *cue22]
FID_TILES, HP_TOL = 1.0, 0.15


def token_match(tok: np.ndarray, side: int, bodies: np.ndarray) -> tuple[float, np.ndarray]:
    """(Dice, matched mask over tok): the row's unit tokens (the DATASET's board: native-engine bodies) vs the SIM
    bodies at that tick -- same side, nearest-first within FID_TILES, hp_frac within HP_TOL when the token knows its hp.
    The token-level twin of cue_drive.body_fid (no card id in a token: side + position + hp only)."""
    ok = np.zeros(len(tok), bool)
    ti = np.flatnonzero((tok[:, 13] == 0) & ((tok[:, 1] > 0) | (tok[:, 2] > 0)))
    if not len(ti) and not len(bodies):
        return 1.0, ok
    if not len(ti) or not len(bodies):
        return 0.0, ok
    bx, by = bodies[:, 1] / 18.0, 1.0 - bodies[:, 2] / 32.0
    if side == 1:                                             # obs_contract._engine_xy: side 1 sees the board mirrored
        bx, by = 1.0 - bx, 1.0 - by
    d = np.hypot((tok[ti, 4:5] - bx) * 18.0, (tok[ti, 5:6] - by) * 32.0)
    d[(tok[ti, 1:2] > 0) != (bodies[:, 0] == side)] = np.inf
    d[(tok[ti, 7:8] > 0) & (np.abs(tok[ti, 6:7] - bodies[:, 3]) > HP_TOL)] = np.inf
    m = 0
    while True:
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if not d[i, j] <= FID_TILES:
            break
        ok[ti[i]] = True
        m += 1
        d[i, :] = np.inf
        d[:, j] = np.inf
    return 2 * m / (len(ti) + len(bodies)), ok


def frame_index(cz: dict) -> tuple[dict, dict]:
    """(periodic frame by tick, first pre-act play frame by tick) -> row index into the cue file."""
    per, play = {}, {}
    for i, (t, p) in enumerate(zip(cz["tick"].tolist(), cz["pidx"].tolist())):
        (per if p < 0 else play).setdefault(int(t), i)
    return per, play


def replay_cue(tok: np.ndarray, n_tok: np.ndarray, tick: np.ndarray, side: np.ndarray, gate: np.ndarray,
               cz: dict | None, min_fid: float, token_gate: bool = True):
    """One replay's rows -> (cue [len(tok), 22] uint8, status [rows] int8, native fid [rows] float32 (NaN = none),
    token fid [rows] float32). ``tok`` = the rows' kept unit tokens back to back (dataset layout), ``n_tok`` their
    counts. The --min-fid bar reads the native fid when the drive had one, else the token Dice (token_match).
    ``token_gate``: a token whose SIM body is not within FID_TILES / HP_TOL of it keeps 0 cues on an accepted row."""
    from pipeline.live_unit_state import align
    from pipeline.model_gen import CUE_N
    cue = np.zeros((len(tok), CUE_N), np.uint8)
    status = np.zeros(len(n_tok), np.int8)
    fid = np.full(len(n_tok), np.nan, np.float32)
    tfid = np.full(len(n_tok), np.nan, np.float32)
    if cz is None:
        return cue, status, fid, tfid
    per, play = frame_index(cz)
    off, bodies, ffid = cz["off"], cz["bodies"], cz["fid"]
    starts = np.concatenate([[0], np.cumsum(n_tok)])
    for i in range(len(n_tok)):
        t = int(tick[i])
        j = (play.get(t, per.get(t)) if gate[i] else per.get(t))
        if j is None:
            status[i] = 1
            continue
        a, b = starts[i], starts[i + 1]
        bb = bodies[off[j]:off[j + 1]]
        tfid[i], ok = token_match(tok[a:b], int(side[i]), bb)
        fid[i] = ffid[j]                                      # native fid (NaN in pod mode); the bar reads it if finite
        if (fid[i] if np.isfinite(fid[i]) else tfid[i]) < min_fid:
            status[i] = 2
            continue
        rows = align(tok[a:b], np.ones(b - a, bool), int(side[i]), [(int(r[0]), float(r[1]), float(r[2]), r[HEAD:]) for r in bb])
        if token_gate:
            rows[~ok] = 0.0
        cue[a:b] = np.rint(np.clip(rows, 0.0, 1.0) * CUE_SCALE).astype(np.uint8)
        status[i] = 4
    return cue, status, fid, tfid


def load_cue_file(cues: Path, tag: str):
    p = cues / f"cue_{tag}.npz"
    if not p.is_file():
        return None
    with np.load(p, allow_pickle=False) as z:
        return {k: z[k] for k in ("tick", "pidx", "fid", "off", "bodies")}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--cues", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-fid", type=float, default=0.9)
    ap.add_argument("--no-token-gate", action="store_true", help="keep cues on tokens with no 1-tile / hp SIM match")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    z = np.load(a.data, allow_pickle=False)
    tok, off, tick, side, gate, rep = (z[k] for k in ("tok", "off", "tick", "side", "y_gate", "rep"))
    tags = [str(t) for t in z["tags"]]
    n_rows = len(tick)
    cue = np.zeros((len(tok), 22), np.uint8)
    status = np.zeros(n_rows, np.int8)
    fid = np.full(n_rows, np.nan, np.float32)
    tfid = np.full(n_rows, np.nan, np.float32)
    order = np.argsort(rep, kind="stable")
    bounds = np.flatnonzero(np.diff(rep[order])) + 1
    for k, ids in enumerate(np.split(order, bounds)):
        if not len(ids):
            continue
        if np.any(np.diff(ids) != 1):
            raise ValueError("rows of one replay are not contiguous: the sidecar assumes dataset_gen's layout")
        r0, r1 = int(ids[0]), int(ids[-1]) + 1
        t0k, t1k = int(off[r0]), int(off[r1])
        c, s, f, tf = replay_cue(tok[t0k:t1k], np.diff(off[r0:r1 + 1]), tick[r0:r1], side[r0:r1], gate[r0:r1],
                                 load_cue_file(a.cues, tags[int(rep[r0])]), a.min_fid, not a.no_token_gate)
        cue[t0k:t1k], status[r0:r1], fid[r0:r1], tfid[r0:r1] = c, s, f, tf
        if k % 500 == 0:
            print(f"{k} replays {time.monotonic() - t0:.0f}s", flush=True)
    counts = {STATUS[i]: int((status == i).sum()) for i in STATUS}
    known = cue[:, 0] > 0
    both = np.isfinite(fid) & np.isfinite(tfid)                # rows with a NATIVE fid: validates the token fid
    meta = dict(data=str(a.data), data_sha256=sha256(a.data), n_rows=n_rows, n_tok=int(len(tok)), min_fid=a.min_fid,
                token_gate=not a.no_token_gate, status=counts, rows_attached=counts["attached"] / max(1, n_rows),
                tokens_known=float(known.mean()),
                play_rows_attached=float((status[gate == 1] == 4).mean()), wait_rows_attached=float((status[gate == 0] == 4).mean()),
                fid_vs_token_fid=dict(rows=int(both.sum()), corr=float(np.corrcoef(fid[both], tfid[both])[0, 1]) if both.sum() > 2 else None,
                                      same_side_of_bar=float(np.mean((fid[both] >= a.min_fid) == (tfid[both] >= a.min_fid))) if both.any() else None),
                cue_scale=CUE_SCALE, seconds=round(time.monotonic() - t0))
    np.savez(a.out, cue=cue, status=status, fid=fid.astype(np.float16), token_fid=tfid.astype(np.float16),
             meta=np.asarray(json.dumps(meta)))
    print("CUE_SIDECAR_DONE", json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
