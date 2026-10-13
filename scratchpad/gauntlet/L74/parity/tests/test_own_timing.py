from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import core as c, planning as p


def b(x, y, key):
    return dict(card_id=7, side=0, key=key, x=x, y=y, hp=10, max_hp=10)


def test_own_spawn_tick():
    play = dict(tick=100, confirmation_tick=130)
    frames = [90, 110, 120, 130, 140]
    assert p.own_spawn_tick(play, frames, 'tap') == 100
    assert p.own_spawn_tick(play, frames, 'spawn') == 130
    assert p.own_spawn_tick(play, frames, 'spawn_mid') == 125
    assert p.own_spawn_tick(dict(tick=125, confirmation_tick=130), frames, 'spawn_mid') == 127  # never before the tap


def test_swarm_pairing_fixes_crossed_members_once():
    live_t, sim_t, pairing = c.Tracks(), c.Tracks(), c.SwarmPairing()
    # Ordinals come from first sight (sorted by x,y); the sim saw its pair earlier, then the members swapped sides.
    sim = sim_t.assign(5, [b(1000, 1100, 's1'), b(1000, 1900, 's2')])
    live = live_t.assign(10, [b(1000, 1000, 'a'), b(1000, 2000, 'b')])
    sim = sim_t.assign(10, [b(1000, 2100, 's1'), b(1000, 900, 's2')])
    assert min(r['position_error_tiles'] for r in c.compare(live, sim)) > 1  # ordinal pairing: crossed
    out = pairing.apply(live, sim, live_t.births, sim_t.births)
    assert sum(r['position_error_tiles'] for r in c.compare(live, out)) < 0.3
    # Fixed for the rest of the match: a later crossing is not re-optimised away.
    live = live_t.assign(20, [b(1000, 1000, 'a'), b(1000, 2000, 'b')])
    sim = sim_t.assign(20, [b(1000, 1000, 's1'), b(1000, 2000, 's2')])
    assert max(r['position_error_tiles'] for r in c.compare(live, pairing.apply(live, sim, live_t.births, sim_t.births))) > 0.9


def test_singletons_and_off_by_default_untouched():
    live_t, sim_t, pairing = c.Tracks(), c.Tracks(), c.SwarmPairing()
    live = live_t.assign(10, [b(1000, 1000, 'a')])
    sim = sim_t.assign(10, [b(5000, 5000, 's')])
    assert pairing.apply(live, sim, live_t.births, sim_t.births) == sim
