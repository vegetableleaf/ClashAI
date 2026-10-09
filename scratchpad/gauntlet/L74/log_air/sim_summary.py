"""log_air SIM A/B summary (staged design, stage_b.py).  python sim_summary.py <sim dir> [evo,lad,air]
Base ran on every seed; a log_air arm ran only on the CANDIDATE games (base played >= 1 Log whose corridor held only flyers --
the only way log_air can touch a game; a game without one is identical in every arm, det_check.py). Paired by (census, tag):
a non-candidate game takes the base result for the arm, a candidate game its own result (a candidate whose arm game has not
finished is left out of that arm's pairs).  Wins (win 1, draw .5), better / worse / same, mean paired difference in pp with a
95 % normal CI (non-inferiority bar: lower bound > -3 pp), sign test; Log plays per game by corridor class (base); the touched
Logs and what the re-aim hits (log_fire_s0 geometry on the decision board)."""
import glob, json, math, os, sys
from collections import Counter, defaultdict

O = sys.argv[1]
SUF = sys.argv[2].split(',') if len(sys.argv) > 2 else ['evo', 'lad', 'air']


def games(arm, s):
    out = {}
    for p in [f'{O}/{arm}_{s}/matches.jsonl'] + sorted(glob.glob(f'{O}/{arm}_{s}_b*/matches.jsonl')):
        if os.path.exists(p):
            for line in open(p):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r['arm'] == 'plain':
                    out[r['tag']] = r
    return out


def fires(arm, s):
    out = defaultdict(list)
    for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl') + glob.glob(f'{O}/fires_{arm}_{s}_b*/fires_*.jsonl'):
        for line in open(f):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            out[x['tag']].append(x)
    return out


def score(r):
    return {'win': 1.0, 'draw': 0.5}.get(r['outcome'], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def stats(d, label, bn):
    n = len(d)
    if not n:
        return
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(n - 1, 1))
    hw = 1.96 * sd / math.sqrt(n)
    up, dn = sum(x > 0 for x in d), sum(x < 0 for x in d)
    print(f'  [{label}] {bn} - base over {n} paired games: better {up} / worse {dn} / same {n - up - dn}; diff {100 * m:+.2f} pp, '
          f'95% CI [{100 * (m - hw):+.2f}, {100 * (m + hw):+.2f}] (half-width {100 * hw:.2f}); sign p {sign_p(up, dn):.3f}; '
          f'non-inferior (lower > -3 pp): {100 * (m - hw) > -3}')


base = {s: games('base', s) for s in SUF}
bfire = {s: fires('base', s) for s in SUF}
cand = {s: {t for t, v in bfire[s].items() if any(x.get('play') and x.get('kind') == 'only_air' for x in v)} for s in SUF}
print('base games:', {s: len(base[s]) for s in SUF}, '| candidate games (base played an only_air Log):',
      {s: len([t for t in cand[s] if t in base[s]]) for s in SUF})
for arm in ('retarget', 'block'):
    res = {s: games(arm, s) for s in SUF}
    fa = {s: fires(arm, s) for s in SUF}
    diffs = defaultdict(list)
    pending = 0
    for s in SUF:
        for t, b in base[s].items():
            if t in cand[s]:
                if t not in res[s]:
                    pending += 1
                    continue
                diffs[s].append(score(res[s][t]) - score(b))
            else:
                diffs[s].append(0.0)
    print(f'--- {arm}  (candidates still pending: {pending})')
    stats([x for s in SUF for x in diffs[s]], 'all', arm)
    for s in SUF:
        stats(diffs[s], s, arm)
    run = [(s, t) for s in SUF for t in res[s]]
    print(f'  candidate games run: {len(run)}; of those the arm touched: {sum(any(x.get("why") == "log_air" for x in fa[s].get(t, [])) for s, t in run)}')
    stats([score(res[s][t]) - score(base[s][t]) for s, t in run if t in base[s]], 'candidate games only', arm)
    touched = [x for s in SUF for v in fa[s].values() for x in v if x.get('why') == 'log_air']
    if arm == 'retarget':
        print(f'  re-aimed {len(touched)} Logs; new cell {dict(Counter(x.get("cell_kind") for x in touched))}; corridor class after '
              f'{dict(Counter(x["kind"] for x in touched))}; hits something {sum(x["kind"] == "hits" for x in touched)} of {len(touched)}; '
              f'mean ground elixir in the new corridor {sum(x["ground_value"] for x in touched) / max(len(touched), 1):.2f}')
    else:
        print(f'  blocked {len(touched)} Logs (WAIT)')
n = sum(len(v) for v in base.values())
plays = [x for s in SUF for v in bfire[s].values() for x in v if x['play']]
k = Counter(x['kind'] for x in plays)
print(f'--- base Log plays: {len(plays)} in {n} games = {len(plays) / max(n, 1):.2f} per game; corridor class {dict(k)} '
      f'({100 * k["only_air"] / max(len(plays), 1):.1f} % only_air, {100 * k["empty"] / max(len(plays), 1):.1f} % empty); '
      f'only_air Logs per game {k["only_air"] / max(n, 1):.3f}')
for s in SUF:
    pl = [x for v in bfire[s].values() for x in v if x['play']]
    kk = Counter(x['kind'] for x in pl)
    print(f'   {s}: {len(pl)} plays in {len(base[s])} games; {dict(kk)}')
