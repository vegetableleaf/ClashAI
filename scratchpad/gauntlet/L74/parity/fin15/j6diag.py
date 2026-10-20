"""W8 round 2, J6 diagnosis: replay the spell / king fights of the given matches (replay_metrics.py fights, K = 0) and dump, for
every crossing that fails (sim-only, live-only, ticks off, other lane) on a body whose J6 label contains NAME, the paired body's
live and SIM tracks (every row: tick, x, y, hp, the enemy bodies within 4 tiles).
  PARITY_SIM_PATH=... python j6diag.py OUTDIR NAME LOG [LOG ...]      -> OUTDIR/<match>.jsonl (one line per failing body)
"""
import json, math, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.metrics import replay_metrics as R  # noqa: E402
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402


def main():
    od = Path(sys.argv[1]); od.mkdir(parents=True, exist_ok=True); want = sys.argv[2]
    orig = R.j6

    def j6(m, events, fight, rows, pert):
        r = orig(m, events, fight, rows, pert)
        cat = fight['catalog']
        pairs = F.initial_pairs(rows, [b for b in rows[0][1] if not b['tower']], cat)
        by_l, by_s = defaultdict(list), defaultdict(list)
        for t, lv, sm in rows:
            for b in lv:
                if not b['tower']:
                    by_l[b['id']].append((t, b))
            for b in sm:
                if not b['tower']:
                    by_s[b['id']].append((t, b))
        rl = {t: (lv, sm) for t, lv, sm in rows}
        t_end = rows[-1][0]

        def enemies(bs, me, side):
            return [(b.get('name') or b.get('card_id'), round(b['x']), round(b['y']), b['hp'])
                    for b in bs if not b['tower'] and b['side'] != side and math.hypot(b['x'] - me['x'], b['y'] - me['y']) <= 4000]
        with open(od / (m['match'] + '.jsonl'), 'a') as f:
            for lid, tl in by_l.items():
                b0 = tl[0][1]
                c = cat.get(b0['card_id'])
                if c is None or c.get('type') == 'spell':
                    continue
                lab = R.label(m, b0['side'], c['display_name'], F.form_of(b0['card_id'], c))
                if want not in lab:
                    continue
                ts = by_s.get(pairs.get(lid), [])
                cl = R.crossing([(t, b['x'], b['y']) for t, b in tl], b0['side'])
                cs = R.crossing([(t, b['x'], b['y']) for t, b in ts], b0['side']) if ts else None
                if (cl is None and cs is None) or (cl and cs and cl[1] == cs[1] and abs(cl[0] - cs[0]) <= 10):
                    continue
                when = max(x[0] for x in (cl, cs) if x)
                if when > t_end - 20 or tl[-1][0] < min(when, t_end - 2) or not ts or ts[-1][0] < min(when, t_end - 2):
                    continue          # not pathing proper (a survival difference or the window's edge)
                f.write(json.dumps(dict(card=lab, t0=fight['t0'], t1=t_end, live_cross=cl, sim_cross=cs,
                                        live=[(t, round(b['x']), round(b['y']), b['hp'], enemies(rl[t][0], b, b0['side'])) for t, b in tl],
                                        sim=[(t, round(b['x']), round(b['y']), b['hp'], enemies(rl[t][1], b, b0['side'])) for t, b in ts]),
                                   default=str) + '\n')
        return r
    R.j6 = j6
    for p in sys.argv[3:]:
        s = R.one((p, 'fights', str(od / 'run'), 0))
        print(Path(p).stem, s.get('fights'), s.get('crash'), flush=True)


if __name__ == '__main__':
    main()
