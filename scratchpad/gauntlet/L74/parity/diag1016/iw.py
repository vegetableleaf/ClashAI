"""Own Hero IW in strict own-IW-anchored fights (current fights.py): damage taken live vs SIM, and the single-frame drop
values seen on one side only (who hurts the IW differently). Also the slow: enemy speed near the IW."""
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import capture, setup, F
src = Path('C:/Users/benpe/pod_backup_weekend/rt35/FIGHTS35/matches')
want = defaultdict(set)
for p in sorted(src.glob('*.json')):
    d = json.loads(p.read_text())
    if d['summary'].get('skipped'): continue
    for r in d['fights']:
        if 'error' not in r and F.is_clean(r, sys.argv[1]) and r['own'] and r['anchor']['name'] == 'IceWizard' and r['anchor']['form'] == 2:
            want[p.stem].add(r['t0'])
tot = Counter(); only = Counter(); per = []
for stem, t0s in sorted(want.items()):
    ctx = setup(stem); side = ctx['m']['side']
    res, _ = capture(stem, lambda f, a: f['t0'] in t0s, ctx)
    for f, a, rows, st, r in res:
        if not rows: continue
        # the anchor IW: live body first seen within 12 ticks of the play; SIM: nearest new IW hero
        lid = next((b['id'] for t, live, _ in rows for b in live if not b['tower'] and b['side'] == side and F.form_of(b['card_id'], ctx['catalog'].get(b['card_id'], {})) == 2 and abs(t-a['tick']) <= 12), None)
        sid = next((b['id'] for t, _, simb in rows for b in simb if b.get('name') == 'IceWizard' and b['form'] == 2 and b['side'] == side and abs(t-a['tick']) <= 12), None)
        if not lid or not sid: continue
        L = [(t, next((b['hp'] for b in live if b['id'] == lid), None)) for t, live, _ in rows]
        S = [(t, next((b['hp'] for b in simb if b['id'] == sid), None)) for t, _, simb in rows]
        dl = Counter(a_[1]-b_[1] for a_, b_ in zip(L, L[1:]) if a_[1] is not None and b_[1] is not None and b_[1] < a_[1])
        ds = Counter(a_[1]-b_[1] for a_, b_ in zip(S, S[1:]) if a_[1] is not None and b_[1] is not None and b_[1] < a_[1])
        for k in set(dl) | set(ds):
            only[k] += dl[k] - ds[k]
        ldead = L[-1][1] is None; sdead = S[-1][1] is None
        per.append(dict(m=stem[-6:], t0=f['t0'], live_dmg=sum(k*v for k, v in dl.items()), sim_dmg=sum(k*v for k, v in ds.items()), ldead=ldead, sdead=sdead))
    print(stem, len(res), flush=True)
print('IW bodies', len(per), 'dies live only', sum(p['ldead'] and not p['sdead'] for p in per), 'sim only', sum(p['sdead'] and not p['ldead'] for p in per))
print('mean damage taken live', round(sum(p['live_dmg'] for p in per)/len(per)), 'sim', round(sum(p['sim_dmg'] for p in per)/len(per)))
print('drop values: live count - sim count (most live-heavy):', sorted(only.items(), key=lambda x: -x[1])[:12])
print('most sim-heavy:', sorted(only.items(), key=lambda x: x[1])[:12])
for p in per:
    if p['ldead'] != p['sdead']: print(p)
