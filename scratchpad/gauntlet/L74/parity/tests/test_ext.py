"""fights.py on ext frame logs (ents_state / proj / fx, READER_VALIDATION_1016.md): live side only, no engine import."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import fights as F
from scratchpad.gauntlet.L74.parity.core import load_catalog

CAT, _ = load_catalog()
KNIGHT, HERO_KNIGHT, TESLA, PRINCE, MK = 26000000, 203000000, 27000006, 26000016, 26000055
LOG, FREEZE, GBARREL = 28000011, 28000005, 28000004
LIFE = {'Freeze': 3500}.get


def towers(princess=3052):
    return [[s, x, y, -1, hp, hp, 12 if x == 9000 else 13, f't{s}{x}']
            for s, (ky, py) in ((0, (3000, 6500)), (1, (29000, 25500)))
            for x, y, hp in ((9000, ky, 4824), (3500, py, princess), (14500, py, princess))]


def xframe(t, ents=(), states=None, proj=(), fx=(), ext=True):
    """Frame event; ents rows [side, x, y, card, hp, max_hp, kind, addr]; states parallel to ents ([state] or None)."""
    ents = towers() + [list(e) for e in ents]
    j = dict(event='frame', tick=t, my_side=1, elixir=5, ents=ents)
    if ext:
        st = [[0, 0, 11, 5000000 + i] for i in range(6)] + [[s, 0, 11, 6000000 + hash(e[7]) % 1000]
                                                            for s, e in zip(states or [1]*len(ents[6:]), ents[6:])]
        j.update(ents_state=st, proj=[list(p) for p in proj], fx=[list(x) for x in fx])
    return j


def write(tmp, events, name='live_play_20261016_120000.jsonl'):
    p = Path(tmp) / name
    p.write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf8')
    return p


HAND = dict(event='decision', tick=100, public=dict(own_hand=[dict(name='Xbow'), dict(name='Tesla')], raw_projectiles=[]))


def test_capped_towers_count_only_for_an_ext_icebow_log(tmp_path):
    k = [[0, 9000, 20000, KNIGHT, 1000, 1000, 15, 'a']]
    m, why = F.read_match(write(tmp_path, [HAND, xframe(100, k), xframe(102, k)]))
    assert why is None and m['ext']
    assert F.read_match(write(tmp_path, [HAND, xframe(100, k, ext=False)], 'old.jsonl'))[1] == 'not_main_account'
    assert F.read_match(write(tmp_path, [xframe(100, k)], 'nohand.jsonl'))[1] == 'not_main_account'


def test_state_generation_and_projectile_ends_are_frame_body_ids(tmp_path):
    ents = [[1, 9000, 12000, KNIGHT, 1000, 1000, 15, '0xaaaa'], [0, 9000, 15000, KNIGHT, 900, 1000, 15, '0xbbbb']]
    shot = [1, 9000, 12500, -1, 9000, 15000, '0xcccc', 4000001, '0xaaaa', '0xbbbb']
    m, _ = F.read_match(write(tmp_path, [HAND, xframe(100, ents, [2, 1], [shot])]))
    _, bodies = m['frames'][0]
    a, b = (next(bd for bd in bodies if bd['x'] == 9000 and bd['y'] == y) for y in (12000, 15000))
    assert (a['state'], b['state']) == (2, 1) and 'gen' in a
    assert m['proj'][100] == [(1, 9000, 12500, -1, 9000, 15000, 4000001, a['id'], b['id'])]
    assert not any('0x' in str(r) for r in m['proj'][100])                # addresses are never kept


def ext_match():
    """Opponent (side 0): a Log thrown then rolling, a Freeze, a Hero Knight cast, a Goblin Barrel and its goblins."""
    m = dict(side=1, ext=True, frames=[], proj={}, fx={}, plays=[], abilities=[], shots=[])
    for t in range(100, 520, 2):
        bodies = [dict(id='hk', side=0, x=4000, y=20000, card_id=HERO_KNIGHT, hp=2000, max_hp=2000, kind=15, tower=False,
                       state=F.CAST if 400 <= t <= 420 else 2)]
        if t >= 470:
            bodies += [dict(id=f'g{i}', side=0, x=3500 + 500*i, y=25500, card_id=GBARREL, hp=202, max_hp=202, kind=14,
                            tower=False, state=4) for i in range(3)]
        m['frames'].append((t, bodies))
        m['proj'][t] = ([(0, 9000, 21000, LOG, 9500, 17500, 1, 'T0K', None)] if 200 <= t <= 210 else []) + \
                       ([(0, 9500, 17000, LOG, 9500, 7400, 2, None, None)] if 212 <= t <= 260 else []) + \
                       ([(0, 9000, 5000, GBARREL, 3500, 25500, 3, 'T0K', None)] if 440 <= t <= 466 else [])
        m['fx'][t] = [(0, 5500, 5500, FREEZE, 3400 - 50*(t-300), 11, 9)] if 300 <= t <= 366 else []
    return m


def test_seen_spells_and_hero_casts_are_events():
    ev, _ = F.deployments(ext_match(), CAT, LIFE)
    seen = [(e['kind'], e['side'], e['name'], e['tick'], e.get('x'), e.get('y')) for e in ev if e['source'] in ('spell_seen', 'cast_seen')]
    assert seen == [('play', 0, 'Log', (198+1+200)//2 - 1, 9500, 17500),       # throw + roll = one cast at the throw's point
                    ('play', 0, 'Freeze', 298 - 1, 5500, 5500),                 # 3400 left at 300 of a 3500 life: made at 298
                    ('ability', 0, 'Knight', (398+1+400)//2 - 1, None, None),   # first state-10 frame of the burst
                    ('play', 0, 'GoblinBarrel', (438+1+440)//2 - 1, 3500, 25500)]
    log = next(e for e in ev if e['name'] == 'Log')
    assert (log['lo'], log['hi'], log['end']) == (198, 199, 260)
    assert not any(e.get('spell_spawned') for e in ev)                         # the barrel's goblins come from the cast


def test_old_log_events_have_no_seen_casts():
    m = ext_match(); m['ext'] = False
    ev, _ = F.deployments(m, CAT, LIFE)
    assert not any(e['source'] in ('spell_seen', 'cast_seen') for e in ev)
    assert any(e.get('spell_spawned') for e in ev)                             # goblins stay a first-seen spell body


def test_an_own_spell_tap_with_a_seen_cast_is_not_doubled():
    m = ext_match(); m['side'] = 0
    m['plays'] = [dict(tick=180, name='Log', x=9500, y=17500, form=0, elixir=9), dict(tick=900, name='Log', x=1, y=1, form=0, elixir=9)]
    ev, _ = F.deployments(m, CAT, LIFE)
    logs = [e['source'] for e in ev if e['name'] == 'Log']
    assert sorted(logs) == ['own_spell_tap+delay', 'spell_seen']               # the unseen tap at 900 stays


def test_seen_targets_latest_shot_with_both_ends_on_board():
    setup = [dict(id='x', side=1, x=9000, y=18000), dict(id='k', side=0, x=9000, y=21000)]
    start = [dict(id='T0L', side=0, x=3500, y=25500, hp=3000, tower=True), dict(id='T0R', side=0, x=14500, y=25500, hp=0, tower=True)]
    m = dict(frames=[(t, []) for t in range(80, 102, 2)], proj={
        84: [(1, 0, 0, 1, 0, 0, 1, 'x', 'k')],
        96: [(1, 0, 0, 1, 0, 0, 2, 'x', 'T0L'), (0, 0, 0, 1, 0, 0, 3, 'T0R', 'x'), (0, 0, 0, 1, 0, 0, 4, 'gone', 'x')]})
    got = F.seen_targets(m, dict(t0=100, frame0=10), setup, start)
    assert got == [(('body', setup[0]), ('tower', 0, 3500, 25500))]          # 84 is older than 20 ticks; T0R is down


class Eng:
    S = {'Tesla': dict(hides_when_not_attacking=True, hide_time_ms=800), 'Prince': dict(speed=60, charge=dict(charge_range_raw=250)),
         'Freeze': dict(area_damage_radius_milli=3000)}

    def stats(self, name):
        return self.S.get(name, {})

    def effect_life(self, name, key='life_duration_ms'):
        return 3500

    def slow_ids(self):
        return dict(hero_cold=66, hero=67, base=1)

    def spawn_table(self, name, probe=True):
        return {'Tombstone': {1: (500, 1), 2: (3500, 0)}}.get(name)


def test_start_state_tesla_charge_jump_and_freeze():
    def bd(i, card, x, y, st, side=1):
        return dict(id=i, side=side, x=x, y=y, card_id=card, hp=500, max_hp=500, kind=15, tower=False, state=st, gen=hash(i))
    frames = []
    for t in range(80, 102, 2):
        frames.append((t, [bd('t', TESLA, 9000, 10000, 2), bd('h', TESLA, 3000, 10000, 0),
                           bd('p', PRINCE, 3500, 20000 - 59*(t-80), 1 if t > 84 else 2, 0),      # walking since 86
                           bd('c', PRINCE, 14500, 20000 - (59 if t < 98 else 120)*(t-80), 1, 0),  # charging at t0
                           bd('mk', MK, 9000, 16000, 3, 0), bd('k', KNIGHT, 5000, 5500, 2),
                           dict(id='T1L', side=1, x=3500, y=6500, hp=3052, tower=True)]))
    start = frames[-1][1]
    setup = [dict(id=b['id'], side=b['side'], x=b['x'], y=b['y']) for b in start if not b['tower']]
    freeze = dict(kind='play', side=0, name='Freeze', source='spell_seen', made=96, x=5500, y=5500)
    m = dict(frames=frames + [(102, [])], buffs={})
    edits, flags = F.start_state(Eng(), m, dict(t0=100, frame0=10), setup, start, [freeze], CAT)
    got = {(r[1]['id'] if r[0] == 'body' else r[1:]): kv for r, kv in edits}
    assert got['t'] == dict(hide='Up', hide_ms=800) and got['h'] == dict(hide='Hidden', hide_ms=0)
    assert got['p'] == dict(charge_progress=round(59*(100-86)*F.CHARGE_PER_MT))   # walked since its first state-1 frame
    assert got['c'] == dict(charged=True, charge_progress=0)
    assert flags['setup_mid_jump:3'] == 1
    assert got['k'] == dict(stun_ms=3500 - 50*4) and got[(1, 3500, 6500)] == dict(stun_ms=3500 - 50*4)
    # phase-2 buffs win over the effect: a Freeze buff on the Knight, an Ice Wizard slow is seeded as the SIM's buff,
    # anything else is only flagged
    m['buffs'] = {98: {hash('k'): [('Freeze', 1000), ('IceWizardHeroSlow', 2000), ('Rage', 1500)]}}
    edits, flags = F.start_state(Eng(), m, dict(t0=100, frame0=10), setup, start, [freeze], CAT)
    assert [(r[1]['id'], kv) for r, kv in edits if 'stun_ms' in kv] == [('k', dict(stun_ms=900))]
    assert [(r[1]['id'], kv) for r, kv in edits if 'buff' in kv] == [('k', dict(buff=(67, 1900)))]
    assert flags['setup_slow_buff'] == 1 and flags['status_unset:Rage'] == 1 and not flags['status_unset:IceWizardHeroSlow']


def test_mid_jump_is_a_strict_blocker():
    assert not F.is_clean(dict(flags={'setup_mid_jump:3': 1}), 'core')
    assert F.is_clean(dict(flags={'status_unset:IceWizardHeroSlow': 1, 'setup_target_seen': 2}), 'strict')


def test_infer_attacks_last_hit_travel_and_ambiguity():
    def fr(t, vhp, whp, extra=()):
        b = [dict(id='k', side=1, x=9000, y=10000, hp=900, tower=False), dict(id='w', side=1, x=3000, y=10000, hp=500, tower=False),
             dict(id='v', side=0, x=9000, y=11000, hp=vhp, tower=False), dict(id='u', side=0, x=3000, y=12000, hp=whp, tower=False)]
        return (t, b + list(extra))
    hpv = lambda t: 2000 - 202*(t >= 72) - 202*(t >= 96)
    hpu = lambda t: 1000 - 89*(t >= 98)
    m = dict(frames=[fr(t, hpv(t), hpu(t)) for t in range(60, 102, 2)])
    atk = dict(k=dict(dmg=202, dmg_tower=202, reach=2500, speed=None), w=dict(dmg=89, dmg_tower=89, reach=6000, speed=700))
    got = F.infer_attacks(m, dict(t0=100, frame0=20), atk)
    assert got == {'k': (95, 96, 'v'), 'w': (97-3, 98-3, 'u')}                 # 2000 mt at 700 mt/tick: 3 ticks of travel
    twin = dict(atk, k2=dict(atk['k']))                                          # a second Knight in reach: the drop is ambiguous
    m2 = dict(frames=[(t, b + [dict(id='k2', side=1, x=9500, y=10000, hp=900, tower=False)]) for t, b in m['frames']])
    assert 'k' not in F.infer_attacks(m2, dict(t0=100, frame0=20), twin)


def test_iw_shots_seed_the_slow_left_by_a_recent_hit():
    """An Ice Wizard projectile last seen at t (it hits at t + 1) leaves IW_SLOW_MS - 50 x (t0 - t - 1) of slow; one
    still flying at t0, or older than IW_SLOW_MS, seeds nothing; the latest hit per target wins; the form is the shot's."""
    hero, base = 203000023, 26000023
    proj = {60: [(1, 0, 0, hero, 0, 0, 1, 'w', 'a')],                          # re-armed by the hit after 80
            80: [(1, 0, 0, hero, 0, 0, 2, 'w', 'a'), (1, 0, 0, KNIGHT, 0, 0, 3, 'x', 'b')],   # a Knight's shot: no slow
            90: [(1, 0, 0, base, 0, 0, 4, None, 'c')],                          # shooter gone: the shot's card says base
            100: [(1, 0, 0, hero, 0, 0, 5, 'w', 'd')]}                          # in flight at t0
    m = dict(frames=[(t, []) for t in range(40, 102, 2)], proj=proj)
    got = F.iw_shots(m, dict(t0=100, frame0=30), CAT)
    assert got == {'a': (2, 2500 - 50*19), 'c': (0, 2500 - 50*9)}
    m['proj'] = {40: [(1, 0, 0, hero, 0, 0, 1, 'w', 'a')]}                     # 2500 - 50 x 59 <= 0
    assert F.iw_shots(m, dict(t0=100, frame0=30), CAT) == {}


def test_set_buff_uses_the_entity_s_own_flat_slots():
    empty = lambda: dict(id=0, ms=0, pulse_ms=0, source=None)
    E = dict(alive=[True]*3, buffs=[empty() for _ in range(12)])
    E['buffs'][4] = dict(empty(), id=9, ms=100)                                # entity 1's first slot is taken
    assert F.set_buff(E, 1, 67, 1900) and E['buffs'][5] == dict(empty(), id=67, ms=1900)
    assert [b['id'] for b in E['buffs']] == [0]*4 + [9, 67, 0, 0] + [0]*4
    for j in range(6, 8):
        E['buffs'][j]['id'] = 1
    assert not F.set_buff(E, 1, 67, 1900)                                     # no free slot left


def test_spawner_timer_from_the_last_wave_seen():
    """A Tombstone whose last pair of skeletons was born at 79/89 (mid-gap of first sightings 80/90) is 3500 - 50 x 11
    ms from its next wave at t0 = 100: what the SIM record holds 11 ticks after the 2nd child of a wave. A lone first
    child gives the 1st-child state; a wave whose next child is overdue, or children too far from it, seed nothing."""
    TOMB = next(k for k, v in CAT.items() if v['display_name'] == 'Tombstone' and k < 100000000)
    tomb = lambda: dict(id='tb', side=0, x=9000, y=12000, card_id=TOMB, hp=400, max_hp=846, kind=13, tower=False)
    kid = lambda i, t: dict(id=i, side=0, x=9100, y=12900, card_id=TOMB, hp=130, max_hp=130, kind=14, tower=False)
    def run(births, t0=100, far=False):
        frames = []
        for t in range(40, t0 + 2, 2):
            frames.append((t, [tomb()] + [dict(kid(i, b), y=12900 + (6000 if far else 0)) for i, b in births if b <= t]))
        setup = [dict(id='tb', side=0, x=9000, y=12000)]
        m = dict(frames=frames, buffs={})
        i0 = [t for t, _ in frames].index(t0)
        return F.start_state(Eng(), m, dict(t0=t0, frame0=i0), setup, frames[i0][1], [], CAT)
    edits, flags = run([('a', 80), ('b', 90)])
    assert [kv for _, kv in edits] == [dict(spawn_ms=3500 - 50*11, spawn_wave_left=0)] and flags['setup_spawner_seen'] == 1
    edits, _ = run([('b', 98)])                                     # 1st child born 97: its 2nd is 500 - 150 ms away
    assert [kv for _, kv in edits] == [dict(spawn_ms=500 - 50*3, spawn_wave_left=1)]
    edits, flags = run([('b', 90)])                                  # 1st child born 89: its 2nd is overdue (not seen)
    assert edits == [] and flags['setup_spawner_overdue'] == 1
    edits, flags = run([('a', 80), ('b', 90)], far=True)
    assert edits == [] and flags['setup_spawner_unseen'] == 1


def test_phase3_state_seeds_target_and_attack_from_the_reader():
    """Phase-3 rows at t0 set attack_ms / load / phase / target as read; a row one tick old is advanced by the measured
    rule (slowed Knight 1190 -> 1225 crosses 1200: load re-armed, Cooldown; frozen: held); a proxy body, a target off
    the board and the fields the SIM lacks are flagged, not set. The seeded ids are returned as observed."""
    XBOW = next(k for k, v in CAT.items() if v['display_name'] == 'Xbow' and k < 100000000)
    class E3(Eng):
        S = dict(Eng.S, Knight=dict(hit_speed_ms=1200, load_time_ms=700), Xbow=dict(hit_speed_ms=400, projectile=dict(speed=1)),
                 PrincessTower=dict(hit_speed_ms=800, projectile=dict(speed=1)))
    bd = lambda i, card, g, side=1: dict(id=i, side=side, x=9000, y=10000 + g, card_id=card, hp=500, max_hp=500, kind=13,
                                         tower=False, gen=g)
    start = [bd('k', KNIGHT, 1), bd('x', XBOW, 2), bd('f', KNIGHT, 3), bd('p', KNIGHT, 4), bd('e', KNIGHT, 5, 0),
             dict(id='T0L', side=0, x=3500, y=6500, hp=3052, tower=True, gen=9)]
    setup = [dict(id=b['id'], side=b['side'], x=b['x'], y=b['y'], proxy=b['id'] == 'p') for b in start if not b['tower']]
    rows = {1: [5, None, 1190, 0, 0, 0], 2: [9, 5, 2400, 0, 0, 1], 3: [5, None, 1850, 300, 0, 0],
            4: [5, None, 600, 0, 0, 0], 5: [77, None, 0, 200, 40, 0]}
    m = dict(attacks={100: rows}, buffs={98: {1: [('IceWizardHeroSlow', 2000)], 3: [('IceWizardHeroFreeze', 999999)]}})
    edits, seen, flags = F.phase3_state(E3(), m, dict(t0=100), setup, start, CAT)
    got = {r[1]['id']: kv for r, kv in edits}
    assert seen == {'k', 'x', 'f', 'e'} and 'p' not in got                      # the proxy is not seeded
    assert got['k'] == dict(attack_ms=1190, attack_load_ms=0, attack_phase='Windup', target=('body', setup[4]), target_locked=False)
    assert got['x'] == dict(attack_ms=2400, attack_load_ms=0, attack_phase='Cooldown', target=('tower', 0, 3500, 6500),
                            target_locked=False)                                # fire tick: Cooldown, so unlocked
    assert got['e']['target'] is None and got['e']['attack_phase'] == 'Idle'
    assert flags == dict(setup_p3_attack=4, setup_p3_target_unresolved=1, setup_p3_pre_unset=1, setup_p3_seq_unset=1)
    m['attacks'] = {99: rows}                                                   # one tick old: advanced
    got = {r[1]['id']: kv for r, kv in F.phase3_state(E3(), m, dict(t0=100), setup, start, CAT)[0]}
    assert (got['k']['attack_ms'], got['k']['attack_load_ms'], got['k']['attack_phase']) == (1225, 700, 'Cooldown')
    assert (got['f']['attack_ms'], got['f']['attack_load_ms']) == (1850, 300)    # frozen: both held
    assert (got['x']['attack_ms'], got['x']['attack_phase'], got['x']['target_locked']) == (2450, 'Windup', True)
    assert got['e']['attack_load_ms'] == 150
    m['attacks'] = {98: rows}                                                   # older than one tick: nothing
    assert F.phase3_state(E3(), m, dict(t0=100), setup, start, CAT)[0] == []


def test_phase3_attacks_from_a_capture_or_the_exported_file(tmp_path, monkeypatch):
    cap = tmp_path/'p3_x'; cap.mkdir()
    (cap/'run.json').write_text(json.dumps(dict(live_log='live_play_a.jsonl')))
    a = dict(target_gen=7, prev_target_gen=None, progress_raw=850, load_raw=0, pre_raw=0, seq_idx=0)
    rows = [dict(game_tick=10, phase3=dict(valid=True, bodies=[dict(generation=5, attack=a), dict(generation=6, attack=None)])),
            dict(game_tick=11, phase3=dict(valid=False, bodies=[]))]
    (cap/'frames.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    monkeypatch.setattr(F, 'P3_DIR', tmp_path)
    monkeypatch.delenv('PARITY_ATTACKS', raising=False)
    want = {10: {5: [7, None, 850, 0, 0, 0]}}
    assert F.phase3_attacks('x/live_play_a.jsonl') == want and F.phase3_attacks('live_play_b.jsonl') == {}
    f = tmp_path/'att.json'; f.write_text(json.dumps({'live_play_a.jsonl': want}))
    monkeypatch.setenv('PARITY_ATTACKS', str(f))
    assert F.phase3_attacks('live_play_a.jsonl') == want
