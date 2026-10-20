"""O3 / O4 scoring (laptop): SIM eval rows from pod/opp_eval.sh vs the live 13k opponents.
    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/o3_score.py ROOT [ROOT ...]  (ROOT = a pulled out/NAME dir
    or its parent; every NAME_SEED/D3/matches.jsonl below it is one config NAME)

Per config:
  * play style (J10): human/opp_behaviour.py features, recomputed from the rows' o3_plays (exact accepted plays) made comparable
    with the live PlayDetector plays: bodiless spells removed (the live detector never sees them), our plays at landing - 26 ticks
    (= the tap, as live `play` events; opp_behaviour.extract_sim's rule). Position features are not available (no x / y in
    o3_plays) and are left out of the distance on both sides.
  * crown path (J9): exact (each row's --crown-log princess falls + king from the final crowns), against live CLX at our tower 4858
    (the all-16 state since 10-19 14:02) and the pooled live 13k matches at 4858.
Live reference: analyze.load_live() (out/live_matches.jsonl.gz)."""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[0] / 'human')]
import analyze as AN  # noqa: E402
import crowns as C  # noqa: E402
import opp_behaviour as OB  # noqa: E402
from pipeline.opp_elixir_count import card_db, card_cost  # noqa: E402

BODY_SPELLS = {'graveyard', 'goblin_barrel', 'barbarian_barrel', 'royal_delivery', 'clone'}
NOPOS = ('own_half', 'bridge', 'our_half', 'opp_el')
FEATS = [f for f in OB.FEATS if f not in NOPOS]


def visible(card):
    k = card.replace('-', '_')
    try:
        kind = card_db().kind(k)
    except Exception:                                  # noqa: BLE001
        kind = None
    return kind != 'spell' or k in BODY_SPELLS


def sim_falls(r):
    f = {}
    for i, e in enumerate((r.get('crown') or {}).get('falls') or []):
        f[('own' if e['who'] == 'own' else 'opp') + f'_P{i}'] = int(e['tick'])
    if r['crowns_for'] == 3:
        f['opp_K'] = int(r['end_tick'])
    if r['crowns_against'] == 3:
        f['own_K'] = int(r['end_tick'])
    return f


def load(root):
    cfg = defaultdict(list)
    for p in glob.glob(str(Path(root) / '**' / 'D3' / 'matches.jsonl'), recursive=True):
        name = Path(p).parents[1].name.rsplit('_', 1)[0]
        for line in open(p, encoding='utf-8'):
            cfg[name].append(json.loads(line))
    return cfg


def behaviour(rows):
    out = []
    for r in rows:
        pl = r.get('o3_plays')
        if not pl:
            continue
        opp = [[int(t), c.replace('-', '_'), card_cost(c.replace('-', '_')) or 0.0, 0.0, 0.0, 1, 99, None]
               for t, c in pl['opp'] if visible(c)]
        m = dict(plays=opp, mine=[int(t) - 26 for t, _ in pl['learner']], end=int(r['end_tick']), t0=0, seen=[])
        out.append((AN.arch2(r.get('opp_deck') or []), OB.features(m)))
    return out


def main():
    live = AN.load_live()
    L13 = [r for r in live if r['tro'] >= 12950 and r['m'] in ('CXXXVIII', 'CLIII', 'CLIX', 'CLX', 'CLX_T16')]
    lf = [(r['a'], OB.features(dict(src='live', id=r['log'], seen=r['seen'], res=0, end=r['end'], t0=r['t0'], side=r['side'],
                                    plays=r['plays'], mine=r['mine']))) for r in L13]
    T16 = [r['rec'] for r in live if r['m'] == 'CLX_T16']
    print(f'live 13k behaviour n={len(lf)}; live CLX @4858 crowns n={len(T16)}')
    lt = C.crown_stats(T16)
    cells = ('win', 'lose_princess', 'take_princess', 'both', 'ot_share', 'reg_loss')
    print('  LIVE CLX@4858: ' + ' | '.join(f'{k} {C.pct(*lt[k])}' for k in cells) + f" | giveback {C.pct(*lt['giveback'])}")
    res = []
    for root in sys.argv[1:]:
        for name, rows in sorted(load(root).items()):
            b = behaviour(rows)
            cmp = OB.compare([f for _, f in lf], [f for _, f in b]) if b else None
            ds = [cmp[k][4] for k in FEATS if cmp and not math.isnan(cmp[k][4])]
            dist = math.sqrt(sum(d * d for d in ds) / len(ds)) if ds else float('nan')
            recs = [C.live_rec(dict(falls=sim_falls(r), end=int(r['end_tick']),
                                    win=1.0 if r['outcome'] == 'win' else 0.0 if r['outcome'] == 'loss' else 0.5), off=0) for r in rows]
            st = C.crown_stats(recs)
            gap = {k: 100 * (st[k][0] / st[k][1] - lt[k][0] / lt[k][1]) for k in cells}
            res.append((dist, name, len(rows), len(b), st, gap, cmp))
    res.sort(key=lambda x: (x[0] if not math.isnan(x[0]) else 9, x[1]))
    print(f"\n  {'config':34s} {'rows':>5s} {'beh':>5s} {'dist':>6s} | SIM - live CLX@4858 (pp): " + ' '.join(f'{k:>13s}' for k in cells))
    for dist, name, n, nb, st, gap, cmp in res:
        print(f'  {name:34s} {n:5d} {nb:5d} {dist:6.2f} | ' + ' '.join(f'{gap[k]:+13.1f}' for k in cells) +
              f"   (SIM win {100 * st['win'][0] / max(1, st['win'][1]):.1f}, opp takes {100 * st['lose_princess'][0] / max(1, st['lose_princess'][1]):.1f})")
    if res and res[0][6]:
        dist, name, n, nb, st, gap, cmp = res[0]
        print(f'\n  best by style distance: {name}; feature means live / SIM (d):')
        for k in FEATS:
            print(f'    {k:12s} {cmp[k][1]:8.2f} / {cmp[k][3]:8.2f}  ({cmp[k][4]:+.2f})')
        print('  crowns: ' + ' | '.join(C.fmt_stats(st)))


if __name__ == '__main__':
    main()
