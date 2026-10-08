"""ot vs ot_behind SIM A/B summary (sim_otb.sh).  python sim_otb_summary.py ~/lethal/sim_otb
Wins / paired sign test; regulation fires (model-board t < 180 s) per match with their tags and times; matches reaching OT
(end_tick > 3600) per arm on the regulation-fire tags; outcome changes on those tags, and any fire-tag match lost by
ot_behind but not by ot (a cost of the Rocket spend)."""
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


a, b = load('ot'), load('ot_behind')
keys = sorted(set(a) & set(b))
print(f'paired games {len(keys)} (ot {len(a)}, ot_behind {len(b)})')
for name, arm in (('ot', a), ('ot_behind', b)):
    print(f'  {name}: wins {sum(score(arm[k]) for k in keys):.1f}; outcomes {dict(Counter(arm[k]["outcome"] for k in keys))}; '
          f'reached OT (end_tick > 3600) {sum(arm[k]["end_tick"] > 3600 for k in keys)}')
up = sum(score(b[k]) > score(a[k]) for k in keys); dn = sum(score(b[k]) < score(a[k]) for k in keys)
print(f'  paired: ot_behind better {up} / worse {dn} (sign test p {sign_p(up, dn):.3f})')
fb, fa = fires('ot_behind'), fires('ot')
reg = {k: [x for x in v if x['t_sec'] < 180] for k, v in fb.items()}
reg = {k: v for k, v in reg.items() if v and k in keys}
ts = sorted(x['t_sec'] for v in reg.values() for x in v)
print(f'ot_behind regulation fires {len(ts)} in {len(reg)} matches; model-board t_sec min {ts[0] if ts else None} max '
      f'{ts[-1] if ts else None} (cutoff 176.70); all behind={all(x["behind"] for v in reg.values() for x in v)}; '
      f'targets HP median {sorted(x["target"]["hp"] for v in reg.values() for x in v)[len(ts) // 2] if ts else None}')
print(f'  OT fires: ot {sum(len(v) for v in fa.values())}, ot_behind {sum(sum(x["t_sec"] >= 180 for x in v) for v in fb.values())}')
went = [k for k in reg if b[k]['end_tick'] > 3600 and a[k]['end_tick'] <= 3600]
print(f'  regulation-fire matches: reached OT under ot_behind but not under ot: {len(went)}; '
      f'reached OT under both {sum(b[k]["end_tick"] > 3600 and a[k]["end_tick"] > 3600 for k in reg)}; '
      f'neither {sum(b[k]["end_tick"] <= 3600 and a[k]["end_tick"] <= 3600 for k in reg)}')
print(f'  on those matches: ot wins {sum(score(a[k]) for k in reg):.1f} / {len(reg)}, ot_behind {sum(score(b[k]) for k in reg):.1f}; '
      f'better {sum(score(b[k]) > score(a[k]) for k in reg)}, worse {sum(score(b[k]) < score(a[k]) for k in reg)}')
for k in sorted(reg):
    x = reg[k][0]
    print(f'    {k}: first fire t {x["t_sec"]:.2f} {x["target"]["lane"]} hp {x["target"]["hp"]} | ot {a[k]["outcome"]} '
          f'{a[k]["crowns_for"]}-{a[k]["crowns_against"]} end {a[k]["end_tick"]} | ot_behind {b[k]["outcome"]} '
          f'{b[k]["crowns_for"]}-{b[k]["crowns_against"]} end {b[k]["end_tick"]}')
other = [k for k in keys if k not in reg and score(a[k]) != score(b[k])]
print(f'  outcome changes on matches WITHOUT a regulation fire (OT-rule / randomness drift): {len(other)} {other[:10]}')
