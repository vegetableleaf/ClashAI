"""OPT-IN live anti-leak (live_play.py --anti-leak): GenPilot computes ``stalled`` with e1_eval.anti_stall and plays
through a waiting gate exactly as SIM's decide does.
(a) off = main's (BASE) decisions on a recorded reader stream (real checkpoint); (b) the 9-elixir / 12.0-s threshold;
(c) parity with e1_eval.live_decide(_batch) given stalled=True on the same rows (real checkpoint, options off / on);
(d) a forced play still lands on a legal cell."""
import copy
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.decision_options import DecisionOptions, match_kwargs
from pipeline.live_gen import legal_cells
from pipeline.live_mem import deck_of, my_side_of
from pipeline.model_v3 import cell_xy
from pipeline.tests.test_live_decision_options import HAND, OFF, OPTS, icebow_frame, pilot

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path(subprocess.check_output(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                    cwd=ROOT, text=True).strip()).parent       # icebow/data lives in the main checkout
CKPT = MAIN / 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt'      # live CKPT_OVERRIDE 10-08
RECORDING = MAIN / 'scratchpad/gauntlet/L70/reader/sidebyside/re_v2xb.jsonl'          # raw v2 reader stream, 995 frames
BASE = 'cea8be8'                      # main before the anti-leak re-add: the "off == today" oracle
real = pytest.mark.skipif(not (CKPT.is_file() and RECORDING.is_file()), reason='live checkpoint / recording absent')
torch.set_num_threads(4)


def head(name, patch=()):
    key = 'pipeline._antileak_head_' + name
    if key not in sys.modules:
        mod = types.ModuleType(key)
        mod.__package__, mod.__file__ = 'pipeline', str(ROOT / 'pipeline' / f'{name}.py')
        src = subprocess.check_output(['git', 'show', f'{BASE}:pipeline/{name}.py'], cwd=ROOT, text=True)
        for a, b in patch:
            src = src.replace(a, b)
        sys.modules[key] = mod
        exec(compile(src, mod.__file__, 'exec'), mod.__dict__)
    return sys.modules[key]


def head_pilot_cls():
    head('live_gen')
    return head('live_gen_v2', [('from .live_gen import', 'from ._antileak_head_live_gen import')]).GenPilot


def frames(limit=None):
    """live_play.py's feed: active + coherent, one hand visible; decide only when the clock advanced."""
    last, n = -1, 0
    for line in RECORDING.open():
        f = json.loads(line)
        if not (f.get('battle_active') and f.get('coherent')):
            continue
        if sum(any(i >= 0 for i in p['hand_deck_indices']) for p in f['players']) != 1:
            continue
        advanced = int(f['game_tick']) > last
        last = max(last, int(f['game_tick']))
        yield f, advanced
        n += advanced
        if limit and n >= limit:
            return


def live_pilot(cls, options=DecisionOptions(), anti_leak=False):
    p = cls(str(CKPT), device='cpu', gate_tau=.35, use_counter=True, extrapolate_ticks=26, decision_options=options)
    p.legal_guard = True                                  # live_play's default
    if anti_leak:
        p.anti_leak_elixir, p.anti_leak_seconds = 9.0, 12.0
    return p


KEYS = ('play', 'p_play', 'no_affordable', 'hand_pos', 'deck_index', 'card', 'form', 'name', 'xy', 'xy_unguarded',
        'gate_tau', 'el_int')


# ---------------------------------------------------------------------------------------------------------- (a)
@real
@pytest.mark.parametrize('options', [DecisionOptions(), OPTS], ids=['default', 'tau_phase+xbow_class'])
def test_off_is_identical_to_main_on_a_recorded_stream(options):
    old, new = live_pilot(head_pilot_cls(), options), live_pilot(live_gen_v2.GenPilot, options)
    assert new.anti_leak_elixir is None
    n = plays = 0
    for f, advanced in frames():
        old.observe(f)
        new.observe(f)
        if not advanced:
            continue
        a, b = old.decide(f), new.decide(f)
        assert b.pop('stalled') is False
        assert {k: a.get(k) for k in KEYS} == {k: b.get(k) for k in KEYS}
        n, plays = n + 1, plays + a['play']
    assert old.rng_decisions.bit_generator.state == new.rng_decisions.bit_generator.state
    assert n > 900 and 0 < plays < n                      # both branches exercised


# ---------------------------------------------------------------------------------------------------------- (b)
def stall_pilot(gate_p=.2, ext_h=0):
    p = pilot(DecisionOptions(), gate_p, card_logits=(9., 0., 0., 0.), ext_h=ext_h)
    p.anti_leak_elixir, p.anti_leak_seconds = 9.0, 12.0
    p.match_index, p.decision_seed, p.drops = -1, 0, None    # reset_match's fields (helper skips __init__)
    return p


def at(tick, elixir):
    f = icebow_frame(tick)
    f['players'][1]['elixir_raw'] = int(round(elixir * 1e4))
    return f


@pytest.mark.parametrize('dt_ticks,elixir,stalled', [(240, 9.0, True), (238, 9.0, False), (240, 8.5, False),
                                                     (400, 10.0, True), (400, 8.99, False)])
def test_threshold_after_a_confirmed_play(dt_ticks, elixir, stalled):
    p = stall_pilot()
    p.record_play(1, 0, (.5, .8), 1000 * .05)              # live_play: the CONFIRMATION frame's tick * 0.05
    d = p.decide(at(1000 + dt_ticks, elixir))
    assert d['stalled'] is stalled and d['play'] is stalled  # gate .2 <= tau .35: only the anti-leak plays
    if stalled:
        assert d['name'] == 'Knight' and d['xy'] is not None


def test_clock_starts_at_the_first_decision_and_off_never_stalls():
    p = stall_pilot()
    assert not p.decide(at(1000, 10.0))['play']            # first decision: starts the clock
    assert not p.decide(at(1239, 10.0))['play']            # 11.95 s
    assert p.decide(at(1240, 10.0))['play']                # 12.0 s
    p.reset_match()
    assert not p.decide(at(5000, 10.0))['play']            # a new match restarts the clock
    off = pilot(DecisionOptions(), .2, card_logits=(9., 0., 0., 0.))
    off.decide(at(1000, 10.0))
    assert not off.decide(at(3000, 10.0))['play'] and off.decide(at(3000, 10.0))['stalled'] is False


def test_stall_elixir_is_the_extrapolated_board_elixir_and_the_clock_the_real_tick():
    """SIM: anti-stall elixir at tick + H, the clock tick real (e1_eval module notes)."""
    on, off = stall_pilot(ext_h=26), stall_pilot(ext_h=0)
    for p in (on, off):
        p.record_play(1, 0, (.5, .8), 1000 * .05)
    assert on.decide(at(1240, 8.6))['stalled'] and not off.decide(at(1240, 8.6))['stalled']
    assert not stall_pilot(ext_h=26).decide(at(1000, 10.0))['stalled']   # +26 ticks of look-ahead never ages the clock


# ---------------------------------------------------------------------------------------------------------- (c)
def sim_decision(pilot_, b, info, frame, stalled, options, seed):
    """SIM's decide on the SAME row: GenPolicy deck-slot heads -> e1_eval.live_decide (options off) or
    live_decide_batch + decision_options.match_kwargs (options on), as Match.decide_row."""
    _, names = deck_of(frame, my_side_of(frame))
    hd = info['hand_deck_indices']
    from pipeline.dataset_gen import card_key
    me = next(p for p in frame['players'] if int(p['side']) == my_side_of(frame))
    forms = me.get('deck_form_flags') or [0] * 8
    slot_card = np.array([pilot_.gid[card_key(n)] for n in names] + [0], np.int64)   # [9]: deck slots + pad
    slot_form = np.array([int(v) for v in forms] + [3], np.int64)
    assert [(int(slot_card[d]), int(slot_form[d])) for d in hd if d >= 0] == [h for h in info['hand'] if h[0] > 0]
    bb = dict(b, hand_slot=torch.tensor([[d if d >= 0 else 8 for d in hd]]),
              slot_card=torch.from_numpy(slot_card)[None], slot_form=torch.from_numpy(slot_form)[None])
    gp = E.GenPolicy(pilot_.model, list(pilot_.gid))
    with torch.no_grad():
        enc, heads = gp.heads_t(bb)
        p = float(torch.sigmoid(heads['gate'])[0])
    pos_ok = E.allowed_slots(np.array([h[0] > 0 for h in info['hand']]), info['costs'], info['el_int'])
    allowed = np.zeros(8, bool)
    for pos, d in enumerate(hd):
        allowed[d] = d >= 0 and pos_ok[pos]
    if not options.active:
        return E.live_decide(gp, enc, heads, p, allowed, tau=pilot_.gate_tau, stalled=stalled), p
    cfg = {k: getattr(options, k) for k in DecisionOptions.__dataclass_fields__}
    from types import SimpleNamespace
    match = SimpleNamespace(cfg=dict(cfg, grid='lattice'), tag='t', k=0, deck=SimpleNamespace(cards=list(names)),
                            _cur=(int(frame['game_tick']), info['bs'], None),
                            rng_decision_options=np.random.default_rng(seed))
    kw = match_kwargs([match])
    return E.live_decide_batch(gp, enc, heads, [p], allowed[None], np.array([stalled]), tau=pilot_.gate_tau,
                               decision_options=kw.pop('decision_options'), **kw)[0], p


@real
@pytest.mark.parametrize('options', [DecisionOptions(), OPTS], ids=['default', 'tau_phase+xbow_class'])
def test_forced_play_matches_sim_card_and_cell(options):
    """Every recorded decision with stalled forced True: the live pilot and SIM pick the same card (deck slot) and
    cell; the forced plays (gate below tau) are the cases this exists for. Guard off = SIM has no guard."""
    pl = live_pilot(live_gen_v2.GenPilot, options, anti_leak=True)
    pl.legal_guard = False
    pl.stalled = lambda frame, el_int: True
    rows = []
    real_row = pl.row
    pl.row = lambda frame: rows.append(real_row(frame)) or rows[-1]
    n = forced = 0
    for k, (f, advanced) in enumerate(frames(limit=240)):
        pl.observe(f)
        if not advanced:
            continue
        seed = k
        pl.rng_decisions = np.random.default_rng(seed)
        rows.clear()
        d = pl.decide(f)
        (b, info), = rows
        s, p = sim_decision(pl, b, info, f, True, options, seed)
        assert abs(p - d['p_play']) < 1e-6
        assert d['play'] == s['play']
        if s['play']:
            assert d['deck_index'] == s['slot'] and d['xy'] == cell_xy(s['cell'], 'lattice')
            forced += s['why'] == 'stall'
        n += 1
    assert n == 240 and forced > 50, (n, forced)


@real
def test_real_stream_with_anti_leak_on_plays_only_when_the_rule_fires():
    """The real rule on the recording (no confirmations replayed): ON differs from OFF only on stalled decisions, and
    only by playing where OFF waits. On this stream the rule fires (ticks ~3420-3470, 2x, elixir -> 10) where the
    gate already plays, so the decisions match OFF there (no forced play) -- the forced case is covered by (b)/(c)."""
    on, off = live_pilot(live_gen_v2.GenPilot, anti_leak=True), live_pilot(live_gen_v2.GenPilot)
    stalled = extra = 0
    for f, advanced in frames():
        on.observe(f)
        off.observe(f)
        if not advanced:
            continue
        a, b = on.decide(f), off.decide(f)
        stalled += a['stalled']
        if a['stalled']:
            assert int(a['bs'].my_elixir) >= 9 and int(f['game_tick']) - on.last_play_tick >= 240 and a['play']
        if a['play'] != b['play']:
            assert a['stalled'] and not b['play']
            extra += 1
        else:
            assert {k: a.get(k) for k in KEYS} == {k: b.get(k) for k in KEYS}
    print(f'stalled decisions {stalled}, forced plays {extra}')
    assert stalled > 0


# ---------------------------------------------------------------------------------------------------------- (d)
@pytest.mark.parametrize('options', [DecisionOptions(), OPTS], ids=['default', 'tau_phase+xbow_class'])
def test_forced_play_goes_to_the_best_legal_cell(options):
    LEGAL = 44 * 36 + 18                                   # my frame (9, 10) tiles
    """Knight forced (gate .2 < tau) with the cell head peaked deep in the enemy half (both princesses standing):
    the guard moves it to the best LEGAL cell, as for a gate play."""
    cell = torch.full((1, 36 * 64), -5.)
    cell[0, OFF[0]] = 9.                                   # near the enemy king: illegal for a troop
    cell[0, LEGAL] = 3.                                    # my half, mid lane: legal, the runner-up
    p = pilot(options, .2, card_logits=(9., 0., 0., 0.), cell=cell)
    p.legal_guard, p.anti_leak_elixir, p.anti_leak_seconds = True, 9.0, 12.0
    p.record_play(1, 0, (.5, .8), 1000 * .05)
    f = at(1240, 10.0)
    d = p.decide(f)
    assert d['stalled'] and d['play'] and d['name'] == 'Knight'
    assert d['xy_unguarded'] == cell_xy(OFF[0], 'lattice') and d['xy'] == cell_xy(LEGAL, 'lattice')
    ok = legal_cells(f['entities'], 1, f['players'][1]['deck_card_ids'][HAND[0]], 'Knight', 'lattice')
    assert ok[LEGAL] and not ok[OFF[0]]
