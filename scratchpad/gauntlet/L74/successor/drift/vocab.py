import json, sys, collections
sys.path[:0] = ['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/weekend']
import archetypes as A
cen = json.load(open('C:/Users/benpe/pod_backup_weekend/parity1016/census/census_all.json'))
live = collections.Counter()
for k, n in cen['plays'].items():
    if k.startswith('opp '):
        live[A.canon(k[4:].split(' ')[0])] += n
voc = collections.Counter()
for f in ['in/icebow/data/rltest/decks_rl.json', 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/mix/decks_live_eval.json']:
    for d in json.load(open(f))['decks']:
        for e in d['engine']:
            voc[A.canon(e.split('@')[0])] += 1
tot = sum(live.values())
print('live names not in either pool vocab:', [(c, n, round(100*n/tot, 2)) for c, n in live.most_common() if c not in voc])
print('pool names never in live (top 40 by pool decks):', [(c, n) for c, n in voc.most_common() if c not in live][:40])
