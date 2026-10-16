"""Summarise probe.py output: per run, the target's walk speed / attack progress / hit interval, slowed vs not.

Usage: python analyze.py probe_out.json
"""
import json
import math
import sys
from collections import Counter

K = 18000  # subtiles per tile


def target_of(frames, kind_card):
    """Track the red target (first red Troop) by entity index."""
    for f in frames:
        for r in f.get('rows', []):
            if r['team'] == 'Red' and r['kind'] == 'Troop':
                return r['i']
    return None


def buff_ids(r):
    return tuple(sorted((b['id'], b['ms']) for b in r['buffs'] if b['id']))


def summarise(name, frames):
    frames = [f for f in frames if 'rows' in f]
    ti = target_of(frames, None)
    rows = []
    for f in frames:
        r = next((r for r in f['rows'] if r['i'] == ti), None)
        king = next((x for x in f['rows'] if x['team'] == 'Blue' and x['kind'] == 'KingTower'), None)
        rows.append((f['tick'], r, king['hp'] if king else None))
    walk = {True: [], False: []}
    prog = {True: Counter(), False: Counter()}
    ids = Counter()
    first_buff = None
    durations = []
    run_start = None
    for (t0, a, _), (t1, b, _) in zip(rows, rows[1:]):
        if a is None or b is None or not b['alive']:
            continue
        slowed = bool(buff_ids(b))
        for bid, _ms in buff_ids(b):
            ids[bid] += 1
        if slowed and first_buff is None:
            first_buff = (t1, buff_ids(b))
        if slowed and run_start is None:
            run_start = t1
        if not slowed and run_start is not None:
            durations.append(t1 - run_start)
            run_start = None
        d = math.hypot(b['pos']['x'] - a['pos']['x'], b['pos']['y'] - a['pos']['y'])
        if d > 0 and b['stun_ms'] == 0:
            walk[slowed].append(d)
        if b['attack_ms'] > a['attack_ms']:
            prog[slowed][b['attack_ms'] - a['attack_ms']] += 1
    seg = []  # (first tick, last tick, buff id set, median walk subtiles/tick) runs of one buff-id set
    for (t0, a, _), (t1, b, _) in zip(rows, rows[1:]):
        if a is None or b is None:
            continue
        key = tuple(sorted(x['id'] for x in b['buffs']))
        d = round(math.hypot(b['pos']['x'] - a['pos']['x'], b['pos']['y'] - a['pos']['y']))
        if seg and seg[-1][2] == key and seg[-1][1] == t1 - 1:
            seg[-1][1] = t1
            seg[-1][3].append(d)
        else:
            seg.append([t1, t1, key, [d]])
    timeline = [(a, b, k, sorted(v)[len(v) // 2]) for a, b, k, v in seg]
    hits = [t for (t, _, h0), (_, _, h1) in zip(rows, rows[1:]) if h0 is not None and h1 is not None and h1 < h0]

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else None
    out = {
        'run': name,
        'first_buffed_tick': first_buff,
        'buff_ids_seen(id: ticks)': dict(ids),
        'buffed_runs_ticks': durations + ([f'open@{run_start}'] if run_start is not None else []),
        'walk_subtiles_per_tick_median': {'unslowed': med(walk[False]), 'slowed': med(walk[True])},
        'walk_ticks': {'unslowed': len(walk[False]), 'slowed': len(walk[True])},
        'attack_progress_gain_per_tick': {'unslowed': dict(prog[False]), 'slowed': dict(prog[True])},
        'timeline(first,last,buff_ids,median_step)': timeline,
        'target_hp_drop_ticks': [t1 for (t0, a, _), (t1, b, _) in zip(rows, rows[1:]) if a and b and b['hp'] < a['hp']][:40],
        'king_hp_drop_ticks': hits[:30],
        'king_hit_intervals': [b - a for a, b in zip(hits, hits[1:])][:30],
    }
    return out


def main():
    res = json.load(open(sys.argv[1]))
    print('royalesim', res['version'], res['provenance'], 'errors:', res.get('errors'))
    for name, frames in res['runs'].items():
        s = summarise(name, frames)
        print(json.dumps(s))


if __name__ == '__main__':
    main()
