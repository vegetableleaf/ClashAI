"""block_verdict.py -- owner 10-29 live bars for a pilot checkpoint (GATE_AND_LIVE.md).
  python block_verdict.py trial W            30-match safety trial: REVERT iff W <= 5 (idle-on-threat is checked separately)
  python block_verdict.py block W [N] [BASE] 150-match block: KEEP iff the Wilson 95% lower bound of W/N > BASE (default 32.7%)
  python block_verdict.py power [N] [BASE]   minimum wins to KEEP and P(KEEP) at true win rates 30-50%
  python block_verdict.py --selftest
Matches whose result is unknown are left out (liveops: 204-420-5 -> 204/624 = 32.7%); a draw counts as a non-win."""
import math
import sys

BASE = 32.7      # CLXIII since it returned, 204 W / 624 decided Ranked matches 10-26..10-28 (liveops/STATUS.md section 5), %


def wilson(w, n, z=1.959964):
    p = w / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (c - h), 100 * (c + h)


def min_keep(n, base):
    return next(w for w in range(n + 1) if wilson(w, n)[0] > base)


def p_at_least(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def selftest():
    lo, hi = wilson(204, 624)                     # 204-420 decided (+5 unknown results excluded) = 32.7%
    assert abs(lo - 29.1) < 0.1 and abs(hi - 36.5) < 0.1, (lo, hi)   # liveops' published CI for CLXIII
    k = min_keep(150, BASE)
    assert wilson(k, 150)[0] > BASE >= wilson(k - 1, 150)[0]
    assert abs(p_at_least(0, 10, .3) - 1) < 1e-12
    print(f"selftest ok (CLXIII 204/624 -> [{lo:.1f}, {hi:.1f}]; keep at >= {k}/150)")


def main(a):
    if a[0] == '--selftest':
        return selftest()
    if a[0] == 'trial':
        w = int(a[1])
        print(f'trial {w}/30: {"REVERT (<= 5 wins)" if w <= 5 else "wins OK (> 5); also check idle-on-threat"}')
        return 1 if w <= 5 else 0
    n = int(a[2]) if len(a) > 2 else 150
    base = float(a[3]) if len(a) > 3 else BASE
    if a[0] == 'block':
        w = int(a[1]); lo, hi = wilson(w, n)
        keep = lo > base
        print(f'block {w}/{n} = {100 * w / n:.1f}% Wilson 95% [{lo:.1f}, {hi:.1f}] vs {base}%: {"KEEP" if keep else "REVERT"}')
        return 0 if keep else 1
    if a[0] == 'power':
        n = int(a[1]) if len(a) > 1 else 150
        base = float(a[2]) if len(a) > 2 else BASE
        k = min_keep(n, base)
        print(f'n {n}, base {base}%: KEEP needs >= {k} wins ({100 * k / n:.1f}%)')
        for p in (.30, .327, .35, .38, .40, .42, .45, .50):
            print(f'  true win {100 * p:.1f}% -> P(KEEP) {p_at_least(k, n, p):.3f}')
        return 0
    raise SystemExit(__doc__)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:] or ['--selftest']))
