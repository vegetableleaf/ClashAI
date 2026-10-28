"""D2-G CLXIII re-baseline score: crforge vs fin16 on the same gate seeds (gap.py D3 rows, paired by seed / side / opp deck).

    python score.py "<cf glob with {s}>" "<rs glob with {s}>" [seed ...]   (default seeds = the pooled gate's four)

Per engine: win rate (draws = non-wins) with a Wilson 95% CI; paired delta cf - rs with a normal 95% CI (paircmp_pooled.py's
rule); per archetype (xbow_arch.arch_of on the opponent deck, push_cal's rule) per engine. Prints text.
"""
import collections
import glob
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'memory'))
from xbow_arch import arch_of  # noqa: E402


def load(pat, seeds):
    out = {}
    for s in seeds:
        for f in sorted(glob.glob(pat.format(s=s))):
            cnt = collections.Counter()
            for line in open(f):
                r = json.loads(line)
                k = (r['seed'], r['tag'], r['learner_side'], tuple(r['opp_deck']))
                cnt[k] += 1
                out[k + (cnt[k],)] = r['outcome'] == 'win'
    return out


def wilson(w, n, z=1.96):
    p = w / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * p, 100 * (c - h), 100 * (c + h)


def main():
    cf_pat, rs_pat = sys.argv[1:3]
    seeds = [int(x) for x in sys.argv[3:]] or [741200, 742000, 743000, 744000]
    a, b = load(cf_pat, seeds), load(rs_pat, seeds)
    ks = sorted(set(a) & set(b))
    print(f'rows: crforge {len(a)}, fin16 {len(b)}, paired {len(ks)} (seeds {seeds})')
    for name, d in (('crforge', a), ('fin16', b)):
        w = sum(d[k] for k in ks)
        print(f'{name:8s} win {w}/{len(ks)} = %.2f%% [%.2f, %.2f]' % wilson(w, len(ks)))
    diff = [a[k] - b[k] for k in ks]
    n = len(diff)
    m = sum(diff) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in diff) / (n - 1))
    print(f'paired crforge - fin16: {100 * m:+.2f} pp [{100 * (m - 1.96 * sd / math.sqrt(n)):+.2f}, '
          f'{100 * (m + 1.96 * sd / math.sqrt(n)):+.2f}]; discordant {sum(x > 0 for x in diff)} cf-only wins / '
          f'{sum(x < 0 for x in diff)} fin16-only wins')
    by = collections.defaultdict(list)
    for k in ks:
        by[arch_of(k[3])].append(k)
    print('per archetype (opponent deck, push_cal rule): n | crforge win% [CI] | fin16 win% [CI] | paired delta pp')
    for g in sorted(by, key=lambda g: -len(by[g])):
        kk = by[g]
        wa, wb = sum(a[k] for k in kk), sum(b[k] for k in kk)
        dd = 100 * (wa - wb) / len(kk)
        print(f'  {g:9s} {len(kk):4d} | %.1f [%.1f, %.1f] | %.1f [%.1f, %.1f] | {dd:+.1f}'
              % (*wilson(wa, len(kk)), *wilson(wb, len(kk))))


if __name__ == '__main__':
    main()
