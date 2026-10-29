"""ENG-FIX2: does the displacement rule (spellk_census rule_run) give the run the SME fitter kept? Joins the census with
fitted_spells.py rows on (match, card, side, window lo); counts only plays validated by exactness (run + 40 < first_div
or the match exact). Prints agree / disagree and each disagreement.
    python -I spellk_join.py CENSUS.tsv FITTED.tsv"""
import collections, csv, sys
NAME = {'GoblinBarrel': 'GoblinBarrel', 'Fireball': 'Fireball', 'Rocket': 'Rocket', 'Snowball': 'Snowball'}
cen = {}
for r in csv.DictReader(open(sys.argv[1]), delimiter='\t'):
    if r['card'] in NAME and (r['src'] or '').endswith('K') and float(r['offline']) <= 50 and abs(float(r['k']) - round(float(r['k']))) <= .05:
        cen[(r['match'], r['card'], r['side'], r['prev'])] = r
n = collections.Counter()
for r in csv.DictReader(open(sys.argv[2]), delimiter='\t'):
    fd = None if r['first_div'] == 'None' else int(r['first_div'])
    if fd is not None and int(r['run']) + 40 >= fd:
        n['after_or_near_div'] += 1
        continue
    c = cen.get((r['match'], r['card'], r['side'], r['lo']))
    if c is None:
        n['no_census_row'] += 1
        continue
    ok = int(c['rule_run']) == int(r['run'])
    n['agree' if ok else 'disagree'] += 1
    n['default_was_' + ('right' if int(r['tick']) == int(r['run']) else 'wrong')] += 1
    if not ok:
        print('DISAGREE', r['match'], r['card'], r['side'], 'window', r['lo'], r['hi'], 'fitted', r['run'], 'rule', c['rule_run'], 'k', c['k'])
print(dict(n))
