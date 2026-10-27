"""A2c-M census: hero Balloon throws. For each hero Balloon ability command of a plan: its run tick R, the first sim line
with a new BalloonHero_Skeletrooper_Projectile of its side (crforge), and the first recorded frame with a new projectile
row of the hero Balloon card (203000006) of that side within [R - 40, R + 40] (the reader).
python3 hb_census.py RUNDIR MATCH [MATCH ...]"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import load_frames, runnable

HB = 203000006
run = sys.argv[1]
for m in sys.argv[2:]:
    plan = runnable(json.load(open(os.path.join(run, m, 'plan.json'))))
    abil = [c for c in plan['cmds'] if c['kind'] == 'ability']
    hb = [c for c in abil if any(p['kind'] == 'play' and p['side'] == c['side'] and p['card'] == 'Balloon' and
                                 c['unit'].startswith('cmd%d_' % i) for i, p in enumerate(plan['cmds']))]
    if not hb:
        continue
    o = run_batch([(plan, max(c['run'] for c in hb) + 60, min(c['run'] for c in hb) - 45)], '/workspace/mech/work/hb_' + m)[0]
    fr = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
    ts = sorted(fr)
    for c in hb:
        R, s = c['run'], c['side']
        prev, sim_first = set(), None
        for line in o:
            if line['t'] <= R:
                continue
            cur = {e[0] for e in line['E'] if e[1] == 'P' and 'Skeletrooper' in e[2] and e[3] == s}
            if cur - prev:
                sim_first = line['t']
                break
            prev = cur
        rec_first, had = None, False
        for t in ts:
            if R - 40 <= t <= R + 40:
                has = any(p[0] == s and p[3] == HB for p in fr[t]['P'])
                if has and not had:
                    rec_first = t
                    break
                had = has
        print(m, 'side', s, 'R', R, 'sim_first', sim_first, 'rec_first', rec_first,
              'k_sim', None if sim_first is None else sim_first - R, 'rec-sim', None if None in (sim_first, rec_first) else rec_first - sim_first)
