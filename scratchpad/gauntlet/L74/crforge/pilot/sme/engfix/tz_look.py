# tz_look.py MATCH SET -- SME_TOWER_ZAP fired / blocked rows of one record (r6 ON plays)
import json, sys, os
os.environ['SME_TOWER_ZAP'] = '1'
R = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/'
sys.path.insert(0, R + 'L74/crforge/pilot/sme')
import mech_rules
x = next(json.loads(l) for l in open(R + 'L74/crforge/pilot/sme/engfix/r6/%s_on.jsonl' % sys.argv[2]) if sys.argv[1] in l)
sides = {int(k): v for k, v in x['sides'].items()}
_, f, b = mech_rules.tower_zaps(mech_rules.raw_frames(R + 'L68/live_reader/' + x['match'] + '.jsonl'), x['plays'], sides, x.get('reader_hidden') or ())
print('my_side', x['my_side'], 'decks', sides[0]['deck'], sides[1]['deck'])
print('fired', f); print('blocked', b)
