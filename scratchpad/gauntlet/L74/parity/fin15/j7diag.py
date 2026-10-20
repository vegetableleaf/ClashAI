"""W8 J7 diagnosis: replay whole matches open loop (replay_metrics.py whole, K = 0) and dump, around each match's first tower
divergence, every frame's tower hp (live / SIM) and the bodies within REACH of the diverging tower in both runs.
  PARITY_SIM_PATH=... python j7diag.py OUTDIR LOG [LOG ...]      -> OUTDIR/<match>.json
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.metrics import replay_metrics as R  # noqa: E402

REACH = 9.0      # tiles from the tower centre
BEFORE, AFTER = 300, 120


def dump(rows, fd):
    k = fd['towers'][0]
    out = []
    lv0 = {b['id']: b for b in rows[0][1] if b['tower']}
    tx, ty = lv0[k]['x'], lv0[k]['y']
    for t, lv, sm in rows:
        if not (fd['tick'] - BEFORE <= t <= fd['tick'] + AFTER):
            continue
        def near(bs):
            return [(b.get('name'), b['side'], round(b['x']), round(b['y']), b['hp'], int(bool(b.get('deploying'))))
                    for b in bs if not b['tower'] and ((b['x'] - tx) ** 2 + (b['y'] - ty) ** 2) ** .5 <= REACH * 1000]
        out.append(dict(t=t, live_hp={b['id']: b['hp'] for b in lv if b['tower']}, sim_hp={b['id']: b['hp'] for b in sm if b['tower']},
                        live_near=near(lv), sim_near=near(sm)))
    return out


def main():
    od = Path(sys.argv[1]); od.mkdir(parents=True, exist_ok=True)
    orig = R.j7

    def j7(m, events, fight, rows, pert):
        r = orig(m, events, fight, rows, pert)
        fd = r['j7'].get('first_div')
        if fd:
            r['j7']['diag'] = dump(rows, fd)
            r['j7']['events'] = [e for e in events if e['kind'] == 'play' and fd['tick'] - 900 <= e['tick'] <= fd['tick']]
        (od / (m['match'] + '.json')).write_text(json.dumps(dict(side=m['side'], j7=r['j7']), default=str))
        return r
    R.j7 = j7
    for p in sys.argv[2:]:
        s = R.one((p, 'whole', str(od / 'run'), 0))
        print(Path(p).stem, s.get('fights'), s.get('crash'), flush=True)


if __name__ == '__main__':
    main()
