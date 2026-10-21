"""Early-game Log holding, pros vs SIM vs live (play lists only; playlist.py sources).

Per source: Logs in the first 60 s / 120 s of a match (all matches), and in CORE-bait matches the share where no Log was
spent before the opponent's first CORE bait play, with that first play's tick.

  python early.py --live per_match.jsonl
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log_use as L                       # noqa: E402
import playlist as P                      # noqa: E402


def rows_pro():
    for line in open(P.PRO, encoding='utf-8'):
        j = json.loads(line)
        if not j.get('icebow8') or sorted(map(P.k, j.get('opp_deck') or [])) == sorted(map(P.k, j['deck'])):
            continue
        ev = j['ev']
        own = [(e[0], P.k(e[2])) for e in ev if e[1] == 'me']
        if own:
            yield own, [(e[0], P.k(e[2])) for e in ev if e[1] == 'op']


def rows_sim(g):
    import glob
    for f in P.match_files(g):
        if 'clx_fin15' not in f:
            continue
        for line in open(f, encoding='utf-8'):
            o3 = json.loads(line).get('o3_plays')
            if o3:
                yield [(t, P.k(c)) for t, c in o3['learner']], [(t, P.k(c)) for t, c in o3['opp']]


def rows_live(path, mark='ICEBOW Mark CLX: PARITY'):
    for line in open(path, encoding='utf-8'):
        j = json.loads(line)
        if j['mark'] == mark and 'own_plays' in j:
            yield sorted((t, c.replace('-', '_')) for t, c in j['own_plays']), sorted(map(tuple, j['opp_plays']))


def stats(label, it, t0):
    """t0: the source's first-play clock offset (tick of the match start on that source's clock)."""
    n = e60 = e120 = 0; held = []; first = []
    for own, opp in it:
        n += 1
        logs = [t for t, c in own if c == P.LOG]
        start = t0 if t0 is not None else min(t for t, _ in own + opp)
        e60 += sum(t - start < 1200 for t in logs); e120 += sum(t - start < 2400 for t in logs)
        fb = min((t for t, c in opp if c in L.CORE), default=None)
        if fb is not None:
            held.append(not any(t < fb for t in logs)); first.append((fb - start) / 20)
    first.sort()
    return (f'- {label}: {n} matches; Logs in the first 60 s {e60/n:.2f}, first 120 s {e120/n:.2f}; CORE-bait matches {len(held)}: '
            f'no Log spent before the first CORE bait play {L.mean(held):.3f} (first bait at median {first[len(first)//2]:.0f} s)')


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', required=True)
    ap.add_argument('--sim', default='C:/Users/benpe/pod_backup_weekend/tonight1020/*/w12_*/**/matches.jsonl')
    a = ap.parse_args(argv)
    # clocks: pro ev ticks and SIM o3 ticks start at 0 = battle start; live ticks are game_tick (battle start ~ tick 78,
    # investment/INVESTMENT.md "live clock = game_tick - 78")
    print(stats('pros', rows_pro(), 0))
    print(stats('SIM CLX vs W7 (w12_clx_fin15)', rows_sim(a.sim), 0))
    print(stats('live CLX', rows_live(a.live), 78))


if __name__ == '__main__':
    main(sys.argv[1:])
