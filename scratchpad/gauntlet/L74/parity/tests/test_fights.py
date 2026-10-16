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
