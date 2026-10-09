"""--gate-hazard-threatened / --gate-hazard-threat-radius: the hazard draw's extra scope (one of MY towers lost HP within
T s, or an enemy unit within R tiles of my alive tower), OR-ed with --gate-hazard-min-elixir. One helper
(decision_options.tower_threat) for SIM match_kwargs and live_gen_v2; off by default = no state, no RNG."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.decision_options import DecisionOptions, hazard_draw, match_kwargs, tower_threat
from pipeline.live_mem import deck_of
from pipeline.tests.test_decision_options import two_class_logits
from pipeline.tests.test_live_decision_options import DEF, HAND, OFF, icebow_frame, pilot

DEPLOYED = DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0)
THREAT = replace(DEPLOYED, gate_hazard_threatened=2.0)
ONLY_THREAT = DecisionOptions(gate_decode='hazard_below_tau', gate_hazard_threatened=2.0)   # no elixir scope
AFFORD_3 = np.array([[True, False, False, False]])     # hand Knight 3, X-Bow 6, Rocket 6, Tesla 4 at 3 elixir


def board(t, my_hp=(1.0, 1.0, 1.0), units=()):
    bs = pilot(DEPLOYED).row(icebow_frame(1000))[1]['bs']
    towers = tuple(replace(tw, hp_frac=h, alive=h > 0) for tw, h in zip(bs.towers[:3], my_hp)) + bs.towers[3:]
    return replace(bs, t_sec=t, towers=towers, units=tuple(units) if units is not None else bs.units)


def test_defaults_off_and_bounds():
    assert DecisionOptions().gate_hazard_threatened == 0 and DecisionOptions().gate_hazard_threat_radius == 0
    assert DEPLOYED == replace(DEPLOYED, gate_hazard_threatened=0.0, gate_hazard_threat_radius=0.0)
    for k in ('gate_hazard_threatened', 'gate_hazard_threat_radius'):
        for bad in (-1.0, float('nan'), float('inf')):
            with pytest.raises(ValueError):
                DecisionOptions(**{k: bad})


def test_tower_threat_window():
    s, thr = tower_threat(THREAT, None, board(10.0))
    assert not thr                                                              # first board: no history
    s, thr = tower_threat(THREAT, s, board(10.5, (1.0, .9, 1.0)))
    assert thr                                                                  # my L princess lost HP
    s2, thr = tower_threat(THREAT, s, board(10.5, (1.0, .9, 1.0)))
    assert thr and s2 == s                                                      # idempotent on a repeated board
    s, thr = tower_threat(THREAT, s, board(12.5, (1.0, .9, 1.0)))
    assert thr                                                                  # 2.0 s after: still in the window
    s, thr = tower_threat(THREAT, s, board(12.6, (1.0, .9, 1.0)))
    assert not thr                                                              # 2.1 s: out
    s, thr = tower_threat(THREAT, s, board(13.0, (1.0, 0.0, 1.0)))
    assert thr                                                                  # destroyed = a drop
    s, thr = tower_threat(THREAT, s, board(13.5, (1.0, 0.0, 1.0)))
    assert thr
    s, thr = tower_threat(THREAT, None, board(1.0))
    s, thr = tower_threat(THREAT, s, board(1.5, (1.0, 1.0, 1.0)))
    assert not thr


def test_enemy_tower_damage_is_not_a_threat():
    bs0 = board(10.0)
    s, _ = tower_threat(THREAT, None, bs0)
    hit = replace(bs0, t_sec=10.5, towers=bs0.towers[:3] + tuple(replace(t, hp_frac=.5) for t in bs0.towers[3:]))
    assert not tower_threat(THREAT, s, hit)[1]


def test_radius_variant():
    opt = replace(DEPLOYED, gate_hazard_threat_radius=4.0)
    u = pilot(DEPLOYED).row(icebow_frame(1000))[1]['bs'].units[0]
    near = replace(u, side=1, x=3.5 / 18, y=0.796875 - 3.9 / 32)               # 3.9 tiles riverward of my L princess
    far = replace(u, side=1, x=3.5 / 18, y=0.796875 - 4.1 / 32)                # 4.1 tiles; > 5 from my king
    mine = replace(near, side=0)
    assert tower_threat(opt, None, board(1.0, units=[near]))[1]
    assert not tower_threat(opt, None, board(1.0, units=[far]))[1]
    assert not tower_threat(opt, None, board(1.0, units=[mine]))[1]
    assert not tower_threat(opt, None, board(1.0, (1.0, 0.0, 1.0), units=[near]))[1]   # that tower is down
    assert not tower_threat(THREAT, None, board(1.0, units=[near]))[1]               # radius off


def test_scope_is_or_with_elixir_and_raises_without_context():
    rng = lambda: np.random.default_rng(0)  # noqa: E731
    # elixir out of scope, not threatened -> False without a draw
    r = rng(); assert not hazard_draw(THREAT, .99, 2.0, r, elixir=3, threatened=False)
    assert r.bit_generator.state == rng().bit_generator.state
    assert hazard_draw(THREAT, .99, 2.0, rng(), elixir=3, threatened=True)      # threatened alone draws
    assert hazard_draw(THREAT, .99, 2.0, rng(), elixir=9.5, threatened=False)   # elixir alone draws (deployed)
    r = rng(); assert not hazard_draw(ONLY_THREAT, .99, 2.0, r, elixir=10, threatened=False)
    assert r.bit_generator.state == rng().bit_generator.state                   # no elixir scope: threat only
    with pytest.raises(ValueError):
        hazard_draw(THREAT, .5, .5, rng(), elixir=3, threatened=None)
    # deployed (threat off): the threatened argument is not read
    assert hazard_draw(DEPLOYED, .99, 2.0, rng(), elixir=3) is False


# ---- live wiring (the real row(): reader frame -> BoardState) ---------------------------------------------------------
def _damage(frame, side, mine, hp):
    """Set the KING tower HP of MY side (``mine``) or the enemy's, native coordinates (observer ``side``)."""
    target = side if mine else 1 - side
    for e in frame['entities']:
        if e['kind'] == 12 and e['side'] == target:
            e['hp'] = hp
    return frame


def _elixir(frame, side, raw=30000):
    next(pl for pl in frame['players'] if pl['side'] == side)['elixir_raw'] = raw   # 3 elixir: below the 9+ scope


def _live_run(options, side, mine, gate_p=.25, seed=0, n=40):
    p = pilot(options, gate_p=gate_p, seed=seed)
    p.match_index, p.decision_seed = -1, 0
    p.reset_match()
    p.rng_decisions = np.random.default_rng(seed)
    out = []
    for i in range(n):
        f = icebow_frame(tick=1000 + 10 * i, side=side)
        _elixir(f, side)                               # 3 elixir: below the 9+ scope
        out.append(p.decide(_damage(f, side, mine, 4000 - 50 * i)))           # HP falls every decision
    return p, out


@pytest.mark.parametrize('side', [0, 1])
def test_live_threat_fires_only_on_my_tower_damage_both_sides(side):
    _, mine = _live_run(THREAT, side, mine=True)
    _, theirs = _live_run(THREAT, side, mine=False)
    assert [d['threatened'] for d in mine] == [False] + [True] * 39
    assert not any(d['threatened'] for d in theirs)
    assert not any(d['play'] for d in theirs)                                 # 3 elixir, p .25 < tau: waits
    plays = sum(any(d['play'] for d in _live_run(THREAT, side, True, seed=s)[1]) for s in range(30))
    assert plays > 0                                                           # the learned rate draws plays


@pytest.mark.parametrize('side', [0, 1])
def test_live_threat_off_is_unchanged_and_reads_nothing(monkeypatch, side):
    def boom(*a, **k):
        raise AssertionError('tower_threat called with the scope off')
    monkeypatch.setattr(live_gen_v2, 'tower_threat', boom)
    p, out = _live_run(DEPLOYED, side, mine=True)
    assert not any(d['play'] for d in out) and not any('threatened' in d for d in out)
    assert p._threat_state is None
    assert p.rng_decisions.bit_generator.state == np.random.default_rng(0).bit_generator.state   # no draw at 3 elixir


def test_live_reset_match_clears_threat_state():
    p, _ = _live_run(THREAT, 1, mine=True, n=3)
    assert p._threat_state is not None
    p.reset_match()
    assert p._threat_state is None


def test_sim_match_kwargs_off_adds_nothing():
    m = SimpleNamespace(cfg={k: getattr(DEPLOYED, k) for k in DecisionOptions.__dataclass_fields__} | dict(
        decide_every=10), tag='t', k=0, deck=SimpleNamespace(cards=['a'] * 8), _cur=(0, board(1.0), None))
    kw = match_kwargs([m])
    assert 'threatened' not in kw and not hasattr(m, 'threat_state')


@pytest.mark.parametrize('side', [0, 1])
def test_sim_and_live_same_threat_and_same_play(side):
    """The live pilot's own decision boards fed to SIM's match_kwargs + live_decide_batch: the same threatened flag at
    every decision, and the same play / slot whenever both accrue the same hazard step (0.5 s, decide_every 10), with
    the SIM match's RNG set to the live RNG's state before the decision."""
    cell = two_class_logits(.4, OFF, DEF)[0]
    _, names = deck_of(icebow_frame(side=side), side)
    hand_names = [names[i] for i in HAND]

    class SimModel:
        def cell_logits(self, enc, slot):
            return cell.repeat(len(slot), 1)
    cfg = {k: getattr(THREAT, k) for k in DecisionOptions.__dataclass_fields__} | dict(grid='lattice', decide_every=10)
    compared = played = 0
    for seed in range(20):
        p = pilot(THREAT, gate_p=.3, seed=seed, cell=cell)
        p.match_index, p.decision_seed = -1, 0
        p.reset_match()
        p.rng_decisions = np.random.default_rng(seed)
        m = SimpleNamespace(cfg=cfg, tag='t', k=0, deck=SimpleNamespace(cards=hand_names))
        for i in range(30):
            f = icebow_frame(tick=1000 + 10 * i, side=side)
            _elixir(f, side)
            state = p.rng_decisions.bit_generator.state
            d = p.decide(_damage(f, side, True, 4000 - (60 * i if i % 7 < 3 else 0)))   # bursts of damage
            m._cur = (1000 + 10 * i, d['bs'], None)
            m.rng_decision_options = np.random.default_rng(0)
            m.rng_decision_options.bit_generator.state = state
            kw = match_kwargs([m])
            assert kw['threatened'] == [d['threatened']]
            if d['hazard_step_s'] != .5:
                continue
            s = E.live_decide_batch(SimModel(), {'g': torch.zeros(1, 2)}, {'card': torch.tensor([[0., 9., 0., 0.]])},
                                    [d['p_play']], AFFORD_3, np.zeros(1, bool), tau=.35,
                                    decision_options=kw.pop('decision_options'), **kw)[0]
            assert (s['play'], s['slot']) == (d['play'], d['hand_pos'])
            compared += 1
            played += d['play']
    assert compared > 100 and played > 0
