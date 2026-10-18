"""L74/habits SIM tables from the probe arms' recorded rows (pod: /workspace/habits/runs/<arm>/<arm>_<seed>/D3/matches.jsonl,
each row's 'hab' record from the patched search_s0). Same A / B / C definitions as live (hablib, live_tables), plus:
  D  counter vs the opponent's TRUE elixir (SIM), the SIM opponent's answer to bridge X-Bows by band / cycle
  E  each probe arm vs base, paired by (seed, census): win, bridge X-Bows, early share, the counter at our bridge X-Bows
    python sim_tables.py --runs /workspace/habits/runs [--arms base,g5w,...] [--json sim_rows.json]"""
from __future__ import annotations

import argparse
import bisect
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hablib as H  # noqa: E402
import live_tables as LT  # noqa: E402
import extra as X  # noqa: E402

pct = LT.pct


def to_match(r, arm):
    h = r['hab']
    L = h['L']
    S = h['samples']
    king = [t for t in S[0][5] if t[0] == L and t[1] == 'k'] if S else []
    flip = bool(king) and king[0][3] < 16000

    def tr(x, y):
        return ((18000 - x) / 1000, (32000 - y) / 1000) if flip else (x / 1000, y / 1000)
    st = [s[0] for s in S]

    def samp(t):
        i = bisect.bisect_right(st, t) - 1
        return S[max(0, i)]
    own, opp = [], []
    for q in h['own']:
        if not q[3]:
            continue
        x, y = tr(q[8], q[9])
        s = samp(q[0])
        own.append(dict(tick=q[1], card=H.norm(q[2]), x=x, y=y, why=q[4], est_model=s[3], dec_tick=q[0]))
    for q in h['opp']:
        if not q[3]:
            continue
        x, y = tr(q[8], q[9])
        opp.append(dict(tick=q[1], card=H.norm(q[2]), x=x, y=y))
    frames = []
    for s in S:
        T = {}
        for side, typ, x, y, hp in s[5]:
            X_ = tr(x, y)[0]
            T[('own' if side == L else 'opp', 'K' if typ == 'k' else 'L' if X_ < 9 else 'R')] = hp
        E = [(f'E{u}', H.norm(n), 0, hp, mx, *tr(x, y)) for u, n, hp, mx, x, y in s[6]]
        O = [(f'M{u}', 'x_bow', hp, *tr(x, y)) for u, hp, x, y in s[7]]
        frames.append((s[0], T, E, O))
    win = 1.0 if r['outcome'] == 'win' else 0.0
    return dict(src='sim', group=arm, key=f"{r['seed']}:{r.get('census')}", win=win, own=own, opp=opp, frames=frames,
                est=lambda t: (samp(t)[2] if samp(t)[2] is not None else 6.0), truth=lambda t: samp(t)[1],
                hand=lambda t: (None, None), samples=S, row=r)


def load(runs, arms):
    out = {}
    for a in arms:
        rows = []
        for p in sorted((Path(runs) / a).glob(f'{a}_*/D3/matches.jsonl')):
            rows += [json.loads(l) for l in open(p, encoding='utf-8')]
        out[a] = [to_match(r, a) for r in rows if 'hab' in r]
    return out


def counter_truth(ms):
    d = [s[2] - s[1] for m in ms for s in m['samples'] if s[1] is not None and s[2] is not None]
    a = [abs(x) for x in d]
    by = {}
    for m in ms:
        for s in m['samples']:
            if s[1] is None or s[2] is None:
                continue
            ph = 'single' if s[0] < 2400 else 'double' if s[0] < 4800 else 'triple'
            by.setdefault(ph, []).append(s[2] - s[1])
    print(f"\n## D. SIM counter (the model's public counter, untouched by the probes) vs TRUE opponent elixir: samples {len(d)}, "
          f"MAE {statistics.fmean(a):.3f}, bias {statistics.fmean(d):+.3f}, within 1 {pct(sum(x <= 1 for x in a) / len(a))}, "
          f"within 2 {pct(sum(x <= 2 for x in a) / len(a))}; " +
          ', '.join(f"{k} MAE {statistics.fmean(map(abs, v)):.3f} bias {statistics.fmean(v):+.3f}" for k, v in by.items()))


def paired(a, b, f, B=2000):
    A = {m['key']: m for m in a}
    Bm = {m['key']: m for m in b}
    k = sorted(set(A) & set(Bm))
    d = [f(A[x]) - f(Bm[x]) for x in k]
    rng = random.Random(0)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(B))
    return round(sum(d) / len(d), 4), (round(bs[int(.025 * B)], 4), round(bs[int(.975 * B) - 1], 4)), len(k)


def arm_summary(D):
    print('\n## E. Probe arms vs base (paired by seed + census; 960 games each when complete)')
    base = D.get('base')
    for a, ms in D.items():
        n = len(ms)
        if not n:
            continue
        xb = [r for m in ms for r in H.xbow_events(m)]
        firsts = [H.xbow_events(m) for m in ms]
        early = H.mean([bool(f and f[0]['early']) for f in firsts])
        g = [m['row'] for m in ms]
        gate = {k: sum(r.get(k, 0) for r in g) for k in ('hab_gate_seen', 'hab_gate_refused', 'hab_gate_masked_play')}
        line = (f"  {a:5s} n {n:4d} win {pct(H.wr(ms))}  bridge X-Bows/match {len(xb) / n:.2f}  early first-2 {pct(early)}  "
                f"counter at our bridge X-Bows median {statistics.median([r['est'] for r in xb]) if xb else float('nan'):.2f} "
                f"(<=3 {pct(H.mean([r['band'] == '<=3' for r in xb]))}, >=7 {pct(H.mean([r['band'] == '>=7' for r in xb]))})  "
                f"heavy-at-it {pct(H.mean([r['heavy'] for r in xb]))}  Rockets/match {sum(q['card'] == 'rocket' for m in ms for q in m['own']) / n:.2f}"
                f"  plays/match {H.mean([r['plays_accepted'] for r in g]):.1f}  gate {gate if gate['hab_gate_seen'] else ''}")
        print(line)
        if base and a != 'base':
            print(f"        - base: win {paired(ms, base, lambda m: m['win'])}  tower HP diff "
                  f"{paired(ms, base, lambda m: m['row']['tower_hp_diff'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default='/workspace/habits/runs')
    ap.add_argument('--arms', default='base,g5w,z0,g7w,g5m,z5')
    ap.add_argument('--json', default=str(HERE / 'sim_rows.json'))
    a = ap.parse_args()
    D = load(a.runs, [x for x in a.arms.split(',')])
    D = {k: v for k, v in D.items() if v}
    print('arms:', {k: len(v) for k, v in D.items()})
    base = D['base']
    counter_truth(base)
    G = list(D)
    Xr = [r for k in G for m in D[k] for r in H.xbow_events(m)]
    LT.timing([m for k in G for m in D[k]], G)
    LT.table_xbow([r for r in Xr if r['group'] == 'base'], ['base'], 'A-SIM. Bridge X-Bows, base arm (CLIII, promotion eval)')
    # the SIM opponent's answer by cycle (cf. extra.py section 2 live / pros)
    rows = []
    for m in base:
        for r in H.xbow_events(m):
            r['out'] = X.heavy_out(m, r['tick'])
            rows.append(r)
    print('\n## D. SIM opponent (E4 T .1) answer to bridge X-Bows by opponent cycle: P(heavy at it in 8 s)')
    print('  ' + ' | '.join(f"{lab}: n {len(S)} heavy {pct(H.mean([r['heavy'] for r in S]))} win {pct(H.wr(S))}"
                            for lab, v in (('none shown', None), ('heavy possible', False), ('heavy out', True))
                            for S in [[r for r in rows if r['out'] is v]] if S))
    fr = [(m, H.xbow_events(m)) for m in base]
    E_ = [dict(key=m['key'], win=m['win']) for m, x in fr if x and x[0]['early']]
    N_ = [dict(key=m['key'], win=m['win']) for m, x in fr if not (x and x[0]['early'])]
    print(f"\n  SIM match level: first bridge X-Bow in the first 2 plays {len(E_)} matches win {pct(H.wr(E_))} vs {len(N_)} not "
          f"{pct(H.wr(N_))}, diff {X.diff_ci(E_, N_, H.wr)}")
    import punish_sens as PS
    pairs = [(m, r) for m in base for r in H.xbow_events(m)]
    print('  punish-window definitions (punish_sens.DEFS): ' + ' | '.join(
        f"{k} yes {len(y)} heavy {pct(H.mean([r['heavy'] for r in y]))} win {pct(H.wr(y))} / no heavy "
        f"{pct(H.mean([r['heavy'] for r in n]))} win {pct(H.wr(n))}"
        for k, f in PS.DEFS.items() for y, n in [([r for m, r in pairs if f(m, r['tick'])], [r for m, r in pairs if not f(m, r['tick'])])]))
    hv = [PS.after_heavy(m, r) for m, r in pairs if r['heavy']]
    nh = [PS.after_heavy(m, r) for m, r in pairs if not r['heavy']]
    print(f"  after the heavy answer (20 s): n {len(hv)} our HP lost {H.mean([x[0] for x in hv]):.0f}, towers lost "
          f"{H.mean([x[1] for x in hv]):.3f} | no heavy n {len(nh)}: HP lost {H.mean([x[0] for x in nh]):.0f}, towers lost {H.mean([x[1] for x in nh]):.3f}")
    B = [r for m in base for r in LT.body_pushes(m)]
    P = [r for m in base for r in H.push_events(m)]
    LT.table_push(B, ['base'], 'B1-SIM. Heavy pushes, BODY-based, base arm', body=True)
    LT.table_push(P, ['base'], 'B2-SIM. Heavy pushes, PLAY-based, base arm')
    K = [r for m in base for r in H.rocket_uses(m)]
    LT.table_rocket(base, K, ['base'])
    print(f"\n  SIM opponent heavy-push rate: body-based {len(B) / len(base):.2f} / match, play-based {len(P) / len(base):.2f} / match")
    arm_summary(D)
    json.dump(dict(xbow=Xr, push_body=B, push_play=P, rocket=K), open(a.json, 'w'), default=str)


if __name__ == '__main__':
    main()
