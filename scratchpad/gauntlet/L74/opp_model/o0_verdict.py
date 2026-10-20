"""O0 verdict: does the SIM reproduce the live effect of our tower level-up (CLX, own princess 4424 -> 4858 on 10-19 14:02)?
SIM: CLX grafted vs E4 T .1, live-mirrored pool, fin13, 13k opponent level table; our tower 15 (pod 13396) vs 16 (pod 14009),
same 1,920 seeds / decks -> PAIRED difference.  Live: the same model before / after the level-up (analyze.load_live).
    python o0_verdict.py [ROOT]      (ROOT default C:/Users/benpe/pod_backup_weekend/o0)"""
import glob
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as AN  # noqa: E402
import crowns as C  # noqa: E402
import sim_sets as S  # noqa: E402

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else 'C:/Users/benpe/pod_backup_weekend/o0')


def rows(t):
    out = []
    for f in sorted(glob.glob(str(ROOT / f'out_t{t}/o0_t{t}_*/D3/matches.jsonl'))):
        for line in open(f, encoding='utf-8'):
            j = json.loads(line)
            r = {k: j.get(k) for k in S.KEEP}
            r['levels'] = j.get('levels')
            r['falls'] = None
            out.append(r)
    return out


def paired(a, b, f):
    ib = {S.pair_key(r): r for r in b}
    d = [f(r) - f(ib[S.pair_key(r)]) for r in a if S.pair_key(r) in ib]
    n = len(d)
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    return m, m - 1.96 * sd / math.sqrt(n), m + 1.96 * sd / math.sqrt(n), n


R15, R16 = rows(15), rows(16)
print(f'SIM rows: tower 15 {len(R15)}, tower 16 {len(R16)}')
for t, R in ((15, R15), (16, R16)):
    lt = Counter((r['levels'] or {}).get('learner', {}).get('tower') for r in R)
    ot = Counter((r['levels'] or {}).get('opp', {}).get('tower') for r in R)
    print(f'  T{t}: learner tower {dict(lt)}; opponent tower {dict(ot)}')
win = lambda r: 1.0 if r['outcome'] == 'win' else 0.0  # noqa: E731
lost = lambda r: 1.0 if C.sim_rec(r)['ever_lost'] else 0.0  # noqa: E731
live = AN.load_live()
L15 = [r for r in live if r['m'] == 'CLX']
L16 = [r for r in live if r['m'] == 'CLX_T16']
print('\n  cell                         SIM T15        SIM T16        SIM T16 - T15 (paired)        LIVE @4424      LIVE @4858      LIVE change [Newcombe]')
for lab, f, lf in (('P(win)', win, lambda r: r['win'] == 1.0), ('P(opp takes a princess)', lost, lambda r: r['rec']['ever_lost'])):
    s15, s16 = sum(map(f, R15)) / len(R15), sum(map(f, R16)) / len(R16)
    d = paired(R16, R15, f)
    k15, k16 = sum(map(lf, L15)), sum(map(lf, L16))
    nd = C.newcombe(k16, len(L16), k15, len(L15))
    print(f'  {lab:26s} {100 * s15:6.1f}%        {100 * s16:6.1f}%        {100 * d[0]:+5.1f} [{100 * d[1]:+5.1f}, {100 * d[2]:+5.1f}] n={d[3]}'
          f'     {100 * k15 / len(L15):5.1f}% n={len(L15)}  {100 * k16 / len(L16):5.1f}% n={len(L16)}  {100 * nd[0]:+5.1f} [{100 * nd[1]:+5.1f}, {100 * nd[2]:+5.1f}]')
print('\n  Full crown profile (same cells as analyze.py J9):')
hdr = ['P(win)', 'P(opp takes)', 'P(we take)', 'both', 'OT share', 'OT 1-1', 'P(win|OT 1-1)', 'P(win|OT 0-0)', 'P(win|lost one)',
       'reg loss', 'gave 1-0 back']
print('  ' + ' | '.join(['group'] + hdr))
for g, recs in (('SIM T15', [C.sim_rec(r) for r in R15]), ('SIM T16', [C.sim_rec(r) for r in R16]),
                ('LIVE CLX @4424', [r['rec'] for r in L15]), ('LIVE CLX @4858', [r['rec'] for r in L16])):
    print('  ' + ' | '.join([g] + C.fmt_stats(C.crown_stats(recs))))
print('\n  Per archetype, SIM T16 - T15 paired win delta (pp):')
for a in AN.ARCH:
    a15 = [r for r in R15 if AN.arch2(r['opp_deck'] or []) == a]
    a16 = [r for r in R16 if AN.arch2(r['opp_deck'] or []) == a]
    if len(a15) >= 30:
        d = paired(a16, a15, win)
        print(f'    {a:17s} {100 * d[0]:+6.1f} [{100 * d[1]:+6.1f}, {100 * d[2]:+6.1f}] n={d[3]}')
