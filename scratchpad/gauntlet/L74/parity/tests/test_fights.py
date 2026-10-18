"""fights.py live-side logic (no engine import): parsing, shadow rows, deployments, fight cutting, verdicts, locks."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import fights as F
from scratchpad.gauntlet.L74.parity.core import load_catalog

CAT, _ = load_catalog()
KNIGHT, GOLEM, IW_HERO, XBOW = 26000000, 26000009, 203000023, 27000008


def towers(own_princess=4424, opp_hp=4858):
    return [[1, 9000, 29000, -1, 7032, 7032, 12, 'k1'], [1, 3500, 25500, -1, 4424, 4424, 13, 'p1'],
            [1, 14500, 25500, -1, own_princess, own_princess, 13, 'p2'], [0, 9000, 3000, -1, 7728, 7728, 12, 'k0'],
            [0, 3500, 6500, -1, opp_hp, 4858, 13, 'p3'], [0, 14500, 6500, -1, 4858, 4858, 13, 'p4']]


def write(tmp, events, name='live_play_20261015_120000.jsonl'):
    p = Path(tmp) / name
    p.write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf8')
    return p


def frame(t, ents, **kw):
    return dict(event='frame', tick=t, my_side=1, elixir=5, ents=towers(**kw) + ents)


def test_main_account_signature(tmp_path):
    m, why = F.read_match(write(tmp_path, [frame(100, [], own_princess=4000)]))
    assert m is None and why == 'not_main_account'


def test_shadow_twin_dropped_and_addresses_hashed(tmp_path):
    ev = []
    for i, t in enumerate(range(100, 140, 2)):
        hp = 911 - 50*i
        ev.append(frame(t, [[1, 5000, 22000 - 100*i, IW_HERO, hp, 911, 15, '0xdeadbeef01'],
                            [1, 5000, 22000 - 100*i, IW_HERO, 911, 911, 15, '0xdeadbeef02']]))
    m, why = F.read_match(write(tmp_path, ev))
    assert why is None
    iw = [[b for b in bodies if b['card_id'] == IW_HERO] for _, bodies in m['frames']]
    assert all(len(x) == 1 for x in iw)                       # the full-hp shadow row is gone
    assert iw[-1][0]['hp'] == 911 - 50*19                      # the real (damaged) row is kept
    assert not any('0xdead' in b['id'] for _, bodies in m['frames'] for b in bodies)


def test_ram_and_rider_are_not_shadows(tmp_path):
    ram = 26000051
    ev = [frame(t, [[0, 3500, 14500 + 10*t, ram, 2822, 2822, 15, 'a'], [0, 3500, 14500 + 10*t, ram, 948, 948, 15, 'b']])
          for t in range(100, 130, 2)]
    m, _ = F.read_match(write(tmp_path, ev))
    assert all(len([b for b in bodies if b['card_id'] == ram]) == 2 for _, bodies in m['frames'])


def test_deployments_children_tap_point_and_mid_gap_tick(tmp_path):
    ev = [frame(100, []), frame(102, [])]
    # an own Knight: the play event rounds xy, the confirmation's 'intended' does not (0.65625*32 = 21.0, a tile edge)
    ev += [dict(event='play', tick=104, name='Knight', xy=[0.5, 0.6562]),
           dict(event='confirmed', tick=128, name='Knight', intended=[0.5, 0.65625])]
    for t in range(104, 128, 2):
        ev.append(frame(t, [[0, 9000, 10000, GOLEM, 8180, 8180, 15, 'g']]))
    for t in range(128, 160, 2):            # Knight first seen at 128; Golem dies at 140, a Golemite appears at 142
        ents = [[1, 9000, 21000, KNIGHT, 2822, 2822, 14 if t < 148 else 15, 'k']]
        if t <= 140:
            ents.append([0, 9000, 10000 + 10*(t-128), GOLEM, 100, 8180, 15, 'g'])
        else:
            ents.append([0, 9300, 10200, GOLEM, 1660, 1660, 15, 'c'])
        ev.append(frame(t, ents))
    m, _ = F.read_match(write(tmp_path, ev))
    events, delay = F.deployments(m, CAT)
    plays = [e for e in events if e['kind'] == 'play']
    names = [(e['side'], e['name']) for e in plays]
    assert (1, 'Knight') in names and names.count((0, 'Golem')) == 1    # the Golem once, never its Golemite
    knight = next(e for e in plays if e['name'] == 'Knight')
    assert (knight['x'], knight['y']) == (9000, 21000) and knight['source'] == 'own_tap'
    assert knight['tick'] == (126 + 1 + 128)//2 - 1                     # born mid-gap between frames 126 and 128
    assert delay == knight['tick'] - 104


def test_cut_starts_before_a_deploying_body_and_keeps_its_play():
    m = dict(side=1, frames=[])
    for t in range(100, 200, 2):
        bodies = []
        if t >= 120:      # a Knight first seen at 120, deploying until 140
            bodies.append(dict(id='k', side=1, x=9000, y=20000, card_id=KNIGHT, hp=2822, max_hp=2822,
                               kind=14 if t < 140 else 15, tower=False))
        m['frames'].append((t, bodies))
    events = [dict(kind='play', side=1, name='Knight', tick=118, source='own_tap'),
              dict(kind='play', side=0, name='Golem', tick=130, source='first_seen')]
    fights = F.cut(m, events, 40)
    golem = next(f for f in fights if f['anchor'] == 1)
    assert golem['t0'] == 118 and 0 in golem['events']               # walked back before the Knight's birth


def body(name, side, live_death=None, sim_death=None, born=100, setup=False, paired=True, q=(1, 1)):
    return dict(name=name, side=side, live_death=live_death, sim_death=sim_death, born=born, setup=setup, paired=paired,
                quarter=q[0], frames=q[1], form=0)


def test_fight_verdict_focus_tower_and_first_death():
    r = dict(anchor=dict(name='Knight', side=1, tick=100, source='own_tap'), sim_only=0,
             bodies=[body('Knight', 1, born=102), body('Golem', 0, live_death=150, sim_death=160, setup=True)],
             towers={'T0L': dict(live=500, sim=480), 'T1L': dict(live=0, sim=0)})
    v = F.fight_verdict(r, 150)
    assert v['agree'] and v['tower_err'] == 20
    r['towers']['T0L']['sim'] = 0
    assert not F.fight_verdict(r, 150)['agree']
    spell = dict(r, anchor=dict(name='Log', side=1, tick=100, source='own_spell_tap+delay'),
                 towers={'T0L': dict(live=0, sim=0)})
    spell['bodies'] = [body('Princess', 0, live_death=130, setup=True)]     # dies live only -> spell outcome differs
    assert not F.fight_verdict(spell, 150)['alive_agree']


def test_clean_modes():
    r = dict(flags={'opp_spell_seen:Fireball': 1, 'setup_form_swapped': 2})
    assert not F.is_clean(r) and F.is_clean(r, 'core') and F.is_clean(r, 'all')
    assert not F.is_clean(dict(flags={'setup_child_skipped': 1}), 'core')


def test_tower_locks():
    def fb(t, xbow_hp, tower_hp):
        return (t, [dict(id='x', side=1, x=15500, y=19500, card_id=XBOW, hp=xbow_hp, max_hp=2556, kind=13, tower=False),
                    dict(id='T0R', side=0, x=14500, y=6500, card_id=-1, hp=tower_hp, max_hp=4858, kind=13, tower=True)])
    m = dict(side=1, frames=[fb(100, 2556, 4858), fb(110, 2500, 4858), fb(122, 2480, 4760)])
    fight = dict(t0=122, frame0=2)
    setup = [dict(id='x', side=1, x=15500, y=19500, card_id=XBOW, proxy=False)]
    locks = F.tower_locks(m, fight, setup, CAT)
    assert len(locks) == 1 and locks[0][1] == (0, 14500, 6500)
    m['frames'][2] = fb(122, 2480, 4858)                        # tower untouched -> no lock
    assert F.tower_locks(m, fight, setup, CAT) == []


def test_cardless_row_off_a_tower_slot_is_not_a_tower(tmp_path):
    # a moving card-less row (an Elixir Golem's blob) sharing the frame must not overwrite a tower's hp
    ev = [frame(t, [[0, 14000 - 100*t, 17000, -1, 293, 293, 14, 'blob']], opp_hp=2905) for t in range(100, 110, 2)]
    m, why = F.read_match(write(tmp_path, ev))
    assert why is None
    for _, bodies in m['frames']:
        towers_ = [b for b in bodies if b['tower']]
        assert len(towers_) == 6 and len({b['id'] for b in towers_}) == 6
        assert next(b['hp'] for b in towers_ if b['id'] == 'T0L') == 2905
        assert any(not b['tower'] and b['card_id'] == -1 for b in bodies)


def test_spell_tick_waits_for_elixir(tmp_path):
    ev = [frame(100, []), frame(102, [])]
    ev += [dict(event='play', tick=104, name='Knight', xy=[0.5, 0.6562], elixir=6.0),
           dict(event='confirmed', tick=128, name='Knight', intended=[0.5, 0.65625])]
    ev += [frame(t, [[1, 9000, 21000, KNIGHT, 2822, 2822, 14, 'k']]) for t in range(128, 140, 2)]
    ev += [dict(event='play', tick=200, name='Log', xy=[0.5, 0.6], elixir=1.5),          # 0.5 short at single elixir
           dict(event='confirmed', tick=230, name='Log', intended=[0.5, 0.6]),
           dict(event='play', tick=300, name='Log', xy=[0.5, 0.6], elixir=4.0),
           dict(event='confirmed', tick=330, name='Log', intended=[0.5, 0.6])]
    ev += [frame(t, []) for t in range(140, 400, 10)]
    m, _ = F.read_match(write(tmp_path, ev))
    events, delay = F.deployments(m, CAT)
    logs = [e for e in events if e['name'] == 'Log']
    assert [e['tick'] - e['tap'] for e in logs] == [round(delay + .5*F.TICKS_PER_ELIXIR), round(delay)]
    assert F.elixir_wait(3000, 1.0, 2) == F.TICKS_PER_ELIXIR/2 and F.elixir_wait(100, None, 2) == 0


def test_spell_drops_window():
    def fb(t, hp):
        return (t, [dict(id='p', side=0, x=9000, y=12000, card_id=KNIGHT, hp=hp, max_hp=2822, kind=15, tower=False)])
    m = dict(side=1, frames=[fb(100, 2822), fb(104, 2432), fb(110, 2432), fb(200, 2042)])
    ev = [dict(source='own_spell_tap+delay', name='Log', tick=102)]
    assert F.spell_drops(m, ev, 'Log') == {390: 1}                  # the drop at 200 is outside the 70-tick window


def test_spell_levels_pick_the_level_whose_damage_is_seen():
    class Eng:
        ids = {'Log': 1}
        def spell_damage(self, name, side, lv):
            return {16: 429, 15: 390, 14: 355}.get(lv)
        def stats(self, name):
            return {}                      # no crown % on the card: tower drops are not used as evidence
    def fb(t, hp, k='p'):
        return (t, [dict(id=k, side=0, x=9000, y=12000, card_id=KNIGHT, hp=hp, max_hp=2822, kind=15, tower=False)])
    m = dict(side=1, frames=[fb(100, 2822), fb(104, 2432), fb(300, 2432), fb(304, 2042)])
    ev = [dict(source='own_spell_tap+delay', name='Log', tick=102), dict(source='own_spell_tap+delay', name='Log', tick=302)]
    assert F.spell_levels(m, ev, Eng(), CAT) == {(1, 'Log'): 15}
    # one exact drop: enough when it is the only level with evidence (log round 2: an opponent spell cast once or twice)
    assert F.spell_levels(dict(m, frames=m['frames'][:2]), ev, Eng(), CAT) == {(1, 'Log'): 15}
    # no drop that equals any level's damage: no level
    assert F.spell_levels(dict(m, frames=[fb(100, 2822), fb(104, 2500)]), ev, Eng(), CAT) == {}


def test_volley_rows_inject_one_central_arrow():
    """H-VOLLEY: a firer's several in-flight rows at one target (the Princess's 5-arrow volley) inject only the row nearest
    the firer -> target line; a lone row and other firers' rows are kept."""
    catalog, by_name = load_catalog()
    pid = by_name['Princess']['card_id']
    bd = lambda i, side, x, y, cid: dict(id=i, side=side, x=x, y=y, card_id=cid, hp=500, max_hp=500, tower=False)
    start = [bd('pr', 1, 14500, 17500, pid), bd('te', 0, 9000, 12000, 27000006), bd('kn', 0, 12000, 9000, KNIGHT),
             bd('k2', 1, 12000, 9500, KNIGHT)]
    rows = [(1, x, y, pid, 0, 0, s, 'pr', 'te') for s, (x, y) in enumerate(
        [(14126, 17250), (14182, 17181), (14108, 17279), (14173, 17191), (14214, 17152)])]
    rows.append((1, 13000, 11000, pid, 0, 0, 9, 'pr', 'kn'))     # a lone row at another target
    m = dict(proj={100: rows})
    out = F.inflight_shots(m, dict(t0=100), start, catalog, {}, (15, 15))
    at_te = [(s['x'], s['y']) for s in out if s['tgt'] == 'te']
    assert at_te == [(14182, 17181)]
    assert next(s for s in out if s['tgt'] == 'te')['volley'] == 5
    assert [s['tgt'] for s in out if s['tgt'] != 'te'] == ['kn'] and 'volley' not in out[-1]


def test_hero_iw_cast_dated_from_its_cube():
    """H-CUBE-DATE: a Hero IW cast (state-10 frame) whose ice cube is first seen within 20 ticks is dated CUBE_LAG before the
    cube's sighting; without a cube it keeps the state-10 gap estimate."""
    catalog, _ = load_catalog()
    hero = dict(id='h', side=0, x=9000, y=8000, card_id=IW_HERO, hp=911, max_hp=911, tower=False, kind=13)
    def fr(t, state, cube=False):
        bodies = [dict(hero, state=state)]
        if cube:
            bodies.append(dict(id='c', side=0, x=9000, y=12000, card_id=IW_HERO, hp=352, max_hp=352, tower=False, kind=13, state=4))
        return (t, bodies)
    m = dict(frames=[fr(96, 1), fr(98, 1), fr(100, F.CAST), fr(102, F.CAST, cube=True), fr(104, 1, cube=True)], proj={}, fx={})
    ab = [e for e in F.seen_casts(m, catalog) if e['kind'] == 'ability']
    assert [(e["tick"], e.get("cube")) for e in ab] == [(102 - F.CUBE_LAG, 102)]
    # a capture that stamps the cube's creation (phase-3b births) dates the press exactly: CUBE_LAG before it, no window
    m["births"] = {77: [101, -1]}
    m["frames"] = [(t, [dict(b, gen=77) if b["id"] == "c" else b for b in bodies]) for t, bodies in m["frames"]]
    ab = [e for e in F.seen_casts(m, catalog) if e["kind"] == "ability"]
    assert [(e["tick"], e["lo"], e["hi"], e.get("cube_born")) for e in ab] == [(101 - F.CUBE_LAG,) * 3 + (101,)]
    del m["births"]
    m['frames'] = [fr(96, 1), fr(98, 1), fr(100, F.CAST), fr(102, F.CAST), fr(104, 1)]
    ab = [e for e in F.seen_casts(m, catalog) if e['kind'] == 'ability']
    assert [(e['tick'], e.get('cube')) for e in ab] == [(98, None)]
