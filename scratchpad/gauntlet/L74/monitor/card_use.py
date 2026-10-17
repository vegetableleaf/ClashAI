"""Live card-use monitor (owner 10-17: "monitor Mark CXXXVIII's rocket and tornado use across matches").

Per live ladder match since --since: the model (start event ckpt -> Mark name via the checkpoint registry), confirmed plays of
each --cards card, all confirmed plays, length, and the ladder result + trophies (overnight.out, the line after the match's
summary). Then per Mark: plays per match and per minute of each card, share of matches with >= 1, win rate, trophies / match,
with a match-bootstrap 95% CI on the difference to --base.

  python card_use.py [--since 20261017_000000] [--cards Rocket,Tornado] [--base "ICEBOW Mark CXXIV: LONGER"]
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import re
import sys

REPO = Path(__file__).resolve().parents[4]
LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
OUT = REPO / 'scratchpad/gauntlet/L70/live/overnight.out'
sys.path.insert(0, str(REPO / 'scratchpad/gauntlet/L74/models'))


def results():
    """{log name: (result, trophies)} from overnight.out: a match's summary JSON line names its log; the next
    '[ladder] result:' line is that match's outcome."""
    out, last = {}, None
    for line in OUT.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('{') and '"log"' in line:
            try:
                last = Path(json.loads(line)['log']).name
            except (ValueError, KeyError):
                pass
        elif line.startswith('[ladder] result:') and last:
            m = re.match(r'\[ladder\] result: (\w+).*?trophies ([+-]?\d+)', line)
            if m:
                out[last] = (m[1], int(m[2]))
            last = None
    return out


def match(path, cards):
    ck = None; n = {c: 0 for c in cards}; plays = 0; secs = None
    for raw in open(path, 'rb'):
        head = raw[:30]
        if b'"start"' in head and ck is None:
            ck = json.loads(raw).get('ckpt')
        elif b'"confirmed"' in head:
            j = json.loads(raw); plays += 1
            if j.get('name') in n:
                n[j['name']] += 1
        elif b'"end"' in head:
            secs = json.loads(raw).get('seconds')
    return ck, n, plays, secs


def mark_of(ck, cache={}):
    """The checkpoint's Mark name (registry lookup by sha256, hashed once per path), else its file name."""
    if ck not in cache:
        name = None
        try:
            import register_ckpt as R
            name = R.Registry(R.HERE / 'registry.json', R.ROOT).lookup(R.sha256(Path(ck)))
        except Exception:                      # noqa: BLE001 -- the registry is a convenience; fall back to the file name
            pass
        cache[ck] = name if name and not name.startswith('unregistered') else Path(ck or 'unknown').name
    return cache[ck]


def boot_diff(a, b, f, B=2000, seed=0):
    rng = random.Random(seed); d = []
    for _ in range(B):
        x = [rng.choice(a) for _ in a]; y = [rng.choice(b) for _ in b]
        d.append(f(x) - f(y))
    d.sort()
    return round(d[int(.025*B)], 3), round(d[int(.975*B)-1], 3)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='20261017_000000')
    ap.add_argument('--cards', default='Rocket,Tornado')
    ap.add_argument('--base', default='ICEBOW Mark CXXIV: LONGER')
    a = ap.parse_args(argv)
    cards = a.cards.split(',')
    res = results()
    rows = defaultdict(list)
    for p in sorted(LOGS.glob('live_play_2026*.jsonl')):
        if p.stem[10:] < a.since or p.name not in res:        # only finished ladder matches with a recorded result
            continue
        ck, n, plays, secs = match(p, cards)
        if not ck or not secs:
            continue
        rows[mark_of(ck)].append(dict(n=n, plays=plays, mins=secs/60, win=res[p.name][0] == 'WIN', tro=res[p.name][1]))
    mean = lambda xs: sum(xs)/len(xs) if xs else float('nan')
    for mk, rs in sorted(rows.items(), key=lambda kv: -len(kv[1])):
        print(f"\n{mk}: {len(rs)} matches, win {mean([r['win'] for r in rs]):.3f}, trophies/match {mean([r['tro'] for r in rs]):+.1f}, "
              f"plays/match {mean([r['plays'] for r in rs]):.1f}")
        for c in cards:
            print(f"  {c}: {mean([r['n'][c] for r in rs]):.2f} / match, {mean([r['n'][c]/r['mins'] for r in rs]):.2f} / min, "
                  f"in {mean([r['n'][c] > 0 for r in rs]):.2f} of matches, {mean([r['n'][c]/max(1, r['plays']) for r in rs]):.3f} of plays")
    base = rows.get(a.base)
    for mk, rs in rows.items():
        if base and mk != a.base and len(rs) >= 2:
            print(f"\n{mk} - {a.base} (match-bootstrap 95% CI):")
            for c in cards:
                f = lambda xs, c=c: mean([r['n'][c] for r in xs])
                print(f"  {c} / match {f(rs) - f(base):+.2f} {boot_diff(rs, base, f)}")
            w = lambda xs: mean([r['win'] for r in xs])
            print(f"  win rate {w(rs) - w(base):+.3f} {boot_diff(rs, base, w)}")


if __name__ == '__main__':
    main(sys.argv[1:])
