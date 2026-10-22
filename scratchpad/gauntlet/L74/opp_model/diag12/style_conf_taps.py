"""W18 DIAG_12 S1 (ledger 8.5): style distance with the live pilot's CONFIRMED taps only (lost / retried taps out), tap tick kept.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/diag12/style_conf_taps.py"""
import sys, math
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import diag12 as D
import live_table as LT, opp_behaviour as OB, o3_score as O3
base, kept, same = [], [], 0
n_same = n_all = 0
for r in D.live_rows():
    d = LT.cached(LT.LOGS / r['key'])
    if not (d and d.get('start')): continue
    plays, conf, unc, el = D.read_exec(r['key'])
    ok = [p['tick'] + D.OFF for p in plays if any(q['name'] == p['name'] and 0 <= q['tick'] - p['tick'] <= 80 for q in conf)]
    m = dict(plays=d['plays'], end=d['end'], t0=d['t0'], seen=[], mine=d['mine'])
    base.append(OB.features(m)); kept.append(OB.features({**m, 'mine': ok}))
    ot = {p[0] for p in d['plays']}
    n_same += sum(t in ot for t in d['mine']); n_all += len(d['mine'])
simf = [f for _, f in O3.behaviour(D.sim_raw())]
for lab, L_ in (('taps (as scored)', base), ('confirmed taps only (tap tick)', kept)):
    cmp = OB.compare(L_, simf)
    ds = [cmp[k][4] for k in O3.FEATS if not math.isnan(cmp[k][4])]
    print(f'{lab:32s} distance {math.sqrt(sum(x*x for x in ds)/len(ds)):.2f} react_s {cmp["react_s"][1]:.2f} d {cmp["react_s"][4]:+.2f} react_3s {cmp["react_3s"][1]:.2f}')
print('live taps on the same tick as a detected opponent play:', n_same, 'of', n_all)
