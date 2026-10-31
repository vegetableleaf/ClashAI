"""FREEZE-LIVE step 2a: one row per Hero-IW press decision (`ability`) / held decision (`ability_held`) in the live logs, with our princess
HP lost (sum over our 2 princess towers of (max - hp) / 4858; a tower row missing = destroyed) at t, t+150, t+300, t+450, t+900 read from
the reader `frame` events. Same layout as the SIM rows of freeze_live_est.py (head_feat = the 'freeze' ability features, index 46 =
the freeze target's troop elixir / 10).

  python -B freeze_live_parse.py OUT.jsonl [FIRST_DAY LAST_DAY]      (default 20261026 20261031)

Low priority, single process, reads each log once (~20 MB per match)."""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
from pathlib import Path

LOGS = Path(__file__).resolve().parents[5] / 'scratchpad/gauntlet/L68/live_reader'
HZ = (0, 150, 300, 450, 900)
PRINCESS_HP = 4858.0   # level-16 princess tower (main account), reader max_hp


def read_match(p):
    r = dict(ckpt=None, opt=None, won=None, secs=None, moments=[], frames=[], my_side=None, towers0=None)
    for raw in open(p, 'rb'):
        head = raw[:40]
        if head.startswith(b'{"event": "frame"'):
            j = json.loads(raw)
            ms = j.get('my_side')
            tw = {}
            for e in j.get('ents') or ():
                if e[6] == 13 and e[0] == ms:
                    tw[(e[1], e[2])] = (e[4], e[5])
            if r['towers0'] is None:
                r['towers0'] = {}
                r['my_side'] = ms
            if j['tick'] < 400:                      # the union of the first frames: a frame can miss a tower row
                for k, v in tw.items():
                    r['towers0'].setdefault(k, v[1])
            r['frames'].append((j['tick'], tw))
        elif head.startswith(b'{"event": "start"'):
            j = json.loads(raw)
            r['ckpt'] = Path(j.get('ckpt') or '').name
            r['opt'] = hashlib.md5(json.dumps(j.get('decision_options') or {}, sort_keys=True).encode()).hexdigest()[:6]
        elif head.startswith(b'{"event": "ability"') and not head.startswith(b'{"event": "ability_'):
            j = json.loads(raw)
            r['moments'].append(dict(kind='press', tick=j['tick'], elixir=j.get('elixir'), feat=j.get('head_feat'), why=j.get('why')))
        elif head.startswith(b'{"event": "ability_confirmed"'):
            j = json.loads(raw)
            for m in reversed(r['moments']):
                if m['kind'] == 'press' and 'conf' not in m:
                    if j['tick'] - m['tick'] < 120:
                        m['conf'] = j['tick']
                    break
        elif head.startswith(b'{"event": "ability_held"'):
            j = json.loads(raw)
            r['moments'].append(dict(kind='held', tick=j['tick'], elixir=j.get('elixir'), feat=j.get('head_feat'), why=j.get('why')))
        elif head.startswith(b'{"event": "end"'):
            j = json.loads(raw)
            r['secs'] = j.get('seconds'); r['won'] = (j.get('towers') or {}).get('won'); r['end_tick'] = (j.get('towers') or {}).get('tick')
    r['frames'] = to_lost(r['frames'], r['towers0'] or {})
    return r


def to_lost(raw, towers0):
    """per-frame (tick, our princess HP lost in princess units). A tower row missing from one frame is a reader gap, not a kill: HP only
    falls (running minimum of the HP seen); a tower is destroyed from its first missing tick only if it never reappears."""
    if not raw:
        return []
    last_seen = {k: None for k in towers0}
    for t, tw in raw:
        for k in towers0:
            if k in tw:
                last_seen[k] = t
    end = raw[-1][0]
    cur = {k: mx for k, mx in towers0.items()}
    out = []
    for t, tw in raw:
        for k, mx in towers0.items():
            if k in tw:
                cur[k] = min(cur[k], max(tw[k][0], 0))
            elif last_seen[k] is not None and t > last_seen[k] and end - last_seen[k] > 40:
                cur[k] = 0                                   # gone for the rest of the match = destroyed
            elif last_seen[k] is None:
                cur[k] = 0
        out.append((t, sum((mx - cur[k]) / PRINCESS_HP for k, mx in towers0.items()), len(tw)))
    return out


def lost_at(frames, t):
    """our princess HP lost at the last frame with tick <= t (None when the log has no frame within 6 ticks after / at t)."""
    lo, hi = 0, len(frames) - 1
    if hi < 0 or frames[0][0] > t:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if frames[mid][0] <= t:
            lo = mid
        else:
            hi = mid - 1
    return frames[lo][1] if t - frames[lo][0] <= 8 else None


def main():
    out = sys.argv[1]
    d0 = sys.argv[2] if len(sys.argv) > 2 else '20261026'
    d1 = sys.argv[3] if len(sys.argv) > 3 else '20261031'
    try:
        os.nice(10)
    except Exception:
        pass
    files = sorted(f for f in glob.glob(str(LOGS / 'live_play_*.jsonl')) if d0 <= Path(f).name[10:18] <= d1)
    n = 0
    with open(out, 'w') as w:
        for i, f in enumerate(files):
            try:
                r = read_match(f)
            except Exception as e:  # noqa
                print('skip', f, e, file=sys.stderr)
                continue
            if r['won'] is None or not r['frames'] or not r['moments']:
                continue
            fr = r['frames']
            last = fr[-1][0]
            for m in r['moments']:
                t = m['tick']
                base = lost_at(fr, t)
                m['lost'] = {str(h): (None if base is None or t + h > last else lost_at(fr, t + h)) for h in HZ}
                m['match'] = Path(f).name[:-6]; m['ckpt'] = r['ckpt']; m['opt'] = r['opt']; m['won'] = r['won']
                m['last'] = last
                w.write(json.dumps(m) + '\n'); n += 1
            if i % 100 == 0:
                print(i, len(files), n, flush=True)
    print('rows', n)


if __name__ == '__main__':
    main()
