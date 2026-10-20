"""W5 / I2 per-instance parity: re-create each pro Tornado cast that pulled enemies toward the caster's king (both princesses
up, king untouched; rows.pkl tornado rows) in RoyaleSim from the NATIVE re-drive's exact play frame (corpus_v6/icebow,
level 11) and compare the outcome: did each pulled unit come <= 3.5 tiles from the caster's king centre in the next 10 s,
and was the king hit?  Same engine coordinates and teams as native (side 0 = low rows in both). Spawned: every non-tower
body whose name is a single-body catalogue TROOP card (multi-body cards, sub-units and buildings are left out -- a known
simplification), with its native hp; towers at their native hp; the caster's Tornado at its native spot at once.

    laptop, no engine:  python sim_replay.py --build-cases sim_replay_cases.json        (needs rows.pkl + corpus_v6/icebow)
    laptop 0.1.35:      <v35>/Scripts/python.exe -I sim_replay.py --cases sim_replay_cases.json --out sim_replay_v35.json
    pod fin13:          ROYALE_RUNTIME=fin13-linux /workspace/venvf13/bin/python sim_replay.py --activate \\
                            --cases sim_replay_cases.json --out sim_replay_fin13.json          (sim_tornado_pod.sh)"""
from __future__ import annotations

import argparse
import json
import os
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[1] / 'ext/corpus_v6/icebow'
REACH = 3.5
HORIZON = 200
I8 = {'Tornado', 'Tesla', 'IceWizard', 'Xbow', 'Rocket', 'Knight', 'Log', 'Skeletons'}


def norm(card):          # = habits/hablib.norm (copied so the pod run needs no pipeline import)
    s = str(card).split('@')[0]
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', s).lower().replace('-', '_')
    s = re.sub(r'_(evo|ev1|ev2|hero)$', '', s)
    return {'xbow': 'x_bow', 'log': 'the_log', 'icewizard': 'ice_wizard', 'x_bow': 'x_bow'}.get(s, s)


def build_cases(path):
    import pickle
    R = pickle.load(open(HERE / 'rows.pkl', 'rb'))
    rows = [x for x in R['tornado'] if x['src'] == 'pro' and x['princesses_up'] == 2 and x['king_full_before']
            and x['toward_king'] is not None and x['toward_king'] > 1 and x['n_in']]
    cases = []
    for x in rows:
        d = json.load(open(NATIVE / f"replay_{x['key']}.json"))
        me = next(int(s) for s, v in d['final_decks'].items() if {c.split('@')[0] for c in v} == I8)
        play = next((p for p in d['log'] if p['side'] == me and p.get('card') == 'tornado' and p.get('accepted')
                     and p['tick'] == x['tick']), None)
        pf = next((f for f in d.get('play_frames', []) if play and f.get('play_index') == play['play_index']), None)
        if pf is None:
            continue
        cases.append(dict(key=x['key'], tick=x['tick'], me=me, play_xy=(play['x'], play['y']),
                          entities=[e[:5] for e in pf['entities'] if e[3] != '-1'], towers=pf['towers'],
                          units=x['units'], native_reach={u: x['reach_king'].get(u, 99) for u in x['units']},
                          native_king_hit=x['king_lost10'] > 0))
    Path(path).write_text(json.dumps(dict(n_rows=len(rows), cases=cases)))
    print('rows', len(rows), 'cases', len(cases))


def run(cases_path, out_path, activate):
    if activate:
        sys.path.insert(0, os.environ.get('CB_REPO', str(HERE.parents[3])))   # pod: CB_REPO=/workspace/cb_stepd
        from pipeline import royale_runtime
        royale_runtime.activate()
    import royalesim as r
    C = json.loads(Path(cases_path).read_text())
    b = r.Battle(None, [[0, 1, 2], [0, 1, 2]], level=11, tower_level=11)
    cat = [dict(zip(r.CATALOGUE_FIELDS, x)) for x in json.loads(b.catalogue_json())]
    ids = {c['name']: i for i, c in enumerate(cat)}
    single = {c['name'] for c in cat if c['count'] == 1 and c['card_kind'] == 'TROOP'}
    S = r.SUBTILE_PER_MILLITILE
    F = r.ENTITY_FIELDS
    out = dict(royalesim=getattr(r, '__version__', '?'), provenance=b.provenance(), n_rows=C['n_rows'], cases=[])
    for c in C['cases']:
        me = c['me']
        kx, ky = 9000, 29000 if me == 1 else 3000          # caster's king centre, engine millitiles
        spawns, skipped = [], []
        for side, ex, ey, name, hp in c['entities']:
            if name in single:
                spawns.append((side, ids[name], int(ex * S), int(ey * S), int(hp)))
            else:
                skipped.append(name)
        th = [[0, 0, 0], [0, 0, 0]]
        for ts, typ, lane, tx, ty, hp, mx in c['towers']:
            th[ts][0 if typ == 'king' else 1 if tx < 9000 else 2] = int(hp)
        deck_me = [ids[n] for n in ('Tornado', 'Knight', 'Skeletons', 'IceWizard', 'Tesla', 'Xbow', 'Rocket', 'Log')]
        deck_op = [ids[n] for n in ('Knight', 'Skeletons', 'Zap', 'Arrows', 'Fireball', 'Cannon', 'Bomber', 'Musketeer')]
        decks = [deck_me, deck_op] if me == 0 else [deck_op, deck_me]
        base = dict(key=c['key'], tick=c['tick'])
        try:
            b.reset(7, decks, 0, max(100, int(c['tick'])), [10000, 10000], th, spawns,
                    levels=[[11] * 8, [11] * 8], tower_levels=[11, 11])
        except Exception as ex_:                       # noqa: BLE001 -- a refused scenario is recorded, not fatal
            out['cases'].append(dict(base, error=f'reset: {ex_!r}'[:200]))
            continue
        res = b.step([(me, 0, int(c['play_xy'][0] * S), int(c['play_xy'][1] * S))], 0)[0]
        if res[1] != 0:
            out['cases'].append(dict(base, error=f'tornado refused {res}'))
            continue
        units = set(c['units'])
        best = defaultdict(lambda: 99.0)
        king0 = th[me][0]
        king_active = False
        for _ in range(HORIZON):
            b.step([], 1)
            s = json.loads(b.state_json())
            for e in s['entities']:
                e = dict(zip(F, e))
                if e['team'] != me and e['card_id'] >= 0:
                    k = norm(cat[e['card_id']]['name'])
                    if k in units:
                        best[k] = min(best[k], math.hypot(e['x'] / S - kx, e['y'] / S - ky) / 1000)
            king_active = king_active or bool(next(p for p in s['players'] if p['team'] == me).get('king_active'))
        s = json.loads(b.state_json())
        kh = next(p for p in s['players'] if p['team'] == me)['tower_hp'][0]
        out['cases'].append(dict(base, units=sorted(units), skipped=sorted(set(skipped)), native_reach=c['native_reach'],
                                 sim_reach={u: round(best[u], 2) for u in units},
                                 native_king_hit=c['native_king_hit'], sim_king_hit=kh < king0, sim_king_active=king_active))
    Path(out_path).write_text(json.dumps(out, indent=0))
    summary(out)


def summary(out):
    agg = defaultdict(lambda: [0, 0, 0, 0])            # n, native yes, sim yes, agree (cases where the unit was spawned)
    for c in out['cases']:
        if 'error' in c:
            continue
        for u in c['units']:
            if c['sim_reach'][u] >= 99:
                continue
            nv, sv = c['native_reach'][u] <= REACH, c['sim_reach'][u] <= REACH
            g = agg[u]
            g[0] += 1
            g[1] += nv
            g[2] += sv
            g[3] += nv == sv
    print('royalesim', out['royalesim'], 'cases', len(out['cases']), 'errors', sum('error' in c for c in out['cases']))
    print('unit | n | native onto king | SIM onto king | per-case agreement')
    for u, (n, nv, sv, ag) in sorted(agg.items(), key=lambda t: -t[1][0]):
        print(f'{u:16s} | {n:3d} | {nv / n:.2f} | {sv / n:.2f} | {ag / n:.2f}')
    ok = [c for c in out['cases'] if 'error' not in c]
    print('king hit: native', round(sum(c['native_king_hit'] for c in ok) / max(1, len(ok)), 3), 'SIM',
          round(sum(c['sim_king_hit'] for c in ok) / max(1, len(ok)), 3), 'agree',
          round(sum(c['native_king_hit'] == c['sim_king_hit'] for c in ok) / max(1, len(ok)), 3), 'n', len(ok))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build-cases')
    ap.add_argument('--cases')
    ap.add_argument('--out')
    ap.add_argument('--activate', action='store_true')
    a = ap.parse_args()
    if a.build_cases:
        build_cases(a.build_cases)
    else:
        run(a.cases, a.out, a.activate)
