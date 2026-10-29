"""ENG-FIX4 planted checks for SME_ZAP_DOT (mech_rules.zap_is_cast curse_level=) on FRESH6 024716@1399 and two real groups
that must stay rejected (laptop, no SIM):   python -I zdot_test.py -> 'ok N'   (MECH_DIR=dir: mech_rules from there)"""
import copy, os, sys
os.environ['SME_ZAP_DOT'] = '1'
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('MECH_DIR') or os.path.dirname(H))
import mech_rules as M  # noqa: E402
L = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_2026%s.jsonl'
G = next(g for g in M.zap_groups(L % '1029_024716') if g['c'] == 1398)
n = 0


def check(name, ok):
    global n
    assert ok, name
    n += 1


def edit(f):
    g = copy.deepcopy(G)
    f(g)
    return g


def hit(g, name):
    return next(h for h in g['hits'].values() if h['name'] == name)


# 1. the real group: two holders (Knight 363, tower 93), both with GoblinCurseDamage -> a Zap with the allowance
check('real group shape', sorted((h['name'], h['drop']) for h in G['hits'].values()) == [('Knight', 363), ('PrincessTower', 93)]
      and not G['electro'])
check('real accepted with curse level 16', M.zap_is_cast(G, 16, 16))
# 2. no allowance without the curse level (flag semantics: the caster's deck has no Goblin Curse) or at a level not tabled
check('no curse level -> rejected (old behaviour)', not M.zap_is_cast(G, 16))
check('curse level 15 not tabled -> rejected', not M.zap_is_cast(G, 16, 15))
# 3. MUST NOT FIRE: the drop is outside the Zap's window after one curse hit (troop window 305..319, tower 76..78)
check('knight 361 (net 304) rejected', not M.zap_is_cast(edit(lambda g: hit(g, 'Knight').update(drop=361)), 16, 16))
check('knight 377 (net 320) rejected', not M.zap_is_cast(edit(lambda g: hit(g, 'Knight').update(drop=377)), 16, 16))
check('tower 95 (net 79) rejected', not M.zap_is_cast(edit(lambda g: hit(g, 'PrincessTower').update(drop=95)), 16, 16))
check('tower 75 (net 59) rejected', not M.zap_is_cast(edit(lambda g: hit(g, 'PrincessTower').update(drop=75)), 16, 16))
check('two curse hits rejected', not M.zap_is_cast(edit(lambda g: hit(g, 'Knight').update(drop=306 + 114)), 16, 16))
# 4. MUST NOT FIRE: the same drops without the curse damage buff
check('no curse buff rejected', not M.zap_is_cast(edit(lambda g: [h.update(buffs=['ZapFreeze']) for h in g['hits'].values()]), 16, 16))
# 5. MUST NOT FIRE: an Electro body near (the existing guard holds under the allowance)
check('electro near rejected', not M.zap_is_cast(edit(lambda g: g.update(electro=[(14500, 24000)])), 16, 16))
# 6. a plain Zap drop on a cursed holder still passes (the allowance is optional, not required)
check('plain drop on cursed holder accepted', M.zap_is_cast(edit(lambda g: (hit(g, 'Knight').update(drop=306),
                                                                           hit(g, 'PrincessTower').update(drop=77))), 16, 16))
# 7. MUST NOT FIRE on real rejected groups no Zap explains (zg_census): FRESH3 133528@3060 (tower 423, the match is exact
#    without a Zap) and FRESH4 235834@4393 (hero Ice Wizard 159), each given a level-16 curse allowance
for m, c in (('1028_133528', 3060), ('1028_235834', 4393)):
    g = next(g for g in M.zap_groups(L % m) if g['c'] == c)
    check('real %s@%d stays rejected' % (m, c), not M.zap_is_cast(g, 16, 16))
print('ok', n)
