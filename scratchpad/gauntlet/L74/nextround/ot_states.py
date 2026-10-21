"""W15 lever 2: the live Ranked 0-0 overtime-start states for rl_royale ``ot_start_share`` -> ot_states.json.

    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/nextround/ot_states.py

One state per CLX Ranked match that was 0-0 at clock 3590 and went to overtime (clx_ranked/rows.json, W13 anatomy.reg_state:
the princess HP fractions at clock 3590 from the reader's tower frames), plus CLX's own elixir at 3590 (the last decision's
hand reading, anatomy.el_at), the number of distinct opponent cards revealed by then and the bodies on the board (the
history and board the SIM start lacks).
Lanes: ``own`` [L, R] in our screen frame = the learner's own TowerSlot [LEFT, RIGHT]; ``opp`` [L, R] in OUR screen frame
(x < 9 = L), i.e. the opponent's own [RIGHT, LEFT] (royalegym protocol: Red's frame is rotated 180 degrees).
Single process, idle priority (anatomy sets it), local files only.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'clx_ranked'))
import anatomy as AN  # noqa: E402

T0 = AN.REG - 10                                   # clock 3590 = reg_state's tick


def lanes(low, mn, sm):
    """[L, R] fractions from reg_state's (low lane, min, sum) of the two standing princesses."""
    other = round(sm - mn, 3)
    return [mn, other] if low == 'L' else [other, mn]


def board(m):
    """Non-tower bodies on the board in the cached frame nearest clock 3590 (the SIM start's board is empty)."""
    f = min(m['frames'], key=lambda fr: abs(fr[0] - T0))
    return sum(1 for k, *_ in f[2] if k)


def main():
    rows = json.load(open(HERE.parent / 'clx_ranked/rows.json'))
    pick = {r['key']: r for r in rows if r['sample'] == 'ranked' and r['ot'] and list(r['reg_cr']) == [0, 0]}
    sub = HERE / '_ot_index.json'
    idx = json.load(open(HERE.parent / 'clx_ranked/index.json'))
    json.dump({k: dict(mark=idx[k]['mark'], result=idx[k]['result'], tro=idx[k].get('tro')) for k in pick}, open(sub, 'w'))
    out = []
    try:
        for m in AN.I.live_matches({'CLX'}, index=sub):
            r = pick[m['key']]
            out.append(dict(key=r['key'], win=r['win'], own=lanes(r['reg_own_low'], r['reg_own_min'], r['reg_own_sum']),
                            opp=lanes(r['reg_opp_low'], r['reg_opp_min'], r['reg_opp_sum']), elixir=AN.el_at(m, T0),
                            opp_cards_seen=len({p['card'] for p in m['opp'] if p['tick'] < T0}),
                            board_units=board(m)))
    finally:
        sub.unlink()
    bad = [s for s in out if min(s['own'] + s['opp']) <= 0 or max(s['own'] + s['opp']) > 1.0 or s['elixir'] is None]
    keep = [s for s in out if s not in bad]
    el = [s['elixir'] for s in keep]
    seen = [s['opp_cards_seen'] for s in keep]
    gap = [min(s['own']) - min(s['opp']) for s in keep]
    summary = dict(n_rows_0_0_ot=len(pick), n_loaded=len(out), n_dropped=len(bad), n=len(keep),
                   behind_gt_0_10=round(sum(g < -0.10 for g in gap) / len(keep), 3),
                   ahead_gt_0_10=round(sum(g > 0.10 for g in gap) / len(keep), 3),
                   elixir_median=statistics.median(el), elixir_mean=round(statistics.mean(el), 3),
                   opp_cards_seen_median=statistics.median(seen), opp_cards_seen_ge7=round(sum(x >= 7 for x in seen) / len(seen), 3),
                   board_units_median=statistics.median(s['board_units'] for s in keep),
                   board_units_zero=round(sum(s['board_units'] == 0 for s in keep) / len(keep), 3),
                   win=round(sum(s['win'] for s in keep) / len(keep), 3))
    json.dump(dict(source='clx_ranked/rows.json + habits/cache (W15 ot_states.py)', tick=T0, summary=summary, states=keep),
              open(HERE / 'ot_states.json', 'w'), indent=0)
    print(json.dumps(summary, indent=1))
    for s in bad:
        print('dropped', s)


if __name__ == '__main__':
    main()
