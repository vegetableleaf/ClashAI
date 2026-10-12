import hashlib
import json
from pathlib import Path
import pytest
import live_truth as T


def decision(tick, *, side=1, loser=None, other_account=False, unknown=False):
    bodies = []
    for s in (0, 1):
        for x, y, hp in ((3500, 6500, 4424), (14500, 6500, 4424), (9000, 3000, 7032)):
            maximum = hp-1 if other_account and s == side else hp
            bodies.append(dict(card_id=-1, side=s, x=x, y=y if s == 0 else 32000-y,
                               hp=0 if s == loser else maximum, max_hp=maximum))
    if unknown:
        bodies.append(dict(card_id=-1, side=side, x=3500, y=14000, hp=100, max_hp=100))
    return dict(event='decision', tick=tick, public=dict(observer_side=side, own_hand=[dict(name='Xbow')],
                raw_bodies=bodies, opp_hand=['SECRET'], opp_elixir=999), opp_hidden='NEVER RETAIN')


def log(path, *, head=None, early=False, closed=True, other=False, reset=False, dry=False):
    h = dict(event='start', ckpt='C:\\repo\\icebow\\data\\model.pt', ckpt_sha256=hashlib.sha256(b'weights').hexdigest(),
             dry_run=dry, decision_options={'spell_aim': 'rocket_area'},
             live_options=dict(status='applied', from_file={'own_effects': True}))
    h.update(head or {})
    rows = [h, decision(100, other_account=other), decision(200 if early else 3000, loser=1 if early else 0, unknown=True)]
    if reset:
        rows.append(decision(2900))
    if early:
        rows.append(dict(event='stop', why='battle_over_hands_visible'))
    if closed:
        rows.append(dict(event='end'))
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf8')
    return path


def test_group_checkpoint_fast_era_and_threshold(tmp_path):
    data = tmp_path/'icebow/data'
    data.mkdir(parents=True)
    (data/'model.pt').write_bytes(b'weights')
    for i in range(30):
        log(tmp_path/f'live_play_{i:03}.jsonl')
    log(tmp_path/'live_play_fast.jsonl', head={'pipeline_decisions': True})
    log(tmp_path/'live_play_era.jsonl', head={'live_options': {'status': 'applied', 'from_file': {'own_effects': False}}})
    log(tmp_path/'live_play_hash.jsonl', head={'ckpt_sha256': 'changed'})
    log(tmp_path/'live_play_early.jsonl', early=True)
    log(tmp_path/'live_play_other.jsonl', other=True)
    log(tmp_path/'live_play_open.jsonl', closed=False)
    log(tmp_path/'live_play_reset.jsonl', reset=True)
    log(tmp_path/'live_play_dry.jsonl', dry=True)
    truth = T.build_truth(tmp_path.glob('live_play*'), root=tmp_path)
    assert truth['accepted'] == 34
    assert len(truth['groups']) == 4
    g = next(g for g in truth['groups'] if g['reportable'])
    assert (g['n'], g['wins'], g['losses'], g['early_terminal']) == (31, 30, 1, 1)
    assert g['checkpoint_verified'] and g['fast_flag_recorded'] == 0
    assert not next(g for g in truth['groups'] if g['checkpoint_sha256'] == 'changed')['checkpoint_verified']
    assert g['ci95'][0] < 30/31 < g['ci95'][1]
    assert truth['excluded'] == dict(other_account_tower_signature=1, no_end_event=1, clock_reset=1, dry_run=1)
    assert 'SECRET' not in json.dumps(truth) and 'opp_hidden' not in json.dumps(truth)
    assert truth['files'][0]['bytes'] == 7


def test_early_defeat_requires_terminal_evidence_and_tower_geometry(tmp_path):
    ps = T.load_phase_stats()
    p = log(tmp_path/'early.jsonl', early=True)
    d, reason = ps.read_live(p)
    assert reason is None and d['early_terminal']
    tw = ps.towers(d['decisions'][-1])
    assert sum(v > 0 for k, v in tw.items() if k.startswith('own_')) == 0
    rows = [json.loads(s) for s in p.read_text().splitlines()]
    rows = [r for r in rows if r['event'] != 'stop']
    p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    assert ps.read_live(p)[1] == 'short_nonterminal_or_invalid_scorecard'


def test_wilson_and_era_ignore_paths_and_decision_rng():
    ps = T.load_phase_stats()
    assert T.wilson(16, 38) == pytest.approx(ps.wilson(16, 38)['ci95'])
    h = dict(live_options={'status': 'applied', 'path': 'a', 'from_file': {'own_effects': True}}, decision_seed=1)
    era = T.era_for(h)
    h['live_options']['path'] = 'b'
    h['decision_seed'] = 200
    assert T.era_for(h) == era
    h['live_options']['from_file']['own_effects'] = False
    assert T.era_for(h) != era
