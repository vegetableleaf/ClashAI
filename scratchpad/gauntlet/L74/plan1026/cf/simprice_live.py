"""SIMPRICE step 0 (lead 10-31): live per-match Rocket / X-Bow / Hero-IW-ability counts by model + live option set.

Events (live_play_*.jsonl, L68/live_reader): `confirmed` {name, intended [x, y] screen-normalised, own side at the bottom};
`ability` = an IW press tapped, `ability_confirmed` = the press seen (elixir drop); `start` {ckpt, decision_options}.
X-Bow placement classes from the intended y (tiles ~ 32.5 * y - 0.3, fitted on the enemy princess y .21 = tile 6.5 and the
bridge .61 = tile 19.5): bridge/offensive y <= .64 (card_use.OFFENSIVE_Y), enemy half (pocket, tile < 16) y < .50.
Groups (the decision_options digest separates the old-rule daytime set from the stripped set):
  CLXIII_rules  = CLXIII, 10-30 daytime option set (rocket_value 9, rocket_tornado only, lethal_rocket ot_behind, tau_phase)
  CLXIII_strip  = CLXIII on the stripped set (10-30 21:38 .. 10-31 02:24, and 04:40 .. 06:04 shown separately)
  CLXV          = CLXV LARGEBATCH (10-31 02:30 .. 04:40 and from 06:04)
Only matches with an `end` event and >= 60 s are counted; win = the end event's towers.won (reader crowns). CIs: match bootstrap 95%.

  python -B simprice_live.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'


def read(p):
    r = dict(rocket=0, xbow=0, xbow_bridge=0, xbow_pocket=0, iw_tap=0, iw_conf=0, plays=0, secs=None, ck=None, opt=None)
    for raw in open(p, 'rb'):
        head = raw[:32]
        if b'"start"' in head and r['ck'] is None:
            j = json.loads(raw)
            r['ck'] = Path(j.get('ckpt') or '').name
            r['opt'] = hashlib.md5(json.dumps(j.get('decision_options') or {}, sort_keys=True).encode()).hexdigest()[:6]
        elif b'"confirmed"' in head:
            j = json.loads(raw); r['plays'] += 1
            n, xy = j.get('name'), j.get('intended') or [None, None]
            r['rocket'] += n == 'Rocket'
            if n == 'Xbow':
                r['xbow'] += 1
                r['xbow_bridge'] += xy[1] is not None and xy[1] <= .64
                r['xbow_pocket'] += xy[1] is not None and xy[1] < .50
        elif b'"ability_confirmed"' in head:
            r['iw_conf'] += 1
        elif b'"ability"' in head:
            r['iw_tap'] += 1
        elif b'"end"' in head:
            j = json.loads(raw); r['secs'] = j.get('seconds'); r['won'] = (j.get('towers') or {}).get('won')
    return r


def group(name, r):
    if r['ck'] == 'ICEBOW_Mark_CLXV_LARGEBATCH.pt':
        return 'CLXV'
    if r['ck'] == 'ICEBOW_Mark_CLXIII_NOLEAK.pt':
        if r['opt'] == '194f55':
            return 'CLXIII_rules'
        if r['opt'] == 'b90c49':
            return 'CLXIII_strip_a' if name < 'live_play_20261031_030000' else 'CLXIII_strip_b'
    return None


def boot(xs, ys=None, B=4000, seed=0):
    rng = random.Random(seed); m = lambda v: sum(v) / len(v); d = []
    for _ in range(B):
        a = [rng.choice(xs) for _ in xs]
        d.append(m(a) - (m([rng.choice(ys) for _ in ys]) if ys else 0))
    d.sort()
    return d[int(.025 * B)], d[int(.975 * B) - 1]


def main():
    rows = {}
    for p in sorted(glob.glob(str(LOGS / 'live_play_2026103[01]_*.jsonl'))):
        name = Path(p).name
        r = read(p)
        g = group(name, r)
        if g is None or not r['secs'] or r['secs'] < 60:
            continue
        r['win'] = None if r.get('won') is None else float(r['won'])
        r['name'] = name
        rows.setdefault(g, []).append(r)
    rows['CLXIII_strip'] = rows.get('CLXIII_strip_a', []) + rows.get('CLXIII_strip_b', [])
    keys = ('rocket', 'xbow', 'xbow_bridge', 'xbow_pocket', 'iw_conf', 'iw_tap', 'plays')
    for g in ('CLXIII_rules', 'CLXIII_strip_a', 'CLXIII_strip_b', 'CLXIII_strip', 'CLXV'):
        rs = rows.get(g, [])
        if not rs:
            continue
        w = [r['win'] for r in rs if r['win'] is not None]
        print(f"{g}: {len(rs)} matches ({rs[0]['name'][10:25]} .. {rs[-1]['name'][10:25]}), win {sum(w)/max(1,len(w)):.3f} "
              f"(n {len(w)}), mins/match {sum(r['secs'] for r in rs)/len(rs)/60:.2f}")
        for k in keys:
            v = [r[k] for r in rs]; lo, hi = boot(v)
            pm = sum(r[k] / (r['secs'] / 60) for r in rs) / len(rs)
            print(f"  {k:12s} {sum(v)/len(v):6.2f} / match [{lo:.2f}, {hi:.2f}]  {pm:.3f} / min  any {sum(x > 0 for x in v)/len(v):.2f}")
    for a, b in (('CLXV', 'CLXIII_strip'), ('CLXV', 'CLXIII_rules'), ('CLXIII_strip', 'CLXIII_rules')):
        if rows.get(a) and rows.get(b):
            print(f"\n{a} - {b}:")
            for k in keys:
                x = [r[k] for r in rows[a]]; y = [r[k] for r in rows[b]]
                lo, hi = boot(x, y)
                print(f"  {k:12s} {sum(x)/len(x) - sum(y)/len(y):+6.2f} [{lo:+.2f}, {hi:+.2f}]")


if __name__ == '__main__':
    main()
