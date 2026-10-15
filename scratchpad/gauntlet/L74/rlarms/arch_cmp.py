"""Per-opponent-archetype win rates, paired by seed: r1 deployed (D3) vs the F1 arms (REWARD_ARCHITECTURE §10: each step
gets a per-archetype breakdown; owner 10-10: weight the unfavourable matchups). Archetype = census.archetype (first-match
win condition) on the SIM deck names.   python arch_cmp.py ARM [ARM ...]   (arms under pod1014b_arms)
"""
import collections, json, math, re, sys
sys.path.insert(0, 'scratchpad/gauntlet/L74/crapi')
from census import ARCH
ARGS, sys.argv = sys.argv[1:], sys.argv[:1]   # arms_cmp runs its comparisons at import
from arms_cmp import REF, arm

KEY = {re.sub(r'[^a-z0-9]', '', a.lower()): a for a in ARCH}


def arch(deck):
    names = {re.sub(r'[^a-z0-9]', '', c.split('@')[0].lower()) for c in deck}
    return next((KEY[k] for k in KEY if k in names), 'Other')


def table(arms):
    base = {(r['census'], r['seed']): r for r in REF['r1 deployed D3']}
    runs = {a: {(r['census'], r['seed']): r for r in arm(a, 'D3')} for a in arms}
    by = collections.defaultdict(list)
    for s, r in base.items():
        by[arch(r['opp_deck'])].append(s)
    print(f"{'archetype':16} {'n':>4} {'r1':>6} " + ' '.join(f'{a[-12:]:>20}' for a in arms))
    for k, seeds in sorted(by.items(), key=lambda kv: -len(kv[1])):
        w0 = [base[s]['outcome'] == 'win' for s in seeds]
        cells = []
        for a in arms:
            d = [(runs[a][s]['outcome'] == 'win') - w for s, w in zip(seeds, w0)]
            m = sum(d) / len(d); se = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, len(d) - 1) / len(d))
            cells.append(f'{100 * m:+6.1f} ±{196 * se:4.1f}pp')
        print(f'{k:16} {len(seeds):4d} {100 * sum(w0) / len(w0):5.1f}% ' + ' '.join(f'{c:>20}' for c in cells))


if __name__ == '__main__':
    table(ARGS)
