"""C1 stage B: the posture head on the LIVE path (live_gen_v2.GenPilot) against the SIM path (e1_eval.posture_dtau /
posture_live / Match._ctx_row). icebow venv:  icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_posture_live.py
(1) absent head = HEAD dbf8e72's live_gen_v2 decision for decision (fake model on fixture frames; real checkpoint on a
recorded reader stream when present); (2) live ctx == SIM ctx, live argmax == SIM argmax; (3) hold / re-choose by game
tick, reset on a new match; (4) threshold in force = SIM's tau_phase / tau_threatened (+ pipeline delta) + dtau;
(5) --check names the head (off = the HEAD JSON, no key)."""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import archetypes as AR
from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.decision_options import DecisionOptions, match_kwargs
from pipeline.live_mem import deck_of
from pipeline.rl_royale import PostureHead
from pipeline.tests.test_live_decision_options import HAND, OPTS, FakeModel, icebow_frame, pilot

REPO = Path(__file__).resolve().parents[2]
HEAD_REV = 'dbf8e72'                                     # stage A tip: live_gen_v2 before stage B
LIVE_CKPT = REPO / 'icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt'
STREAM = REPO / 'scratchpad/gauntlet/L70/reader/sidebyside/re_v2xb.jsonl'   # recorded icebow reader frames (local)
D_G = 4


@pytest.fixture(scope='module')
def head_mod(tmp_path_factory):
    """live_gen_v2 as of HEAD_REV, imported as a sibling module of pipeline (its relative imports resolve)."""
    src = subprocess.run(['git', 'show', f'{HEAD_REV}:pipeline/live_gen_v2.py'], cwd=REPO, capture_output=True,
                         text=True, encoding='utf-8')
    if src.returncode:
        pytest.skip(f'git show {HEAD_REV} failed: {src.stderr}')
    p = tmp_path_factory.mktemp('head') / 'live_gen_v2_head.py'
    p.write_text(src.stdout, encoding='utf-8')
    spec = importlib.util.spec_from_file_location('pipeline._live_gen_v2_head', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class GModel(FakeModel):
    """FakeModel + the trunk feature g the posture head reads (live: out['g'] of the same forward)."""
    g = torch.zeros(1, D_G)

    def __call__(self, b, card=None, form=None):
        out = super().__call__(b, card, form)
        return out if card is not None else {**out, 'g': self.g.clone()}


def make_head(seed=0, bias=None):
    torch.manual_seed(seed)
    h = PostureHead(D_G)
    with torch.no_grad():
        for prm in h.parameters():
            prm.copy_(torch.randn_like(prm))
        if bias is not None:
            h.net[2].weight.zero_()
            h.net[2].bias.copy_(torch.tensor(bias))
    return h.eval()


def posture_cfg(head, every=200, dtau=(0.10, 0.0, -0.10)):
    return {'head': head, 'every': every, 'dtau': list(dtau), 'mode': 'argmax'}


def head_pilot(head, options=OPTS, gate_p=.6, g=None, **kw):
    p = pilot(options, gate_p, **kw)
    p.model.__class__ = GModel
    p.model.g = torch.zeros(1, D_G) if g is None else g
    p.posture = posture_cfg(head)
    p.decision_seed, p.match_index = 0, -1               # reset_match's own state (pilot() skips __init__)
    return p


def pend(p, tick):
    """One outstanding tap (--pipeline-decisions): my Tesla (hand position 3), landing 20 ticks later."""
    from pipeline.dataset_gen import card_key
    name = deck_of(icebow_frame(), 1)[1][HAND[3]]
    return [dict(hand_pos=3, deck_index=HAND[3], card=p.gid[card_key(name)], form=0, name=name, xy=(.5, .3),
                 land=tick + 20)]


# --------------------------------------------------------------------------------------------- (2) ctx parity
FOE = [(1500, ['HogRider']), (2500, ['Golem']), (3000, ['RoyalGiant', 'Monk'])]   # (from tick, foe bodies on board)
CARD_ID = {'HogRider': 26000021, 'Golem': 26000009, 'RoyalGiant': 26000024, 'Monk': 26000077}


def situation(tick, side):
    """The same public situation twice: a live reader frame (catalogue card ids; a destroyed tower is absent) and the
    SIM engine state (engine names; episode.crown_towers with the tower marked destroyed), seen from ``side``."""
    foe = next((n for t, n in reversed(FOE) if tick >= t), [])
    drop = 3500 if tick >= 2800 else None                # my opponent's princess falls at 2800 (I lead 1-0)
    f = icebow_frame(tick, side=side, drop_enemy_native_x=drop)
    if tick >= 3300:                                     # and one of MINE falls at 3300 (1-1)
        mine = next(e for e in f['entities'] if e['kind'] == 13 and e['side'] == side)
        f['entities'].remove(mine)
    for i, n in enumerate(foe):
        f['entities'].append(dict(address=f'0xf{i}', category=0, kind=15, side=1 - side, x=9000, y=16000,
                                  card_id=CARD_ID[n], level=11, hp=100, max_hp=100, behavior_state_raw=0))
    f['entities'].append(dict(address='0xc0', category=0, kind=15, side=1 - side, x=9000, y=16000, card_id=-1,
                              level=11, hp=100, max_hp=100, behavior_state_raw=0))   # a card_id -1 troop: unnamed in SIM
    towers = [dict(side=e['side'], type='king' if abs(e['x'] - 9000) < 1500 else 'princess', hp=e['hp'],
                   max_hp=e['max_hp'], destroyed=False) for e in icebow_frame(tick, side=side)['entities']
              if e['card_id'] < 0 and e['kind'] in (12, 13)]
    live_towers = {(e['side'], e['x']) for e in f['entities'] if e['card_id'] < 0 and e['kind'] in (12, 13)}
    full = [(e['side'], e['x']) for e in icebow_frame(tick, side=side)['entities'] if e['card_id'] < 0 and e['kind'] in (12, 13)]
    for t, key in zip(towers, full):
        t['destroyed'] = key not in live_towers
    state = {'entities': [dict(side=1 - side, name=n) for n in foe] + [dict(side=side, name='Knight')],
             'episode': {'crown_towers': towers}}
    return f, state


@pytest.mark.parametrize('side', [0, 1])
def test_live_ctx_equals_sim_ctx_row(side):
    p = head_pilot(make_head())
    sim = SimpleNamespace(side=side, state=None)
    rows = []
    for tick in range(1000, 4000, 100):
        f, sim.state = situation(tick, side)
        p._ctx_frame = f
        live, want = p._ctx_row(tick), E.Match._ctx_row(sim, tick)
        assert live == want, (side, tick, live, want)
        rows.append(live)
    a = np.array(rows)                                   # non-vacuous: every arch step, phase and crown state seen
    assert set(a[:, 0]) == {AR.ARCH_IDS.index(k) for k in ('none_seen', 'other', 'golem', 'royal_giant_monk')}
    assert set(a[:, 2]) == {0, 1, 2} and {tuple(r[3:]) for r in rows} == {(0, 0), (1, 0), (1, 1)}


def test_live_argmax_equals_sim_argmax():
    seen = set()
    for seed in range(6):
        head = make_head(seed)
        gen = torch.Generator().manual_seed(100 + seed)
        for side in (0, 1):
            for tick in (1200, 2600, 3400):
                g = torch.randn(1, D_G, generator=gen) * 3
                f, state = situation(tick, side)
                d = head_pilot(head, g=g).decide(f)
                sim = SimpleNamespace(side=side, state=state, _cur=(tick,))
                sim._ctx_row = lambda t, s=sim: E.Match._ctx_row(s, t)
                dt = E.posture_dtau([sim], {'g': g}, {'posture': posture_cfg(head)})
                ctx = torch.tensor([E.Match._ctx_row(SimpleNamespace(side=side, state=state), tick)])
                z = int(torch.log_softmax(head(g, ctx).double(), -1).argmax())
                assert d['posture'] == sim._posture[0] == z and d['posture_dtau'] == dt[0] and d['posture_new']
                seen.add(z)
    assert seen == {0, 1, 2}                             # non-vacuous: every posture is some case's argmax


# ------------------------------------------------------------------------------------- (3) hold / re-choose / reset
def test_hold_rechoose_by_game_tick_and_reset_on_new_match():
    p = head_pilot(make_head(1))
    news = [(t, p.decide(icebow_frame(t))['posture_new']) for t in (1000, 1010, 1199, 1200, 1300, 1399, 1400)]
    assert news == [(1000, True), (1010, False), (1199, False), (1200, True), (1300, False), (1399, False),
                    (1400, True)]
    assert p.posture_choices == 3 and sum(p.posture_counts) == 7
    p.reset_match()                                      # a new match: no posture, no seen cards, counts cleared
    assert not hasattr(p, '_posture') and not hasattr(p, '_ctx_seen') and not hasattr(p, 'posture_counts')
    assert p.decide(icebow_frame(1450))['posture_new']   # chooses at its first decision, not 200 after 1400
    assert p.decide(icebow_frame(300))['posture_new']    # clock went backwards (no reset_match): a new match too
    assert sum(p.posture_counts) == 1 and p.posture_choices == 1


def test_no_affordable_decision_still_chooses():
    """SIM posture_live runs on every decision, affordable or not: the first decision chooses even with 0 elixir."""
    f = icebow_frame(1000)
    f['players'][1]['elixir_raw'] = 0
    d = head_pilot(make_head(2)).decide(f)
    assert d['no_affordable'] and d['posture_new'] and 'posture' in d


# ----------------------------------------------------------------------------------------- (4) threshold in force
@pytest.mark.parametrize('z,dtau', [(0, .10), (1, 0.0), (2, -.10)])
@pytest.mark.parametrize('tick,pending', [(1000, False), (2600, False), (3700, False), (2600, True)])
def test_threshold_is_sim_tau_plus_dtau(z, dtau, tick, pending):
    bias = [0.0, 0.0, 0.0]
    bias[z] = 9.0
    head = make_head(bias=bias)
    opts = DecisionOptions(tau_phase=(.3, .5, .7), tau_threatened=.2)
    for gate_p in (.25, .35, .45, .55, .65, .75):
        p = head_pilot(head, options=opts, gate_p=gate_p)
        p.pipeline_tau_delta = .05
        f = icebow_frame(tick)
        p.pending_plays = pend(p, tick) if pending else []
        d = p.decide(f)
        # SIM: posture_live on the same match context -> decide_batch's tau_delta (pipeline delta + dtau)
        cfg = {k: getattr(opts, k) for k in DecisionOptions.__dataclass_fields__}
        cfg.update(grid='lattice', posture=posture_cfg(head), pipeline_tau_delta=.05)
        m = SimpleNamespace(cfg=cfg, tag='t', k=0, deck=SimpleNamespace(cards=[None] * 4), _cur=(tick, d['bs'], None),
                            rng_decision_options=np.random.default_rng(0), side=1, state=situation(tick, 1)[1],
                            pend=[1] if pending else [])
        m._ctx_row = lambda t, s=m: E.Match._ctx_row(s, t)
        kw = match_kwargs([m])
        tau, kw = E.posture_live([m], {'g': torch.zeros(1, D_G)}, cfg, .35, kw)
        from pipeline.decision_options import gate_taus, threat_taus
        base = threat_taus(opts, gate_taus(opts, .35, kw['t_sec'], 1), kw.get('tau_threat'))
        sim_tau = float((base + np.asarray(kw['tau_delta'], dtype=np.float64))[0])
        assert d['posture'] == z and d['posture_dtau'] == dtau
        assert d['gate_tau'] == sim_tau                  # bit-equal: the same float64 sums in the same order
        assert abs(sim_tau - ([.3, .5, .7][0 if tick < 2400 else 1 if tick < 3600 else 2] + dtau
                              + (.05 if pending else 0.0))) < 1e-12
        if not d.get('why'):
            assert d['play'] == (d['p_play'] > sim_tau)


# ------------------------------------------------------------------------- (1) absent head = HEAD, byte for byte
@pytest.mark.parametrize('opts', [DecisionOptions(), OPTS, DecisionOptions(tau_phase=(.3, .5, .7), tau_threatened=.2)])
def test_absent_head_fixture_frames_identical_to_head(head_mod, opts):
    for tick in (1000, 2600, 3700):
        for side in (0, 1):
            for gate_p in (.2, .6, .9):
                for pending in (False, True):
                    new = pilot(opts, gate_p)
                    old = pilot(opts, gate_p, cls=head_mod.GenPilot)
                    for q in (new, old):
                        q.pipeline_tau_delta = .05
                        q.pending_plays = pend(q, tick) if pending else []
                    f = icebow_frame(tick, side=side)
                    a, b = new.decide(copy.deepcopy(f)), old.decide(copy.deepcopy(f))
                    assert repr(a) == repr(b) and 'posture' not in a
                    assert new.rng_decisions.bit_generator.state == old.rng_decisions.bit_generator.state


def _deployed_options():
    from pipeline.tests.test_live_options import DEPLOYED_FILE, parse
    return parse([], _write(DEPLOYED_FILE))[0]


def _write(text):
    import tempfile
    p = Path(tempfile.mkdtemp()) / 'LIVE_OPTIONS'
    p.write_text(text)
    return p


@pytest.mark.skipif(not (LIVE_CKPT.is_file() and STREAM.is_file()), reason='live checkpoint / recorded stream absent')
def test_absent_head_recorded_stream_real_model_identical_to_head(head_mod):
    """The deployed checkpoint (no head) + the deployed LIVE_OPTIONS on a recorded icebow reader stream: every
    decision of this pilot = HEAD's, and the head-free pilot never logs a posture."""
    opts = _deployed_options()
    kw = dict(device='cpu', gate_tau=.35, extrapolate_ticks=24, own_effects=True, hero_ability_spec='supplement',
              decision_options=opts, decision_seed=0)
    new, old = live_gen_v2.GenPilot(str(LIVE_CKPT), **kw), head_mod.GenPilot(str(LIVE_CKPT), **kw)
    assert new.posture is None
    for q in (new, old):
        q.legal_guard, q.identity_ext, q.afford_ticks = True, True, 23
    frames = [json.loads(line) for line in STREAM.read_text(encoding='utf-8').splitlines() if line.strip()]
    frames = [f for f in frames if f.get('event') == 'mumu_live_frame' and f.get('battle_active')]
    n = 0
    for i, f in enumerate(frames):
        for q in (new, old):
            try:
                q.observe(copy.deepcopy(f))
            except ValueError:
                pass
        if i % 5:
            continue
        out = []
        for q in (new, old):
            try:
                out.append(repr(q.decide(copy.deepcopy(f))))
            except Exception as exc:                     # noqa: BLE001 -- the same refusal on both sides
                out.append(f'raised {type(exc).__name__}: {exc}')
        assert out[0] == out[1], (i, f['game_tick'])
        n += not out[0].startswith('raised')
    assert n >= 100, n                                   # non-vacuous: >= 100 real decisions compared


@pytest.mark.skipif(not (LIVE_CKPT.is_file() and STREAM.is_file()), reason='live checkpoint / recorded stream absent')
def test_head_on_recorded_stream_real_model(tmp_path):
    """A head-carrying deployed checkpoint on the recorded stream: every decision carries the posture in force, a choice
    = argmax head(the decision's own g, its ctx), first decision chooses, re-choices >= `every` game ticks apart."""
    opts = _deployed_options()
    p = live_gen_v2.GenPilot(str(_head_ckpt(tmp_path / 'h.pt', seed=3)), device='cpu', gate_tau=.35,
                             extrapolate_ticks=24, own_effects=True, hero_ability_spec='supplement',
                             decision_options=opts, decision_seed=0)
    p.legal_guard, p.identity_ext, p.afford_ticks = True, True, 23
    gs, fwd = [], p.model.forward

    def spy(b, card=None, form=None):
        o = fwd(b, card, form)
        if card is None:
            gs.append(o['g'])
        return o
    p.model.forward = spy
    frames = [json.loads(line) for line in STREAM.read_text(encoding='utf-8').splitlines() if line.strip()]
    frames = [f for f in frames if f.get('event') == 'mumu_live_frame' and f.get('battle_active')]
    chose, n = [], 0
    for i, f in enumerate(frames):
        try:
            p.observe(copy.deepcopy(f))
        except ValueError:
            pass
        if i % 5:
            continue
        try:
            d = p.decide(copy.deepcopy(f))
        except ValueError:                               # unreadable hand: live_play never decides on it either
            continue
        n += 1
        assert d['posture_new'] or n > 1                 # the first decision of the match chooses
        assert d['posture_dtau'] == p.posture['dtau'][d['posture']]
        if d['posture_new']:
            p._ctx_frame = f
            ctx = torch.tensor([p._ctx_row(int(f['game_tick']))])      # idempotent: same frame, same seen-set
            assert d['posture'] == int(p.posture['head'](gs[-1], ctx).argmax())
            chose.append(int(f['game_tick']))
    assert n >= 100
    assert all(b - a >= 200 for a, b in zip(chose, chose[1:])) and len(chose) >= 5, chose


# ------------------------------------------------------------------------------------------------- (5) --check
def _head_ckpt(path, seed=None):
    """The deployed checkpoint + a posture head (init weights, or random ones with ``seed``) as stage A saves it."""
    st = torch.load(LIVE_CKPT, map_location='cpu')
    d = int(st['args']['d'])
    h = PostureHead(d)
    if seed is not None:
        torch.manual_seed(seed)
        with torch.no_grad():
            for prm in h.parameters():
                prm.copy_(torch.randn_like(prm) * .3)
    st['rl'] = {**st['rl'], 'posture_head': h.state_dict(),
                'posture': {'every': 200, 'dtau': [.1, 0.0, -.1], 'd_g': d, 'hidden': 64}}
    torch.save(st, path)
    return path


def _check(ckpt, tmp_path):
    from pipeline.tests.test_live_options import DEPLOYED_FILE
    f = tmp_path / 'LIVE_OPTIONS'
    f.write_text(DEPLOYED_FILE)
    out = subprocess.run([sys.executable, str(REPO / 'scratchpad/gauntlet/L68/live_reader/live_play.py'), '--check',
                          '--ckpt', str(ckpt), '--live-options-file', str(f), '--tau', '0.35', '--no-anti-leak'],
                         capture_output=True, text=True, timeout=600, cwd=REPO)
    assert out.returncode == 0, out.stdout + out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not LIVE_CKPT.is_file(), reason='live checkpoint not present')
def test_check_names_the_head_on_and_off(tmp_path):
    on = _check(_head_ckpt(tmp_path / 'with_head.pt'), tmp_path)
    assert on['check'] == 'LIVE_CHECK_PASS' and on['posture_head'] == 'on (every 200, dtau [0.1, 0.0, -0.1])'
    off = _check(LIVE_CKPT, tmp_path)
    assert off['check'] == 'LIVE_CHECK_PASS' and 'posture_head' not in off


@pytest.mark.skipif(not LIVE_CKPT.is_file(), reason='live checkpoint not present')
def test_head_with_inactive_options_or_wrong_width_refuses(tmp_path):
    ck = _head_ckpt(tmp_path / 'h.pt')
    with pytest.raises(ValueError, match='decision options active'):
        live_gen_v2.GenPilot(str(ck), device='cpu', decision_options=DecisionOptions())
    st = torch.load(ck, map_location='cpu')
    st['rl']['posture']['d_g'] = 7
    torch.save(st, tmp_path / 'bad.pt')
    with pytest.raises(ValueError, match='d_g 7'):
        live_gen_v2.GenPilot(str(tmp_path / 'bad.pt'), device='cpu', decision_options=OPTS)
