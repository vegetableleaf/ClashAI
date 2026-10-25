"""succ48 (owner 10-25: CLXIII "struggles with Rocket use in general, as well as rocket cycling enemy tower as a long-term
strategy"): Rocket counts straight from board-recorded SIM rows (gap.py --record-board 'hab'), no extra telemetry needed.

    python rocket_count.py NAME=DIR [NAME=DIR ...]      DIR holds */D3/matches.jsonl (one dir per seed block)

Per source: matches, win; Rockets / match; TOWER Rockets / match (blast centre <= 3 tiles of an enemy crown tower: the
hablib.rocket_uses tower rule) by phase 1x (< 120 s) / 2x (120-180 s) / OT; share of matches with >= 2 tower Rockets; win rate
by tower-Rocket count (association only). Coordinates as ape_score.hab_match (engine millitiles or tiles)."""
import glob
import json
import math
import sys

TOWER_R = 3.0          # tiles: hablib.rocket_uses tower rule


def tiles(x, y):
    return (x / 1000, y / 1000) if max(abs(x), abs(y)) > 100 else (x, y)


def phase(t):
    return '1x' if t < 2400 else '2x' if t < 3600 else 'OT'


def match_rows(d):
    for f in sorted(glob.glob(f'{d}/*/D3/matches.jsonl') + glob.glob(f'{d}/*/D3/*/matches.jsonl')):
        for line in open(f):
            r = json.loads(line)
            h = r.get('hab')
            if h and h.get('samples'):
                yield r, h


def one(r, h):
    side = h['L']
    towers = [tiles(t[2], t[3]) for t in h['samples'][0][5] if t[0] != side]
    out = {'win': r.get('outcome') == 'win', 'rk': 0, 'tw': {'1x': 0, '2x': 0, 'OT': 0}}
    for q in h['own']:
        if not q[3] or 'rocket' not in str(q[2]).lower():
            continue
        out['rk'] += 1
        x, y = tiles(q[8], q[9])
        if any(math.hypot(x - a, y - b) <= TOWER_R for a, b in towers):
            out['tw'][phase(q[1] if q[1] is not None else q[0])] += 1
    return out


def main():
    for arg in sys.argv[1:]:
        name, d = arg.split('=', 1)
        M = [one(r, h) for r, h in match_rows(d)]
        n = len(M)
        if not n:
            print(f'{name}: no board-recorded rows under {d}')
            continue
        tw = [sum(m['tw'].values()) for m in M]
        line = (f"{name}: matches {n}, win {sum(m['win'] for m in M) / n:.3f}, Rockets / match {sum(m['rk'] for m in M) / n:.2f}, "
                f"tower Rockets / match {sum(tw) / n:.2f} (1x {sum(m['tw']['1x'] for m in M) / n:.2f}, 2x "
                f"{sum(m['tw']['2x'] for m in M) / n:.2f}, OT {sum(m['tw']['OT'] for m in M) / n:.2f}), share >= 2 tower "
                f"Rockets {sum(t >= 2 for t in tw) / n:.3f}")
        print(line)
        for lo, hi, lab in ((0, 0, '0'), (1, 1, '1'), (2, 99, '2+')):
            S = [m for m, t in zip(M, tw) if lo <= t <= hi]
            if S:
                print(f"   tower Rockets {lab}: n {len(S)}, win {sum(m['win'] for m in S) / len(S):.3f}")


if __name__ == '__main__':
    main()
