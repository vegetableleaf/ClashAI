"""L74 runover, pass 3: matches.jsonl + episodes.jsonl -> summary.txt (plain stdlib)."""
import os, json, collections, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
M = [json.loads(l) for l in open(os.path.join(HERE, 'matches.jsonl'))]
E = [json.loads(l) for l in open(os.path.join(HERE, 'episodes.jsonl'))]
out = []
def P(*a): out.append(' '.join(str(x) for x in a))
def med(v): v = [x for x in v if x is not None]; return round(st.median(v), 2) if v else None
def pc(k, n): return f'{k}/{n} ({100 * k / n:.0f}%)' if n else f'{k}/0'


def cause(e):
    if e['gate_s'] >= 1.0 and e['gate_s'] >= e['broke_s']: return 'gate_hold'
    if e['broke_s'] >= 1.0: return 'broke'
    return 'answered_still_fell'


def block(name, ms, es):
    W = sum(m['result'] == 'WIN' for m in ms); L = sum(m['result'] == 'LOSS' for m in ms)
    L3 = [m for m in ms if m['result'] == 'LOSS' and m['cc'] == 3]
    P(f'\n=== {name}: matches {len(ms)}  W {W} L {L}  3-crowned {len(L3)} ({100 * len(L3) / max(L, 1):.0f}% of losses)')
    P('  crowns conceded in losses:', dict(collections.Counter(m['cc'] for m in ms if m['result'] == 'LOSS')))
    P('  fall episodes (my tower falls; princesses that fall with the king are not double counted):', len(es))
    for n in (10, 15, 20, 30):
        P(f'    fall within {n:2d} s of the push crossing: {pc(sum(e["dur"] <= n for e in es), len(es))}')
    ro = [e for e in es if e['dur'] <= 20]; slow = [e for e in es if e['dur'] > 20]
    for lab, xs in (('RUN-OVER (<= 20 s)', ro), ('slower falls (> 20 s)', slow)):
        if not xs: continue
        P(f'  -- {lab}: n={len(xs)}')
        P(f'     elixir at push crossing: median {med([e["el0"] for e in xs])}; < 4: {pc(sum((e["el0"] or 0) < 4 for e in xs), len(xs))}; '
          f'window min elixir median {med([e["el_min"] for e in xs])}')
        fs = sum(e['fire_s'] for e in xs)
        P(f'     seconds under fire (tower losing HP) {fs:.0f}: gate hold (affordable defence, no play) {sum(e["gate_s"] for e in xs):.0f} '
          f'({100 * sum(e["gate_s"] for e in xs) / max(fs, 1e-9):.0f}%), broke {sum(e["broke_s"] for e in xs):.0f} '
          f'({100 * sum(e["broke_s"] for e in xs) / max(fs, 1e-9):.0f}%), playing {sum(e["play_s"] for e in xs):.0f}')
        g = [e for e in xs if e['gate_s'] >= 2]
        P(f'     episodes with >= 2 s gate hold while under fire: {pc(len(g), len(xs))}; their p median {med([e["gate_p_med"] for e in g if e["gate_p_med"] >= 0])} '
          f'vs tau median {med([e["gate_tau_med"] for e in g if e["gate_tau_med"] >= 0])}')
        held = collections.Counter()
        for e in g: held.update(e['held'].keys())
        P('     cards affordable and held in those episodes (episodes):', dict(held.most_common()))
        P(f'     primary cause: {dict(collections.Counter(cause(e) for e in xs))}')
        nl = sum(e['plays_in_lane'] == 0 for e in xs)
        P(f'     no non-X-Bow play in the threat lane (or anywhere for king) from 2 s before the crossing to the fall: {pc(nl, len(xs))}')
        nl0 = sum(e['plays_in_lane'] == 0 and not e['plays'] for e in xs)
        P(f'       of which no play at all {nl0}; played only elsewhere {nl - nl0}')
        P(f'     spent in the 12..2 s before the crossing: median {med([e["pre_cost"] for e in xs])} elixir; >= 6: '
          f'{pc(sum(e["pre_cost"] >= 6 for e in xs), len(xs))}; with an X-Bow: {pc(sum("Xbow" in e["pre"] for e in xs), len(xs))}; '
          f'with a Rocket: {pc(sum("Rocket" in e["pre"] for e in xs), len(xs))}')
        P('     cards played in those 10 s:', dict(collections.Counter(n for e in xs for n in e['pre']).most_common(8)))
        cards = collections.Counter(n for e in xs for n, l in e['plays'])
        P('     cards played in the windows:', dict(cards.most_common()))
        un = sum(e['att_child_unres'] for e in xs); rs = sum(e['att_child_res'] for e in xs); an = sum(e['att_n'] for e in xs)
        P(f'     attacker body-observations within 7 tiles of the tower (last 3 s): {an}; parent-named spawns resolved to the child class '
          f'{rs} ({100 * rs / max(an, 1):.0f}%), UNRESOLVED (model sees the parent) {un} ({100 * un / max(an, 1):.1f}%); '
          f'episodes with any unresolved: {sum(e["att_child_unres"] > 0 for e in xs)}')
        att = collections.Counter()
        for e in xs: att.update(e['att'].keys())
        P('     attacker cards (episodes):', dict(att.most_common(15)))
    return ro


P('L74 runover scan -- live logs since 2026-10-05 (scratchpad/gauntlet/L74/runover; parse.py -> analyze.py -> summarize.py)')
P('results src:', dict(collections.Counter(m['src'] for m in M)))
ro_all = block('ALL since 10-05', M, E)
for era in ('pre', 'bundle2'):
    block(f'era {era}', [m for m in M if m['era'] == era], [e for e in E if e['era'] == era])
for fam in sorted({m['fam'] for m in M}):
    ms = [m for m in M if m['fam'] == fam]
    W = sum(m['result'] == 'WIN' for m in ms); L = sum(m['result'] == 'LOSS' for m in ms)
    L3 = sum(m['result'] == 'LOSS' and m['cc'] == 3 for m in ms)
    es = [e for e in E if e['fam'] == fam]
    P(f'  family {fam:22s} n {len(ms):3d} W-L {W}-{L}  3-crowned {L3}  falls {len(es)} run-over<=20s {sum(e["dur"] <= 20 for e in es)}')

# losses: how many contain a run-over fall
L_ = [m for m in M if m['result'] == 'LOSS']
rof = {e['file'] for e in E if e['dur'] <= 20}
P(f'\nlosses with >= 1 run-over fall: {pc(sum(m["file"] in rof for m in L_), len(L_))}; wins with one: '
  f'{pc(sum(m["file"] in rof for m in M if m["result"] == "WIN"), sum(m["result"] == "WIN" for m in M))}')

# matchup: opponents with skeleton swarms
def has(m, *names): return any(n in m['opp'] for n in names)
for lab, names in (('Skeleton Barrel', ('SkeletonBalloon',)), ('Skeleton King', ('SkeletonKing',)), ('Skeleton Army', ('SkeletonArmy',)),
                   ('Graveyard', ('Graveyard',)), ('Witch', ('Witch',)), ('Goblin Barrel', ('GoblinBarrel',)), ('Golem', ('Golem',)),
                   ('Hog', ('HogRider',)), ('Balloon', ('Balloon',)), ('Royal Hogs', ('RoyalHogs',)), ('Lava', ('LavaHound',))):
    ms = [m for m in M if has(m, *names)]
    if not ms: continue
    W = sum(m['result'] == 'WIN' for m in ms); L = sum(m['result'] == 'LOSS' for m in ms)
    L3 = sum(m['result'] == 'LOSS' and m['cc'] == 3 for m in ms)
    es = [e for e in E if e['file'] in {m['file'] for m in ms} and e['dur'] <= 20]
    P(f'  opp has {lab:15s}: matches {len(ms):3d} W-L {W}-{L} (WR {100 * W / max(W + L, 1):.0f}%) 3-crowned {L3}; run-over falls {len(es)}')
W = sum(m['result'] == 'WIN' for m in M); L = sum(m['result'] == 'LOSS' for m in M)
P(f'  all: WR {100 * W / (W + L):.0f}%')

# 3-crown losses list (bundle2 + towerref)
P('\n3-crown losses, towerref_w2 family (file | push->king seconds | elixir at crossing | gate s / broke s | held | plays | attackers):')
for m in M:
    if m['result'] == 'LOSS' and m['cc'] == 3 and m['fam'] == 'towerref_w2':
        for e in E:
            if e['file'] == m['file'] and e['slot'] == 'mK':
                P(f'  {m["file"][10:25]} {m["era"]:7s} {e["dur"]:5.1f}s el0 {e["el0"]:.1f} gate {e["gate_s"]}/{e["broke_s"]} held {e["held"]} '
                  f'plays {e["plays"]} att {list(e["att"])[:4]}')

# ---- identity census (Q2 live)
P('\n=== Q2 live identity census (bodies seen across decision states; one body counted once per state)')
un, rs = collections.Counter(), collections.Counter(); unm, rsm = collections.Counter(), collections.Counter()
for m in M:
    for k, v in m['unres'].items(): un[k] += v; unm[k] += 1
    for k, v in m['resolved'].items(): rs[k] += v; rsm[k] += 1
P('resolved to a child class (model receives the child):')
agg = collections.defaultdict(lambda: [0, 0, set(), set()])
for k, v in rs.items():
    name, form, hp, cls, why = k.split('|'); a = agg[(name, form, cls, why)]; a[0] += v; a[1] += rsm[k]; a[2].add(int(hp))
for k, a in sorted(agg.items(), key=lambda x: -x[1][0]): P(f'  {k}: {a[0]} body-states in {a[1]} (name,hp) match-entries, max_hp {sorted(a[2])[:8]}')
P('UNRESOLVED (a non-parent body whose class stays the parent card):')
agg = collections.defaultdict(lambda: [0, 0, set()])
for k, v in un.items():
    name, form, hp, cls, why = k.split('|'); a = agg[(name, form, cls, why)]; a[0] += v; a[1] += unm[k]; a[2].add(int(hp))
for k, a in sorted(agg.items(), key=lambda x: -x[1][0]): P(f'  {k}: {a[0]} body-states, {a[1]} match-entries, max_hp {sorted(a[2])[:8]}')
P('max simultaneous model bodies of one enemy class in one state (classes >= 3), matches:')
mx = collections.Counter(); mxv = collections.defaultdict(int)
for m in M:
    for k, v in m['mb_max'].items(): mx[k] += 1; mxv[k] = max(mxv[k], v)
for k, n in mx.most_common(40): P(f'  {k:20s} in {n:3d} matches (max {mxv[k]})')

open(os.path.join(HERE, 'summary.txt'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
