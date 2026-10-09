"""lethal_log off vs on SIM A/B summary (sim_log.sh).  python sim_log_summary.py ~/lethal/sim_log
Wins / paired sign test; Log fires (phase, target HP, damage) per match; per fire-match outcomes in both arms; outcome
changes on matches WITHOUT a Log fire (should be 0: the arms are identical until the first Log fire)."""
import glob, json, math, os, sys
from collections import Counter, defaultdict

O = sys.argv[1]


def load(arm):
    out = {}
    for s in ('evo', 'lad'):
        p = f'{O}/v3_{arm}_{s}/matches.jsonl'
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r['arm'] == 'plain':
                    out[(s, r['tag'])] = r
    return out


def fires(arm):
    out = defaultdict(list)
    for s in ('evo', 'lad'):
        for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl'):
            for line in open(f):
                x = json.loads(line)
                out[(s, x['tag'])].append(x)
    return out


def score(r):
    return {'win': 1.0, 'draw': 0.5}.get(r['outcome'], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


a, b = load('off'), load('on')
keys = sorted(set(a) & set(b))
print(f'paired games {len(keys)} (off {len(a)}, on {len(b)})')
for name, arm in (('off', a), ('on', b)):
    print(f'  {name}: wins {sum(score(arm[k]) for k in keys):.1f}; outcomes {dict(Counter(arm[k]["outcome"] for k in keys))}')
up = sum(score(b[k]) > score(a[k]) for k in keys); dn = sum(score(b[k]) < score(a[k]) for k in keys)
print(f'  paired: on better {up} / worse {dn} (sign test p {sign_p(up, dn):.3f})')
fon, foff = fires('on'), fires('off')
logs = {k: [x for x in v if x['why'] == 'lethal_log'] for k, v in fon.items()}
logs = {k: v for k, v in logs.items() if v and k in keys}
n = sum(map(len, logs.values()))
print(f'Log fires {n} in {len(logs)} matches; phases {dict(Counter("OT" if x["t_sec"] >= 180 else "reg" for v in logs.values() for x in v))}; '
      f'damage {dict(Counter(x["target"]["damage"] for v in logs.values() for x in v))}; '
      f'Rocket fires off {sum(len(v) for v in foff.values())} / on {sum(sum(x["why"] == "lethal_rocket" for x in v) for v in fon.values())}')
for k in sorted(logs):
    x = logs[k][0]
    print(f'    {k}: first Log t {x["t_sec"]:.2f} {x["target"]["lane"]} hp {x["target"]["hp"]} | off {a[k]["outcome"]} '
          f'{a[k]["crowns_for"]}-{a[k]["crowns_against"]} end {a[k]["end_tick"]} | on {b[k]["outcome"]} '
          f'{b[k]["crowns_for"]}-{b[k]["crowns_against"]} end {b[k]["end_tick"]}')
other = [k for k in keys if k not in logs and score(a[k]) != score(b[k])]
print(f'  outcome changes on matches WITHOUT a Log fire: {len(other)} {other[:10]}')
