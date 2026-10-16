"""fights.py tolerant card scoring and noise-ceiling logic (no engine import): views, agreement, history, table."""
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import fights as F
from scratchpad.gauntlet.L74.parity.core import load_catalog

CAT, _ = load_catalog()
KNIGHT, GOLEM, SKEL = 26000000, 26000009, 26000010


def b(id_, side, x, y, cid, hp, tower=False):
    return dict(id=id_, side=side, x=x, y=y, card_id=cid, hp=hp, max_hp=hp, kind=15, tower=tower)


def test_jitter_tick_stays_in_the_frame_gap_or_the_residuals():
    rng = random.Random(1)
    draws = {F.jitter_tick(dict(tick=120, lo=120, hi=121), rng) for _ in range(50)}
    assert draws == {120, 121}
    draws = {F.jitter_tick(dict(tick=300, jit=[-2, 0, 3]), rng) for _ in range(80)}
    assert draws == {298, 300, 303}
    assert F.jitter_tick(dict(tick=7), rng) == 7


def test_card_agree_tolerances():
    v = lambda own, tower=0: dict(spell=False, own=own, tower=tower)
    assert F.card_agree(v([100, None]), v([110, None]))[0]                # death 10 ticks (0.5 s) apart: same
    assert not F.card_agree(v([100, None]), v([111, None]))[0]            # 11 ticks: not
    assert not F.card_agree(v([None]), v([150]))[0]                       # survives vs dies
    assert not F.card_agree(v([100]), v([100, 120]))[0]                   # a body missing on one side
    swarm = [100]*10
    assert F.card_agree(v(swarm), v(swarm[:9] + [None]))[0]               # 1 of 10 may differ (floor(0.1 n))
    assert not F.card_agree(v(swarm), v(swarm[:8] + [None, None]))[0]
    assert F.card_agree(v([], 0), v([], 100))[0]                          # tower: floor 100
    assert not F.card_agree(v([], 0), v([], 101))[0]
    assert F.card_agree(v([], 2000), v([], 2200))[0]                      # 10% of the larger
    assert not F.card_agree(v([], 2000), v([], 2250))[0]


def test_card_agree_spell_scores_the_union_of_bodies_hit():
    s = lambda hit, enemy: dict(spell=True, hit=hit, enemy=enemy, tower=0)
    a = s(['p', 'q'], {'p': 130, 'q': None, 'r': None})
    assert F.card_agree(a, s(['p'], {'p': 134, 'q': None, 'r': None}))[:3] == (True, 0, 2)   # q hit live only, both survive
    assert F.card_agree(a, s(['p'], {'p': 134, 'q': 160, 'r': None}))[:3] == (False, 1, 2)
    assert F.card_agree(a, s(['p'], {'p': 134}))[:3] == (False, 1, 2)                         # q not paired: missing


def test_card_view_own_bodies_and_tower_share():
    rows = []
    for t in range(100, 142, 2):
        live = [b('T0L', 0, 3500, 6500, -1, 4000 if t <= 110 else 3800, tower=True),
                b('old', 1, 9000, 20000, KNIGHT, 2000)]                          # the same card already on the board
        if t >= 104:
            live.append(b('k1', 1, 3500, 8500, KNIGHT, 2000))                       # anchor body, in reach of T0L
            if t <= 120:
                live.append(b('k2', 1, 9000, 15000, KNIGHT, 2000))                  # anchor body, dies after 120
        live.append(b('g', 1, 3600, 8600, GOLEM, 8000))                             # another card in reach: shares
        rows.append((t, live, []))
    anchor = dict(kind='play', side=1, name='Knight', tick=103)
    v = F.card_view(rows, 1, {}, anchor, 999, None, lambda n: 1700, CAT)
    assert v == dict(spell=False, own=[120, None], tower=100)                     # 200 split over 2 cards


def test_card_view_spell_hit_set_and_crown_damage():
    rows = []
    for t in range(100, 202, 2):
        live = [b('T0L', 0, 3500, 6500, -1, 4000 if t < 116 else 3902, tower=True)]
        live.append(b('e1', 0, 4000, 9000, KNIGHT, 2000 if t < 112 else 1610))      # a 390 drop: hit
        if t <= 112:
            live.append(b('e2', 0, 4200, 9000, SKEL, 81))                           # dies 112 -> 114: hit
        live.append(b('e3', 0, 4400, 9000, GOLEM, 8000 if t < 112 else 7950))       # a 50 drop: not hit
        if t <= 180:
            live.append(b('e4', 0, 4600, 9000, KNIGHT, 2000 if t < 112 else 1610))  # hit, killed after the window
        if t <= 120:
            live.append(b('e5', 0, 17000, 31000, SKEL, 81))                         # dies out of the spell's reach
        rows.append((t, live, []))
    anchor = dict(kind='play', side=1, name='Log', tick=110)
    spell = dict(d=390, dt=51, x=4000, y=12000, reach=13400)
    v = F.card_view(rows, 1, {}, anchor, 999, spell, lambda n: 1000, CAT)
    assert v['spell'] and v['hit'] == ['e1', 'e2', 'e4']
    assert v['enemy'] == {'e1': None, 'e2': 112, 'e3': None, 'e4': None, 'e5': None}   # e4 dies 68 ticks after its hit
    assert v['tower'] == 51                                                        # a 98 drop >= 80% of 51, in reach


def test_a_tunnelling_miner_is_played_where_it_surfaces(tmp_path):
    miner = 26000032
    towers = [[1, 9000, 29000, -1, 7032, 7032, 12, 'k1'], [1, 3500, 25500, -1, 4424, 4424, 13, 'p1'],
              [1, 14500, 25500, -1, 4424, 4424, 13, 'p2'], [0, 9000, 3000, -1, 7728, 7728, 12, 'k0'],
              [0, 3500, 6500, -1, 4858, 4858, 13, 'p3'], [0, 14500, 6500, -1, 4858, 4858, 13, 'p4']]
    ev = [dict(event='frame', tick=t, my_side=1, ents=list(towers)) for t in (96, 98)]
    for i, t in enumerate(range(100, 140, 2)):   # seen active while tunnelling from its own side, deploying from 120
        x, y = (9000 - 300*i, 5000 + 1000*i) if t < 120 else (3000, 15000)
        ev.append(dict(event='frame', tick=t, my_side=1, ents=towers + [[0, x, y, miner, 1000, 1000, 15 if t < 120 else 14, 'm']]))
    p = tmp_path / 'live_play_20261015_120000.jsonl'
    p.write_text(''.join(json.dumps(e) + '\n' for e in ev), encoding='utf8')
    m, why = F.read_match(p)
    events, _ = F.deployments(m, CAT)
    e = next(e for e in events if e['name'] == 'Miner')
    assert (e['x'], e['y'], e.get('dig'), e['tick'], e['lo'], e['hi']) == (3000, 15000, True, 98, 98, 99)


class FakeEng:
    ids = {'Knight': 0, 'Golem': 1}
    cat = [dict(flying=False), dict(flying=False)]
    _s = {'Knight': dict(range_milli=1200, collision_radius_milli=500, attacks_ground=True),
          'Golem': dict(range_milli=750, collision_radius_milli=750, attacks_ground=True, target_only_buildings=True)}

    def stats(self, name):
        return self._s.get(name, {})


def test_engagement_reads_reach_history():
    frames = []
    for t in range(80, 112, 2):
        bodies = [b('A', 1, 9000, 20000, KNIGHT, 2000), b('B', 1, 3000, 20000, KNIGHT, 2000),
                  b('G', 0, 9000, 20000 - (5000 if t <= 104 else 2000), GOLEM, 8000)]
        if t <= 104:
            bodies.append(b('C', 0, 3000, 18500, KNIGHT, 100))
        frames.append((t, bodies))
    h = F.engagement(dict(frames=frames), dict(t0=110, frame0=len(frames)-1), FakeEng(), CAT)
    assert h['A'] == (5, None, True)            # Golem in reach from 106 to t0 110
    assert h['B'] == (0, 6, True)               # its enemy was last in reach at 104
    assert h['G'][:2] == (0, None)              # a Golem never has a building in reach here


def test_ceiling_table_flags(tmp_path):
    ok = dict(spell=False, own=[100], tower=0)
    late = dict(spell=False, own=[140], tower=0)
    fights = []
    for i in range(30):                         # 30 Knight fights over 10 matches: every run agrees
        fights.append(dict(match=f'm{i % 10}', own=True, anchor=dict(name='Knight', form=0), verdict=dict(agree=i % 2 == 0),
                           card=dict(live=ok, sim=[ok] + [ok]*8)))
    for i in range(5):                          # 5 Golem fights: live disagrees with every SIM run
        fights.append(dict(match=f'm{i}', own=False, anchor=dict(name='Golem', form=0), verdict=dict(agree=False),
                           card=dict(live=late, sim=[ok] + [ok]*8)))
    out = F.ceiling_table(tmp_path, fights, 'strict')
    rows = {r['card']: r for r in out['cards']}
    k = rows['own Knight']
    assert (k['n'], k['agree'], k['ceiling'], k['normalised'], k['flag']) == (30, 1.0, 1.0, 1.0, 'MEETS')
    assert k['whole_fight_outcome'] == .5
    g = rows['opp Golem']
    assert (g['agree'], g['flag']) == (0.0, 'insufficient n')
    assert out['overall']['n'] == 35 and out['overall']['flag'] == 'below' and out['k'] == 8
    assert 'own Knight | 30 | 10 |' in (tmp_path/'CEILING_strict.txt').read_text()
    assert json.loads((tmp_path/'ceiling_strict.json').read_text())['definitions']['TOWER_FLOOR'] == 100
