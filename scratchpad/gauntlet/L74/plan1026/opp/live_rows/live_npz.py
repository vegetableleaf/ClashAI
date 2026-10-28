"""V1-LIVEROWS step 3: live slot-row shards (live_rows.py) -> the train_gen file for P2-OPP2's live fine-tune.

    python -I live_npz.py --src SRC/<block> --index REC/<block>/index.jsonl --block train|calibration \
        --vocab vocab_hf.json --deck-map HF_TRAIN_ROWS(dir or npz with deck_keys) --out OUT_DIR [--tail 0.1]

= rows_to_npz.py (called unchanged: --keep-wait 1, i.e. every slot kept, row_w 1; ids from --deck-map) + the live context columns
it cannot know, overwritten in the output (an EXTRACTED dir of NAME.npy, as train_gen --data reads):
  * ctx_band 4 / 5 / 6 = live L (ladder 12.0-12.9k) / M (ladder >= 13k) / R (Ranked); ctx_mode 1 = Ranked (pathOfLegend), 2 = ladder;
    ctx_era 2 = live.
  * split, strictly by time: train block -> 0, its newest --tail share of matches (by log name) -> 1 (the time-ordered tail to stop
    on); calibration block -> 2 (level A). The sealed block never reaches this script (live_records refuses it by name).
  * ab_ok = ab_ev = ab_tick = 0: an opponent's ability press is not detected from the reader (no labels; the ability head is not
    trained on live rows).
Writes OUT_DIR (rows), OUT_DIR_memory.npz (rows_to_npz's memory tables), OUT_DIR.sizes.json (rows / play rows / matches per band,
archetype, split)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
BAND = {'L': 4, 'M': 5, 'R': 6}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, required=True)
    ap.add_argument('--index', type=Path, required=True)
    ap.add_argument('--block', choices=('train', 'calibration'), required=True)
    ap.add_argument('--vocab', type=Path, required=True)
    ap.add_argument('--deck-map', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--tail', type=float, default=0.1)
    a = ap.parse_args()
    import rows_to_npz as RN
    empty = a.out.parent / 'no_hf_replays'
    empty.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_name(a.out.name + '.npz')                 # rows_to_npz at HEAD writes one npz; extract it to the dir
    RN.main(['--src', str(a.src), '--vocab', str(a.vocab), '--hf-replays', str(empty), '--out', str(tmp),
             '--keep-wait', '1', '--deck-map', str(a.deck_map)])
    import zipfile
    with zipfile.ZipFile(tmp) as z:
        z.extractall(a.out)
    tmp.unlink()
    tmp.with_name(tmp.stem + '_memory.npz').rename(a.out.with_name(a.out.name + '_memory.npz'))
    info = {}
    for line in open(a.index):
        j = json.loads(line)
        if 'live' in j and j['live'].get('opp_deck'):
            info[j['stem']] = j['live']
    tags = np.load(a.out / 'tags.npy')
    rep = np.load(a.out / 'rep.npy')
    lv = [info[str(t)] for t in tags]
    if any(x['block'] != a.block for x in lv):
        raise SystemExit('a tag of another block in the rows')
    order = sorted(range(len(tags)), key=lambda i: str(tags[i]))
    n_tail = int(round(len(tags) * a.tail)) if a.block == 'train' else 0
    tail = set(order[len(order) - n_tail:]) if n_tail else set()
    sp_tag = np.array([2 if a.block == 'calibration' else 1 if i in tail else 0 for i in range(len(tags))], np.int8)
    band_tag = np.array([BAND[x['band']] for x in lv], np.int8)
    mode_tag = np.array([1 if x['band'] == 'R' else 2 for x in lv], np.int8)
    np.save(a.out / 'split.npy', sp_tag[rep])
    np.save(a.out / 'ctx_band.npy', band_tag[rep])
    np.save(a.out / 'ctx_mode.npy', mode_tag[rep])
    np.save(a.out / 'ctx_era.npy', np.full(len(rep), 2, np.int8))
    for k in ('ab_ok', 'ab_ev', 'ab_tick'):
        np.save(a.out / f'{k}.npy', np.zeros(len(rep), np.int8))
    meta = json.loads(str(np.load(a.out / 'meta.npy')))
    gate = np.load(a.out / 'y_gate.npy')
    slot_ok, slot_ev, card_ok = (np.load(a.out / f'{k}.npy') for k in ('slot_ok', 'slot_ev', 'card_ok'))
    sizes = defaultdict(Counter)
    for i, x in enumerate(lv):
        m = rep == i
        for key in (f"band:{x['band']}", f"arch:{x['arch']}", f'split:{int(sp_tag[i])}', 'all'):
            s = sizes[key]
            s['matches'] += 1
            s['rows'] += int(m.sum())
            s['play_rows'] += int((m & (gate == 1)).sum())
            s['play_rows_card_ok'] += int((m & (gate == 1) & (card_ok == 1)).sum())
            s['slot_rows'] += int((m & (slot_ok == 1)).sum())
            s['slot_events'] += int((m & (slot_ev == 1)).sum())
    meta.update(source=f'live opponent seats ({a.block} block, V1-LIVEROWS)', eras={'1': 'hf', '2': 'live'},
                bands={'1': 'hf_pol', '2': 'hf_other', '3': 'pro', '4': 'live_L', '5': 'live_M', '6': 'live_R'},
                live=dict(block=a.block, split_rule='by log name: train 0 / newest tail 1 / calibration 2', tail=a.tail,
                          tail_from=str(tags[order[len(order) - n_tail]]) if n_tail else None,
                          ability='no opponent ability labels (ab_ok 0)', deck_map=str(a.deck_map)),
                sizes={k: dict(v) for k, v in sorted(sizes.items())})
    np.save(a.out / 'meta.npy', np.asarray(json.dumps(meta)))
    (a.out.parent / (a.out.name + '.sizes.json')).write_text(json.dumps(meta['sizes'], indent=1))
    print(json.dumps(dict(out=str(a.out), all=dict(sizes['all']), tail_from=meta['live']['tail_from'])))


if __name__ == '__main__':
    main()
