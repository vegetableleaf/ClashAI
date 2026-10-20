"""O1 step 3: (a) the SELF-CHECK on OUR seat, (b) the hand-inference check, (c) the final O2 inputs.
Single process, laptop.

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/o1_finalize.py   -> o1_check.out (+ out/o1_{train,holdout}_v32.npz)

Inputs: out/o1_{train,holdout}.npz (pipeline.dataset_gen --feature-version 5 over out/o1_corpus/{train,holdout}), the corpus
index, the live logs.

(a) Self-check: every OUR-seat row whose tick equals a logged live decision tick is compared field by field with what the live
    pilot logged at that decision (public, pre-look-ahead values):
      hand (4 cards as a set) | own elixir (|d| <= 0.1) | the dataset's public opponent-elixir counter vs the live counter
      (|d| <= 0.5) | own-frame unit positions vs the logged raw bodies (same count, each within 0.02) | tower hp fractions (<= 0.01).
(b) Hand inference: the opponent rule (hand = deck - last 4 publicly detected plays) applied to OUR side, i.e. our plays as the
    opponent's seat detects them, against the hand we really held before each play (logged).
(c) Remap every card-identity column to gen_v32_s0's card vocabulary (the fine-tune's embedding table) and add `opp_mask`
    (1 = an OPPONENT-seat row with all hand / deck / label cards in that vocabulary). Our-seat rows stay in the file, masked 0:
    they are the live model's own play, never imitation targets."""
from __future__ import annotations

import bisect
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(ROOT)]
import o1_records as R  # noqa: E402
from pipeline.dataset import load as load_ds  # noqa: E402
from pipeline.obs_contract import _engine_xy  # noqa: E402
from pipeline.public_observation import recording_observers  # noqa: E402
from pipeline.native_recording import tag_native_recording  # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies  # noqa: E402

OUT = HERE / 'out'
V32_META = ROOT / 'icebow/data/pipeline/gen_dataset_v32_fv5.json'
CARD_ARRS = ('hand_card', 'next_card', 'deck_card', 'y_card', 'y_wait_card')
COL0_ARRS = ('past', 'opp_past', 'opp_cycle', 'projectiles', 'effects', 'own_ability')
TOWER_COLS = slice(52, 58)       # sc: tower_hp_frac_6 follows t_300, de, ot, my_el, exact, opp_el, known, 36 + 9 one-hots


def pct(k, n):
    return f'{100 * k / max(n, 1):.2f}% ({k}/{n})'


def log_view(path):
    """decisions by tick (hand keys, own elixir, raw bodies) and the live counter per frame tick."""
    dec, est = {}, {}
    side = None
    with open(path, 'rb') as fh:
        for raw in fh:
            if raw.startswith(b'{"event": "frame"'):
                j = R.LT.loads(raw)
                side = int(j['my_side'])
                if j.get('opp_elixir_est') is not None:
                    est[int(j['tick'])] = float(j['opp_elixir_est'])
            elif raw.startswith(b'{"event": "decision"'):
                j = R.LT.loads(raw)
                p = j.get('public') or {}
                if 'own_hand' in p:
                    dec[int(j['tick'])] = dict(hand=sorted(R.key_of(h['name']) for h in p['own_hand']),
                                               own_el=float(p['own_elixir_raw']) if p.get('own_elixir_raw') is not None else None,
                                               bodies=dedupe_hero_bodies(dict(entities=p.get('raw_bodies') or []))['entities'])
    return side, dec, est


def selfcheck(arrs, meta, index):
    vocab = meta['card_vocab']
    tags = arrs['tags']
    by_tag = defaultdict(list)
    for i, (rep, side) in enumerate(zip(arrs['rep'], arrs['side'])):
        t = str(tags[rep])
        if index[t]['my_side'] == int(side):
            by_tag[t].append(i)
    c = Counter()
    off = arrs['off']
    for t, rows in by_tag.items():
        side, dec, est = log_view(R.LT.LOGS / index[t]['recording'])
        mir = side == 1
        for i in rows:
            tick = int(arrs['tick'][i])
            d = dec.get(tick)
            if d is None:
                continue
            c['rows_compared'] += 1
            hand = sorted(vocab[k].replace('-', '_') for k in arrs['hand_card'][i] if k > 0)   # vocab slugs use '-', keys '_' 
            c['hand_ok'] += hand == d['hand']
            if d['own_el'] is not None:
                c['el_n'] += 1
                c['el_ok'] += abs(float(arrs['sc'][i, 3]) * 10 - d['own_el']) <= 0.1
            if tick in est:
                c['opp_n'] += 1
                c['opp_ok'] += abs(float(arrs['sc'][i, 5]) * 10 - est[tick]) <= 0.5
                c['opp_absdiff_x1000'] += round(1000 * abs(float(arrs['sc'][i, 5]) * 10 - est[tick]))
            tok = arrs['tok'][off[i]:off[i + 1]]
            ours = sorted((round(float(x), 2), round(float(y), 2)) for x, y in tok[:, 4:6])
            ref = sorted((round(a, 2), round(b, 2)) for a, b in
                         (_engine_xy(float(b_['x']), float(b_['y']), mir) for b_ in d['bodies']
                          if int(b_.get('card_id', -1)) >= 0 and int(b_.get('side', -1)) in (0, 1)
                          and not (b_['hp'] <= 0 < b_['max_hp'])))
            c['units_n'] += 1
            same = len(ours) == len(ref) and all(abs(a[0] - b[0]) <= .02 and abs(a[1] - b[1]) <= .02 for a, b in zip(ours, ref))
            c['units_ok'] += same
            if len(ours) != len(ref):
                c['units_count_diff'] += 1
            tw = [b_ for b_ in d['bodies'] if int(b_.get('card_id', 0)) == -1]
            ref_t = [round(max(0, b_['hp']) / b_['max_hp'], 3) for b_ in tw if b_.get('max_hp')]
            ref_t = sorted(ref_t + [0.0] * (6 - len(ref_t)))          # a destroyed tower leaves the reader's list = 0
            got_t = sorted(round(float(v), 3) for v in arrs['sc'][i, TOWER_COLS])
            c['tower_n'] += 1
            c['tower_ok'] += len(ref_t) == 6 and all(abs(a - b) <= .01 for a, b in zip(got_t, ref_t))
            if not (len(ref_t) == 6 and all(abs(a - b) <= .01 for a, b in zip(got_t, ref_t))) and c['tower_examples'] < 3:
                c['tower_examples'] += 1
                print('   tower mismatch example', t, tick, got_t, ref_t)
    print('\n## (a) self-check, OUR seat rows vs the live decision logged at the same tick')
    print(f"  rows compared {c['rows_compared']} (of {sum(len(v) for v in by_tag.values())} our-seat rows; the rest have no decision at that exact tick)")
    print(f"  hand (4-card set)                {pct(c['hand_ok'], c['rows_compared'])}")
    print(f"  own elixir (|d| <= 0.1)          {pct(c['el_ok'], c['el_n'])}")
    print(f"  opponent elixir counter (<= 0.5) {pct(c['opp_ok'], c['opp_n'])}  mean |d| {c['opp_absdiff_x1000'] / 1000 / max(1, c['opp_n']):.3f}")
    print(f"  unit positions (count + 0.02)    {pct(c['units_ok'], c['units_n'])}  (count differs in {c['units_count_diff']})")
    print(f"  tower hp fractions (<= 0.01)     {pct(c['tower_ok'], c['tower_n'])}")
    return c


def inference_check(index, split):
    """Our hand inferred from OUR publicly detected plays (observers[opp].plays) vs the hand we logged before each play."""
    c = Counter()
    for m in index:
        if m['split'] != split:
            continue
        rec = json.loads((OUT / 'o1_corpus' / split / f"replay_{m['tag']}.json").read_text(encoding='utf-8'))
        me, opp = m['my_side'], m['opp_side']
        obs = recording_observers(tag_native_recording(dict(rec, log=[]), {}))
        seq = [dict(key=R.key_of(e['card']), **e) for e in sorted(obs[opp].plays, key=lambda e: e['tick'])]
        deck = sorted({R.key_of(n.split('@')[0]) for n in rec['final_decks'][str(me)]})
        hands = R.infer_hands(seq, deck)
        mine = [e for e in rec['log'] if e['side'] == me and e['hand_before']]
        mt = [e['tick'] for e in mine]
        for e, h in zip(seq, hands):
            c['detected'] += 1
            j = bisect.bisect_right(mt, int(e['tick'])) - 1      # the tap this sighting belongs to (<= 60 ticks before)
            if j < 0 or int(e['tick']) - mt[j] > 60 or mine[j]['card'] != e['key']:
                c['no_matching_tap'] += 1
                continue
            truth = sorted(R.key_of(n) for n in mine[j]['hand_before'])
            if h is None:
                c['undetermined'] += 1
                continue
            c['inferred'] += 1
            c['exact'] += sorted(h[0]) == truth
        c['true_plays'] += sum(1 for e in rec['log'] if e['side'] == me)
    print(f'\n## (b) hand inference on OUR seat ({split}): the opponent rule applied to our publicly detected plays')
    print(f"  our true plays {c['true_plays']}, publicly detected {c['detected']} ({pct(c['detected'], c['true_plays'])} of true), "
          f"matched to a tap {c['detected'] - c['no_matching_tap']}")
    print(f"  hand determined {pct(c['inferred'], c['detected'] - c['no_matching_tap'])}; of those, exactly the true 4 cards "
          f"{pct(c['exact'], c['inferred'])}")
    return c


def remap(arrs, meta, index, dst):
    v32 = json.loads(V32_META.read_text(encoding='utf-8'))['card_vocab']
    gid = {k: i for i, k in enumerate(v32)}
    loc = meta['card_vocab']
    lut = np.array([gid.get(k, -1) if i else 0 for i, k in enumerate(loc)], np.int64)
    missing = sorted(k for i, k in enumerate(loc) if i and k not in gid)
    out = dict(arrs)
    bad = np.zeros(len(arrs['sc']), bool)
    for k in CARD_ARRS:
        a = lut[arrs[k].astype(np.int64)]
        if k in ('hand_card', 'deck_card', 'y_card'):
            bad |= (a < 0).reshape(len(a), -1).any(1)
        out[k] = np.where(a < 0, 0, a).astype(np.int16)
    for k in COL0_ARRS:
        if k in arrs:
            a = arrs[k].copy()
            ids = lut[a[..., 0].astype(np.int64)]
            a[..., 0] = np.where(ids < 0, 0, ids)
            out[k] = a
    order = np.argsort(out['deck_card'], 1, kind='stable')       # canonical deck order (by card id), as dataset_gen
    out['deck_card'] = np.take_along_axis(out['deck_card'], order, 1)
    out['deck_form'] = np.take_along_axis(arrs['deck_form'], order, 1)
    tags = arrs['tags']
    opp = np.array([index[str(tags[r])]['opp_side'] == int(s) for r, s in zip(arrs['rep'], arrs['side'])])
    out['opp_mask'] = (opp & ~bad).astype(np.int8)
    m = dict(meta, card_vocab=v32, o1=dict(source_vocab=loc, cards_not_in_v32=missing, opp_rows=int(opp.sum()),
                                          opp_rows_kept=int(out['opp_mask'].sum()), own_rows=int((~opp).sum())))
    np.savez_compressed(dst, meta=json.dumps(m), **{k: v for k, v in out.items() if k != 'meta'})
    play = out['y_gate'] == 1
    print(f'\n## (c) {dst.name}: rows {len(opp)}; opponent-seat {int(opp.sum())} (kept {int(out["opp_mask"].sum())}; play '
          f'{int((play & (out["opp_mask"] == 1)).sum())}, wait {int((~play & (out["opp_mask"] == 1)).sum())}); our seat {int((~opp).sum())}; '
          f'cards not in the v32 vocabulary: {missing}')
    return m


def main():
    idx = json.loads((OUT / 'o1_corpus/index.json').read_text(encoding='utf-8'))
    index = {m['tag']: dict(m, recording=m['tag'] + '.jsonl') for m in idx['matches']}
    print(f"records {idx['n']} (holdout from {idx['cut_ts']}); builder totals {json.dumps(idx['totals'])}")
    for split in ('train', 'holdout'):
        arrs, meta = load_ds(OUT / f'o1_{split}.npz')
        arrs['tags'] = arrs['tags']
        print(f'\n==== {split}: {len(arrs["sc"])} rows from {len(arrs["tags"])} records; dataset_gen stats '
              f'play_rows {meta["stats"].get("play_rows")} wait_rows {meta["stats"].get("wait_rows")} '
              f'play_skipped {meta["stats"].get("play_skipped")} wait_no_hand {meta["stats"].get("wait_no_hand")}')
        selfcheck(arrs, meta, index)
        inference_check(list(index.values()), split)
        remap(arrs, meta, index, OUT / f'o1_{split}_v32.npz')


if __name__ == '__main__':
    main()
