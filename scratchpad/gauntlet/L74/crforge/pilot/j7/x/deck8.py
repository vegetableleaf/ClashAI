import json, sys
with open(sys.argv[2], 'w', newline='\n') as w:
    for line in open(sys.argv[1]):
        r = json.loads(line)
        cyc = r['own_cycle_fail'] is None and r['opp_fitting_deals'] > 0
        if cyc and not any(':deck_seen:' in f for f in r['flags']):
            w.write(r['match'] + '\n')
