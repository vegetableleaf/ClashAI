"""Summarise the last N battles of crapi/data/own_battlelog.jsonl (mode, crowns, decks, levels, starting trophies); no opponent tag/name printed."""
import json, sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
rows = [json.loads(l) for l in open(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crapi\data\own_battlelog.jsonl')][-N:]
for r in rows:
    b = r['battle']; me, op = b['team'][0], b['opponent'][0]
    f = lambda p: [(c['name'], c['level'], c.get('evolutionLevel'), c.get('starLevel')) for c in p['cards']]
    print(b['battleTime'], b['type'], b['gameMode']['name'], 'my crowns', me['crowns'], 'opp crowns', op['crowns'],
          'my trophies', me.get('startingTrophies'), 'opp trophies', op.get('startingTrophies'), 'trophyChange', me.get('trophyChange'),
          'princess left (me/opp)', me.get('kingTowerHitPoints'), me.get('princessTowersHitPoints'), '/', op.get('kingTowerHitPoints'), op.get('princessTowersHitPoints'))
    print('   opp deck:', f(op)); print('   opp supports:', op.get('supportCards'))
