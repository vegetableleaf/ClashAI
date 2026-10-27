"""Hero Valkyrie ability dating: per Valkyrie ability command (run R, extractor window), the sim's first
ValkyrieHero_AEO line a_s after R and the recorded first frame a_r >= R-10 holding a hero-Valkyrie area (203000011) of
that side, plus the frame before it. Prints the distribution of a_r - a_s and of (a_r - prev frame).
    python3 valk_check.py RUNDIR"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
d, gaps, n = collections.Counter(), collections.Counter(), 0
for l in open(os.path.join(run, 'results.jsonl')):
    m = json.loads(l)['match']
    p = os.path.join(run, m, 'plan.json')
    if not os.path.exists(p):
        continue
    plan = json.load(open(p))
    cards = {'cmd%d_0' % i: c.get('card') for i, c in enumerate(plan['cmds'])}
    abil = [c for c in plan['cmds'] if c['kind'] == 'ability' and cards.get(c['unit']) == 'Valkyrie']
    if not abil:
        continue
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'valk'))[0]
    if o is None:
        continue
    ts = sorted(frames)
    for c in abil:
        R, side = c['run'], c['side']
        a_s = next((x['t'] for x in o if x['t'] > R and any(e[2] == 'ValkyrieHero_AEO' and e[3] == side for e in x['E'])), None)
        a_r = next((t for t in ts if t >= R - 10 and any(a[3] == 203000011 and a[0] == side for a in frames[t]['A'])), None)
        if a_s is None or a_r is None or abs(a_r - a_s) > 30:
            continue
        prev = max((t for t in ts if t < a_r), default=None)
        n += 1
        d[a_r - a_s] += 1
        gaps[(a_r - R, a_s - R, c['_src']['source'], c['_src']['hi'] - c['_src']['lo'])] += 1
        c_src = c['_src']
print('abilities', n)
print('recorded first hero-Valkyrie area minus the sim first ValkyrieHero_AEO line:', sorted(d.items()))
print('(rec - R, sim - R, source, window width):', sorted(gaps.items()))
