"""Plan A S4 (owner 10-25: "you can't just consider the average lock rate ... lock rates will swing wildly depending on matchup and
opponent skill"): own reach-X-Bow lock rate BY OPPONENT ARCHETYPE, SIM and live, on one definition (match_memory's: reach <= 13.5
tiles of an alive enemy princess, locked = it lost >= 5% of max HP within 600 ticks).

    pod:    python xbow_arch.py --sim NAME=DIR [NAME=DIR ...]          (gap.py --record-board rows, */D3/matches.jsonl)
    laptop: python xbow_arch.py --live CKPT_SUBSTRING [...]           (live logs via memory/live_dump.read + match_memory.build)

Archetype = push_cal.arch on the opponent's cards (SIM: its deck; live: the cards it showed). Per archetype: matches, reach
X-Bows, lock rate with a match-cluster bootstrap 95% CI, and the per-match lock-rate spread (share of matches with lock rate
0 / < 0.5 / >= 0.5 among matches with >= 2 reach X-Bows) -- the opponent-to-opponent swing the owner pointed at."""
import argparse
import glob
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'opp_model' / 'push_cal'), str(HERE.parent / 'succ48'), str(HERE.parents[3])]


# push_cal.py's archetype rule, copied (push_cal imports the whole push stack)
WINCON = ('x_bow', 'mortar', 'royal_giant', 'lava_hound', 'golem', 'electro_giant', 'goblin_giant', 'giant', 'elixir_golem',
          'mega_knight', 'pekka', 'hog_rider', 'royal_hogs', 'ram_rider', 'battle_ram', 'balloon', 'graveyard', 'goblin_drill',
          'miner', 'goblin_barrel', 'wall_breakers', 'three_musketeers', 'sparky', 'skeleton_barrel', 'goblin_machine',
          'rune_giant', 'boss_bandit', 'giant_skeleton', 'skeleton_king', 'goblinstein', 'bowler', 'executioner')  # anatomy
GROUP = dict(hog_rider='hog', mega_knight='bridge', pekka='bridge', royal_hogs='bridge', ram_rider='bridge',
             battle_ram='bridge', boss_bandit='bridge', goblin_barrel='bait', skeleton_barrel='bait', goblin_drill='bait',
             wall_breakers='bait', graveyard='control', miner='control', x_bow='control', mortar='control',
             sparky='control', bowler='control', executioner='control', skeleton_king='control', goblin_machine='control')
GROUP.update({w: 'beatdown' for w in ('royal_giant', 'lava_hound', 'golem', 'electro_giant', 'goblin_giant', 'giant',
                                      'elixir_golem', 'balloon', 'three_musketeers', 'rune_giant', 'giant_skeleton',
                                      'goblinstein')})


def canon(c):
    """live keys ('giant-skeleton') and SIM deck names ('GiantSkeleton', 'MegaKnight@evolution', 'XBow') -> snake_case."""
    import re
    c = str(c).split('@')[0]
    j = lambda m: m.group(1) + '_' + m.group(2)
    c = re.sub('([A-Z])([A-Z][a-z])', j, re.sub('([a-z0-9])([A-Z])', j, c))
    return c.replace('-', '_').lower().replace('_evo', '').replace('_hero', '')


def arch(cards):
    w = next((w for w in WINCON if w in cards), 'other')
    return w, GROUP.get(w, 'other')


def arch_of(cards):
    return arch({canon(c) for c in cards})[1]


def sim_matches(d):
    import xbow_count as XC
    for r, h in XC.rows(d):
        o = XC.one(h)
        yield arch_of(r.get('opp_deck') or []), o['reach'], o['reach'] - o['fail']


def live_matches(key):
    import live_dump as LD
    from pipeline import match_memory as M
    logs = Path(__file__).resolve().parents[2] / 'L68' / 'live_reader'
    for f in sorted(logs.glob('live_play_*.jsonl')):
        ok = False
        with open(f, 'rb') as fh:                                 # the start event (with the ckpt) is not always line 1
            for _, raw in zip(range(400), fh):
                if b'"event": "start"' in raw[:60]:
                    ok = key.encode() in raw
                    break
        if not ok:
            continue
        try:
            m = LD.read(f)
        except Exception as exc:                                  # a truncated / odd log: skip, count it
            print(f'skip {f.name}: {exc!r}'[:160], file=sys.stderr)
            continue
        ev = M.build(m['side'], m['samples'], m['plays']).events(m['last'] + 1)
        opp = {e['card'] for e in ev if e['type'] == 'play' and not e['mine']}
        rch = [e for e in ev if e['type'] == 'play' and e['mine'] and e['card'] == 'x-bow' and e['reach'] and e.get('xb')]
        if CARDS is not None:                                     # --cards: per-card answer / deck views (xbow_cards.py's)
            for e in rch:
                L = int(bool(e['xb']['locked']))
                for k in ('ans:' + (e.get('answer') or '-'),) + tuple('deck:' + c for c in opp):
                    CARDS[k][0] += L
                    CARDS[k][1] += 1
        yield arch_of(opp), len(rch), sum(bool(e['xb']['locked']) for e in rch)


CARDS = None


def card_report(min_n):
    tot = [sum(v[i] for k, v in CARDS.items() if k.startswith('ans:')) for i in (0, 1)]
    base = tot[0] / tot[1]
    print(f'## per card: {tot[1]} reach X-Bows, lock {base:.3f} ("ans:-" = unanswered)')
    for view in ('ans:', 'deck:'):
        for k, (y, n) in sorted(((k, v) for k, v in CARDS.items() if k.startswith(view) and v[1] >= min_n),
                                key=lambda kv: kv[1][0] / kv[1][1]):
            print(f'  {k:28s} n {n:4d} lock {y / n:.3f} lift {y / n - base:+.3f}')


def report(name, M):
    by = defaultdict(list)
    for a, n, k in M:
        by[a].append((n, k))
        by['ALL'].append((n, k))
    print(f'## {name}')
    rng = random.Random(0)
    for a in sorted(by, key=lambda x: (x != 'ALL', x)):
        L = by[a]
        n = sum(x for x, _ in L)
        if not n:
            continue
        k = sum(y for _, y in L)
        bs = []
        for _ in range(500):
            s = [L[rng.randrange(len(L))] for _ in L]
            sn = sum(x for x, _ in s)
            bs.append(sum(y for _, y in s) / sn if sn else 0)
        bs.sort()
        multi = [y / x for x, y in L if x >= 2]
        spread = (f"| per-match (>= 2 reach) lock 0: {sum(v == 0 for v in multi) / len(multi):.2f}, < .5: "
                  f"{sum(v < .5 for v in multi) / len(multi):.2f}, >= .5: {sum(v >= .5 for v in multi) / len(multi):.2f} "
                  f"(n {len(multi)})") if multi else ''
        print(f"  {a:9s} matches {len(L):5d} reach X-Bows {n:5d} lock {k / n:.3f} [{bs[12]:.3f}, {bs[487]:.3f}] {spread}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sim', nargs='*', default=[])
    ap.add_argument('--live', nargs='*', default=[])
    ap.add_argument('--cards', type=int, default=0, help='live: also print per-card views with n >= this')
    a = ap.parse_args()
    global CARDS
    if a.cards:
        CARDS = defaultdict(lambda: [0, 0])
    for arg in a.sim:
        name, d = arg.split('=', 1)
        report(f'SIM {name}', list(sim_matches(d)))
    for key in a.live:
        report(f'LIVE {key}', list(live_matches(key)))
        if CARDS is not None:
            card_report(a.cards)
            CARDS.clear()


if __name__ == '__main__':
    assert [canon(x) for x in ('GiantSkeleton', 'MegaKnight@evolution', 'XBow', 'PEKKA', 'hog-rider', 'x-bow')] == \
        ['giant_skeleton', 'mega_knight', 'x_bow', 'pekka', 'hog_rider', 'x_bow']
    main()
