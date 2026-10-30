"""style_s0.py SIM_ROWS_DIR [...] -- OPP-PUSH style track S0 (laptop, no training, sealed block never read): is the opponent's B-live
style error HUMAN DRIFT (CLXIII-era humans play differently from the humans the model imitated) or a model / closed-loop error?
Splits the registered v5/v6 live reference (data/allref_v5.json.gz, its masks applied) into eras, UNWEIGHTED inside each era:
  pre   = train block with every timing stat valid (10-19 .. 10-24, older Marks)    -- imitation-era humans (live_train's span)
  clxiii = calibration block (10-25 08:49 .. 10-28 09:06, CLXIII)                   -- the v6 newest block (scoring reference)
and prints Cohen d per stat for: clxiii humans - pre humans (drift), each SIM dir - pre, each SIM dir - clxiii.
Reading: a stat with |d(model - pre)| ~ |d(model - clxiii)| and small drift = NOT drift (re-imitation on newer rows cannot fix it)."""
import sys
from pathlib import Path

H = Path(__file__).resolve().parents[3] / 'opp_model' / 'humanlike'
sys.path.insert(0, str(H))
import card  # noqa: E402

th = card.json.loads((H / 'THRESHOLDS.json').read_text())
recs, rows = card.ref_v5(th)
era = {'pre': [], 'clxiii': []}
for r, x in zip(recs, rows):
    y = dict(x); y['_w'] = 1.0
    if '20261019_002011' <= r['ts'] < card.SPLIT['train_before']:
        era['pre'].append(y)
    elif card.SPLIT['train_before'] <= r['ts'] < card.SPLIT['sealed_from']:
        era['clxiii'].append(y)
sims = {Path(p).name: card.rows(card.sim_records(p)) for p in sys.argv[1:]}
K = card.STATS
cols = [('drift', era['clxiii'], era['pre'])] + [(f'{n}-pre', s, era['pre']) for n, s in sims.items()] + \
       [(f'{n}-cl', s, era['clxiii']) for n, s in sims.items()]
D = {name: card.wcohen(L, S, K) for name, S, L in cols}
print(f"n humans pre {len(era['pre'])} clxiii {len(era['clxiii'])}; sims " + ' '.join(f'{n} {len(s)}' for n, s in sims.items()))
print(f"{'stat':14s} " + ' '.join(f'{c[0][:14]:>14s}' for c in cols))
for k in K:
    print(f'{k:14s} ' + ' '.join(f'{D[c[0]][k][6]:+14.2f}' for c in cols))
