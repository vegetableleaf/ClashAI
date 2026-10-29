# rascal_census.py -- ENG-FIX4: every first_seen Rascals play on dev + FRESH1-6 scored records: point, girls at first sight
import json, sys
sys.path.insert(0, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme')
import mech_rules as M
H = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/engfix/'
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
SETS = [(s, H + 'r6/%s_on.jsonl' % s) for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5')] + [('fresh6', H + 'fresh6/inputs_rngfree.jsonl')]
for s, f in SETS:
    for line in open(f):
        r = json.loads(line)
        ps = [p for p in r['plays'] if p.get('card') == 'Rascals' and p['kind'] == 'play']
        if not ps:
            continue
        fr = M.zd_frames(LIVE + r['match'] + '.jsonl')
        for p in ps:
            g = next(([(b['x'], b['y']) for b in B.values() if b['side'] == p['side'] and b['name'] == 'RascalGirl'] + [(b['x'], b['y']) for b in B.values() if b['side'] == p['side'] and b['name'] == 'RascalBoy']
                      for t, B, _, _ in fr if p['tick'] < t <= p['tick'] + 8 and any(b['name'] == 'RascalGirl' and b['side'] == p['side'] for b in B.values())), None)
            print(s, r['match'][10:], 'side', p['side'], 'tick', p['tick'], 'pt', (p['x'], p['y']), p.get('source'), p.get('dated'), 'girls+boy', g)
