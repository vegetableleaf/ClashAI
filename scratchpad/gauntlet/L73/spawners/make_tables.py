"""Compact pros-vs-bot per-family table (markdown) from rows_*.jsonl -> tables.md. Run after spawner_behaviour.py."""
import json, os, collections, statistics
HERE = os.path.dirname(os.path.abspath(__file__))


def rd(n):
    return [json.loads(l) for l in open(os.path.join(HERE, n))]


rows = {'pros': [r for r in rd('rows_pros.jsonl') if r.get('core', 0) >= 7], 'bot': rd('rows_bot.jsonl')}
FAMS = ['Witch', 'NightWitch', 'Furnace', 'MotherWitch', 'Tombstone', 'GoblinHut', 'BarbarianHut', 'Graveyard']
AB = {'same-lane own-back': 'sameL-back', 'opp-lane own-back': 'oppL-back', 'same-lane bridge': 'sameL-bridge', 'opp-lane bridge': 'oppL-bridge',
      'same-lane enemy-half': 'sameL-attack', 'opp-lane enemy-half': 'oppL-attack', 'NEAR': 'NEAR', 'ON': 'ON'}


def pc(a, b):
    return round(100 * a / b) if b else 0


def top(c, k=3):
    t = sum(c.values())
    return ', '.join('%s %d' % (n, pc(v, t)) for n, v in c.most_common(k))


def med(v):
    v = [x for x in v if x is not None]
    return round(statistics.median(v), 1) if v else None


L = ['| family | who | n (games) | ignored % | 1st delay s | 1st card % | 1st placement % | no same-lane play 8s % | life med s (>20s %) | killed: Rocket / tower-in-range / Xbow-in-range % | my elixir at deploy | tower dmg 15s (% princ) |',
     '|---|---|---|---|---|---|---|---|---|---|---|---|']
for fam in FAMS:
    for who in ('pros', 'bot'):
        R = [r for r in rows[who] if r['fam'] == fam]
        if not R:
            continue
        n = len(R)
        first = collections.Counter(r['resp'][0]['card'] for r in R if r['resp'])
        wh = collections.Counter(AB[r['resp'][0]['where']] for r in R if r['resp'])
        D = [r for r in R if r['died']]
        D2 = [r for r in R if not r['dmg_trunc']]
        gy = fam == 'Graveyard'
        kill = '-' if gy else '%d / %d / %d' % (pc(sum(r['cause'] == 'Rocket' for r in D), len(D)), pc(sum('Tower' in r['attackers'] for r in D), len(D)), pc(sum('Xbow' in r['attackers'] for r in D), len(D)))
        L.append('| %s | %s | %d (%d) | %d | %s | %s | %s | %d | %s (%d) | %s | %s | %s |' % (
            fam, who, n, len(set(r['src'] for r in R)), pc(sum(r['ignored'] for r in R), n), med([r['resp'][0]['delay'] for r in R if r['resp']]),
            top(first), top(wh), pc(sum(r['first_same_lane'] is None for r in R), n), med([r['life_s'] for r in R]), pc(sum(r['life_s'] > 20 for r in R), n),
            kill, med([r['my_elixir'] for r in R]), round(statistics.mean([r['dmg_pct_princess'] for r in D2]), 1) if D2 else None))
open(os.path.join(HERE, 'tables.md'), 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
