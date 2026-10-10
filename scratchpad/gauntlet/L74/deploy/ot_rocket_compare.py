"""Owner 10-10: does the new live model (E4 u20 + grafted add-ons) Rocket less in overtime than the old one?
Same recorded OT decisions (towerref_w2-era live logs, rebuilt by L73/lethal_rocket/rebuild.Match), three models:
OLD = previous live, NEW = E4 u20 + add-ons, RAW = E4 u20 without add-ons. Per decision with a Rocket playable:
P(play) x P(Rocket | play), top card == Rocket, and whether the Rocket's best cell is in the enemy tower area.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/deploy/ot_rocket_compare.py [n_logs]"""
import glob, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path[:0] = [REPO, os.path.join(REPO, 'scratchpad/gauntlet/L73/lethal_rocket')]
import numpy as np, torch  # noqa: E402
from rebuild import Match  # noqa: E402
from pipeline.model_gen import load_model  # noqa: E402
from pipeline.model_v3 import cell_xy  # noqa: E402
torch.set_num_threads(2)
B = 'C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/'
CK = {'OLD': B + 'rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt',
      'NEW': B + 'rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt', 'RAW': B + 'rdef_e4/rdef_e4_u0020.pt'}
M = {k: load_model(v, torch.device('cpu'))[0].eval() for k, v in CK.items()}
OT = 3600
logs = []
for f in sorted(glob.glob('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_2026*.jsonl'))[::-1]:
    head = open(f, encoding='utf-8', errors='replace').readline()
    if 'towerref_w2' in head and 'rdef_e4' not in head:
        logs.append(f)
n_logs = int(sys.argv[1]) if len(sys.argv) > 1 else 40
per_match, used = [], 0
for f in logs:
    if used >= n_logs: break
    try:
        m = Match(f, CK['OLD'])
    except Exception:  # noqa: BLE001 -- old-schema / incomplete logs
        continue
    rows = []
    for i, d in enumerate(m.dec):
        if d['public']['model_tick'] < OT: continue
        b, info = m.batch(i)
        if 'Rocket' not in info['names']: continue
        s = info['names'].index('Rocket')
        if not info['allowed'][s]: continue
        r = {}
        with torch.no_grad():
            for k, mod in M.items():
                o = mod(b, card=b['hand_card'][:, s], form=b['hand_form'][:, s])
                pc = torch.softmax(o['card'][0], -1)
                y = cell_xy(int(o['cell'][0].argmax()), m.grid)[1]
                r[k] = (float(torch.sigmoid(o['gate'][0])) * float(pc[s]), float(int(pc.argmax()) == s), float(y > 1 - 10 / 32))   # tile y = (1 - y) * 32: enemy towers at tile y < 10
        rows.append(r)
    if rows:
        used += 1; per_match.append(rows)
        print(os.path.basename(f)[10:25], len(rows), 'OT decisions', flush=True)
def stat(k, j):
    return np.array([np.mean([r[k][j] for r in rows]) for rows in per_match])
rng = np.random.default_rng(0)
for j, name in enumerate(['P(Rocket now)', 'top card = Rocket', 'Rocket aimed at tower area']):
    o = stat('OLD', j)
    for k in ('NEW', 'RAW'):
        d = stat(k, j) - o
        bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
        print(f'{name:28s} OLD {o.mean():.3f}  {k} {stat(k, j).mean():.3f}  diff {d.mean():+.3f} [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]  (matches {len(d)})')
