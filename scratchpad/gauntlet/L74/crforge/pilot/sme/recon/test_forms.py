"""Planted checks for forms.py (laptop, no engine):  python -I test_forms.py  -> 'ok N' or an AssertionError.
Real-record checks read the git-ignored frozen extractor inputs under .foreman/scratch (skipped, and said so, when absent)."""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import forms  # noqa: E402
import recon  # noqa: E402

tab = recon.Tab()
ru = forms.rules(tab)
need, hero = ru
N = [0]


def ok(cond, what):
    assert cond, what
    N[0] += 1


# ---- tables (16.635.3): the rule's inputs
ok(need['Knight'] == 2 and need['Skeletons'] == 2 and need['Giant'] == 1 and need['MegaKnight'] == 1 and need['Zap'] == 2, 'evolved cost')
ok({'Knight', 'IceWizard', 'MiniPekka', 'BarbLog', 'Tombstone'} <= hero, 'hero rows')
ok('IceWizard' not in need and 'BarbLog' not in need and 'Tesla' in need, 'a card lists only the forms it has')

# ---- the rule (crforge MatchSide.item / count)
ok(forms.predict(7, 1, 2, False) == [0, 0, 1, 0, 0, 1, 0], 'Knight evo slot')
ok(forms.predict(5, 1, 1, False) == [0, 1, 0, 1, 0], 'Giant evo slot')
ok(forms.predict(3, 2, 0, True) == [2, 2, 2], 'hero slot')
ok(forms.predict(3, 0, 2, False) == [0, 0, 0], 'no slot, never evolves')

# ---- a synthetic opponent: deck with a Mirror, Knight in the evolution slot, deal [0,7,1,2 | 3,4,5,6] (Mirror in hand)
DECK = ['Knight', 'Zap', 'Fireball', 'Musketeer', 'HogRider', 'Log', 'Skeletons', 'Mirror']
FLAGS = [1, 0, 0, 0, 0, 0, 0, 0]


def make(seq, deal, flags=FLAGS, deck=DECK):
    """seq: [(deck index, form seen)] one play per 200 ticks from 100 (the bank rule needs the income), side 0 (the opponent); side 1 plays nothing."""
    plays, cmds = [], []
    for i, (d, f) in enumerate(seq):
        R = 100 + 200 * i
        plays.append({'side': 0, 'kind': 'play', 'card': deck[d], 'deck_index': d, 'form': f, 'tick': R, 'run_ticks': [R, R]})
        cmds.append({'kind': 'play', 'given': R - 20, 'run': R, 'side': 0, 'card': deck[d], 'level': 16, 'x': 9000, 'y': 5000,
                     '_src': {'lo': R, 'hi': R, 'tick': R, 'own': False, 'source': 'first_seen'}})
    rec = {'my_side': 1, 'plays': plays, 'sides': {'0': {'deck': deck, 'slot_flags': flags}, '1': {'deck': deck, 'slot_flags': flags}}}
    plan = {'decks': [deck, deck], 'deals': [deal, list(range(8))], 'levels': [[16] * 8, [16] * 8], 'cmds': cmds,
            '_deal_unknown': [True, False], '_cycle_base': [recon.fitting_deal([d for d, _ in seq]) is not None, True],
            '_elixir_base': [True, True]}
    return rec, plan


DEAL = [0, 7, 1, 2, 3, 4, 5, 6]
# real sequence: Knight, Mirror (copies the Knight: a plain Knight body), then 1 2 3 4 5 6 and Knight again twice.
real = [0, 7, 1, 2, 3, 4, 5, 6, 0, 7, 1, 2, 3, 4, 5, 6, 0]
# forms the reader shows: Knight plays are 0 0 1 (count 2 -> third evolved); Mirror copies read as the copied card, plain
shown = []
cnt = 0
for d in real:
    if d == 0:
        f = 1 if cnt >= 2 else 0
        cnt = 0 if f else cnt + 1
        shown.append((0, f))
    elif d == 7:
        shown.append((0, 0))                      # the extractor reads the Mirror's copy as a Knight play: plain
    else:
        shown.append((d, 0))
rec, plan = make(shown, DEAL)
# the extracted sequence has Knight, Knight(copy), ...: the second Knight is not in hand -> cycle fails, forms see a deleted play
ok(not plan['_cycle_base'][0], 'planted Mirror read breaks the cycle')
res = forms.analyse(rec, 0, tab, ru)
ok(res['Knight'][0] >= 1, 'planted Mirror read detected by the form rule')
vs = forms.form_repairs(rec, plan, 0, tab, 5.99, ru)
ok(vs, 'a repair exists')
mir = [v for v in vs if v[0].startswith('formmirror')]
ok(mir, 'the Mirror reading is proposed (previous play is the same card)')
ticks = {int(t) for v in mir for t in v[0].split(' R')[-1].split(',')}
ok(ticks & {300, 1900}, 'the Mirror copies (R300 / R1900) are among the proposed readings')
v = mir[0][2]
ok(any(c['card'] == 'Mirror' for c in v['cmds']) and recon.cycle_ok(v, 0), 'the repaired plan fits a deal and carries the Mirror')
ok(forms.plan_cost(rec, plan, 0, tab, ru).get('Knight', 0) >= 1, 'base plan carries a form cost')
# the repaired plan's FORMS: Mirror play is no longer a Knight play -> alignment cost 0 for the plan
rec2 = rec
ok(forms.plan_cost(rec2, v, 0, tab, ru) == {}, 'the Mirror repair explains every observed form (cost 0)')
# a deck WITHOUT a Mirror: only drops are proposed
DECK_NM = list(DECK)
DECK_NM[7] = 'Cannon'
rec_n, plan_n = make([(d if d != 7 else 0, f) for d, f in shown], DEAL, deck=DECK_NM)
ok(not [x for x in forms.form_repairs(rec_n, plan_n, 0, tab, 5.99, ru) if x[0].startswith('formmirror')], 'no Mirror in the deck, no Mirror reading')

# ---- clean sequence: nothing to repair
clean = [(d, 0) for d in [1, 2, 3, 4, 5, 6, 0, 1]]
rec_c, plan_c = make(clean, [1, 2, 3, 4, 5, 6, 0, 7])
ok(forms.form_repairs(rec_c, plan_c, 0, tab, 5.99, ru) == [], 'a clean record has no form repair')
# own side (deal known) is never repaired by deletion
ok(forms.form_repairs(rec_c, plan_c, 1, tab, 5.99, ru) == [], 'the known-deal side is not repaired')

# ---- planted wrong form on a clean sequence is detected (card has plays 0, 0, 1; flip each)
for flip in range(3):
    f3 = [0, 0, 1]
    f3[flip] = 1 - f3[flip]
    rr, pp = make([(0, f3[0]), (1, 0), (2, 0), (3, 0), (0, f3[1]), (1, 0), (2, 0), (3, 0), (0, f3[2])], [0, 1, 2, 3, 4, 5, 6, 7])
    ok(forms.analyse(rr, 0, tab, ru)['Knight'][0] >= 1, 'flipped form %d detected' % flip)
rr, pp = make([(0, 0), (1, 0), (2, 0), (3, 0), (0, 0), (1, 0), (2, 0), (3, 0), (0, 1)], [0, 1, 2, 3, 4, 5, 6, 7])
ok(forms.analyse(rr, 0, tab, ru)['Knight'][0] == 0, 'the unflipped record is clean')

# ---- real records (frozen extractor inputs): the rule reproduces the observed forms, a planted flip is caught, own taps corroborate
S = '/c/Users/benpe/ClashBot/.foreman/scratch'.replace('/c/', 'C:/', 1)
files = sorted(glob.glob(S + '/recon2/off/f*.jsonl')) + [S + '/recon4/f9/off/inputs_all.jsonl', S + '/recon5/f10/off/inputs_all.jsonl']
if all(os.path.exists(f) for f in files):
    seqs = clean_n = flips = caught = 0
    for fn in files:
        for line in open(fn):
            r = json.loads(line)
            for side in (0, 1):
                for card, (cost, alts, n, ranks) in forms.analyse(r, side, tab, ru).items():
                    seqs += 1
                    clean_n += cost == 0
                    if cost == 0 and n >= 2 and not tab.is_spell(card):
                        # plant: flip one observed form of this card's plays, re-run the alignment on the planted record
                        sd = r['sides'][str(side)]
                        pl = forms.side_plays(r['plays'], sd['deck'], side)
                        mine = [p for _, p in pl if p['card'] == card]
                        for j in range(len(mine)):
                            old = mine[j].get('form', 0)
                            mine[j]['form'] = 1 - old if old in (0, 1) else 0
                            c2 = forms.analyse(r, side, tab, ru)[card][0]
                            mine[j]['form'] = old
                            flips += 1
                            caught += c2 >= 1
    ok(seqs > 2500 and clean_n / seqs >= 0.995, 'real: %d / %d sequences explained' % (clean_n, seqs))
    ok(caught / flips >= 0.97, 'real: planted flips caught %d / %d' % (caught, flips))
    print('real-record check: %d / %d (side, card) sequences cost 0; planted flips caught %d / %d' % (clean_n, seqs, caught, flips))
else:
    print('real-record checks SKIPPED (frozen inputs absent)')
print('ok', N[0])
