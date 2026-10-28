"""V1-LIVEROWS self-check (REPORT_opponents 1.4: the same builder on OUR seat must reproduce the live decision inputs on >= 99% of
fields) + the label-quality numbers that need our seat's truth. Called per chunk by live_rows.py (check_npz) on the BOTH-seat rows;
`python -I selfcheck.py summarize SRC [SRC ...]` sums the per-chunk files.

(A) PIPELINE fields -- every OUR-seat row whose tick equals a logged live decision tick, vs that decision's public inputs
    (o1_finalize.selfcheck's comparisons): hand (4-card set) | own elixir |d| <= 0.1 | the rows' public opponent-elixir counter vs
    the live counter |d| <= 0.5 | own-frame unit positions vs the logged raw bodies (same count, each within 0.02) | tower hp
    fractions (<= 0.01). The opponent seat's rows go through the same frame -> token code (mirrored), so these bound it.
(B) LABEL quality on our seat (what the opponent seat's labels would get wrong, measured where the truth is known):
    * act dating: (our first public sighting - LAG) - our decision tick of that tap, per card class;
    * cycle-rule hand: o1_records.infer_hands on OUR public sightings vs the hand logged at that tap's decision;
    * public counter as an elixir estimate: the OPPONENT-seat rows' estimate of OUR elixir (sc[:, 5], the public counter the
      opponent seat's 'own elixir' input mirrors) vs our true elixir at that tick (|d| <= 0.5 / 1.0)."""
from __future__ import annotations

import bisect
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[2]
ROOT = L74.parents[2]
sys.path[:0] = [str(L74 / 'opp_model'), str(ROOT)]
TOWER_COLS = slice(52, 58)
LAG = 20
SPELLS = {'rocket', 'the_log', 'tornado'}


def _open(p):
    return gzip.open(p, 'rb') if str(p).endswith('.gz') else open(p, 'rb')


def log_view(path):
    import o1_records as R
    dec, est, own = {}, {}, {}
    side = None
    with _open(path) as fh:
        for raw in fh:
            if raw.startswith(b'{"event": "frame"'):
                j = R.LT.loads(raw)
                side = int(j['my_side'])
                t = int(j['tick'])
                own[t] = float(j.get('elixir') or 0.0)
                if j.get('opp_elixir_est') is not None:
                    est[t] = float(j['opp_elixir_est'])
            elif raw.startswith(b'{"event": "decision"'):
                j = R.LT.loads(raw)
                p = j.get('public') or {}
                if 'own_hand' in p:
                    dec[int(j['tick'])] = dict(hand=sorted(R.key_of(h['name']) for h in p['own_hand']),
                                               own_el=float(p['own_elixir_raw']) if p.get('own_elixir_raw') is not None else None,
                                               bodies=R.dedupe_hero_bodies(dict(entities=p.get('raw_bodies') or []))['entities'])
    return side, dec, est, own


def check_npz(npz, logs: Path) -> dict:
    import live_table as LT
    import o1_records as R
    from pipeline.obs_contract import _engine_xy
    z = np.load(npz, allow_pickle=False)
    meta = json.loads(str(z['meta']))
    vocab = meta['card_vocab']
    tags, rep, side, tick, off = z['tags'], z['rep'], z['side'], z['tick'], z['off']
    sc, hand_card, tok = z['sc'], z['hand_card'], z['tok']
    c = Counter()
    lag = Counter()
    ex = []
    for r, tag in enumerate(tags):
        tag = str(tag)
        p = logs / (tag + '.jsonl.gz')
        p = p if p.exists() else logs / (tag + '.jsonl')
        me, dec, est, own = log_view(p)
        mir = me == 1
        rows = np.where(rep == r)[0]
        rec = json.loads((Path(npz).parent / 'corpus' / f'replay_{tag}.json').read_text())
        lv = rec['live']
        from pipeline.opp_elixir_count import card_cost
        pend = [((s - LAG - 1) if (s - LAG) % 10 == 0 else (s - LAG), s, card_cost(k) or 0.0) for s, k in lv['our_sightings']]
        for i in rows:
            t = int(tick[i])
            if int(side[i]) != me:                              # opponent-seat row: the public counter's error on OUR elixir
                if t in own:
                    d = abs(float(sc[i, 5]) * 10 - own[t])
                    c['cnt_n'] += 1
                    c['cnt_le05'] += d <= 0.5
                    c['cnt_le10'] += d <= 1.0
                    c['cnt_absdiff_x1000'] += round(1000 * d)
                    # as the OPPONENT seat's own-elixir input is built: the counter minus acted-but-unsighted costs
                    d2 = abs(max(0.0, float(sc[i, 5]) * 10 - sum(cst for a_, s_, cst in pend if a_ < t < s_)) - own[t])
                    c['cnt2_le05'] += d2 <= 0.5
                    c['cnt2_le10'] += d2 <= 1.0
                    c['cnt2_absdiff_x1000'] += round(1000 * d2)
                continue
            d = dec.get(t)
            if d is None:
                continue
            c['rows_compared'] += 1
            hand = sorted(vocab[k].replace('-', '_') for k in hand_card[i] if k > 0)
            c['hand_ok'] += hand == d['hand']
            if d['own_el'] is not None:
                c['el_n'] += 1
                c['el_ok'] += abs(float(sc[i, 3]) * 10 - d['own_el']) <= 0.1
            if t in est:
                c['opp_n'] += 1
                c[f'opp_n_day:{tag[10:18]}'] += 1
                dd = abs(float(sc[i, 5]) * 10 - est[t])
                c['opp_ok'] += dd <= 0.5
                if dd > 0.5:
                    c[f'opp_miss_day:{tag[10:18]}'] += 1
                    if len(ex) < 12:
                        ex.append(dict(kind='counter', tag=tag, tick=t, rows=round(float(sc[i, 5]) * 10, 3), live=est[t]))
                c['opp_absdiff_x1000'] += round(1000 * dd)
            tk = tok[off[i]:off[i + 1]]
            ours = sorted((round(float(x), 2), round(float(y), 2)) for x, y in tk[:, 4:6])
            ref = sorted((round(a, 2), round(b, 2)) for a, b in
                         (_engine_xy(float(b_['x']), float(b_['y']), mir) for b_ in d['bodies']
                          if int(b_.get('side', -1)) in (0, 1) and not (b_['hp'] <= 0 < b_['max_hp'])
                          and ((int(b_.get('card_id', -1)) >= 0 and R.cname(b_['card_id']))
                               or (int(b_.get('card_id', 0)) == -1 and LT.slot(b_['x'], b_['y']) is None))))
            c['units_n'] += 1
            same = len(ours) == len(ref) and all(abs(a[0] - b[0]) <= .02 and abs(a[1] - b[1]) <= .02 for a, b in zip(ours, ref))
            c['units_ok'] += same
            c['units_count_diff'] += len(ours) != len(ref)
            # a card_id -1 body OFF the six tower slots (an unresolved spawn, e.g. hp 1006 kind 15) is a unit to the live
            # model too (decision model_bodies include it, 20261027_122836 t 817): units, not towers
            tw = [b_ for b_ in d['bodies'] if int(b_.get('card_id', 0)) == -1 and LT.slot(b_['x'], b_['y']) is not None]
            ref_t = [round(max(0, b_['hp']) / b_['max_hp'], 3) for b_ in tw if b_.get('max_hp')]
            ref_t = sorted(ref_t + [0.0] * (6 - len(ref_t)))
            got_t = sorted(round(float(v), 3) for v in sc[i, TOWER_COLS])
            c['tower_n'] += 1
            tok_ok = len(ref_t) == 6 and all(abs(a - b) <= .01 for a, b in zip(got_t, ref_t))
            c['tower_ok'] += tok_ok
            if (not same or not tok_ok) and len(ex) < 6:
                ex.append(dict(tag=tag, tick=t, units=[len(ours), len(ref)], ours=ours[:12], ref=ref[:12], got_t=got_t, ref_t=ref_t))
        # (B) act dating + cycle-rule hand on our seat, from the record (the chunk corpus next to the npz)
        taps = lv['our_taps']                                   # (decision tick, confirm tick, key)
        tt = [x[0] for x in taps]
        dticks = sorted(dec)
        deck = sorted({R.key_of(n.split('@')[0]) for n in rec['final_decks'][str(me)]})
        seq = [dict(key=k, tick=t) for t, k in lv['our_sightings']]
        hands = R.infer_hands(seq, deck)
        used = set()
        for e, h in zip(seq, hands):
            c['our_sightings'] += 1
            j = bisect.bisect_right(tt, e['tick']) - 1
            while j >= 0 and (j in used or taps[j][2] != e['key']) and e['tick'] - tt[j] <= 80:
                j -= 1
            if j < 0 or e['tick'] - tt[j] > 80 or taps[j][2] != e['key']:
                c['sighting_no_tap'] += 1
                continue
            used.add(j)
            cls = 'spell' if e['key'] in SPELLS else 'building' if e['key'] in ('x_bow', 'tesla') else 'troop'
            lag[f'{cls}:{(e["tick"] - LAG) - tt[j]}'] += 1
            k = bisect.bisect_right(dticks, tt[j]) - 1
            truth = dec[dticks[k]]['hand'] if k >= 0 else None
            if h is None:
                c['hand_undetermined'] += 1
            elif truth is not None:
                c['hand_inferred'] += 1
                c['hand_inferred_exact'] += sorted(h[0]) == truth
        c['our_taps'] += len(taps)
        c['taps_sighted'] += len(used)
    return dict(c=dict(c), lag=dict(lag), ex=ex)


def summarize(srcs):
    c, lag = Counter(), Counter()
    for s in srcs:
        for f in sorted((Path(s) / 'selfcheck').glob('*.json')):
            d = json.loads(f.read_text())
            c.update(d['c'])
            lag.update(d['lag'])
    pct = lambda k, n: round(100 * c[k] / max(1, c[n]), 2)  # noqa: E731
    out = {'(A) pipeline, our-seat rows at a live decision tick': dict(
        rows_compared=c['rows_compared'], hand=pct('hand_ok', 'rows_compared'), own_elixir_0p1=pct('el_ok', 'el_n'),
        opp_counter_0p5=pct('opp_ok', 'opp_n'), opp_counter_mean_absdiff=round(c['opp_absdiff_x1000'] / 1000 / max(1, c['opp_n']), 3),
        units=pct('units_ok', 'units_n'), units_count_diff=c['units_count_diff'], towers=pct('tower_ok', 'tower_n')),
        '(B) label quality on our seat': dict(
            our_taps=c['our_taps'], sighted_and_matched=c['taps_sighted'], sighted_pct=pct('taps_sighted', 'our_taps'),
            sightings_without_tap=c['sighting_no_tap'],
            cycle_hand_determined_pct=round(100 * c['hand_inferred'] / max(1, c['hand_inferred'] + c['hand_undetermined']), 2),
            cycle_hand_exact_pct=pct('hand_inferred_exact', 'hand_inferred'),
            counter_as_elixir_le0p5=pct('cnt_le05', 'cnt_n'), counter_as_elixir_le1p0=pct('cnt_le10', 'cnt_n'),
            counter_as_elixir_mean_absdiff=round(c['cnt_absdiff_x1000'] / 1000 / max(1, c['cnt_n']), 3), counter_n=c['cnt_n'],
            corrected_counter_as_elixir_le0p5=pct('cnt2_le05', 'cnt_n'), corrected_counter_as_elixir_le1p0=pct('cnt2_le10', 'cnt_n'),
            corrected_counter_as_elixir_mean_absdiff=round(c['cnt2_absdiff_x1000'] / 1000 / max(1, c['cnt_n']), 3))}
    dating = {}
    for cls in ('troop', 'building', 'spell'):
        xs = sorted(int(k.split(':')[1]) for k, v in lag.items() if k.startswith(cls + ':') for _ in range(v))
        if xs:
            q = lambda f: xs[int(f * (len(xs) - 1))]  # noqa: E731
            dating[cls] = dict(n=len(xs), p10=q(.1), p25=q(.25), p50=q(.5), p75=q(.75), p90=q(.9),
                               within2=round(100 * sum(abs(x - q(.5)) <= 2 for x in xs) / len(xs), 1))
    out['(B) act dating: (sighting - 20) - decision tick, ticks'] = dating
    out['raw'] = dict(c)
    return out


if __name__ == '__main__':
    if sys.argv[1] == 'summarize':
        print(json.dumps(summarize(sys.argv[2:]), indent=1))
