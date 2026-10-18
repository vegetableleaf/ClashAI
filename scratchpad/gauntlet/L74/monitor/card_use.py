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


def results(lines=None):
    """{log name: (result, trophies)} from overnight.out: a match's summary JSON line names its log; the next
    '[ladder] result:' line is that match's outcome. A match with no result line (a trophy-road reward screen replaced the
    results screen) or with 'trophies n/a' gets its change from the '[ladder] trophies: N total' readings around it, when it
    is the only such match between two readings (critic 10-17: 3 CXXXVIII wins at 13k were missing): WIN if > 0, LOSS if < 0
    or 0 at the 13,000 floor; otherwise it stays out."""
    out, last, ev = {}, None, []          # ev: ('A', total) trophy readings and ('M', log) matches, in file order
    for line in (OUT.read_text(encoding='utf-8', errors='replace').splitlines() if lines is None else lines):
        if line.startswith('{') and '"log"' in line:
            try:
                last = Path(json.loads(line)['log']).name; ev.append(('M', last))
            except (ValueError, KeyError):
                pass
        elif line.startswith('[ladder] trophies:'):
            m = re.match(r'\[ladder\] trophies: (\d+) total', line)
            if m:
                ev.append(('A', int(m[1])))
        elif line.startswith('[ladder] result:') and last:
            m = re.match(r'\[ladder\] result: (\w+).*?trophies ([+-]?\d+)', line)
            if m:
                out[last] = (m[1], int(m[2]))
            last = None
    anchors = [k for k, e in enumerate(ev) if e[0] == 'A']
    for a, b in zip(anchors, anchors[1:]):
        logs = [e[1] for e in ev[a + 1:b] if e[0] == 'M']
        miss = [n for n in logs if n not in out]
        if len(miss) == 1:
            d = ev[b][1] - ev[a][1] - sum(out[n][1] for n in logs if n in out)
            if d > 0 or d < 0 or ev[b][1] == 13000:
                out[miss[0]] = ('WIN' if d > 0 else 'LOSS', d)
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


LATE_TICK = 2400          # double elixir (the last 60 s of regulation) onward = "late stage"
OFFENSIVE_Y = .64         # X-Bow intended y (screen-normalised, own side at the bottom): 0.61 = at the bridge (offensive, 662 of
                          # 838 on 10-17), 0.67-0.70 = back by our towers (defensive) -- a clean two-mode split


def late(path):
    """--late: (opponent X-Bow-unfavourable?, late offensive X-Bows, late Rockets, late Tornados) for one match. The matchup comes
    from the opponent's played cards (fights.py play detection) through livecal.census.unfavorable (the owner's six archetypes)."""
    sys.path.insert(0, str(REPO))
    from scratchpad.gauntlet.L74.parity import fights as F
    from scratchpad.gauntlet.L74.livecal.census import unfavorable
    catalog, _ = F.load_catalog()
    m, _ = F.read_match(path)
    opp = set()
    if m is not None:
        events, _ = F.deployments(m, catalog)
        opp = {ev['name'] for ev in events if ev.get('kind') == 'play' and ev['side'] != m['side']}
    xb = rk = tn = 0
    for raw in open(path, 'rb'):
        if b'"confirmed"' in raw[:30]:
            j = json.loads(raw)
            if (j.get('tick') or 0) < LATE_TICK:
                continue
            name, xy = j.get('name'), j.get('intended') or (None, None)
            xb += name == 'Xbow' and xy[1] is not None and xy[1] <= OFFENSIVE_Y
            rk += name == 'Rocket'; tn += name == 'Tornado'
    return unfavorable(opp) if opp else None, xb, rk, tn


def tower_aim(xy):
    """A Rocket aimed at an enemy princess tower (10-17 aims cluster at x 0.2 / 0.8, y 0.19-0.23; own side at the bottom)."""
    return xy and (.1 <= xy[0] <= .3 or .7 <= xy[0] <= .9) and .15 <= xy[1] <= .27


def habits(path):
    """--habits (owner 10-17 observations; observe only, the fixes must be learned): (X-Bow in the opening hand?, an offensive
    X-Bow among the first two plays?, tower Rockets, of them forced by the finishing-rocket rule). A forced one = a Rocket play
    within 80 ticks after a decision carrying a lethal_rocket dict (the rule firing)."""
    opening, plays, forced_ticks = None, [], []
    for raw in open(path, 'rb'):
        head = raw[:30]
        if b'"decision"' in head:
            j = json.loads(raw)
            if opening is None:
                opening = 'Xbow' in [h.get('name') for h in (j.get('public') or {}).get('own_hand', [])]
            if isinstance((j.get('decision') or {}).get('lethal_rocket'), dict):
                forced_ticks.append(j['tick'])
        elif b'"confirmed"' in head:
            j = json.loads(raw); plays.append((j.get('tick') or 0, j.get('name'), j.get('intended')))
    plays.sort(key=lambda p: p[0])
    early = any(n == 'Xbow' and xy and xy[1] <= OFFENSIVE_Y for _, n, xy in plays[:2])
    rockets = [(t, xy) for t, n, xy in plays if n == 'Rocket' and tower_aim(xy)]
    forced = sum(any(0 <= t - f <= 80 for f in forced_ticks) for t, _ in rockets)
    return bool(opening), early, len(rockets), forced


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
    ap.add_argument('--late', action='store_true', help="owner 10-17: late-stage offensive X-Bows vs Rockets, by X-Bow-"
                    "unfavourable matchup (slower: runs fights.py play detection per match)")
    ap.add_argument('--habits', action='store_true', help="owner 10-17: early bridge X-Bow (X-Bow in the opening hand) and "
                    "tower Rockets the finishing rule did not force ('rocket cycling')")
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
        rows[mark_of(ck)].append(dict(n=n, plays=plays, mins=secs/60, win=res[p.name][0] == 'WIN', tro=res[p.name][1],
                                      late=late(p) if a.late else None, hab=habits(p) if a.habits else None))
    mean = lambda xs: sum(xs)/len(xs) if xs else float('nan')
    if a.habits:
        print('HABITS (observe only): early bridge X-Bow = an offensive X-Bow among the first 2 plays, in matches with X-Bow in the '
              'opening hand; rocket cycling = tower Rockets the finishing rule did not force')
        for mk, rs in sorted(rows.items(), key=lambda kv: -len(kv[1])):
            op = [r for r in rs if r['hab'][0]]
            free = [r['hab'][2] - r['hab'][3] for r in rs]
            print(f"  {mk}: early bridge X-Bow in {mean([r['hab'][1] for r in op]):.3f} of {len(op)} X-Bow-opening matches "
                  f"(win {mean([r['win'] for r in op if r['hab'][1]]):.3f} when it did, {mean([r['win'] for r in op if not r['hab'][1]]):.3f} "
                  f"when not); tower Rockets {mean([r['hab'][2] for r in rs]):.2f} / match, forced {mean([r['hab'][3] for r in rs]):.2f}, "
                  f"cycling {mean(free):.2f} / match, matches with any cycling rocket {mean([f > 0 for f in free]):.3f}")
    if a.late:
        print('LATE STAGE (tick >= %d): per Mark x matchup -- matches, win, offensive X-Bows / Rockets / Tornados per match' % LATE_TICK)
        for mk, rs in sorted(rows.items(), key=lambda kv: -len(kv[1])):
            for label, want in (('X-Bow-unfavourable', True), ('other', False)):
                g = [r for r in rs if r['late'] and r['late'][0] is want]
                if g:
                    print(f"  {mk} | {label}: {len(g)} matches, win {mean([r['win'] for r in g]):.3f}, late offensive X-Bow "
                          f"{mean([r['late'][1] for r in g]):.2f}, Rocket {mean([r['late'][2] for r in g]):.2f}, "
                          f"Tornado {mean([r['late'][3] for r in g]):.2f}")
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
