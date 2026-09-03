"""AGGRO drills: graded on the engine's LOCK STATE, not on hp totals (HANDOFF §5bt / §5bu).

Why a separate module and why it is NOT auto-imported: `scenarios.load_all()` imports every
`sim/drills_*.py` by filename at env construction, so a new file with that prefix would silently
join the pool of whatever run is training. These drills join the deck's pool only through an explicit
`register_all()` call (to be made from `drills_icebow.py` once the coef-0.5 run has stopped).

Why they exist: the two aggro drills the deck already has do not grade aggro (§5bt, measured).
`knight_guards_the_bow` passes the step ANY knight is played (bow alive + knight played, verdict fires
at once) and `nado_the_sneaky_lock`'s tornado earns nothing (knight-only 60% > reference 47.5%; the
bow never re-locks after a 2-tile pull against an 11.5-tile reach). What the owner asked for is the
model answering "who will lock onto whom" and acting on it, so the predicates here read `Unit.target`
and `Unit.locked` -- the same fields `sim/aggro_oracle.py` reads -- and the boards were chosen by
oracle sweep so that BOTH outcomes are reachable from legal cells (§5bu, `scratchpad/gauntlet/L20`).

The pass/fail of both drills is decided by placement and timing alone; the enemy's ladder level
(13-16) does not move it (the lock rule is geometric), which is the property the old drills lacked.
"""
from __future__ import annotations

from .engine import Tower, Unit
from .scenarios import Scenario, enemy_units, register, _REGISTRY


def _our(eng, base: str):
    # never a distractor: `_place_noise` also deals OUR cards as noise, tagged `drill_noise`
    return [u for u in eng.units if u.team == 0 and u.hp > 0 and u.spec.base == base
            and not getattr(u, "drill_noise", False)]


def _no_distractors(env) -> None:
    """Scenario `setup`: drop the tagged noise bodies `_place_noise` dealt (it runs before setup).

    Noise lands in "the lane the drill is NOT about" (drill_env `_place_noise`), and for a drill
    whose ANSWER is the other lane that is exactly the wrong place: an enemy body at y 0.30-0.46
    is always nearer to a river-row bow than the tower at 11.6 tiles, so the reference had no
    passing cell in every episode that rolled an enemy distractor (measured L20: 5% scripted).
    A `noise` field on `Scenario` is the proper switch; `scenarios.py` is imported by the running
    trainer's workers, so this is the opt-out until the run stops.
    """
    env.eng.units[:] = [u for u in env.eng.units if not getattr(u, "drill_noise", False)]


# ---------------------------------------------------------------------------------------------
# tank_for_bow: the Knight goes IN FRONT and the walking Valkyrie re-locks onto him.
# ---------------------------------------------------------------------------------------------

def lock_taken_by_our(base: str):
    """SUCCESS: a live drill enemy is targeting one of our `base` units. This fires at the retarget
    itself -- the aggro event -- so it is independent of who then wins the fight (the level roll's
    business, not the placement's)."""
    def _p(eng, _s=None):
        ours = _our(eng, base)
        return bool(ours) and any(getattr(u, "target", None) in ours for u in enemy_units(eng))
    return _p


def enemy_locked_on_our(base: str):
    """FAILURE: a drill enemy has started swinging at our `base` (engine `locked` = first hit landed).
    Once locked, a nearer body no longer pulls it (§5bs: window closes at the first hit), so this is
    the moment the interposition became impossible -- or our unit is already gone."""
    def _p(eng, _s=None):
        ours = _our(eng, base)
        if not ours:
            return True
        return any(getattr(u, "locked", False) and getattr(u, "target", None) in ours
                   for u in enemy_units(eng))
    return _p


TANK_FOR_BOW = Scenario(
    name="tank_for_bow",
    goal="Put the Knight between the walking Valkyrie and our X-Bow so SHE re-locks onto him.",
    tier="compound",
    hand=("knight",),
    elixir=4.0,
    # The bow stands BEHIND the first legal agent row (y 0.5625, 18x24 grid, min_own_gy 13): at
    # y 0.56 no cell the agent can choose is in front of it, and the L20 trace showed the
    # reference knight snapping to y 0.58 -- behind the bow -- and failing 100%.
    spawns=(("x_bow", 0, 0.26, 0.60, 0.0), ("valkyrie", 1, 0.24, 0.42, 0.0)),
    success=lock_taken_by_our("knight"),
    failure=enemy_locked_on_our("x_bow"),
    # MEASURED WINDOW (§5bu, oracle on LEGAL cells, our L16 / enemy L14 and L16 identical): she
    # first hits the bow 3.7 s after spawning; a Knight takes her lock from 16 cells (rows
    # 0.562-0.646, x 0.08-0.42) landing 0.85 s after her spawn, 10 at 1.45 s, 6 at 2.05 s, 4 at
    # 3.25 s ((0.19-0.31, 0.562) and (0.25, 0.604)), none after her first hit. Actions land
    # +0.25 s late (action_latency), so the last useful agent step is the 5th.
    time_limit=8.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "xbow_lock"),
    prereq=("knight_blocks_the_charge",),
    reference=(("knight", 0.25, 0.5625, 0.6),),
    notes="Replaces the aggro content `knight_guards_the_bow` was named for and does not grade "
          "(§5bt: it passes the step any knight is played). Success is the Valkyrie's target "
          "becoming the Knight; failure is her first hit landing on the bow.",
)


# ---------------------------------------------------------------------------------------------
# bow_lane_choice: with a defender committed to one lane, place the bow where its FIRST lock after
# the 3.5 s deploy is a TOWER, not the defender.
# ---------------------------------------------------------------------------------------------

def _bow_first_lock(eng, st):
    """Memoise the FIRST target our X-Bow acquires after its deploy timer ends: 'tower' / 'unit' /
    None. Read from the drill's own scratch dict so a later re-lock (the knight dies, the bow turns
    to the tower) cannot rewrite the answer to the question, which is about the placement."""
    st = st if st is not None else {}
    got = st.get("bow_first_lock")
    if got is not None:
        return got
    for b in _our(eng, "x_bow"):
        if getattr(b, "deploy_left", 0.0) > 0.0:
            continue
        t = getattr(b, "target", None)
        if isinstance(t, Tower):
            st["bow_first_lock"] = "tower"
        elif isinstance(t, Unit):
            st["bow_first_lock"] = "unit"
        else:
            continue
        return st["bow_first_lock"]
    return None


def bow_first_lock_is_tower(eng, st=None) -> bool:
    return _bow_first_lock(eng, st) == "tower"


def bow_first_lock_is_unit(eng, st=None) -> bool:
    return _bow_first_lock(eng, st) == "unit"


BOW_LANE_CHOICE = Scenario(
    name="bow_lane_choice",
    goal="A Knight is walking down one lane. Place the X-Bow so its first lock is a TOWER, not him.",
    tier="compound",
    hand=("x_bow",),
    elixir=6.0,
    spawns=(("knight", 1, 0.26, 0.45, 0.0),),
    success=bow_first_lock_is_tower,
    failure=bow_first_lock_is_unit,
    # MEASURED MAP (§5bu, oracle on the agent's own cells, bow landing 0.85 s in, our L16 vs
    # knight L13 and L16 identical): on the first legal row (y 0.5625) 15/18 cells first-lock the
    # Knight and only x 0.86-0.97 first-lock the right tower; on the next row (y 0.604) 16 lock
    # the Knight and the last two reach nothing. The bow's 11.5-tile reach is why: the tower is
    # 11.6 tiles from the river row, so a troop anywhere nearer than that is the first lock, and
    # the only tower-first cells are the far corner of the lane the troop is NOT in.
    time_limit=10.0,
    randomise=("lane",),
    graded_by=("xbow_lock",),
    prereq=("bank_to_six_then_bow",),
    setup=_no_distractors,
    reference=(("x_bow", 0.917, 0.5625, 0.6),),
    notes="The owner's 'does a placed X-Bow get blocked or lock the tower after its deploy time' "
          "question as a drill; `AggroOracle.draws()` answers it for any cell. A bow that first "
          "locks the knight can still be a fine defensive bow -- that is a different drill.",
)


ALL = (TANK_FOR_BOW, BOW_LANE_CHOICE)


def register_all() -> int:
    """Idempotent: registering a name twice is an error in `scenarios.register`, and tests build
    several envs in one process."""
    n = 0
    for s in ALL:
        if s.name not in _REGISTRY:
            register(s)
            n += 1
    return n
