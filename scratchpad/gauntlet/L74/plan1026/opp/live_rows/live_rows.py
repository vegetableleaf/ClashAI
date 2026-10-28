"""V1-LIVEROWS step 2: live records (live_records.py) -> the HF slot-row shard layout, so rows_to_npz.py reads them unchanged.

    OPP_VOCAB=vocab_hf.json PYTHONPATH=REPO:PYARROW python -I live_rows.py --rec OUT/<block> --src SRC/<block> --logs LOGDIR --workers N
      per record chunk c####:  SRC/work/<sid>/corpus/replay_*.json (the chunk's usable records)
                               SRC/work/<sid>/rows_all.npz   dataset_gen.build, BOTH seats (fv 5, wait_stride 10, play_window 0)
                               SRC/selfcheck/<sid>.json      OUR-seat rows vs the logged live decisions (selfcheck.py)
                               SRC/work/<sid>/rows.npz       the OPPONENT seat's rows only (our seat = the bot: never a target)
                               SRC/rows/<sid>.parquet + .slot.npz, SRC/mem/<sid>.npz   slot_redrive._slot_n2p (unchanged)
                               SRC/shards/<sid>.json         done marker (resumable per chunk)
The one change to the HF builder: WAIT rows only on grid frames (tick % 10 == 0; live_records puts a frame on every grid tick),
via a wrapper around dataset.build_replay that hands it the grid frames (HF frames sit on the grid + play ticks; rows_to_npz
drops off-grid wait rows anyway). Play rows (play_frames), observers, memory tables and tokens see every frame.
Records with a card outside --vocab are left out (counted): rows_to_npz's global ids would KeyError on them."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[2]
ROOT = L74.parents[2]
os.environ.setdefault('RD_DIR', str(HERE.parents[1] / 'redrive'))
sys.path[:0] = [str(HERE), str(HERE.parent), str(L74 / 'opp_model'), str(ROOT)]
GRID = 10


def _patch():
    import pipeline.dataset_gen as DG
    if getattr(DG, '_v1lr_patched', False):
        return DG
    orig = DG.build_replay

    def grid_build_replay(rec, *a, **k):
        return orig(dict(rec, frames=[f for f in rec['frames'] if int(f['tick']) % GRID == 0]), *a, **k)
    DG.build_replay = grid_build_replay
    DG._v1lr_patched = True
    return DG


def opp_only(src: Path, dst: Path, opp_of: dict) -> dict:
    """Rows of the opponent seat only: per-row arrays sliced, per-token arrays (tok, unit_form) re-sliced through off."""
    z = np.load(src, allow_pickle=False)
    tags, rep, side = z['tags'], z['rep'], z['side'].astype(np.int64)
    opp = np.array([opp_of[str(t)] for t in tags], np.int64)
    keep = side == opp[rep]
    idx = np.where(keep)[0]
    off = z['off']
    cnt = (off[1:] - off[:-1])[idx]
    sel = np.concatenate([np.arange(off[j], off[j + 1]) for j in idx]) if len(idx) else np.zeros(0, np.int64)
    n = len(side)
    out = {}
    for k in z.files:
        a = z[k]
        if k in ('meta', 'tags'):
            out[k] = a
        elif k == 'off':
            out[k] = np.concatenate([[0], np.cumsum(cnt)]).astype(off.dtype)
        elif k in ('tok', 'unit_form'):
            out[k] = a[sel]
        elif a.shape[:1] == (n,):
            out[k] = a[idx]
        else:
            raise ValueError(f'{src}: array {k} {a.shape} is neither per row nor per token')
    np.savez(dst, **out)
    return dict(rows_all=int(n), rows_opp=int(len(idx)))


def run_chunk(job):
    rec_dir, src, logs, vocab = job
    sid = rec_dir.name
    if (src / 'shards' / f'{sid}.json').exists():
        return json.loads((src / 'shards' / f'{sid}.json').read_text())
    DG = _patch()
    import slot_redrive as SR                                  # patches DG.build -> wait_stride 10, play_window 0
    import selfcheck as SC
    t0 = time.time()
    st = Counter()
    work = src / 'work' / sid
    corpus = work / 'corpus'
    if work.exists():
        shutil.rmtree(work)
    corpus.mkdir(parents=True)
    vset = set(vocab)
    opp_of, grades, recs = {}, {}, []
    import o1_records as R
    for f in sorted(rec_dir.glob('replay_*.json')):
        rec = json.loads(f.read_text())
        cards = {R.key_of(n.split('@')[0]).replace('_', '-') for d in rec['final_decks'].values() for n in d}
        if not cards <= vset:
            st['rec_card_not_in_vocab'] += 1
            st.update(f'card_not_in_vocab:{c}' for c in cards - vset)
            continue
        lv = rec['live']
        opp_of[rec['tag']] = int(lv['opp_side'])
        hk = {s: (-10 ** 9 if v is None else int(v)) for s, v in lv['hand_known_from'].items()}
        grades[rec['tag']] = dict(tier='A', hand_known_from=hk)
        shutil.copyfile(f, corpus / f.name)
        recs.append(rec['tag'])
    st['records'] = len(recs)
    if recs:
        npz_all = work / 'rows_all.npz'
        DG.build([corpus], npz_all, grid='lattice', workers=1, val_pct=0, v3val_npz=Path('/nonexistent.npz'),
                 feature_version=5, log=None)
        sc = SC.check_npz(npz_all, logs)
        (src / 'selfcheck').mkdir(parents=True, exist_ok=True)
        (src / 'selfcheck' / f'{sid}.json').write_text(json.dumps(sc))
        st.update(opp_only(npz_all, work / 'rows.npz', opp_of))
        (src / 'rows').mkdir(parents=True, exist_ok=True)
        (src / 'mem').mkdir(parents=True, exist_ok=True)
        st['parquet_rows'] = SR._slot_n2p(work / 'rows.npz', src / 'rows' / f'{sid}.parquet', grades)
        npz_all.unlink()                                       # the self-check is kept; the both-seat rows are not
    st['seconds'] = round(time.time() - t0, 1)
    out = dict(sid=sid, **st)
    (src / 'shards').mkdir(parents=True, exist_ok=True)
    (src / 'shards' / f'{sid}.json').write_text(json.dumps(out))
    return out


def _safe(job):
    try:
        return run_chunk(job)
    except Exception as ex:                                    # noqa: BLE001 -- a failed chunk is named, the rest go on
        import traceback
        return dict(sid=job[0].name, error=repr(ex)[:500], tb=traceback.format_exc()[-1500:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rec', type=Path, required=True, help='live_records OUT/<block>')
    ap.add_argument('--src', type=Path, required=True)
    ap.add_argument('--logs', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    vocab = json.loads(Path(os.environ['OPP_VOCAB']).read_text())
    chunks = sorted(p for p in a.rec.glob('c*') if p.is_dir())
    chunks = chunks[:a.limit] if a.limit else chunks
    a.src.mkdir(parents=True, exist_ok=True)
    (a.src / 'manifest.json').write_text(json.dumps(dict(schema='v1lr-live-slot-rows.v1', rec=str(a.rec), chunks=len(chunks),
                                                         row_builder=dict(fn='pipeline.dataset_gen.build', feature_version=5,
                                                                          wait_stride=10, play_window=0, record_every=10,
                                                                          wait_rows='grid frames only'),
                                                         vocab_sha256=__import__('hashlib').sha256(
                                                             Path(os.environ['OPP_VOCAB']).read_bytes()).hexdigest()), indent=1))
    t0, tot = time.time(), Counter()
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(_safe, [(c, a.src, a.logs, vocab) for c in chunks])):
            if 'error' in r:
                print('CHUNK_ERROR', json.dumps(r), flush=True)
                tot['chunk_errors'] += 1
                continue
            tot.update({k: v for k, v in r.items() if isinstance(v, (int, float)) and k != 'seconds'})
            print(i + 1, len(chunks), r['sid'], r.get('records'), r.get('rows_opp'), r.get('seconds'), round(time.time() - t0), 's', flush=True)
    print('TOTAL', json.dumps(dict(tot)), round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
