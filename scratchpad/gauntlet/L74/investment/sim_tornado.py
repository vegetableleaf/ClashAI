"""W5 / I2 SIM check: does a Tornado pull an enemy bridge attacker onto OUR king and activate it, and how does that depend on
the unit (mass, range, building-targeting)?  Pure RoyaleSim public API, both sides level 16, no defenders: the opponent drops
unit U at its bridge (own frame 3.5, 14.5; we are team 1, king at y 29, own frame = engine millitiles), U walks at our left
princess; when U's y first reaches TRIGGER we cast a Tornado at P. Baseline: no Tornado. Recorded per run: U's pull
(tiles toward P), its target 2 s after the cast, king_active (first tick), king / princess HP lost in the 15 s after the drop.

    laptop (upstream 0.1.35 composite venv, NOT fin13):  <v35>/Scripts/python.exe -I sim_tornado.py --out sim_tornado_v35.json
    pod fin13 (the training SIM):  ROYALE_RUNTIME=fin13-linux /workspace/venvf13/bin/python sim_tornado.py --activate \
                                       --out sim_tornado_fin13.json        (sim_tornado_pod.sh)"""
from __future__ import annotations

import argparse
import json
import os
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNITS = ['HogRider', 'RoyalHogs', 'Balloon', 'BattleRam', 'RamRider', 'Giant', 'RoyalGiant', 'GoblinGiant', 'ElectroGiant',
         'Golem', 'Knight', 'MiniPekka', 'Valkyrie', 'Musketeer', 'Wizard', 'Pekka', 'MegaKnight', 'Prince', 'DarkPrince']
STATS_KEY = {'RoyalHogs': 'RoyalHog'}          # card name -> unit stats name where they differ
# Tornado centres (own frame, tiles). pro_spot = the pros' modal cast vs a bridge Hog in the left lane (rows.pkl: (8, 24),
# 198 / 403 casts); king_pocket nearer the king; princess = a pull that keeps it on the princess side (control).
SPOTS = {'pro_spot': (8.0, 24.0), 'king_pocket': (7.0, 26.0), 'mid': (6.0, 22.5), 'princess': (3.5, 22.5)}
TRIGGERS = (17.0, 19.0, 21.0)
DROP = (3.5, 14.5)
HORIZON = 300                      # 15 s after the drop


def load(activate):
    if activate:
        sys.path.insert(0, os.environ.get('CB_REPO', str(HERE.parents[3])))   # pod: CB_REPO=/workspace/cb_stepd
        from pipeline import royale_runtime
        royale_runtime.activate()
    import royalesim
    return royalesim


def run(r, ids, cat, unit, spot, trig):
    S = r.SUBTILE_PER_MILLITILE
    filler = [ids[n] for n in ('Knight', 'Skeletons', 'Zap', 'Arrows', 'Fireball', 'Cannon', 'Bomber', 'Musketeer', 'Giant')
              if n != unit][:7]
    d_opp = [ids[unit]] + filler
    d_us = [ids[n] for n in ('Tornado', 'Knight', 'Skeletons', 'IceWizard', 'Tesla', 'Xbow', 'Rocket', 'Log')]
    b = r.Battle(None, [[0, 1, 2], [0, 1, 2]])
    b.reset(7, [d_opp, d_us], 0, 0, [10000, 10000], None, [], forms=None, levels=[[16] * 8, [16] * 8], tower_levels=[16, 16])
    dx, dy = int(DROP[0] * 1000 * S), int(DROP[1] * 1000 * S)
    for _ in range(400):                            # deploys are refused (TOO_EARLY) during the start countdown
        if b.check_deploy(0, 0, dx, dy) == 0:
            break
        b.step([], 1)
    row = b.step([(0, 0, dx, dy)], 0)[0]
    if row[1] != 0:
        return dict(unit=unit, error=f'drop refused {row}')
    F = r.ENTITY_FIELDS
    king = pr_l = None
    cast_tick = pre = post = tgt = None
    king_active_tick = None
    first = None
    for k in range(HORIZON):
        s = json.loads(b.state_json())
        ents = [dict(zip(F, e)) for e in s['entities']]
        if king is None:
            king = next(e for e in ents if e['team'] == 1 and e['card_id'] == -1 and e['tower_slot'] == 0)
            pr_l = next(e for e in ents if e['team'] == 1 and e['card_id'] == -1 and e['tower_slot'] == 1 and e['x'] < 162000)
            first = {e['uid']: e['hp'] for e in ents if e['card_id'] == -1 and e['team'] == 1}
        us = [e for e in ents if e['team'] == 0 and e['card_id'] == ids[unit]]
        pl = next(p for p in s['players'] if p['team'] == 1)
        if king_active_tick is None and pl.get('king_active'):
            king_active_tick = s['tick']
        if us and spot and cast_tick is None and max(e['y'] for e in us) / (1000 * S) >= trig:
            pre = [(e['x'] / (1000 * S), e['y'] / (1000 * S)) for e in us]
            res = b.step([(1, 0, int(SPOTS[spot][0] * 1000 * S), int(SPOTS[spot][1] * 1000 * S))], 0)[0]
            if res[1] != 0:
                return dict(unit=unit, spot=spot, trig=trig, error=f'tornado refused {res}')
            cast_tick = s['tick']
        if cast_tick is not None and post is None and s['tick'] >= cast_tick + 30:
            post = [(e['x'] / (1000 * S), e['y'] / (1000 * S)) for e in us]
        if cast_tick is not None and tgt is None and s['tick'] >= cast_tick + 40:
            tu = {e['target_uid'] for e in us}
            tgt = 'king' if king['uid'] in tu else 'princess' if pr_l['uid'] in tu else 'none' if tu == {-1} or not us else 'other'
        b.step([], 1)
    s = json.loads(b.state_json())
    hp = {dict(zip(F, e))['uid']: dict(zip(F, e))['hp'] for e in s['entities'] if dict(zip(F, e))['card_id'] == -1
          and dict(zip(F, e))['team'] == 1}
    km = king['max_hp']
    pm = pr_l['max_hp']
    pull = None
    if pre and post and len(pre) == len(post):
        cx, cy = SPOTS[spot]
        pull = round(sum(math.hypot(a - cx, b_ - cy) - math.hypot(c - cx, d - cy) for (a, b_), (c, d) in zip(pre, post)) / len(pre), 2)
    u = cat.get(STATS_KEY.get(unit, unit), {})
    return dict(unit=unit, mass=u.get('mass'), range=u.get('range_milli'), sight=u.get('sight_range_milli'),
                buildings_only=u.get('target_only_buildings'), spot=spot, trig=trig, cast_tick=cast_tick,
                pre=pre and [tuple(round(v, 2) for v in p) for p in pre], post=post and [tuple(round(v, 2) for v in p) for p in post],
                pull_tiles=pull, target_after=tgt, king_active_tick=king_active_tick,
                king_lost=round((first[king['uid']] - hp.get(king['uid'], 0)) / km, 3),
                princess_lost=round(sum(first[i] - hp.get(i, 0) for i in first if i != king['uid']) / pm, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--activate', action='store_true', help='pipeline.royale_runtime.activate() first (pod fin13)')
    a = ap.parse_args()
    r = load(a.activate)
    b = r.Battle(None, [[0, 1, 2], [0, 1, 2]])
    names = [x[0] for x in json.loads(b.catalogue_json())]
    ids = {n: i for i, n in enumerate(names)}
    units = json.loads(r.EMBEDDED_CARDS_160402017_JSON)['units'] if hasattr(r, 'EMBEDDED_CARDS_160402017_JSON') else {}
    out = dict(royalesim=getattr(r, '__version__', '?'), provenance=b.provenance(), runs=[])
    for unit in UNITS:
        if unit not in ids:
            out['runs'].append(dict(unit=unit, error='not in catalogue'))
            continue
        out['runs'].append(run(r, ids, units, unit, None, None))
        for spot in SPOTS:
            for trig in TRIGGERS:
                out['runs'].append(run(r, ids, units, unit, spot, trig))
    Path(a.out).write_text(json.dumps(out, indent=0))
    for x in out['runs']:
        print({k: x.get(k) for k in ('unit', 'mass', 'spot', 'trig', 'pull_tiles', 'target_after', 'king_active_tick',
                                     'king_lost', 'princess_lost', 'error')})


if __name__ == '__main__':
    main()
