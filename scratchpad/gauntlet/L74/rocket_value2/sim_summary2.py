"""Paired SIM summary of subset arms against the scout BASE.
  python sim_summary2.py SCOUT_DIR ARM_DIR arm1,arm2,... [--censuses evo,lad] [--n-boot 4000] [--ni -0.03]

A match on which the arm's trigger never held is IDENTICAL to BASE (same seeds, the rule draws no RNG; mk_subsets.py), so the arm's
full result = BASE's with the simulated subset's outcomes substituted, and the paired difference is zero outside the subset. Reported
over ALL matches of the censuses (n = every BASE match): wins, better/worse (sign test p), win-rate delta with a bootstrap 95 % CI over
all n matches (zeros included) and its non-inferiority bound (ni), tower HP, fires per match (the arm's rocket_value plays, from the full-board
windows), and the CONTROL check: simulated seeds on which the arm fired nothing must equal BASE exactly (outcome and tower HP)."""
import argparse, glob, json, math, os, random
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument('scout'); ap.add_argument('arms_dir'); ap.add_argument('arms')
ap.add_argument('--censuses', default='evo,lad')
ap.add_argument('--n-boot', type=int, default=4000)
ap.add_argument('--ni', type=float, default=-0.03)
a = ap.parse_args()
random.seed(0)
C = a.censuses.split(',')


def score(r): return {'win': 1.0, 'draw': 0.5}.get(r['outcome'], 0.0)


def load(d, arm, c):
    out = {}
    for dd in d.split(','):                               # several chunk directories may hold one arm's seeds
        p = f'{dd}/{arm}_{c}/matches.jsonl'
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r.get('arm') == 'plain':
                    out[r['tag']] = r
    return out


def fires(d, arm, c):
    cnt, tags = 0, set()
    for dd in d.split(','):
        for f in glob.glob(f'{dd}/fires_{arm}_{c}/bw_*.jsonl'):
            for line in open(f):
                r = json.loads(line)
                if r['play'] and r.get('why') in ('rocket_value', 'rocket_tornado'):
                    cnt += 1; tags.add(r['tag'])
    return cnt, tags


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def ci(v):
    m = sorted(sum(random.choices(v, k=len(v))) / len(v) for _ in range(a.n_boot))
    return m[int(.025 * a.n_boot)], m[int(.975 * a.n_boot)]


base = {c: load(a.scout, 'base', c) for c in C}
n = sum(len(v) for v in base.values())
print(f'BASE (scout): n={n} ({", ".join(f"{c} {len(base[c])}" for c in C)}) wins {sum(score(r) for c in C for r in base[c].values()):.1f}')
for arm in a.arms.split(','):
    diffs, tower, enemy, sim, ident_bad, ident_n, fired_tags = [], [], [], 0, 0, 0, 0
    nf = 0
    fu = {}
    per = {}
    for c in C:
        arm_r = load(a.arms_dir, arm, c)
        cnt, ftags = fires(a.arms_dir, arm, c)
        nf += cnt; fired_tags += len(ftags)
        for tag, b in base[c].items():
            if tag in arm_r:
                sim += 1
                x = arm_r[tag]
                for k_, v_ in (x.get('follow_ups') or {}).items():
                    fu[k_] = fu.get(k_, 0) + v_
                diffs.append(score(x) - score(b)); tower.append(x['tower_hp_for'] - b['tower_hp_for']); enemy.append(x['tower_hp_against'] - b['tower_hp_against'])
                if tag not in ftags:
                    ident_n += 1
                    ident_bad += (x['outcome'], x['tower_hp_for'], x['tower_hp_against']) != (b['outcome'], b['tower_hp_for'], b['tower_hp_against'])
                per.setdefault(c, []).append(diffs[-1])
            else:
                diffs.append(0.0); tower.append(0.0); enemy.append(0.0)
    up, dn = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    w = sum(diffs)
    lo, hi = ci(diffs)
    miss = sum(len(base[c]) for c in C) - len(diffs)
    print(f'\n== {arm}: simulated {sim} of {n} (fires {nf} = {nf / n:.3f}/match in {fired_tags} matches); wins {w:+.1f} vs base | better {up} worse {dn} '
          f'(sign p={sign_p(up, dn):.3f}) | win-rate delta {sum(diffs) / n:+.4f} [{lo:+.4f},{hi:+.4f}] -> non-inferior (lower > {a.ni:+.2f}): {lo > a.ni}')
    for c in C:
        d = per.get(c, [])
        print(f'   {c}: simulated {len(d)}, net wins {sum(d):+.1f} (better {sum(x > 0 for x in d)} worse {sum(x < 0 for x in d)})')
    if fu:
        print(f'   Tornado follow-ups (combo second tap): {fu}')
    print(f'   my tower HP left per match {sum(tower) / n:+.0f}, enemy tower HP left {sum(enemy) / n:+.0f} | controls (simulated, no fire): {ident_n}, differing from BASE: {ident_bad}')
