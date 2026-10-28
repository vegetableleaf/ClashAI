import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
fn = '''

def own_charge_presses(path, plays, my, sides):
    """A2c round 8.7 (SME_CHARGE8=1): our own hero ability presses seen only as a charge drop. The reader's phase-2 unit
    row of our hero carries ability.own_action.charges_raw (our own side only). Census over the 138 matches: 122 drops,
    121 have an extracted own press within [drop - 30, drop + 2]; the other one is 225213@3588 (our hero Ice Wizard: no
    cast_seen, no tap; our elixir drops 2.0 on the same frame pair). Such a drop becomes a press with R in the frame pair
    [prev, drop - 1] (the cost is taken in step R, visible on line R + 1)."""
    presses = [q['tick'] for q in plays if q['kind'] == 'ability' and q['side'] == my]
    deck = sides[my]['deck']
    last, seen, add = {}, set(), []
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        for u in (d.get('phase2') or {}).get('units', []):
            oa = (u.get('ability') or {}).get('own_action')
            if u.get('side') != my or not oa or oa.get('charges_raw') is None:
                continue
            k, c = u.get('generation'), oa['charges_raw']
            card = str(u.get('name', ''))[:-4] if str(u.get('name', '')).endswith('Hero') else None
            if k in last and c < last[k][0] and card in deck and \
                    not any(-30 <= x - t <= 2 for x in presses):
                add.append(dict(side=my, kind='ability', card=card, deck_index=deck.index(card), name=card, form=0,
                                run_ticks=[last[k][1], t - 1], tick=t - 1, source='charge_drop'))
            last[k] = (c, t)
    return plays + add
'''
anchor = '\n\ndef match(path, bl=None'
assert anchor in s and 'def own_charge_presses' not in s
s = s.replace(anchor, fn + anchor, 1)
old = "    build = next(((json.loads(r).get('phase2') or {}).get('build')"
assert s.count(old) == 1
s = s.replace(old, "    if os.environ.get('SME_CHARGE8') == '1':   # round 8.7\n        plays = own_charge_presses(path, plays, my, sides)\n" + old)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ok')
