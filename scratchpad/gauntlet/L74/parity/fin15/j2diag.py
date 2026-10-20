"""W8 Tornado diagnosis: replay the spell fights of the given matches (replay_metrics.py fights, K = 0) and dump, for every
Tornado cast whose victims include NAME (substring of the victim label), each row's position / hp / deploying flag of every
non-tower body within 6 tiles of the cast point, live and SIM (paired ids), from the cast to cast + 40 ticks.
  PARITY_SIM_PATH=... python j2diag.py OUTDIR NAME LOG [LOG ...]      -> OUTDIR/<match>_<tick>.json
"""
import json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.metrics import replay_metrics as R  # noqa: E402
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402


def main():
    od = Path(sys.argv[1]); od.mkdir(parents=True, exist_ok=True); want = sys.argv[2]
    orig_j2 = R.j2

    def j2(m, events, fight, rows, pert):
        r = orig_j2(m, events, fight, rows, pert)
        if r['spell'] == 'Tornado' and any(want in b['victim'] for b in r['j2']):
            ev = events[fight['anchor']]
            pairs = F.initial_pairs(rows, [b for b in rows[0][1] if not b['tower']], fight['catalog'])
            near = lambda b: not b['tower'] and math.hypot(b['x'] - ev['x'], b['y'] - ev['y']) <= 6000
            dump = []
            for t, lv, sm in rows:
                if ev['tick'] - 4 <= t <= ev['tick'] + 40:
                    dump.append(dict(t=t, live=[(b['id'], pairs.get(b['id']), b.get('name') or b.get('card_id'), round(b['x']), round(b['y']), b['hp'])
                                                for b in lv if near(b)],
                                     sim=[(b['id'], b.get('name'), round(b['x']), round(b['y']), b['hp'], int(bool(b.get('deploying'))))
                                          for b in sm if near(b)]))
            (od / f"{m['match']}_{ev['tick']}.json").write_text(json.dumps(dict(cast=dict(tick=ev['tick'], x=ev['x'], y=ev['y'], side=ev['side']),
                                                                               j2=r['j2'], rows=dump), default=str))
        return r
    R.j2 = j2
    R.j3 = lambda m, events, fight, rows, pert: dict(j3=[])      # J3 windows are not needed here
    for p in sys.argv[3:]:
        s = R.one((p, 'fights', str(od / 'run'), 0))
        print(Path(p).stem, s.get('fights'), s.get('crash'), flush=True)


if __name__ == '__main__':
    main()
