"""Live king activation vs its trigger, from live frames only (lead 10-22: does the SIM wake our king later than live?).
Per side and match: the first frame the king tower reads active (kind 13), the first princess-fall tick (row gone or hp <= 0)
and the first king hp drop. Wake - trigger is compared with the SIM's law (king_activate_time_ms 3550 = 71 ticks after the
trigger: J3 'wake law given the SIM trigger' 1107 / 1107 on fin15).
  python king_wake.py LIVE_DIR [GLOB]"""
import glob
import json
import sys
from collections import Counter
from pathlib import Path

SLOTS = ((9000, 3000), (3500, 6500), (14500, 6500), (9000, 29000), (3500, 25500), (14500, 25500))
d, g = Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'live_play_*.jsonl'
res = Counter(); rows = []
for p in sorted(glob.glob(str(d / g))):
    ticks, my = [], None
    st = {s: dict(kwake=None, khp0=None, khurt=None, last={}, fall=None) for s in (0, 1)}
    with open(p, 'rb') as f:
        for raw in f:
            if b'"frame"' not in raw[:40]:
                continue
            j = json.loads(raw)
            t = j['tick']; ticks.append(t); my = j['my_side']
            for s_, x, y, cid, hp, mx, kind, addr in j['ents']:
                if cid != -1 or not any(abs(x - tx) < 600 and abs(y - ty) < 600 for tx, ty in SLOTS):
                    continue
                S = st[s_]
                if abs(x - 9000) < 1000:
                    if S['khp0'] is None:
                        S['khp0'] = hp
                    if S['khurt'] is None and hp < S['khp0']:
                        S['khurt'] = t
                    if S['kwake'] is None and kind == 13:
                        S['kwake'] = t
                else:
                    k = 'L' if x < 9000 else 'R'
                    if hp <= 0:
                        S['fall'] = t if S['fall'] is None else min(S['fall'], t)
                    else:
                        S['last'][k] = t
    if not ticks:
        continue
    for s_ in (0, 1):
        S = st[s_]
        fall = S['fall']
        for k, t in S['last'].items():
            nxt = [u for u in ticks if u > t]
            if nxt and ticks[-1] - t > 40:
                fall = nxt[0] if fall is None else min(fall, nxt[0])
        if S['kwake'] is None or S['kwake'] == ticks[0]:
            res['awake at start or never'] += S['kwake'] == ticks[0]
            continue
        trig = min([x for x in (fall, S['khurt']) if x is not None], default=None)
        if trig is None:
            res['wake without a seen trigger'] += 1
            continue
        cause = 'princess' if fall is not None and fall <= (S['khurt'] or 10 ** 9) else 'damage'
        rows.append((cause, 'own' if s_ == my else 'opp', S['kwake'] - trig))
print(dict(res))
for cause in ('princess', 'damage'):
    for side in ('own', 'opp'):
        v = sorted(r[2] for r in rows if r[0] == cause and r[1] == side)
        if v:
            print(f'{cause:8s} {side}: n {len(v)}, wake - trigger ticks median {v[len(v)//2]}, '
                  f'quartiles {v[len(v)//4]} / {v[3*len(v)//4]}, within 71 +-4: {sum(67 <= x <= 75 for x in v)}, '
                  f'> 75: {sum(x > 75 for x in v)}, < 67: {sum(x < 67 for x in v)}; top {Counter(v).most_common(5)}')
