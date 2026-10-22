"""O4 GATE v2 (owner decisions 10-22: G1-G4 approved + the recent-window target) -- the opponent-model gate used from 10-22 on.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w18/o4_gate.py [--n 100] [--brief] [--targets] ROOT [ROOT ...]
Changes vs W14's O4-Ranked (w14/o4r_table.py, whose cells / SIM rows / z rule it reuses):
  TARGET  the most recent N (100) live Ranked CLX matches (diag12/recent/rows_ext.json, W13's anatomy rows over all 267 CLX Ranked
          logs to the 10-21 14:32 switch); point tolerances scaled by sqrt(n_233 / n_N) of each cell's live n (o4r_recent.py).
  G1      live overtime label = the SIM's rule: end > 3610 AND crowns level at 3:00 (4 regulation results were labelled OT).
  G2      the SIM rows must come from CLX playing WITH its measured live handicap (search_s0 --tap-loss 1x:0.0180,2x:0.0363,
          ot2x:0.0388,ot3x:0.0890 --tap-slow 0.151:17; DIAG_12 section 10). A row set without it is NOT a gate result (flagged,
          verdict 'INVALID (G2)').
  G3      both took one is scored per MATCH (Wilson on matches, as before -- stated); the 1-1 X-Bow lock cell (monitored, not
          gated) gets a match-cluster bootstrap CI (live: 41 X-Bows sit in 13 matches).
  G4      live style uses the pilot's CONFIRMED taps (lost / retried taps out, tap tick kept), as the SIM counts landed plays.
Style bound 0.65 (vs the same N matches' opponents); |z| < 1.96 per cell; an undefined cell fails."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPP = HERE.parent
sys.path[:0] = [str(OPP / 'w14'), str(OPP / 'diag12'), str(HERE)]
import o4r_table as T  # noqa: E402
import o4r_recent as R  # noqa: E402

VERSION = 'O4 gate v2 (10-22: recent-100 target, G1-G4)'
HANDICAP = '--tap-loss 1x:0.0180,2x:0.0363,ot2x:0.0388,ot3x:0.0890 --tap-slow 0.151:17'


def g1(rows):
    """SIM-consistent overtime label on live rows (a copy)."""
    return [dict(r, ot=bool(r['ot']) and tuple(r['reg_cr'])[0] == tuple(r['reg_cr'])[1]) for r in rows]


def live_style_confirmed(rows):
    """G4: opponent behaviour features of these live matches with our plays = the confirmed taps' tap ticks."""
    import diag12 as D
    import live_table as LT
    import opp_behaviour as OB
    out = []
    for r in rows:
        d = LT.cached(LT.LOGS / r['key'])
        if not (d and d.get('start')):
            continue
        plays, conf, _, _ = D.read_exec(r['key'])
        mine = [p['tick'] + D.OFF for p in plays if any(q['name'] == p['name'] and 0 <= q['tick'] - p['tick'] <= 80 for q in conf)]
        out.append(OB.features(dict(src='live', id=r['key'], seen=d['seen'], res=0, end=d['end'], t0=d['t0'], side=d['side'],
                                    plays=d['plays'], mine=mine)))
    return out


def cluster_ci(xs, reps=2000, seed=0):
    """G3: rate of x['lock_reach'] over X-Bows with a bootstrap over MATCHES (x['key']). -> (rate, lo, hi, n X-Bows, n matches)."""
    import random
    by = {}
    for x in xs:
        by.setdefault(x['key'], []).append(bool(x['lock_reach']))
    keys = list(by)
    if not keys:
        return float('nan'), float('nan'), float('nan'), 0, 0
    rng = random.Random(seed)
    rate = sum(map(sum, by.values())) / sum(map(len, by.values()))
    bs = []
    for _ in range(reps):
        pick = [by[rng.choice(keys)] for _ in keys]
        bs.append(sum(map(sum, pick)) / max(1, sum(map(len, pick))))
    bs.sort()
    return rate, bs[int(.025 * reps)], bs[int(.975 * reps)], sum(map(len, by.values())), len(keys)


def lock11(live, raws):
    """G3 monitored cell: our X-Bow lock rate at 1-1 (live rule), live recent N vs the SIM rows that carry positions."""
    import diag12 as D
    import invlib as I
    keys = {r['key'] for r in live}
    keep, _, _ = D.PK.A.load(OPP / 'diag12/recent/index_ext.json')     # the 267-match index (the habits cache covers it)
    sub = HERE / '_index_g3.json'
    json.dump({k: dict(mark=v['mark'], result=v['result'], tro=v['tro']) for k, v in keep.items() if k in keys}, open(sub, 'w'))
    lx = []
    try:
        for m in I.live_matches({'CLX'}, index=sub):
            lx += [dict(key=m['key'], lock_reach=x['lock']) for x in I.xbow_rows(m)
                   if 'lock' in x and D.PK.state(x['our_cr'], x['their_cr']) == '1-1']
    finally:
        sub.unlink()
    r = cluster_ci(lx)
    print(f'  G3 monitored: X-Bow lock at 1-1 live {100 * r[0]:.1f} [{100 * r[1]:.1f}, {100 * r[2]:.1f}] ({r[3]} X-Bows in {r[4]} matches, '
          'match-cluster bootstrap)', end='')
    sx = [x for j in raws if j.get('o3_trace') for x in D.sim_xbows(j) if x['state'] == '1-1']
    if sx:
        s = cluster_ci(sx)
        print(f' | SIM {100 * s[0]:.1f} [{100 * s[1]:.1f}, {100 * s[2]:.1f}] ({s[3]} in {s[4]})')
    else:
        print(' | SIM: no position rows (run the block with O3_POS=1)')


def g2_ok(raw):
    n = sum('plays_tap_lost' in j and 'plays_tap_slow' in j for j in raw)
    return n == len(raw), n


def setup(n):
    live, _ = R.recent_rows(n)
    live = g1(live)
    l233 = g1(T.ranked_rows())
    T.TOL.clear()
    T.TOL.update(R.scaled_tol(live, l233))
    T.ranked_rows = lambda: live
    T._LIVE_STYLE.clear()
    T._LIVE_STYLE['ranked'] = live_style_confirmed(live)
    return live, l233


def main():
    n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 100
    roots = [a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()]
    live, l233 = setup(n)
    print(f'{VERSION}: live = the last {len(live)} CLX Ranked matches ({live[0]["key"][10:25]} .. {live[-1]["key"][10:25]}), G1 '
          f'labels; tolerances ' + ', '.join(f'{k} {v:.1f}' for k, v in T.TOL.items()) + '; style vs these matches, G4 taps')
    if '--targets' in sys.argv:
        print('\n| cell | target (recent, G1) [95%] | tolerance (pp) |\n|---|---|---|')
        for cell, sel, hit in T.CELLS:
            b = sel(live)
            print(f'| {"* " if cell in T.GATE else ""}{cell} | {T.AN.fmt(sum(map(hit, b)), len(b))} | '
                  f'{T.TOL[cell]:.1f} |' if cell in T.TOL else f'| {"* " if cell in T.GATE else ""}{cell} | '
                  f'{T.AN.fmt(sum(map(hit, b)), len(b))} | z only |')
    for root in roots:
        for name, raw in sorted(T.load_sim(root).items()):
            ok, k = g2_ok(raw)
            out, fails, dr = T.table(name, raw, live, brief='--brief' in sys.argv)
            verdict = (f'{12 - len(fails)} of 12 pass' if ok else
                       f'INVALID (G2): {k} of {len(raw)} rows carry the CLX handicap; re-run with W18_EXTRA="{HANDICAP}"')
            print(f'  >> {VERSION}: {name}: {verdict}' + (f'; fails {fails}' if ok and fails else ''))
            if '--lock11' in sys.argv:
                lock11(live, raw)


if __name__ == '__main__':
    main()
