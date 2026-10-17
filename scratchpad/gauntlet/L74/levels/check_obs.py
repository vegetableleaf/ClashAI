"""What changes for the MODEL when levels change (factor D; pod, ROYALE_RUNTIME=fork36-linux, ROYALE_HEROIW_FORM=hero):

    python scratchpad/gauntlet/L74/levels/check_obs.py CKPT [N_DECKS]

1. Identity (the token's cls / form) of the SAME play at level 11 vs at live levels: per card of icebow (side 0) and of
   the first N_DECKS eval decks (side 1, the opponent), the card in the opening hand, played at a fixed spot at tick 200;
   the learner's BoardState (e1_eval's own from_engine call: sim_compact, deck, engine_deck, feature_version) 30 and 100
   ticks later. Levels B: (card 16, tower 15), (card 14, tower 16), (card 15, tower 15) for the opponent (ours: the table).
   Reports every (card, condition) whose enemy / own (cls, form) multiset differs from level 11, and hp_frac bounds.
2. Model inputs carrying ABSOLUTE hp: the policy tokens (obs_contract.to_tokens) hold hp_frac only; the ability-head
   features (royale_env._ability_features: enemy hp sums within 3 / 5 tiles / 2000) scale with the level multiplier.
3. Real self-play matches (CKPT both sides, live condition) at level 11 vs live levels: unmapped names, degraded obs.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

from pipeline.royale_runtime import activate

activate()
import numpy as np  # noqa: E402
from pipeline import e1_eval as E  # noqa: E402
from pipeline.obs_contract import from_engine, to_tokens  # noqa: E402
from pipeline.rl_royale import REPO, card_level, draw_live_levels, live_levels  # noqa: E402
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from pipeline.search_s0 import live_cfg  # noqa: E402

CK = sys.argv[1]
ND = int(sys.argv[2]) if len(sys.argv) > 2 else 40
T = live_levels({'league': True, 'live_levels': True})
model, info = E.load_policy(REPO / CK, 'cpu')
fv = E.policy_feature_version(model)
print('checkpoint', CK, 'feature_version', fv, 'grid', info['grid'])
ICE = list(E.ICEBOW_ENGINE_DECK)
DECKS = [d['engine'] for d in json.loads((REPO / 'scratchpad/gauntlet/L74/mix/decks_live_eval.json').read_text())['decks']][:ND]
env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode='deck', hero_abilities=True, ability_policy='v2')
base = lambda n: str(n).split('@')[0]
cfg = {**live_cfg(0.35, info['grid']), 'entry_index': 0}
own_lv = [card_level(base(n), T['own']['cards'].get(base(n), T['own']['default'])) for n in ICE]


def seed_with(card, side, names):
    for s in range(1000):
        order = list(range(8))
        random.Random(f'deal:{s}:{side}').shuffle(order)
        if [base(n) for n in names].index(card) in order[:4]:
            return s
    raise ValueError(card)


def board(m, side_obj):
    raw = env.raw()
    unm = set()
    bs = from_engine(E.sim_compact(side_obj, raw), side_obj.side, side_obj.deck, engine_deck=side_obj.engine_deck,
                     unmapped=unm, feature_version=side_obj.feature_version)
    tok, mask, sc = to_tokens(bs)
    hp = tok[mask][:, 6][tok[mask][:, 7] > 0]
    return bs, unm, (float(hp.min()) if len(hp) else None, float(hp.max()) if len(hp) else None)


def play(opp_deck, card, side, levels):
    names = (ICE, opp_deck)[side]
    spec = {'tag': f'obs:{card}', 'opp': {'id': 'gen'}, 'learner_deck': ICE, 'opp_deck': opp_deck, 'learner_side': 0,
            'seed': seed_with(card, side, names)}
    if levels is not None:
        spec['levels'] = levels
    m = E.SelfPlayMatch(env, spec, 0, dict(cfg), dict(cfg), model, model)
    env.advance_to(200)
    r = env.eng.act(side=side, deck_index=[base(n) for n in names].index(card), x=9000, y=9000 if side == 0 else 23000)
    out = []
    for dt in (30, 70):
        env.advance_to(env.tick + dt)
        bs, unm, hpb = board(m, m.learner)
        out.append((Counter((u.side, u.cls, u.form) for u in bs.units), sorted(unm), hpb))
    return r['accepted'], out


diff, n_cmp, hp_bad, unm_all, refused = [], 0, [], Counter(), Counter()
conds = [(16, 15), (14, 16), (15, 15)]
cases = [(None, c, 0) for c in [base(n) for n in ICE]] + [(d, base(c), 1) for d in DECKS for c in d]
done = set()
for d, card, side in cases:
    if (card, side) in done:
        continue
    done.add((card, side))
    opp = d or DECKS[0]
    acc0, ref = play(opp, card, side, None)
    for cl, tl in ([(None, None)] if side == 0 else conds):
        if side == 0:
            lv = {'learner': {'cards': own_lv, 'tower': 15}, 'opp': {'cards': [15] * 8, 'tower': 15, 'profile': -1}}
            tag = f'own table level {own_lv[[base(n) for n in ICE].index(card)]}, tower 15'
        else:
            lv = {'learner': {'cards': own_lv, 'tower': 15},
                  'opp': {'cards': [card_level(base(n), cl) for n in opp], 'tower': tl, 'profile': -1}}
            tag = f'card {cl}, tower {tl}'
        acc, got = play(opp, card, side, lv)
        if not (acc and acc0):
            refused[card] += 1
            continue
        for (ca, ua, _), (cb, ub, hb) in zip(ref, got):
            n_cmp += 1
            unm_all.update(ub)
            if hb[0] is not None and not (0.0 <= hb[0] <= hb[1] <= 1.0):
                hp_bad.append((card, tag, hb))
            if ca != cb:
                diff.append((card, 'opp' if side else 'own', tag, dict(ca - cb), dict(cb - ca)))
print(f'1. identity: {n_cmp} board pairs (L11 vs live levels) over {len(done)} cards; differing: {len(diff)}; '
      f'refused plays (skipped) {dict(refused)}; hp_frac outside [0, 1]: {hp_bad[:5]}; unmapped at live levels {dict(unm_all)}')
for x in diff[:40]:
    print('   DIFF', x)
cards = json.loads((REPO / 'research/ext/Royale/RoyaleSim/data/derived/cards.json').read_text(encoding='utf-8'))['cards']
mult = cards[0]['level_scaling']['multiplier_percent_by_level']
print('2. absolute-hp inputs: level multiplier vs level 11 =', {lv: round(mult[lv - 1] / mult[10], 3) for lv in (13, 14, 15, 16)},
      '-> ability-head hp sums x that factor; policy tokens: hp_frac only (level-free)')

# 3. real matches
res = {}
for name, on in (('L11', False), ('live', True)):
    rows = []
    jobs = []
    for i, d in enumerate(DECKS[:8]):
        sp = {'tag': f'obs_real:{i}', 'opp': {'id': 'gen'}, 'learner_deck': ICE, 'opp_deck': d, 'learner_side': i % 2,
              'seed': 900 + i}
        if on:
            sp['levels'] = draw_live_levels(T, ICE, d, f'{900 + i}:obs')
        jobs.append((i, sp, 0))
    E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(decision_ticks=10, forms_mode='deck', hero_abilities=True,
                                                   ability_policy='v2'),
                         model, {'gen': (model, dict(cfg))}, jobs, dict(cfg), 4, rows.append)
    res[name] = rows
    print(f"3. {name}: {len(rows)} matches; unmapped {Counter(u for r in rows for u in r['unmapped'])}; degraded_obs "
          f"{sum(r['degraded_obs'] for r in rows)} of {sum(r['decisions'] for r in rows)} decisions; outcomes "
          f"{Counter(r['outcome'] for r in rows)}; plays {np.mean([r['plays_accepted'] for r in rows]):.1f}/match")
