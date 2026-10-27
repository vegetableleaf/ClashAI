"""Hero IW / cube target-lost events by attack timer at the loss: atk >= hit speed (1700, a held attack) vs below.
python3 lost_iw.py LOST.jsonl RUNDIR"""
import collections, json, os, sys
ev = [json.loads(l) for l in open(sys.argv[1])]
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(sys.argv[2], 'results.jsonl'))}
c = collections.Counter()
for e in ev:
    if not e['name'].startswith('IceWizardHero') or e.get('G') is None:
        continue
    fd = res.get(e['match'], {}).get('first_div')
    clean = fd is None or e['S'] + 2 < fd
    held = e['atk'] >= 1700
    # the game frame strictly between the loss frame and S that shows a target: G < S; G - Gprev == 1 is a 1-tick pair
    c[(e['name'], 'held' if held else 'running', 'clean' if clean else 'diverged',
       'late' if e['late'] else 'agree')] += 1
    if held and e['late']:
        print(e['match'][10:], e['name'], e['t0'], 'S', e['S'], 'G', e['G'], 'Gprev', e['Gprev'], 'atk', e['atk'], 'clean', clean)
for k, v in sorted(c.items()):
    print(k, v)
