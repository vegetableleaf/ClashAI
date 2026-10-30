"""GATE-SAMPLE (plan1026 Pillar 3 P1, 10-30): the deployed gate = the trained gate. The pilot trains
Bernoulli(sigmoid((z - logit tau) / T_gate)) (e1_eval.sample_decide_batch -> decision_options.decide decode 'sample');
the SIM eval (search_s0 / gap.py --gate-sample T -> match_kwargs -> decide gate_sample) and live (live_play --gate-sample T
-> GenPilot.decide -> decide gate_sample) must draw the SAME gate given the same RNG draws.

  * recorded rows: every gate row of test_decide_identity's 4 recorded CLXIII live matches (z = logit p_play, tau = the
    logged gate_tau): the trainer's decode and the SIM / live decode, each from an identical per-row stream -> identical
    play / wait on every row, same u, p_b and lp_gate; gate_steps all 1 = byte-identical to no gate_steps; k != 1 =
    1 - (1 - p_b)^k.
  * SIM plumbing: match_kwargs adds gate_sample + one seeded stream per match only when cfg has gate_sample (absent: the
    old keys, rng_decision_options untouched).
  * live replay (slow; CLXIII + logs): GenPilot --gate-sample 0.1 on the recorded frames; each draw == the trainer's
    decode from a copy of the live stream taken just before the decision; with --gate-sample-step-ticks 10 the per-time
    exponent k (1 on rows after a play / no draw / a 10-tick wait).

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_gate_sample_identity.py
"""
import copy
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline.tests.test_decide_identity import CKPT, LIVE_DIR, LOGS, read_log  # noqa: E402

T = 0.1


def recorded_rows():
    """-> z, tau, affordable, stalled arrays from the logged live decisions (the model's gate inputs, as decided live)."""
    z, tau, aff, st = [], [], [], []
    for name in LOGS:
        for line in open(LIVE_DIR / name, encoding='utf-8'):
            e = json.loads(line)
            if e.get('event') != 'decision':
                continue
            d = e['decision']
            p = min(max(float(d['p_play']), 1e-12), 1 - 1e-12)
            z.append(math.log(p / (1 - p)))
            tau.append(float(d.get('gate_tau', 0.35)))
            aff.append(not d.get('no_affordable', False))
            st.append(bool(d.get('stalled', False)))
    return np.array(z), np.array(tau), np.array(aff), np.array(st)


def _decide(z, tau, aff, st, rngs, mode, steps=None):
    import torch
    from pipeline.decision_options import DecisionOptions, decide, sample_rules
    n = len(z)
    heads = {'gate': torch.tensor(z, dtype=torch.float32), 'card': torch.zeros(n, 4)}
    allowed = np.zeros((n, 4), dtype=bool)
    allowed[:, 0] = aff
    kw = dict(cell_logits=lambda ids, slots: torch.zeros(len(ids), 2304), trace=[])
    if mode == 'train':                 # e1_eval.sample_decide_batch's call (tau_r = the row's phase tau, T_gate = T)
        out = decide(heads, 1 / (1 + np.exp(-z)), allowed, st, tau=0.35, options=sample_rules(DecisionOptions()),
                     rngs=[None] * n, decode='sample',
                     sampler={'tau_r': tau, 'T': 0.5, 'T_gate': T, 'heads': frozenset(('gate',)), 'rngs': rngs}, **kw)
    else:                               # SIM decide_batch / live GenPilot.decide: greedy + gate_sample from gate_rngs
        out = decide(heads, 1 / (1 + np.exp(-z)), allowed, st, tau=tau, options=DecisionOptions(), rngs=[None] * n,
                     gate_sample=T, gate_rngs=rngs, gate_steps=steps, **kw)
    return out, kw['trace']


def _streams(n, salt=0):
    return [np.random.default_rng([r, 0x6A7E, salt]) for r in range(n)]


def test_recorded_rows_trainer_and_deploy_decode_identical():
    z, tau, aff, st = recorded_rows()
    n = len(z)
    tr_out, _ = _decide(z, tau, aff, st, _streams(n), 'train')
    for steps in (None, np.ones(n)):
        dp_out, trace = _decide(z, tau, aff, st, _streams(n), 'deploy', steps)
        assert [o['play'] for o in tr_out] == [o['play'] for o in dp_out]
        for r in range(n):
            g = trace[r].get('gate_sample')
            assert (g is not None) == bool(tr_out[r]['gate_sampled'])
            if g is not None:
                pb = g['p_b']
                assert tr_out[r]['lp_gate'] == math.log(pb if g['fire'] else 1 - pb)
                assert g['fire'] == tr_out[r]['play']
                assert g.get('k', 1.0) == 1.0
    p = np.array([t['gate_sample']['p_b'] for t in trace if 'gate_sample' in t])
    fires = sum(o['play'] for o in dp_out)
    mid = int(((p > .01) & (p < .99)).sum())
    print(f'recorded rows: {n} rows, {len(p)} gate draws ({mid} with .01 < p_b < .99), {fires} plays: trainer == deploy')
    assert n >= 1700 and mid >= 100


def test_per_time_exponent():
    z, tau, aff, st = recorded_rows()
    n = len(z)
    base, tb = _decide(z, tau, aff, st, _streams(n, 1), 'deploy')
    k = np.where(np.arange(n) % 3 == 0, 2.0, np.where(np.arange(n) % 3 == 1, 0.2, 1.0))
    out, tk = _decide(z, tau, aff, st, _streams(n, 1), 'deploy', k)
    for r in range(n):
        if 'gate_sample' not in tb[r]:
            assert 'gate_sample' not in tk[r] and out[r]['play'] == base[r]['play']
            continue
        a, b = tb[r]['gate_sample'], tk[r]['gate_sample']
        assert a['u'] == b['u'] and b['k'] == k[r]
        want = a['p_b'] if k[r] == 1.0 else 1 - (1 - a['p_b']) ** k[r]
        assert abs(b['p_b'] - want) <= 1e-12 and b['fire'] == (b['u'] < b['p_b']) == out[r]['play']
    import pytest
    with pytest.raises(ValueError):
        _decide(z[:2], tau[:2], aff[:2], st[:2], _streams(2), 'deploy', np.array([1.0, 0.0]))


def test_gate_step():
    from pipeline.decision_options import gate_step
    assert gate_step(None, 100, 10) == 1.0                  # first decision of the match: one trainer draw
    assert gate_step((90, False), 100, 10) == 1.0           # after a play / no draw: one draw
    assert gate_step((90, True), 100, 10) == 1.0            # a 10-tick wait = the trainer's step
    assert gate_step((96, True), 100, 10) == 0.4
    assert gate_step((74, True), 100, 10) == 2.6
    assert gate_step((0, True), 100, 10) == 4.0             # capped (2 s, = HAZARD_STEP_CAP_S)
    assert gate_step((100, True), 100, 10) == 1.0           # clock did not move


def _sim_matches(cfg, k=0):
    return [SimpleNamespace(cfg=cfg, tag='gs:test', k=k, deck=SimpleNamespace(cards=['Xbow'] * 8))]


def test_sim_match_kwargs_gate_sample_opt_in():
    from pipeline.decision_options import match_kwargs
    cfg0 = {'card_choice': 'filtered', 'decision_seed': 3}
    m0 = _sim_matches(cfg0)
    off = match_kwargs(m0)
    assert set(off) == {'decision_options', 'rngs', 'card_names'} and not hasattr(m0[0], 'rng_gate_sample')
    m1 = _sim_matches({**cfg0, 'gate_sample': T})
    on = match_kwargs(m1)
    assert set(on) == set(off) | {'gate_sample', 'gate_rngs'} and on['gate_sample'] == T
    assert on['rngs'][0].bit_generator.state == off['rngs'][0].bit_generator.state   # decision stream untouched
    again = match_kwargs(_sim_matches({**cfg0, 'gate_sample': T}))['gate_rngs'][0]
    assert again.random() == on['gate_rngs'][0].random()                                # seeded per match
    other = match_kwargs(_sim_matches({**cfg0, 'gate_sample': T}, k=1))['gate_rngs'][0]
    assert other.random() != again.random()
    assert match_kwargs(m1)['gate_rngs'][0] is m1[0].rng_gate_sample                   # one stream for the match


def _need_live():
    import pytest
    if not CKPT.is_file() or any(not (LIVE_DIR / n).is_file() for n in LOGS):
        pytest.skip('recorded live logs / CLXIII not in this checkout')


def _live_replay(step_ticks):
    """GenPilot --gate-sample T (+ --gate-sample-step-ticks) on the recorded frames -> per draw: the live draw, the
    trainer's decode of the same row from a copy of the live stream taken just before the decision, the expected k."""
    import torch
    from pipeline.decision_options import gate_step
    torch.set_num_threads(1)
    sys.path.insert(0, str(LIVE_DIR))
    import live_play as lp
    rows = []
    for name in LOGS:
        start, ev = read_log(LIVE_DIR / name)
        a = SimpleNamespace(device='cpu', ckpt=str(CKPT), tau=start['tau'], no_opp_counter=not start['opp_counter'],
                            extrapolate=start['extrapolate'], decision_seed=start['decision_seed'], public_audit=False,
                            own_effects=start['own_effects'], hero_ability_spec=start['hero_ability_spec'],
                            identity_ext='on' if start['identity_ext'] in (True, 'on') else 'off',
                            afford_ticks=start['afford_ticks'], reader='merged', gate_sample=T,
                            gate_sample_step_ticks=step_ticks,
                            cue_inputs='on' if (start.get('cue_inputs') or {}).get('active') else 'off',
                            iw_press=start['iw_press'], iw_press_head_decode=start['iw_press_head_decode'])
        pilot = lp.load_pilot(a, dict(start['decision_options']))[1]
        assert pilot.gate_sample == T and pilot.gate_sample_step_ticks == step_ticks
        pilot.reset_match()
        f, prev = None, None
        for e in ev:
            if e[0] == 'frame':
                f = e[1]
                pilot.observe(f)
            elif e[0] == 'decision' and f is not None and f['game_tick'] == e[1]:
                rng = copy.deepcopy(pilot.rng_gate)
                pilot.decide(f)
                g = pilot.last_gate_draw
                if g is not None:
                    k = gate_step(prev, e[1], step_ticks) if step_ticks else 1.0
                    out, _ = _decide(np.array([g['z']]), np.array([g['tau']]), np.array([True]), np.array([False]),
                                     [copy.deepcopy(rng)], 'train')
                    u = float(rng.random())
                    rows.append(dict(g=g, k=k, train_play=bool(out[0]['play']), u=u))
                prev = (e[1], g is not None and not g['fire'])
            elif e[0] == 'confirmed' and None not in e[2:]:
                pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
            elif e[0] == 'ability':
                pilot.record_ability(e[1], e[2])
    return rows


def test_live_replay_draws_equal_trainer_decode():
    _need_live()
    rows = _live_replay(0)
    bad = [r for r in rows if r['g']['fire'] != r['train_play'] or r['g']['u'] != r['u'] or 'k' in r['g']]
    print(f'live replay (per decision): {len(rows)} draws, {sum(r["g"]["fire"] for r in rows)} fires, {len(bad)} differ')
    assert len(rows) > 1000 and not bad, bad[:3]


def test_live_replay_per_time():
    _need_live()
    rows = _live_replay(10)
    bad = []
    for r in rows:
        g = r['g']
        if g['k'] != r['k'] or g['u'] != r['u'] or (r['k'] == 1.0 and g['fire'] != r['train_play']):
            bad.append(r)
    k = np.array([r['k'] for r in rows])
    print(f'live replay (step 10 ticks): {len(rows)} draws, k == 1 on {int((k == 1).sum())}, k < 1 on {int((k < 1).sum())}, '
          f'k > 1 on {int((k > 1).sum())}; {len(bad)} differ')
    assert len(rows) > 1000 and not bad, bad[:3]
