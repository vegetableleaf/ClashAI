"""L74/habits: sensitivity of the 'punish window' definition, and what a heavy answer on our bridge X-Bow costs afterwards.
  1 P(heavy at the X-Bow within 8 s) by punish window under 4 definitions (back = y <= 7 in our frame):
      P1 >= 1 card cost >= 4 in the back, last 5 s (hablib's)  P2 back spend >= 5 in the last 8 s
      P3 back spend >= 6 in the last 10 s                        P4 any spend >= 6 in the last 5 s (anywhere)
  2 after a heavy answer (live; SIM in sim_tables): our tower HP lost and towers lost in the 20 s after the heavy card
    python punish_sens.py [--sim-json sim_rows.json]  (live cache + pro sides)"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hablib as H  # noqa: E402
import live_tables as LT  # noqa: E402
import pro_tables as PT  # noqa: E402

pct = LT.pct
DEFS = {'P1': lambda m, t: any(t - 100 <= p['tick'] <= t and p['y'] is not None and p['y'] <= H.BACK_Y and H.cost(p['card']) >= 4
                               and H.kind(p['card']) != 'spell' for p in m['opp']),
        'P2': lambda m, t: sum(H.cost(p['card']) for p in m['opp'] if t - 160 <= p['tick'] <= t and p['y'] is not None
                               and p['y'] <= H.BACK_Y) >= 5,
        'P3': lambda m, t: sum(H.cost(p['card']) for p in m['opp'] if t - 200 <= p['tick'] <= t and p['y'] is not None
                               and p['y'] <= H.BACK_Y) >= 6,
        'P4': lambda m, t: sum(H.cost(p['card']) for p in m['opp'] if t - 100 <= p['tick'] <= t) >= 6}


def after_heavy(m, r):
    """Our tower HP / towers lost in the 20 s after the first heavy answer to X-Bow row r (live frames)."""
    hv = [p for p in m['opp'] if r['tick'] < p['tick'] <= r['tick'] + H.PUNISH_TICKS and p['card'] in r['heavy_cards']]
    t = hv[0]['tick'] if hv else r['tick'] + 40
    T0, T1 = H.tower_at(m, t), H.tower_at(m, t + 400)
    return H.tower_sum(T0, 'own') - H.tower_sum(T1, 'own'), sum(T0.get(('own', s), 0) > 0 and T1.get(('own', s), 0) <= 0 for s in 'KLR')


def main():
    live = LT.load()
    pros = PT.load()
    print('## 1. P(heavy at our bridge X-Bow within 8 s) by punish-window definition (yes / no)')
    for g in ['CXXIV', 'CXXXVIII', 'CLIII', 'pro icebow crawl2', 'pro icebow8 HF', 'pro other X-Bow HF']:
        M = [m for m in live + pros if m['group'] == g]
        rows = [(m, r) for m in M for r in H.xbow_events(m)]
        parts = []
        for k, f in DEFS.items():
            yes = [r for m, r in rows if f(m, r['tick'])]
            no = [r for m, r in rows if not f(m, r['tick'])]
            parts.append(f"{k} yes {len(yes)} {pct(H.mean([r['heavy'] for r in yes]))} win {pct(H.wr(yes))} / no {len(no)} "
                         f"{pct(H.mean([r['heavy'] for r in no]))} win {pct(H.wr(no))}")
        print(f'  {g:20s} ' + '\n  ' + ' ' * 20 + ' '.join(['']) + ('\n  ' + ' ' * 21).join(parts))
    print('\n## 2. Live: our tower HP / towers lost in the 20 s after the heavy answer vs 20 s after an unanswered X-Bow (+2 s)')
    for g in ['CXXIV', 'CXXXVIII', 'CLIII']:
        M = [m for m in live if m['group'] == g]
        hv, nh = [], []
        for m in M:
            for r in H.xbow_events(m):
                (hv if r['heavy'] else nh).append(after_heavy(m, r))
        f = lambda xs: (H.mean([x[0] for x in xs]), H.mean([x[1] for x in xs]))
        a, b = f(hv), f(nh)
        print(f"  {g:9s} heavy answer n {len(hv)}: HP lost {a[0]:.0f}, towers lost {a[1]:.3f} | no heavy n {len(nh)}: HP lost {b[0]:.0f}, "
              f"towers lost {b[1]:.3f}")


if __name__ == '__main__':
    main()
