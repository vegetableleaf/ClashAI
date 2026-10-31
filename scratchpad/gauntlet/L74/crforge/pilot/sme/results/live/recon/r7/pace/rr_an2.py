"""RECON-7 pace: SIM rows (rr_probe rows.jsonl with own_reasons) vs live CLXIII (calibration block, live_table cache): per-minute rates, 1x rate, median gap.
  python rr_an2.py A.jsonl [B.jsonl ...]    (laptop, icebow venv)"""
import json, sys, statistics as st, random
from pathlib import Path
H = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/humanlike')
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent))

def sim_stats(path):
    rows = [json.loads(l) for l in open(path)]
    per = []
    for r in rows:
        mins = r['end_tick'] / 1200.0
        acc = sorted(q[1] if q[1] is not None else q[0] for q in r['own_reasons'] if q[3])
        att = [q for q in r['own_reasons'] if q[4] not in ('game_over', 'match_over_before_landing')]
        m1 = [t for t in acc if t < 90 + 2400]
        gaps = [(b - a) / 20 for a, b in zip(acc, acc[1:])]
        per.append(dict(seed=r['seed'], acc=len(acc) / mins, att=len(att) / mins, acc1x=len(m1) / ((min(r['end_tick'], 2490) - 90) / 1200.0), gaps=gaps, win=r['outcome'] == 'win',
                        refused_elixir=sum(1 for q in r['own_reasons'] if (q[4] or '').startswith('not_enough_elixir')), n=len(r['own_reasons'])))
    return per

def summ(name, per):
    g = [x for p in per for x in p['gaps']]
    print('%-6s n %3d accepted/min %.2f attempted/min(real) %.2f accepted/min 1x %.2f median gap %.2f s  not_enough_elixir %.1f%% of attempts  wins %d/%d' % (
        name, len(per), st.mean(p['acc'] for p in per), st.mean(p['att'] for p in per), st.mean(p['acc1x'] for p in per), st.median(g),
        100 * sum(p['refused_elixir'] for p in per) / sum(p['n'] for p in per), sum(p['win'] for p in per), len(per)))

if __name__ == '__main__':
    import card
    import live_table as LT
    recs = card.live_records('calibration')
    acc = []; acc1 = []; gaps = []; att = []
    for r in recs:
        d = LT.cached(card.LOGS / r['id'])
        if not d: continue
        conf = sorted(t for t, n in d['own_conf'] if t)
        mins = max(d['end'] - d['t0'], 1) / 1200.0
        acc.append(len(conf) / mins); att.append(len(d['mine']) / mins)
        t0 = d['t0']
        m1 = [t for t in conf if t < t0 + 2400]
        acc1.append(len(m1) / (min(d['end'] - t0, 2400) / 1200.0))
        gaps += [(b - a) / 20 for a, b in zip(conf, conf[1:])]
    print('LIVE   n %3d confirmed/min %.2f attempted/min %.2f confirmed/min 1x %.2f median gap %.2f s' % (len(acc), st.mean(acc), st.mean(att), st.mean(acc1), st.median(gaps)))
    pers = {}
    for f in sys.argv[1:]:
        pers[f] = sim_stats(f); summ(Path(f).parent.name, pers[f])
    if len(sys.argv) >= 3:
        A, B = pers[sys.argv[1]], pers[sys.argv[2]]
        bs = {p['seed']: p for p in A}
        d = [(p['acc'] - bs[p['seed']]['acc']) for p in B if p['seed'] in bs]
        random.seed(0); bm = sorted(st.mean(random.choices(d, k=len(d))) for _ in range(5000))
        print('paired accepted/min B - A: %+.2f [%+.2f, %+.2f] (n %d)' % (st.mean(d), bm[125], bm[4875], len(d)))
