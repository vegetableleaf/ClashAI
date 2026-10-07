"""Live wiring of the L73 decode options (tau_phase, xbow_class) in live_gen_v2.GenPilot -- the pilot live_play.py
loads -- checked against SIM's decide path (e1_eval.live_decide_batch + decision_options.match_kwargs).
Reader frame = test_live_mem.FRAME (probe1.jsonl, side 1) with the icebow deck; side 0 = the same board rotated."""
import copy
from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.dataset_gen import card_key
from pipeline.decision_options import DecisionOptions, match_kwargs
from pipeline.live_gen import GenPilot as LegacyGenPilot
from pipeline.live_mem import deck_of
from pipeline.model_v3 import cell_xy
from pipeline.tests.test_decision_options import two_class_logits
from pipeline.tests.test_live_mem import FRAME

ICEBOW = [26000000, 26000023, 27000006, 28000012, 27000008, 28000003, 26000010, 28000011]
HAND = [0, 4, 5, 2]                    # Knight, Xbow, Rocket, Tesla -> X-Bow at hand position 1
OFF, DEF = (5 * 36 + 9, 5 * 36 + 10), (2000, 2001)    # near the enemy king / deep in my half (lattice)
OPTS = DecisionOptions(tau_phase=(.3, .5, .7), xbow_class='class_sample', xbow_class_floor=.2)


def icebow_frame(tick=2000, side=1, drop_enemy_native_x=None):
    """drop_enemy_native_x: remove the ENEMY princess at this NATIVE x (destroyed tower)."""
    f = copy.deepcopy(FRAME)
    f['game_tick'] = tick
    f['players'][1].update(deck_card_ids=ICEBOW, deck_form_flags=[0] * 8, hand_deck_indices=HAND,
                           next_deck_index=6, cycle_deck_indices=[6, 7, 1, 3], elixir_raw=100000)
    if side == 0:                      # rotate the whole board 180 deg and swap sides: a genuine side-0 frame
        for p in f['players']:
            p['side'] = 1 - p['side']
        for e in f['entities']:
            e.update(side=1 - e['side'], x=18000 - e['x'], y=32000 - e['y'])
    if drop_enemy_native_x is not None:
        f['entities'] = [e for e in f['entities'] if not (e['kind'] == 13 and e['side'] == 1 - side
                                                          and e['x'] == drop_enemy_native_x)]
    return f


class FakeModel:
    def __init__(self, gate_p, card_logits, cell):
        self.gate = torch.logit(torch.tensor([gate_p], dtype=torch.float64)).float()
        self.card, self.cell = torch.tensor([card_logits], dtype=torch.float32), cell

    def __call__(self, b, card=None, form=None):
        if card is not None:
            return {'cell': self.cell[None].clone()}
        return {'gate': self.gate.clone(), 'card': self.card.clone()}


def pilot(options, gate_p=.6, card_logits=(0., 9., 0., 0.), cell=None, seed=0, ext_h=0, cls=live_gen_v2.GenPilot):
    p = object.__new__(cls)
    _, names = deck_of(icebow_frame(), 1)
    p.gid = {card_key(n): i + 1 for i, n in enumerate(names)}
    p.grid, p.dev, p.gate_tau = 'lattice', torch.device('cpu'), .35
    p.past, p.history, p.opp, p.opp_est = [], {}, None, None
    p.ext_h, p.frames = ext_h, deque(maxlen=30)
    p.model = FakeModel(gate_p, list(card_logits), two_class_logits(.4, OFF, DEF)[0] if cell is None else cell)
    p.decision_options, p.public_audit = options, False
    p.rng_decisions = np.random.default_rng(seed)
    return p


CASES = [dict(tick=t, side=s, drop_enemy_native_x=x) for t in (1000, 2600, 3700) for s in (0, 1) for x in (None, 3500)]


@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('gate_p,card_logits', [(.6, (0., 9., 0., 0.)), (.2, (0., 9., 0., 0.)), (.9, (9., 0., 1., 0.))])
def test_live_default_is_byte_identical_to_the_legacy_pilot(case, gate_p, card_logits):
    new = pilot(DecisionOptions(), gate_p, card_logits)
    old = pilot(None, gate_p, card_logits, cls=LegacyGenPilot)
    f = icebow_frame(**case)
    assert new.decide(f) == old.decide(f)
    assert new.rng_decisions.bit_generator.state == np.random.default_rng(0).bit_generator.state


def sim_decide(d, tick, hand_names, options, seed, cell):
    """SIM's decision on the SAME board (the live pilot's BoardState as the prepared match board) and logits."""
    cfg = {k: getattr(options, k) for k in DecisionOptions.__dataclass_fields__}
    match = SimpleNamespace(cfg=dict(cfg, grid='lattice'), tag='t', k=0, deck=SimpleNamespace(cards=hand_names),
                            _cur=(tick, d['bs'], None), rng_decision_options=np.random.default_rng(seed))
    kw = match_kwargs([match])

    class SimModel:
        def cell_logits(self, enc, slot):
            return cell.repeat(len(slot), 1)
    heads = {'card': torch.tensor([[0., 9., 0., 0.]])}
    return E.live_decide_batch(SimModel(), {'g': torch.zeros(1, 2)}, heads, [d['p_play']], np.ones((1, 4), bool),
                               np.zeros(1, bool), tau=.35, decision_options=kw.pop('decision_options'), **kw)[0]


@pytest.mark.parametrize('case', CASES)
def test_live_and_sim_choose_the_same_slot_and_cell_with_options_on(case):
    f = icebow_frame(**case)
    _, names = deck_of(f, case['side'])
    hand_names = [names[i] for i in HAND]
    cell = two_class_logits(.4, OFF, DEF)[0]
    classes = set()
    for seed in range(40):
        d = pilot(OPTS, .6, cell=cell, seed=seed).decide(f)
        s = sim_decide(d, case['tick'], hand_names, OPTS, seed, cell)
        assert (d['play'], d['hand_pos']) == (s['play'], s['slot'])
        if d['play']:
            assert d['xy'] == cell_xy(s['cell'], 'lattice')
            classes.add(s['cell'])
    # p = .6: plays in 1x (.3) and 2x (.5), waits in OT (.7); the near-balanced X-Bow draws both classes
    assert classes == ({OFF[0], DEF[1]} if case['tick'] < 3600 else set())


@pytest.mark.parametrize('tick,ext_h,tau', [(2399, 0, .3), (2400, 0, .5), (3599, 0, .5), (3600, 0, .7),
                                            (2373, 26, .3), (2374, 26, .5), (3574, 26, .7)])
def test_live_phase_boundaries_use_the_model_board_time(tick, ext_h, tau):
    """The phase is that of the board the model sees: bs.t_sec = (tick + extrapolation) * 0.05, as SIM."""
    d = pilot(OPTS, .4, card_logits=(9., 0., 0., 0.), ext_h=ext_h).decide(icebow_frame(tick))
    assert abs(d['bs'].t_sec - (tick + ext_h) * .05) < 1e-9
    assert d['gate_tau'] == tau and d['play'] == (.4 > tau)


@pytest.mark.parametrize('side,drop,alive', [(1, None, (True, True, True)), (1, 3500, (True, True, False)),
                                             (1, 14500, (True, False, True)), (0, None, (True, True, True)),
                                             (0, 3500, (True, False, True)), (0, 14500, (True, True, False))])
def test_live_xbow_class_gets_enemy_towers_in_my_frame_on_both_sides(monkeypatch, side, drop, alive):
    seen = []
    real = live_gen_v2.choose_cells

    def spy(logits, names, options, **kw):
        seen.append((names, options.xbow_class, kw))
        return real(logits, names, options, **kw)
    monkeypatch.setattr(live_gen_v2, 'choose_cells', spy)
    p = pilot(OPTS, .6, seed=3)
    d = p.decide(icebow_frame(1000, side, drop))
    assert d['play'] and d['name'] == 'Xbow'
    (names, mode, kw), = seen
    assert names == ['Xbow'] and mode == 'class_sample'
    assert kw['enemy_alive'] == [alive] and kw['grid'] == 'lattice' and kw['rngs'] == [p.rng_decisions]
    assert tuple(t.alive for t in d['bs'].towers[3:6]) == alive


def test_live_wait_draws_no_rng_and_keeps_the_plain_xbow_argmax():
    p = pilot(OPTS, .2, seed=4)
    before = copy.deepcopy(p.rng_decisions.bit_generator.state)
    d = p.decide(icebow_frame(1000))
    assert not d['play'] and d['name'] == 'Xbow'
    assert d['xy'] == cell_xy(OFF[0], 'lattice')          # plain argmax of the cell logits (class_sample would draw)
    assert p.rng_decisions.bit_generator.state == before
