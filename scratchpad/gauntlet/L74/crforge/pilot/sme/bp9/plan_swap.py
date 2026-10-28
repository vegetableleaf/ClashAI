"""plan_swap.py IN_PLAN OUT_PLAN MODE -- A2c-9R: reorder same-run plays of the two sides (the game creating one side's units first).
MODE side1: within a run tick, side-1 plays before side-0 plays; side0: the reverse; opp: the opponent's (not own) plays first.
Only the relative order of plays sharing a run tick changes; ability commands' unit names (cmd<i>_<k>) are remapped to the new
indices. Prints the swaps."""
import json, re, sys
src, dst, mode = sys.argv[1], sys.argv[2], sys.argv[3]
p = json.load(open(src))
cmds = p['cmds']


def key(i):
    c = cmds[i]
    if c.get('kind') != 'play': return (c.get('run', 0), 0, i)
    if mode == 'side1': pri = 0 if c['side'] == 1 else 1
    elif mode == 'side0': pri = 0 if c['side'] == 0 else 1
    else: pri = 0 if not (c.get('_src') or {}).get('own') else 1
    return (c['run'], pri, i)


# keep every command where it is unless it is a play sharing its run tick with a play of the other side
order = list(range(len(cmds)))
groups = {}
for i, c in enumerate(cmds):
    if c.get('kind') == 'play': groups.setdefault(c['run'], []).append(i)
for run, ix in groups.items():
    if len({cmds[i]['side'] for i in ix}) < 2: continue
    new = sorted(ix, key=key)
    if new != ix:
        print('swap run', run, [(i, cmds[i]['side'], cmds[i]['card']) for i in ix], '->', [(i, cmds[i]['side'], cmds[i]['card']) for i in new])
    for slot, i in zip(sorted(ix), new): order[slot] = i
newidx = {old: new for new, old in enumerate(order)}
out = []
for old in order:
    c = dict(cmds[old])
    if c.get('kind') == 'ability' and isinstance(c.get('unit'), str):
        c['unit'] = re.sub(r'^cmd(\d+)', lambda mm: 'cmd%d' % newidx[int(mm.group(1))], c['unit'])
    out.append(c)
p['cmds'] = out
json.dump(p, open(dst, 'w'))
