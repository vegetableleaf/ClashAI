"""MEM-FULL (owner 10-30): full-match memory (``e_max``) + a board snapshot per play (``snap``), both opt-in.

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_memory_full.py -q

Absent = byte-identical (golden sha256s from the pre-MEM-FULL code, mem_full_golden.json); e_max keeps more of the oldest
events and changes nothing else; snap adds SNAP_FIELDS after FIELDS and changes nothing else; incremental == offline ==
features_at == rows_features with both on; causality with both on; the snapshot's counts / values / tower HP on a crafted
board; mirror."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]
from pipeline import match_memory as M  # noqa: E402
from mem_full_golden import GOLDEN, digests  # noqa: E402
from test_match_memory import DECK, GID, rand_match, rich_match, same, samples, unit  # noqa: E402

DK = [GID.get(M.card_key(c), 0) for c in DECK]
CX = M._COLX


def long_match(seed, n=260):
    """rich_match + n extra plays, so the match passes 128 events (pro max 229)."""
    side, sm, plays = rich_match(seed)
    rng = np.random.default_rng(seed)
    for _ in range(n):
        plays.append(dict(tick=int(rng.integers(0, 4200)), side=int(rng.integers(2)), card='Knight',
                          x=float(rng.integers(0, 18000)), y=float(rng.integers(0, 32000))))
    return side, sm, plays


def test_absent_is_byte_identical_to_golden():
    assert digests() == json.loads(GOLDEN.read_text())


def test_e_max_keeps_older_events_only():
    side, sm, plays = long_match(1)
    a, b = M.build(side, sm, plays), M.build(side, sm, plays, e_max=512)
    n_all = len(a.events(10 ** 6))
    assert n_all > 300
    for t in [s['tick'] for s in sm][::9] + [10 ** 6]:
        fa, fb = a.features(t, GID, DK, 'v2'), b.features(t, GID, DK, 'v2')
        k = int(fa['mem_mask'].sum())
        assert fb['mem_ev'].shape == (512, M.F) and np.array_equal(fb['mem_ev'][:128], fa['mem_ev'])
        for key in ('mem_mask', 'mem_card', 'mem_form'):
            assert np.array_equal(fb[key][:128], fa[key])
        assert int(fb['mem_mask'].sum()) == min(len(a.events(t)), 512) and (k < 128 or fb['mem_mask'].sum() >= k)
        assert np.array_equal(fa['mem_summary'], fb['mem_summary']) and fa['mem_answer'] == fb['mem_answer']
    assert int(b.features(10 ** 6, GID, DK)['mem_mask'].sum()) == min(n_all, 512)


def test_snap_appends_only():
    side, sm, plays = rich_match(3)
    a, b = M.build(side, sm, plays), M.build(side, sm, plays, snap=True)
    for t in [s['tick'] for s in sm][::5] + [10 ** 6]:
        fa, fb = a.features(t, GID, DK, 'v2'), b.features(t, GID, DK, 'v2')
        assert fb['mem_ev'].shape == (128, M.F_SNAP) and np.array_equal(fb['mem_ev'][:, :M.F], fa['mem_ev'])
        assert all(np.array_equal(fa[k], fb[k]) for k in M.MEM_KEYS if k != 'mem_ev')
    ev = b.features(10 ** 6, GID, DK)['mem_ev']
    tower = (ev[:, CX['is_tower_damage']] == 1) | (ev[:, CX['is_tower_fall']] == 1)
    assert tower.any() and not ev[tower, M.F:].any()                    # tower events carry no snapshot
    play = ev[:, CX['is_play']] == 1
    assert (ev[play, CX['sn_hp_known']] == 1).any() and (ev[play, CX['sn_units_known']] == 1).any()
    ta, tb = a.table(GID), b.table(GID)
    assert all(np.array_equal(ta[k], tb[k]) for k in M.TABLE_KEYS if k != 'vals')
    assert np.array_equal(ta['vals'], tb['vals'][:, :M.F])


def _both(seed):
    side, sm, plays = long_match(seed, 200)
    return side, sm, plays, dict(e_max=384, snap=True)


def test_incremental_offline_features_at_rows_full():
    n = 0
    tabs, refs = [], []
    for seed in range(3):
        side, sm, plays, o = _both(600 + seed)
        inc = M.MatchMemory(side, **o)
        off = M.build(side, sm, plays, **o)
        ticks = []
        for s in sm:
            inc.observe(**s, plays=[p for p in plays if p['tick'] <= s['tick'] and p.get('seen', p['tick']) <= s['tick']])
            if len(ticks) < 60 or s is sm[-1]:
                ticks.append(s['tick'])
                for v in ('v1', 'v2'):
                    assert same(inc.features(s['tick'], GID, DK, v), off.features(s['tick'], GID, DK, v)), (seed, s['tick'])
                n += 1
        ticks = [s['tick'] for s in sm][::3] + [10 ** 6]
        tab = off.table(GID)
        assert tab['vals'].shape[1] == M.F_SNAP
        for v in ('v1', 'v2'):
            fa = M.features_at(tab, ticks, DK, v, GID, e_max=384)
            for i, t in enumerate(ticks):
                ref = off.features(t, GID, DK, v)
                assert all(np.array_equal(fa[k][i], ref[k]) for k in M.MEM_KEYS), (seed, t, v)
        assert int(fa['mem_mask'][-1].sum()) > 128                    # the full window is really used
        tabs.append(tab)
        refs.append(off)
    packed = M.pack(tabs)
    rng = np.random.default_rng(2)
    rt, tt = rng.integers(-1, 3, 30), rng.integers(0, 4400, 30)
    got = M.rows_features(packed, rt, tt, np.tile(DK, (30, 1)), np.arange(30), 'v2', GID, e_max=384)
    for i in range(30):
        ref = (refs[rt[i]] if rt[i] >= 0 else M.MatchMemory(0, e_max=384, snap=True)).features(int(tt[i]), GID, DK, 'v2')
        if rt[i] < 0:                               # no table: the F_SNAP width comes from the packed tables' vals
            assert ref['mem_ev'].shape == got['mem_ev'][i].shape
        assert all(np.array_equal(got[k][i], ref[k]) for k in M.MEM_KEYS), (i, [k for k in M.MEM_KEYS
                                                                                  if not np.array_equal(got[k][i], ref[k])])
    assert n > 150


def test_causality_full():
    for seed in range(4):
        side, sm, plays, o = _both(700 + seed)
        _, sm2, plays2 = rand_match(800 + seed)
        full = M.build(side, sm, plays, **o)
        for t in np.random.default_rng(seed).integers(50, 4200, 10):
            t = int(t)
            alt = M.build(side, [s for s in sm if s['tick'] < t] + [s for s in sm2 if s['tick'] >= t],
                          [p for p in plays if p['tick'] < t] + [p for p in plays2 if p['tick'] >= t], **o)
            assert same(full.features(t, GID, DK, 'v2'), alt.features(t, GID, DK, 'v2')), (seed, t)


def test_snapshot_values():
    """Side 0 (engine = own frame up to the y flip): 2 own Knights back-left, 1 enemy Hog front-right, towers read."""
    def units(t):
        return [unit(1, 0, 'Knight', 1000.0, 1000.0, 3000, 5000), unit(2, 0, 'Knight', 500.0, 1000.0, 3000, 6000),
                unit(3, 1, 'HogRider', 800.0, 800.0, 15000, 26000)]
    hp = (1.0, .9, .8, 1.0, .7, .6)
    sm = samples(range(0, 400, 10), towers=lambda t: hp, units=units)
    plays = [dict(tick=205, side=0, card='Knight', x=9000, y=14000)]
    m = M.build(0, sm, plays, snap=True)
    e = next(d for d in m.events(10 ** 6) if d['type'] == 'play')
    s = dict(zip(M.SNAP_FIELDS, e['snap']))
    assert s['sn_me_back_l_n10'] == .2 and s['sn_opp_front_r_n10'] == .1
    assert np.isclose(s['sn_me_back_l_v10'], (M._value('knight', 1000.0, 1000.0, {'knight': 1000.0})
                                              + M._value('knight', 500.0, 1000.0, {'knight': 1000.0})) / 10)
    assert s['sn_opp_front_r_v10'] > 0 and np.isclose(sum(v for f, v in s.items() if f.endswith('n10')), .3)
    assert [s[f'sn_hp_{x}'] for x in ('mk', 'ml', 'mr', 'ok', 'ol', 'or')] == list(hp)
    assert s['sn_hp_known'] == 1 and s['sn_units_known'] == 1


def test_mirror_snap():
    side, sm, plays = rich_match(9)
    ev = M.build(side, sm, plays, snap=True).features(10 ** 6, GID)['mem_ev']
    m = M.mirror_ev(ev)
    assert np.array_equal(m[:, CX['sn_me_back_l_n10']], ev[:, CX['sn_me_back_r_n10']])
    assert np.array_equal(m[:, CX['sn_hp_ol']], ev[:, CX['sn_hp_or']])
    assert np.array_equal(m[:, CX['sn_hp_mk']], ev[:, CX['sn_hp_mk']])
    assert np.allclose(M.mirror_ev(m), ev, atol=1e-6)
    assert np.array_equal(M.mirror_ev(ev[:, :M.F]), m[:, :M.F])          # the FIELDS part = the F-width mirror


def test_empty_rows_and_opts():
    e = M.empty_rows(2, 'v2', 300, M.F_SNAP)
    assert e['mem_ev'].shape == (2, 300, M.F_SNAP) and e['mem_mask'].shape == (2, 300)
    assert M.opts(None) == dict(e_max=128, snap=False)

    class Mem:
        e_max, snap = 320, True
    assert M.opts(Mem()) == dict(e_max=320, snap=True)


# ------------------------------------------------------------------------------------------------------ model / config
def _net(seed=0, version='v2'):
    import torch
    from pipeline import model_gen as MG
    from test_memory_s1b import _tiny
    net = _tiny(True, seed=seed, live=True, version=version)
    with torch.no_grad():                                   # a trained-looking encoder: every weight nonzero
        for n, q in net.mem.named_parameters():
            if not n.startswith('out.'):
                q.add_(torch.randn_like(q) * 0.05)
    return net, MG


def _mem_out(net, f):
    import torch
    t = {k: torch.from_numpy(np.asarray(v)[None]) for k, v in f.items()}
    with torch.no_grad():
        return net.mem(t['mem_ev'], t['mem_mask'].bool(), net.emb(t['mem_card'], t['mem_form']), t['mem_summary'],
                       net.card_id(t['mem_answer'].long()), net.card_id(t['mem_answer'].new_zeros(1).long()))


def test_mem_full_widen_is_identity_at_init():
    """mem_full(256, snap): same outputs on the same events (new ev_in columns zero; the history is length-free).
    Measured: max |diff| of the memory output, short (<= 128) and long matches (> 128: the longer window is NEW input)."""
    import copy
    net, MG = _net()
    side, sm, plays = rich_match(11)
    gid = net.gid if hasattr(net, 'gid') else GID
    m0, m1 = M.build(side, sm, plays), M.build(side, sm, plays, e_max=256, snap=True)
    wide = copy.deepcopy(net)
    wide.mem_full(256, True)
    assert wide.mem.ev_in.in_features == M.F_SNAP and wide.mem.e_max == 256 and wide.mem.snap
    assert np.array_equal(wide.mem.ev_in.weight[:, :M.F].detach().numpy(), net.mem.ev_in.weight.detach().numpy())
    assert not wide.mem.ev_in.weight[:, M.F:].any()
    worst, n = 0.0, 0
    for t in [s['tick'] for s in sm][::4] + [10 ** 6]:
        a, b = m0.features(t, gid, DK, 'v2'), m1.features(t, gid, DK, 'v2')
        if int(b['mem_mask'].sum()) > 128:                                   # only histories 128 also holds whole
            continue
        n += 1
        d = float((_mem_out(net, a) - _mem_out(wide, b)).abs().max())
        worst = max(worst, d)
    assert n > 3 and worst < 1e-5, (n, worst)
    print(f'MEM-FULL widen identity: {n} ticks, max |diff| {worst:.3g}')
    sd = wide.state_dict()
    assert sd['mem.full'].tolist() == [256, 1] and sd['mem.cfg'][0] == M.F_SNAP
    plain = _net()[0]
    del plain.mem                                                            # a model with no encoder: built by content
    plain.load_state_dict(sd)
    assert plain.mem.e_max == 256 and plain.mem.snap and plain.mem.ev_in.in_features == M.F_SNAP
    assert M.opts(plain.mem) == dict(e_max=256, snap=True)
    same_arch = _net()[0]                                                    # an encoder WITHOUT full: widened on load
    same_arch.load_state_dict(sd)
    assert same_arch.mem.snap and float((_mem_out(same_arch, b) - _mem_out(wide, b)).abs().max()) == 0.0
    assert 'mem.full' not in net.state_dict()                                # absent = the state dict unchanged
    try:
        wide.mem_full(256, False)
        raise AssertionError('a snap encoder was narrowed')
    except ValueError:
        pass


def test_config_keys_absent_is_historical_hash():
    from pipeline import rl_royale as RL
    from test_memory_s1b import YAML
    base = RL.load_config(YAML, ['memory=v2'], False)
    assert RL.config_sha({**base, 'memory_e_max': None, 'memory_board_snap': False}) == RL.config_sha(base)
    on = RL.load_config(YAML, ['memory=v2', 'memory_e_max=256', 'memory_board_snap=true'], False)
    assert on['memory_e_max'] == 256 and on['memory_board_snap'] is True
    assert RL.config_sha(on) != RL.config_sha(base)
    for bad in (['memory=v2', 'memory_e_max=0'], ['memory=v2', 'memory_board_snap=2'], ['memory_e_max=256'],
                ['memory_board_snap=true']):
        try:
            RL.load_config(YAML, bad, False)
            raise AssertionError(bad)
        except SystemExit:
            pass


def test_warm_start_copies_encoder_and_keeps_snap_columns_zero(tmp_path):
    from pipeline.train_memory import _aux_trainable, warm_start
    import torch
    old = _net(1)[0]
    old.add_memory_aux()
    p = tmp_path / 'old.pt'
    torch.save({'model': old.state_dict()}, p)
    new = _net(2)[0]
    new.mem_full(256, True)
    new.add_memory_aux()
    out0 = new.mem.out.weight.detach().clone()
    assert warm_start(new, p) == sum(_aux_trainable(k) for k, _ in new.named_parameters())
    w, o = new.state_dict(), old.state_dict()
    assert torch.equal(w['mem.ev_in.weight'][:, :46], o['mem.ev_in.weight'])
    assert float(w['mem.ev_in.weight'][:, 46:].abs().max()) == 0
    assert all(torch.equal(w[k], o[k]) for k, _ in new.named_parameters() if _aux_trainable(k) and k != 'mem.ev_in.weight')
    assert torch.equal(new.mem.out.weight, out0)          # the coupling stays out of it
