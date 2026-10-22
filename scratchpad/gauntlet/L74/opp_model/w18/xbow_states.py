"""W18 R4 input: live Ranked BRIDGE-X-Bow start states for rl_royale ``xbow_start_share`` (opponent training) -> xbow_states.json.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w18/xbow_states.py
One state per bridge X-Bow CLX placed at 0-0 in its 267 Ranked matches (diag12/recent/index_ext.json; habits cache frames):
  tick          the clock tick 26 before the X-Bow's confirmation (the decision; the forced X-Bow lands at the start)
  learner       the OPPONENT's princess HP fractions in ITS OWN frame [LEFT, RIGHT] (= our screen's [R, L]: Red is rotated)
  icebow        CLX's princess HP fractions in its own frame [LEFT, RIGHT] (our screen frame)
  icebow_elixir CLX's own elixir at the decision (>= 6: it paid for the X-Bow); the OPPONENT's elixir is never read live
                (owner rule) -- rl_royale draws another state's icebow_elixir for it, as W15's ot_start does
  xbow_board    the X-Bow's point in CLX's own board frame, [x / 18, y / 32] (engine_play.board_to_engine's input)
Public / own data only. Idle priority (anatomy sets it)."""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPP = HERE.parent
sys.path[:0] = [str(OPP.parent / 'clx_ranked'), str(OPP.parent / 'investment')]
import anatomy as AN  # noqa: E402
import invlib as I  # noqa: E402

DELAY = 26


def main():
    keep, _, _ = AN.load(OPP / 'diag12/recent/index_ext.json')
    rk = {k: v for k, v in keep.items() if v['sample'] == 'ranked'}
    sub = HERE / '_xbow_index.json'
    json.dump({k: dict(mark=v['mark'], result=v['result'], tro=v['tro']) for k, v in rk.items()}, open(sub, 'w'))
    out, drop = [], 0
    try:
        for m in I.live_matches({'CLX'}, index=sub):
            pm_o, pm_t = m['tmax'].get(('own', 'L')) or 1, m['tmax'].get(('opp', 'L')) or 1
            for r in I.xbow_rows(m):
                if r['type'] != 'bridge' or (r['our_cr'], r['their_cr']) != (0, 0):
                    continue
                t = int(r['tick']) - DELAY
                T = I._tower_at(m, t)
                own = [round(T.get(('own', s), 0) / pm_o, 3) for s in 'LR']
                opp_screen = [round(T.get(('opp', s), 0) / pm_t, 3) for s in 'LR']
                h = m['hand'](t)
                el = None if h is None else round(h[1], 2)
                if el is None or el < 6 or min(own + opp_screen) <= 0 or max(own + opp_screen) > 1:
                    drop += 1
                    continue
                out.append(dict(key=m['key'], tick=t, learner=opp_screen[::-1], icebow=own, icebow_elixir=el,
                                xbow_board=[round(r['x'] / 18, 4), round(r['y'] / 32, 4)]))
    finally:
        sub.unlink()
    el = [s['icebow_elixir'] for s in out]
    summary = dict(n=len(out), dropped=drop, matches=len({s['key'] for s in out}),
                   tick_median=statistics.median(s['tick'] for s in out),
                   in_2x=round(sum(s['tick'] >= 2400 for s in out) / len(out), 3),
                   icebow_elixir_median=statistics.median(el),
                   xbow_left=round(sum(s['xbow_board'][0] < .5 for s in out) / len(out), 3))
    json.dump(dict(source='diag12/recent/index_ext.json + habits/cache (w18/xbow_states.py)', delay=DELAY, summary=summary,
                   states=out), open(HERE / 'xbow_states.json', 'w'), indent=0)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
