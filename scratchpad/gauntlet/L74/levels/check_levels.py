"""Pod checks for factor D live levels (ROYALE_RUNTIME=fork36-linux, ROYALE_HEROIW_FORM=hero; PYTHONPATH=checkout):

    python scratchpad/gauntlet/L74/levels/check_levels.py

1. RoyaleSelfPlayEnv.reset(levels=...): the MatchSetup's levels follow the deal (every deck card keeps its level), the
   towers read the asked levels (own 4424 / 7032 = live), a played card's body has unit_hitpoints(card, its level), a
   later reset without levels is back to level 11; the opening hand is env.deal[side][:4].
2. Every card of every eval / training deck loads at its lowest and highest catalog level (card_level's range) and at a
   draw, both sides; the Hero Ice Wizard loads at level 14 with base IceWizard's level-14 hit points.
3. draw_live_levels: 20,000 keys -> opponent tower levels match the table's, card levels match its card readings, the
   same key draws the same levels, our side always the table's own levels.
Exit 1 on any failure."""
import json
import random
import sys
from collections import Counter

from pipeline.royale_runtime import activate

activate()
from pipeline import e1_eval as E  # noqa: E402
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from pipeline.rl_royale import REPO, card_level, draw_live_levels, league_decks, live_levels  # noqa: E402

ok = True


def check(cond, msg):
    global ok
    print(('PASS ' if cond else 'FAIL ') + msg, flush=True)
    ok &= bool(cond)


T = live_levels({'league': True, 'live_levels': True})
ICE = list(E.ICEBOW_ENGINE_DECK)
DECKS = [d['engine'] for d in league_decks(REPO / 'icebow/data/rltest/decks_rl.json')]
DECKS += [d['engine'] for d in json.loads((REPO / 'scratchpad/gauntlet/L74/mix/decks_live_eval.json').read_text())['decks']]
env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode='deck', hero_abilities=True, ability_policy='v2')
seen = []
real_reset = env.core.reset
env.core.reset = lambda seed, setup: (seen.append(setup), real_reset(seed, setup))[1]
base = lambda n: str(n).split('@')[0]


def uhp(name, level):
    """unit_hitpoints rows of card ``name`` at ``level`` ([] for a spell / no unit)."""
    try:
        return env.core._battle.unit_hitpoints(env.ids[name], int(level)) or []
    except ValueError:
        return []


def seed_with(card, side, deck_names):
    """A seed whose deal puts ``card`` in ``side``'s opening hand (RoyaleSelfPlayEnv.reset's shuffle)."""
    for s in range(1000):
        order = list(range(8))
        random.Random(f'deal:{s}:{side}').shuffle(order)
        if [base(n) for n in deck_names].index(card) in order[:4]:
            return s
    raise ValueError(card)


def towers(raw):
    return {s: sorted(t['max_hp'] for t in raw['episode']['crown_towers'] if t['side'] == s) for s in (0, 1)}


# 1. one match's levels
OPP = DECKS[0]
lv = draw_live_levels(T, ICE, OPP, '5:check')
print('draw', lv)
kw = {'cards': [lv['learner']['cards'], lv['opp']['cards']], 'towers': [lv['learner']['tower'], lv['opp']['tower']]}
raw = env.reset(ICE, OPP, 5, levels=kw)
st = seen[-1]
want = {s: dict(zip([base(n) for n in (ICE, OPP)[s]], kw['cards'][s])) for s in (0, 1)}
got = {s: {env.names[c]: l for c, l in zip(st.decks[s], st.levels[s])} for s in (0, 1)}
check(got == want, f'MatchSetup levels follow the deal: {got}')
check(towers(raw)[0] == [4424, 4424, 7032], f'our towers = live L15 (4424 / 7032): {towers(raw)[0]}')
print('opp towers', towers(raw)[1], 'level', lv['opp']['tower'])
hand0 = [h['name'] for h in raw['players'][0]['hand']]
check(sorted(hand0) == sorted(base(n) for n in env.deal[0][:4]), f'opening hand = deal[:4]: {hand0} / {env.deal[0][:4]}')
env.advance_to(250)
for side, y in ((0, 9000), (1, 23000)):
    hand = [h['name'] for h in env.raw()['players'][side]['hand']]
    troop = next((n for n in hand if uhp(n, 11)), None)
    if troop is None:
        print('side', side, 'no troop in hand', hand)
        continue
    r = env.eng.act(side=side, deck_index=env.decks[side].index(troop), x=9000, y=y)
    env.advance_to(env.tick + 25)
    hp = sorted({e['max_hp'] for e in env.raw()['entities'] if e['side'] == side and e['name'] == troop})
    exp = uhp(troop, want[side][troop])[0][2]
    check(r['accepted'] and exp in hp, f'side {side} {troop} at level {want[side][troop]}: body max_hp {hp} has {exp}')
raw = env.reset(ICE, OPP, 5)
check(seen[-1].levels is None and towers(raw)[0] == [3052, 3052, 4824] and towers(raw)[1] == [3052, 3052, 4824],
      f'a later reset without levels is back to level 11: {towers(raw)}')

# 2. every deck card loads at its range ends and at a draw
bad = []
for i, d in enumerate(DECKS):
    for mode in ('lo', 'hi', 'draw'):
        if mode == 'draw':
            x = draw_live_levels(T, ICE, d, f'{i}:range')
            cards = [x['learner']['cards'], x['opp']['cards']]
        else:
            cards = [[card_level(base(n), 1 if mode == 'lo' else 99) for n in dk] for dk in (ICE, d)]
        try:
            env.reset(ICE, d, i, levels={'cards': cards, 'towers': [15, 16]})
            env.reset(d, ICE, i, levels={'cards': cards[::-1], 'towers': [16, 15]})
        except Exception as exc:           # noqa: BLE001 -- report every refusal
            bad.append((i, mode, d, repr(exc)[:200]))
check(not bad, f'{len(DECKS)} decks x (lo, hi, draw) x both sides load; refused: {bad[:5]}')
iw_cards = [card_level(base(n), T['own']['cards'].get(base(n), 16)) for n in ICE]
env.reset(ICE, OPP, seed_with('IceWizard', 0, ICE), levels={'cards': [iw_cards, [15] * 8], 'towers': [15, 15]})
print('loaded forms side 0', env.loaded_forms[0], '; IceWizard form', env.loaded_forms[0][ICE.index('IceWizard')],
      'level', iw_cards[ICE.index('IceWizard')])
env.advance_to(160)
r = env.eng.act(side=0, deck_index=ICE.index('IceWizard'), x=9000, y=9000)
env.advance_to(env.tick + 25)
iw = sorted({(e['max_hp'], e.get('public_form'), e.get('unit_name')) for e in env.raw()['entities']
             if e['side'] == 0 and e['name'] == 'IceWizard'})
iw14 = uhp('IceWizard', 14)[0][2]
check(r['accepted'] and any(h == iw14 for h, _, _ in iw),
      f'Hero Ice Wizard at level 14: bodies {iw}, base IceWizard L14 max_hp {iw14}')

# 3. draws
N = 20000
draws = [draw_live_levels(T, ICE, DECKS[k % len(DECKS)], f'{k}:d') for k in range(N)]
tw = Counter(x['opp']['tower'] for x in draws)
tab = Counter(p[1] for p in T['opp_profiles'])
n = len(T['opp_profiles'])
print('opp tower draws', {k: round(v / N, 4) for k, v in sorted(tw.items())}, 'table', {k: round(v / n, 4) for k, v in sorted(tab.items())})
check(all(abs(tw[k] / N - v / n) < 0.012 for k, v in tab.items()), 'opponent tower level frequencies match the table (1.2 pp)')
cl = Counter(c for x in draws for c in x['opp']['cards'])
m = sum(cl.values())
print('opp card-level draws', {k: round(v / m, 4) for k, v in sorted(cl.items())})
check(len({json.dumps(draw_live_levels(T, ICE, OPP, 'same')) for _ in range(20)}) == 1, 'same key, same levels')
check(all(x['learner'] == draws[0]['learner'] for x in draws), f"our side always {draws[0]['learner']}")
random.seed(0)
sys.exit(0 if ok else 1)
