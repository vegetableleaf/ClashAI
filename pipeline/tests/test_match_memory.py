"""Plan A S1a: pipeline/match_memory.py (the causal match memory).

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_match_memory.py -q

Synthetic matches, our side 0 unless stated (engine side 0: our king at engine y 3000 = own-frame y 0.906, enemy princesses
at engine y 25500). One test per event type, the pending -> resolved boundaries, randomised causality, incremental == offline,
E_MAX truncation, unknown reads flagged, and the X-Bow rule cross-checked against succ48/xbow_count.py and habit_terms."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import habit_terms as HT                                    # noqa: E402
from pipeline import match_memory as M                                    # noqa: E402
from pipeline import vocab                                                # noqa: E402
from pipeline.public_observation import _native_ids                      # noqa: E402

GID = {k: i + 1 for i, k in enumerate(sorted(['x-bow', 'rocket', 'tornado', 'knight', 'skeletons', 'the-log', 'tesla',
                                               'ice-wizard', 'hog-rider', 'goblins', 'fireball', 'goblin-gang']))}
DECK = ['Xbow', 'Tesla', 'IceWizard', 'Tornado', 'Rocket', 'Knight', 'Log', 'Skeletons']
FULL, UP = (1.0,) * 6, (True,) * 6
C = M._COL


def unit(addr, side, card, hp, mx, x, y):
    """A public_frame entity (engine side / millitiles, native catalog id)."""
    return dict(side=side, x=x, y=y, hp=hp, max_hp=mx, card_id=_native_ids()[(vocab.engine_key(card), 0)], address=(side, addr))


def samples(ticks, towers=lambda t: FULL, alive=lambda t: UP, units=lambda t: [], elixir=lambda t: 5.0):
    return [dict(tick=t, towers=towers(t), alive=alive(t), elixir=elixir(t), units=units(t)) for t in ticks]


def row(feat, i=0):
    return {k: float(feat['mem_ev'][i, j]) for k, j in C.items()}


def same(a, b):
    return all(np.array_equal(a[k], b[k]) for k in a)


# ------------------------------------------------------------------------------------------------------------ play
def test_play_event():
    """Every accepted play of both sides; own frame for side 1 (mirrored); state BEFORE the play; ids from gid."""
    sm = samples(range(0, 3000, 50), elixir=lambda t: t / 100)
    plays = [dict(tick=75, side=1, card='Knight', form=1, x=4000, y=20000),            # ours (observer side 1)
             dict(tick=2500, side=0, card='hog_rider', form=0, x=4000, y=20000),       # theirs, 2x
             dict(tick=80, side=0, card='Skeletons', x=1, y=1, accepted=False)]       # refused: not an event
    m = M.build(1, sm, plays)
    ev = m.events(2501)
    assert [(e['card'], e['mine']) for e in ev] == [('knight', True), ('hog-rider', False)]
    f = m.features(2501, GID, DECK)
    hog, kn = row(f, 0), row(f, 1)
    assert kn['is_play'] == 1 and kn['mine'] == 1 and kn['xy_known'] == 1
    assert kn['x'] == pytest.approx(14 / 18) and kn['y'] == pytest.approx(1 - 12 / 32)          # mirrored into OUR frame
    assert kn['elixir_10'] == pytest.approx(0.05) and kn['elixir_known'] == 1                  # sample 50 (< 75): 0.5
    assert kn['cost_10'] == pytest.approx(0.3) and kn['ph_1x'] == 1 and kn['margin_known'] == 1
    assert kn['ago_60'] == pytest.approx((2501 - 75) * 0.05 / 60)
    assert hog['mine'] == 0 and hog['elixir_known'] == 0 and hog['ph_2x'] == 1 and hog['x'] == pytest.approx(14 / 18)
    on = M.build(1, sm, [dict(tick=150, side=1, card='Knight', x=4000, y=20000)]).events(151)    # a sample AT the play tick
    assert on[0]['el'] == pytest.approx(1.0)                                   # is not "before": sample 100's elixir
    assert f['mem_card'][:2].tolist() == [GID['hog-rider'], GID['knight']] and f['mem_form'][:3].tolist() == [0, 1, 3]
    assert f['mem_mask'].sum() == 2


def test_ability_event():
    """Own presses are events (no position): cost from own_ability, tower outcome known, value removed UNKNOWN."""
    sm = samples(range(0, 600, 10), units=lambda t: [unit(1, 1, 'Knight', 600, 600, 9000, 9000)])
    m = M.build(0, sm, [dict(tick=100, side=0, card='IceWizard', ability=True, accepted=True)])
    r = row(m.features(301, GID))
    assert r['is_ability'] == 1 and r['is_play'] == 0 and r['xy_known'] == 0 and r['cost_10'] == pytest.approx(0.2)
    assert r['out_done'] == 1 and r['out_tower_known'] == 1 and r['out_value_known'] == 0 and r['out_value_10'] == 0


# ------------------------------------------------------------------------------------------------------------ towers
def test_tower_damage_debounced():
    """2 % every 5 ticks on their L princess: events >= 20 ticks apart carrying the accumulated loss; < 2 % in total -> none."""
    sm = samples(range(0, 205, 5), towers=lambda t: (1, 1, 1, 1, 1 - 0.004 * t, 1))
    ev = [e for e in M.build(0, sm).events(10 ** 6) if e['type'] == 'tower_damage']
    assert ev and all(e['tower'] == 4 and not e['mine'] and e['lost'] >= M.DMG_MIN - 1e-9 for e in ev)
    assert all(b['tick'] - a['tick'] >= M.DMG_GAP for a, b in zip(ev, ev[1:])) and len(ev) <= 200 // M.DMG_GAP + 1
    assert sum(e['lost'] for e in ev) == pytest.approx(0.8, abs=0.1)
    small = samples(range(0, 400, 5), towers=lambda t: (1, 1 - 0.00005 * t, 1, 1, 1, 1))     # 2 % never reached
    assert not [e for e in M.build(0, small).events(10 ** 6) if e['type'] == 'tower_damage']
    holes = samples(range(0, 400, 5), towers=lambda t: (1, 1, 1, 1, None if t % 20 else 1 - 0.001 * t, 1))
    assert [e for e in M.build(0, holes).events(10 ** 6) if e['type'] == 'tower_damage']     # unread samples are skipped


def test_tower_fall_once_and_crowns():
    """Their R princess falls at 300, reads alive again at 310 (a blip), dead from 320: one fall, our crown counted."""
    alive = lambda t: (True,) * 5 + (not (t == 300 or t >= 320),)          # noqa: E731
    sm = samples(range(0, 600, 10), towers=lambda t: (1, 1, 1, 1, 1, 0.5 if alive(t)[5] else 0), alive=alive)
    ev = M.build(0, sm, [dict(tick=400, side=0, card='Knight', x=9000, y=10000)]).events(401)
    falls = [e for e in ev if e['type'] == 'tower_fall']
    assert [(e['tick'], e['tower'], e['mine']) for e in falls] == [(300, 5, False)]
    assert ev[-1]['card'] == 'knight' and ev[-1]['crowns'] == (1, 0)
    r = row(M.build(0, sm).features(301, GID))
    assert r['is_tower_fall'] == 1 and r['tower_r'] == 1 and r['mine'] == 0 and r['crowns_me_3'] == pytest.approx(1 / 3)


# ------------------------------------------------------------------------------------------------------------ outcomes
def test_generic_outcome_pending_then_resolved():
    """Our Knight at 100 next to their Hog Rider (killed at 250) while their L princess loses 10 %: pending through
    tick 300 (window end 100 + 200 is not < 300), resolved at 301 with the hp-scaled elixir value and the tower loss."""
    hog = lambda t: [unit(7, 1, 'HogRider', 1000 if t < 150 else 400, 1000, 4000, 12000)] if t < 250 else []   # noqa: E731
    sm = samples(range(0, 600, 10), towers=lambda t: (1, 1, 1, 1, 1 if t < 200 else 0.9, 1), units=hog)
    m = M.build(0, sm, [dict(tick=100, side=0, card='Knight', x=5000, y=12500)])

    def k(t):
        f = m.features(t, GID)
        return row(f, int(np.flatnonzero(f['mem_card'] == GID['knight'])[0]))
    p = k(300)
    assert p['out_done'] == 0 and p['out_enemy_lost'] == 0 and p['out_value_known'] == 0 and p['out_value_10'] == 0
    r = k(301)
    assert r['out_done'] == 1 and r['out_tower_known'] == 1 and r['out_value_known'] == 1
    assert r['out_enemy_lost'] == pytest.approx(0.1) and r['out_own_lost'] == 0
    assert r['out_value_10'] == pytest.approx(HT.body_value('hog_rider', 1000, 1000, {}) / 10)     # = 4 elixir


def _xbow_count():
    path = REPO / 'scratchpad/gauntlet/L74/succ48/xbow_count.py'
    if not path.is_file():
        pytest.skip('succ48/xbow_count.py not in this tree')
    spec = importlib.util.spec_from_file_location('xbow_count_ref', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _xbow_match():
    """X-Bow A (100) at their R princess: -6 % within 600 -> locked; B (1000): -3 % -> failed; C (1500) defensive, no reach.
    Their Knight at 150 answers A. Their X-Bow D (2000) at our L princess: -10 % -> locked for them; our Skeletons answer it."""
    def tw(t):
        r = 1.0 if t < 300 else 0.94 if t < 1200 else 0.91
        return (1, 1.0 if t < 2200 else 0.9, 1, 1, 1, r)
    sm = samples(range(0, 3000, 20), towers=tw)
    plays = [dict(tick=100, side=0, card='Xbow', form=0, x=14500, y=13000),
             dict(tick=150, side=1, card='knight', form=0, x=14000, y=15000),
             dict(tick=1000, side=0, card='Xbow', form=0, x=14500, y=13000),
             dict(tick=1500, side=0, card='Xbow', form=0, x=9000, y=5000),
             dict(tick=2000, side=1, card='x_bow', form=0, x=3500, y=19000),
             dict(tick=2050, side=0, card='Skeletons', form=0, x=3500, y=17000)]
    return sm, plays


def test_xbow_outcome_matches_xbow_count_and_habit_terms():
    sm, plays = _xbow_match()
    m = M.build(0, sm, plays)
    own = [e for e in m.events(10 ** 6) if e.get('card') == 'x-bow' and e['mine']]
    mine = [(bool(e['reach']), None if e['xb'] is None else e['xb']['locked']) for e in own]
    assert mine == [(True, True), (True, False), (False, None)]
    # succ48/xbow_count.py on the same match (absolute HP = fraction x 3052; enemy princesses at engine y 25500)
    ref = _xbow_count()
    tow = lambda s: [[1, 'p', 3500, 25500, s['towers'][4] * 3052], [1, 'p', 14500, 25500, s['towers'][5] * 3052],  # noqa: E731
                     [1, 'k', 9000, 29000, 4824]]
    h = dict(L=0, samples=[[s['tick'], 0, 0, 0, 0, tow(s)] for s in sm],
             own=[[p['tick'], None, 'Xbow', True, 0, 0, 0, 0, p['x'], p['y']] for p in plays if p['card'] == 'Xbow'])
    out = ref.one(h)
    assert (out['xb'], out['reach'], out['fail']) == (3, 2, 1)
    assert (ref.REACH, ref.LOCK_FRAC, ref.WINDOW) == (M.XB_REACH, M.XB_LOCK, M.XB_WINDOW)
    # habit_terms' X-Bow term (the reward rule) agrees too
    towers = [(s['tick'], [(3.5, 25.5, s['towers'][4] * 3052), (14.5, 25.5, s['towers'][5] * 3052)]) for s in sm]
    hp = HT.events([(0, 5.0, [])], [(p['tick'], 'Xbow', p['x'], p['y']) for p in plays if p['card'] == 'Xbow'], True, towers)
    assert hp['xbow'] == [[100, 0], [1000, 1]]


def test_xbow_pending_answer_and_opponent_xbow():
    sm, plays = _xbow_match()
    m = M.build(0, sm, plays)
    at = lambda t, tick: next(e for e in m.events(t) if e['tick'] == tick)    # noqa: E731
    assert at(700, 100)['xb'] is None and at(701, 100)['xb']['locked']         # window (100, 700] closes at 701
    assert at(150, 100)['answer'] is None                                     # the Knight (150) is not yet visible
    assert at(151, 100)['answer'] == 'knight' and at(151, 150)['is_answer']
    assert at(1080, 1000)['answer'] is None and at(1081, 1000)['answer'] == ''   # none within 4 s: resolved at 1081
    opp = at(2601, 2000)
    assert not opp['mine'] and opp['reach'] == (1,) and opp['xb']['locked'] and opp['answer'] == 'skeletons'
    f = m.features(2601, GID)
    r = row(f, int(np.flatnonzero(f['mem_card'] == GID['skeletons'])[0]))
    assert r['is_xb_answer'] == 1 and r['mine'] == 1
    s, ans = M.summary(m.events(10 ** 6), 10 ** 6, DECK, GID)
    v = dict(zip(M.SUMMARY_FIELDS, s))
    assert (v['xb_placed_10'], v['xb_resolved_10'], v['xb_locked_10'], v['xb_failed_10']) == pytest.approx((.3, .2, .1, .1))
    assert v['xb_fails_since_lock_10'] == pytest.approx(.1) and v['xb_has_lock'] == 1 and ans == GID['knight']
    assert v['xb_answered_share'] == pytest.approx(1 / 3)                      # A answered; B, C not
    assert v['xb_mean_damage'] == pytest.approx((0.06 + 0.03) / 2)


def test_rocket_outcome_and_combo():
    """Rocket at 500 on their L princess (-5 %) with Goblins in the blast and our Tornado at 520 (Rocket - Tornado = -20:
    combo); Rocket at 2000 on troops with a Tornado at 2030 (-30: no combo). Pending through 600, resolved at 601."""
    gob = lambda t: [unit(a, 1, 'Goblins', 100, 100, 3500 + 300 * a, 24000) for a in range(3) if t < 540]   # noqa: E731
    sm = samples(range(0, 2400, 10), towers=lambda t: (1, 1, 1, 1, 0.8 if t < 540 else 0.75, 1), units=gob)
    plays = [dict(tick=500, side=0, card='Rocket', x=3500, y=24500), dict(tick=520, side=0, card='Tornado', x=3500, y=22000),
             dict(tick=2000, side=0, card='Rocket', x=9000, y=17000), dict(tick=2030, side=0, card='Tornado', x=9000, y=17000)]
    m = M.build(0, sm, plays)
    at = lambda t, tick: next(e for e in m.events(t) if e['tick'] == tick)    # noqa: E731
    assert at(600, 500)['rk'] is None and at(600, 500)['aim'] == 4
    rk = at(601, 500)['rk']
    assert rk['tower_lost'] == pytest.approx(0.05) and rk['combo']
    assert rk['value'] == pytest.approx(3 * HT.body_value('goblins', 100, 100, {}))
    late = at(2101, 2000)
    assert late['aim'] is None and not late['rk']['combo']
    s, _ = M.summary(m.events(2101), 2101, DECK, GID)
    v = dict(zip(M.SUMMARY_FIELDS, s))
    assert (v['rk_tower_5'], v['rk_all_5'], v['rk_combo_5']) == pytest.approx((.2, .4, .2))
    assert v['rk_tower_damage'] == pytest.approx(0.05)
    f = m.features(601, GID)
    r = row(f, int(np.flatnonzero(f['mem_card'] == GID['rocket'])[0]))
    assert r['rk_tower'] == 1 and r['rk_done'] == 1 and r['rk_combo'] == 1 and r['rk_tower_known'] == 1


# ------------------------------------------------------------------------------------------------------------ properties
CARDS = ['Xbow', 'Rocket', 'Tornado', 'Knight', 'Skeletons', 'Log', 'Tesla', 'IceWizard', 'HogRider', 'Goblins', 'Fireball']
BODIES = ['Knight', 'HogRider', 'Goblins', 'Skeletons', 'Tesla', 'Giant']


def rand_match(seed):
    rng = np.random.default_rng(seed)
    side = int(rng.integers(2))
    ticks = sorted(set(int(t) for t in rng.integers(0, 4200, 260)))
    hp, alive, bodies, nxt = [1.0] * 6, [True] * 6, {}, 0
    sm, plays, prev = [], [], -1
    for t in ticks:
        for i in range(6):
            if alive[i] and rng.random() < .15:
                hp[i] = max(0.0, hp[i] - float(rng.random()) * .08)
                alive[i] = hp[i] > 0 or i % 3 == 0
        for _ in range(int(rng.poisson(.6))):
            nxt += 1
            bodies[nxt] = [int(rng.integers(2)), str(rng.choice(BODIES)), 1000.0, 1000.0, float(rng.integers(0, 18000)),
                           float(rng.integers(0, 32000))]
        for k in list(bodies):
            b = bodies[k]
            b[2] -= float(rng.random()) * 300 if rng.random() < .4 else 0
            b[4] += float(rng.normal(0, 400))
            if b[2] <= 0:
                del bodies[k]
        units = None if rng.random() < .03 else [unit(k, *b) for k, b in bodies.items()]
        sm.append(dict(tick=t, towers=tuple(None if rng.random() < .05 else h for h in hp), alive=tuple(alive),
                       elixir=None if rng.random() < .05 else float(rng.random() * 10), units=units))
        for _ in range(int(rng.poisson(.5))):
            tp, s = int(rng.integers(prev + 1, t + 1)), int(rng.integers(2))
            c = str(rng.choice(CARDS))
            if c == 'IceWizard' and s == side and rng.random() < .5:
                plays.append(dict(tick=tp, side=s, card=c, ability=True))
                continue
            xy = {} if rng.random() < .05 else dict(x=float(rng.integers(0, 18000)), y=float(rng.integers(0, 32000)))
            plays.append(dict(tick=tp, side=s, card=c, form=int(rng.integers(3)), **xy))
        prev = t
    return side, sm, plays


def incremental(side, sm, plays, ticks):
    m, out = M.MatchMemory(side), {}
    for s in sm:
        m.observe(**s, plays=[p for p in plays if p['tick'] <= s['tick']])
        if s['tick'] in ticks:
            out[s['tick']] = m.features(s['tick'], GID, DECK)
    return m, out


def test_incremental_equals_offline():
    n = 0
    for seed in range(6):
        side, sm, plays = rand_match(seed)
        ticks = {s['tick'] for s in sm}
        m, inc = incremental(side, sm, plays, ticks)
        off = M.build(side, sm, plays)
        assert m.late == 0
        for t in sorted(ticks):
            assert same(inc[t], off.features(t, GID, DECK)), (seed, t)
            n += 1
        assert sum(inc[max(ticks)]['mem_mask']) > 20               # the random matches are not trivially empty
    assert n > 1000


def test_causality_randomised():
    """Altering or inserting any HP read, body, elixir or play at tick >= t never changes features(t)."""
    for seed in range(8):
        side, sm, plays = rand_match(100 + seed)
        rng = np.random.default_rng(seed)
        _, sm2, plays2 = rand_match(200 + seed)                        # the source of the altered future
        full = M.build(side, sm, plays)
        for t in rng.integers(50, 4200, 12):
            t = int(t)
            fut_s = [dict(s, tick=s['tick']) for s in sm2 if s['tick'] >= t]
            alt = M.build(side, [s for s in sm if s['tick'] < t] + fut_s,
                          [p for p in plays if p['tick'] < t] + [p for p in plays2 if p['tick'] >= t])
            assert same(full.features(t, GID, DECK), alt.features(t, GID, DECK)), (seed, t)


def test_late_play_offline_with_seen():
    """A play reported after a decision later than its tick is visible from the decision that receives it (counted)."""
    sm = samples(range(100, 200, 10))
    p = dict(tick=105, side=0, card='Knight', x=9000, y=10000)
    m = M.MatchMemory(0)
    vis = {}
    for s in sm:
        m.observe(**s, plays=[p] if s['tick'] >= 130 else [])
        vis[s['tick']] = int(m.features(s['tick'], GID)['mem_mask'].sum())
    assert m.late == 1 and vis[120] == 0 and vis[130] == 1
    off = M.build(0, sm, [dict(p, seen=130)])
    assert all(same(off.features(t, GID), m.features(t, GID)) for t in range(100, 200, 10))


def test_emax_truncation():
    sm = samples(range(0, 5000, 10))
    plays = [dict(tick=10 + 20 * i, side=i % 2, card='Knight' if i % 3 else 'Skeletons', x=9000, y=16000) for i in range(200)]
    f = M.build(0, sm, plays).features(10 ** 6, GID)
    assert f['mem_mask'].sum() == M.E_MAX == 128
    ago = f['mem_ev'][:, C['ago_60']]
    assert ago[0] == ago.min() and np.all(np.diff(ago) > 0)                     # newest first
    assert ago[-1] == pytest.approx((10 ** 6 - (10 + 20 * 72)) * 0.05 / 60)     # plays 0..71 dropped


def test_unknown_reads_stay_flagged():
    """None tower reads, no board bodies, unknown elixir, an X-Bow with no position: known flags 0 AND the value 0."""
    sm = samples(range(0, 1000, 10), towers=lambda t: (1, 1, 1, 1, None, 1), units=lambda t: None, elixir=lambda t: None)
    m = M.build(0, sm, [dict(tick=100, side=0, card='Knight', x=9000, y=10000), dict(tick=110, side=0, card='Xbow')])
    f = m.features(999, GID)
    xb, kn = row(f, 0), row(f, 1)
    for r in (kn, xb):
        assert r['out_done'] == 1 and r['out_tower_known'] == 0 and r['out_enemy_lost'] == 0 and r['out_own_lost'] == 0
        assert r['out_value_known'] == 0 and r['out_value_10'] == 0
        assert r['margin_known'] == 0 and r['margin_2'] == 0 and r['elixir_known'] == 0 and r['elixir_10'] == 0
    assert kn['xy_known'] == 1 and xb['xy_known'] == 0 and xb['xb_reach'] == 0 and xb['xb_answer_done'] == 0
    ev = m.events(999)
    assert ev[1]['reach'] is None and ev[1]['answer'] is None


def test_summary_per_card_block():
    sm, plays = _xbow_match()
    s, _ = M.summary(M.build(0, sm, plays).events(10 ** 6), 10 ** 6, DECK, GID)
    assert s.shape == (M.S,) and s.dtype == np.float32
    blk = s[len(M.SUMMARY_FIELDS):].reshape(M.DECK_N, len(M.CARD_FIELDS))
    xb, sk = dict(zip(M.CARD_FIELDS, blk[0])), dict(zip(M.CARD_FIELDS, blk[DECK.index('Skeletons')]))
    assert xb['plays_10'] == pytest.approx(.3) and xb['swing_known'] == 1
    assert sk['plays_10'] == pytest.approx(.1) and blk[DECK.index('Tesla')].tolist() == [0.0] * len(M.CARD_FIELDS)
