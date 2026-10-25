"""succ48 (owner 10-25: "the model still insists on spamming offensive xbows in matchups where an xbow lock is entirely impossible
... 10 separate occasions where an xbow failed and it still tries ... it's a in-general rule"): X-Bow outcomes from board-recorded
SIM rows (gap.py --record-board 'hab').

    python xbow_count.py NAME=DIR [NAME=DIR ...]      DIR holds */D3/matches.jsonl (one dir per seed block)

REACH X-Bow = our accepted X-Bow whose placement is <= REACH tiles (centre to centre) from an alive enemy princess (INVESTMENT.md
lock reach 13.5). FAILED = no enemy princess lost >= LOCK_FRAC of its max HP within WINDOW ticks after the play (the lock rule
"lost >= 5% of a princess while the X-Bow lived", with a fixed window instead of the X-Bow's life). Per source: X-Bows / match,
reach X-Bows / match, failed share, failed reach X-Bows / match, matches with >= 3 failed, and how many reach X-Bows follow 2+
failures in the same match (the 'keeps trying' count). Coordinates as ape_score.hab_match."""
import glob
import json
import math
import sys

REACH, LOCK_FRAC, WINDOW = 13.5, 0.05, 600          # tiles, share of princess max HP, ticks (30 s; ponytail: not the X-Bow life)


def tiles(x, y):
    return (x / 1000, y / 1000) if max(abs(x), abs(y)) > 100 else (x, y)


def rows(d):
    seen = set()
    for f in sorted(set(glob.glob(f'{d}/*/D3/matches.jsonl') + glob.glob(f'{d}/*/D3/*/matches.jsonl'))):
        for line in open(f):
            r = json.loads(line)
            h = r.get('hab')
            k = (r.get('seed'), r.get('tag'), r.get('learner_side'), str(r.get('opp_deck')))
            if h and h.get('samples') and k not in seen:
                seen.add(k)
                yield r, h


def one(h):
    side = h['L']
    smp = h['samples']
    # enemy princesses: (x, y) -> [(tick, hp)]; kind 'k' = king
    series = {}
    for s in smp:
        for t_ in s[5]:
            if t_[0] != side and t_[1] != 'k':
                series.setdefault(tiles(t_[2], t_[3]), []).append((s[0], t_[4]))
    out = {'xb': 0, 'reach': 0, 'fail': 0, 'after2': 0}
    fails = 0
    for q in h['own']:
        if not q[3] or 'bow' not in str(q[2]).lower().replace('-', ''):
            continue
        out['xb'] += 1
        t0 = q[1] if q[1] is not None else q[0]
        x, y = tiles(q[8], q[9])
        near = []
        for pos, ser in series.items():
            hp0 = next((hp for t, hp in reversed(ser) if t <= t0), None)
            if hp0 and hp0 > 0 and math.hypot(x - pos[0], y - pos[1]) <= REACH:
                near.append((hp0, max(hp for _, hp in ser), [hp for t, hp in ser if t0 < t <= t0 + WINDOW]))
        if not near:
            continue
        out['reach'] += 1
        if fails >= 2:
            out['after2'] += 1
        locked = any(later and (hp0 - min(later)) >= LOCK_FRAC * mx for hp0, mx, later in near)
        if not locked:
            out['fail'] += 1
            fails += 1
    return out


def main():
    for arg in sys.argv[1:]:
        name, d = arg.split('=', 1)
        M = [one(h) for _, h in rows(d)]
        n = len(M)
        if not n:
            print(f'{name}: no board-recorded rows under {d}')
            continue
        s = {k: sum(m[k] for m in M) for k in ('xb', 'reach', 'fail', 'after2')}
        print(f"{name}: matches {n} | X-Bows / match {s['xb'] / n:.2f} | reach X-Bows / match {s['reach'] / n:.2f} | failed share "
              f"{s['fail'] / max(1, s['reach']):.3f} | failed / match {s['fail'] / n:.2f} | matches with >= 3 failed "
              f"{sum(m['fail'] >= 3 for m in M) / n:.3f} | reach X-Bows after 2+ failures / match {s['after2'] / n:.2f}")


if __name__ == '__main__':
    main()
