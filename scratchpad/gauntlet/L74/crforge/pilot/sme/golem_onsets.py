"""Hero Ice Golem onsets: for each match/onset tick given, the IceGolemite ability commands within 40 ticks before it,
the sim's hero Ice Golem bodies' death line, and which golem areas the sim and the recorded frame hold at the onset.
    python3 golem_onsets.py RUNDIR MATCH:TICK ..."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch, card_name  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
for arg in sys.argv[2:]:
    m, t0 = arg.split(':')
    t0 = int(t0)
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
    o = run_batch([(runnable(plan), t0 + 30, t0 - 45)], os.path.join(run, m, 'gon'))[0]
    by = {x['t']: x for x in o}
    ab = [(i, c['run'], c['_src']) for i, c in enumerate(plan['cmds']) if c['kind'] == 'ability' and t0 - 40 <= c['run'] <= t0
          and plan['cmds'][int(c['unit'][3:].split('_')[0])].get('card') == 'IceGolemite']
    golems = {}
    for x in o:
        for e in x['E']:
            if e[1] == 'C' and e[2].startswith('IceGolemiteHero'):
                golems.setdefault(e[0], [x['t'], x['t']])[1] = x['t']
    sa = sorted({e[2] for e in by[t0]['E'] if e[1] == 'A' and 'Golem' in e[2]}) if t0 in by else None
    ra = [(a[0], a[1], a[2], card_name(a[3])) for a in frames.get(t0, {'A': []})['A']]
    print(m, 'onset', t0, '| golem ability cmds', ab, '| hero golem lines (first, last)', list(golems.values()),
          '| sim golem areas at onset', sa, '| recorded areas', ra)
