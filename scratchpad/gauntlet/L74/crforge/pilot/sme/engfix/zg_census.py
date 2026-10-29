# zg_census.py OUT -- ENG-FIX4: every ZapFreeze buff group on dev + FRESH1-6 scored logs that ZAP_ADD rejects (zap_is_cast False)
# and that no extracted opponent Zap play explains (|tick - (c - 1)| <= 3); per hit: name, drop, buffs.
import json, sys
sys.path.insert(0, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme')
import mech_rules as M
H = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/engfix/'
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
SETS = [(s, H + 'r6/%s_on.jsonl' % s) for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5')] + [('fresh6', H + 'fresh6/inputs_rngfree.jsonl')]
out = open(sys.argv[1], 'w')
n = 0
for s, f in SETS:
    for line in open(f):
        r = json.loads(line)
        sides = {int(k): v for k, v in r['sides'].items()}
        for g in M.zap_groups(LIVE + r['match'] + '.jsonl'):
            o = g['s']
            if o not in sides or 'Zap' not in sides[o]['deck'] or not g['hits']:
                continue
            if any(p['side'] == o and p['kind'] == 'play' and p['card'] == 'Zap' and abs(p['tick'] - (g['c'] - 1)) <= 3 for p in r['plays']):
                continue
            lv = sides[o]['levels'][sides[o]['deck'].index('Zap')]
            if M.zap_is_cast(g, lv):
                continue
            n += 1
            print(s, r['match'][10:], 'c', g['c'], 's', o, 'lv', lv, 'electro', len(g['electro']),
                  [(h['name'], h['drop'], [b for b in h['buffs'] if b != 'ZapFreeze']) for h in g['hits'].values()], file=out)
print('rejected groups', n, file=out)
out.close()
print(open(sys.argv[1]).read())
