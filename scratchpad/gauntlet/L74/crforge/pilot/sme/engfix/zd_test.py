"""ENG-FIX3 planted checks for SME_ZAP_DEAD (mech_rules.zap_dead) on FRESH5 021310@1986 (laptop, no SIM):
    python -I zd_test.py   -> 'ok N' or an AssertionError naming the plant."""
import copy, json, os, sys
os.environ['SME_ZAP_DEAD'] = '1'
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(H))
import mech_rules  # noqa: E402
R = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/'
T = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
x = next(json.loads(l) for l in open(H + '/fresh5/inputs_all.jsonl') if '021310' in l)
sides = {int(k): v for k, v in x['sides'].items()}
FR = mech_rules.zd_frames(R + 'L68/live_reader/live_play_20261029_021310.jsonl')
ti = next(i for i, f in enumerate(FR) if f[0] == 1984)
VIC = [a for a, b in FR[ti][1].items() if b['name'] == 'Skeleton']
n = 0


def run(fr=FR, plays=x['plays'], sd=sides):
    return mech_rules.zap_dead(fr, plays, sd, T)


def fires(fr=FR, plays=x['plays'], sd=sides):
    return [e for e in run(fr, plays, sd)[1] if e['tp'] == 1984]


def check(name, ok):
    global n
    assert ok, name
    n += 1


def edit(f):
    fr = copy.deepcopy(FR)
    f(fr)
    return fr


# 1. the real case fires once, at R 1985, window [1984, 1985], one side-0 Zap whose point reaches all 3 victims only
e = fires()
check('real fires', len(e) == 1 and e[0]['R'] == 1985 and e[0]['run_ticks'] == [1984, 1985] and len(e[0]['victims']) == 3)
p = [q for q in run()[0] if q.get('mech') == 'zap_dead']
check('one Zap play added', len(p) == 1 and p[0]['side'] == 0 and p[0]['card'] == 'Zap' and p[0]['tick'] == 1985)
check('only firing in the match', len(run()[1]) == 1)
# 2. no Zap in the opponent's deck
sd = copy.deepcopy(sides)
sd[0]['deck'] = [c if c != 'Zap' else 'Arrows' for c in sd[0]['deck']]
check('no Zap in deck', not fires(sd=sd))
# 3. victims above the Zap's damage (only one left <= 306: below ZD_MIN)
check('hp above Zap damage', not fires(edit(lambda fr: [fr[ti][1][a].update(hp=400) for a in VIC[:2]])))
# 4. a victim relisted on the next frame (a reader flicker)
e = fires(edit(lambda fr: fr[ti + 2][1].update({VIC[0]: dict(FR[ti][1][VIC[0]])})))
check('one relisted: 2 victims left', len(e) == 1 and len(e[0]['victims']) == 2)
check('two relisted', not fires(edit(lambda fr: fr[ti + 2][1].update({a: dict(FR[ti][1][a]) for a in VIC[:2]}))))
# 5. an opponent projectile aimed near a victim
check('enemy projectile', not fires(edit(lambda fr: fr[ti][2].append([0, 12000, 17000, -1, 13098, 16861]))))
# 6. an opponent area near a victim
check('enemy area', not fires(edit(lambda fr: fr[ti][3].append([0, 12500, 17000, 28000008]))))
# 7. the Mega Knight targets a victim
mk = next(a for a, b in FR[ti][1].items() if b['name'] == 'MegaKnight')
check('enemy targets victim', not fires(edit(lambda fr: fr[ti][1][mk].update(tgt=FR[ti][1][VIC[0]]['gen']))))
# 8. the Mega Knight moving (a dash) over the gap
check('enemy body moving', not fires(edit(lambda fr: fr[ti + 1][1][mk].update(x=FR[ti][1][mk]['x'] + 400))))
# 9. a Valkyrie (self-centred splash) next to the victims
check('enemy splash', not fires(edit(lambda fr: fr[ti][1].update(vk=dict(side=0, x=12800, y=17300, hp=1000, tower=False,
                                                                        name='Valkyrie', gen=1, tgt=None)))))
# 10. an opponent play in the 20 ticks before
check('opp play', not fires(plays=x['plays'] + [dict(side=0, kind='play', card='Bats', tick=1975, x=1000, y=1000)]))
# 11. a living side-1 body (unchanged hp) at the victims' centroid: no point reaches the victims and misses it
check('own body in reach', not fires(edit(lambda fr: [f[1].update(own=dict(side=1, x=12833, y=17272, hp=900, tower=False,
                                                                           name='Knight', gen=2, tgt=None)) for f in fr[ti:ti + 2]])))
# 12. a kamikaze victim (it may leave by itself)
check('kamikaze victim', not fires(edit(lambda fr: fr[ti][1][VIC[0]].update(name='IceSpirits'))))
print('ok', n)
