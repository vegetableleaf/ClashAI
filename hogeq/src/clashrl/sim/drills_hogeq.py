"""HOGEQ DRILLS. Each one rehearses a single interaction; see `scenarios.py` for the design.

Coordinates are the engine's: OUR side is HIGH y (princesses ~0.80, king ~0.91), the enemy is LOW
y (~0.20), the river is ~0.50, and the bridges sit at x ~0.19 / ~0.81. The frontmost row we may
legally deploy on is y = 0.5625 (`actions.min_own_gy` = 13), which is the bridge row -- every
scenario here is written in rows that actually exist, because a threshold or a spawn placed at a
coordinate the action grid cannot produce is the single most expensive mistake in this file's
history (see HANDOFF SS8: `_hog_wincon` was verified at y=0.47 and shipped scoring -1.0 at every
legal cell).

This deck is a CYCLE deck: the Hog is the plan, everything else buys him a window. So the drills
are ordered around him -- send him at the right moment, never into a push, and clear the one
building that stops him.
"""
from __future__ import annotations

from .scenarios import (Scenario, enemy_tower_hp_lost, first_play_t, n_plays, played,
                        played_before, play_xy, princess_hp_lost, register,
                        spent_more_than)

_BRIDGE_ROW = 0.5625          # actions.min_own_gy = 13: the frontmost legal own-half row


def _our(eng, base):
    return [u for u in eng.units if u.team == 0 and u.hp > 0 and u.spec.base == base]


def _enemy(eng, base=None):
    return [u for u in eng.units if u.team == 1 and u.hp > 0
            and (base is None or u.spec.base == base)]


def _hog_sent(eng, _s=None) -> bool:
    """A Hog of ours is on the board -- the send happened."""
    return bool(_our(eng, "hog_rider"))


def _hog_crossed(eng, _s=None) -> bool:
    """A Hog of ours has actually crossed into the enemy half."""
    return any(u.y < 0.47 for u in _our(eng, "hog_rider"))


# ---------------------------------------------------------------------------------------------
# TIER 1 -- FOUNDATIONAL: one card, one question.
# ---------------------------------------------------------------------------------------------

register(Scenario(
    name="hog_send_on_a_quiet_board",
    goal="A quiet board is the WINDOW, not a reason to sit on the elixir.",
    tier="foundational",
    hand=("hog_rider",),
    elixir=7.0,
    spawns=(),                    # nothing at all: the whole point is that nothing is coming
    # Success is simply that the Hog went, and went far enough to threaten. This drill exists
    # because the measured collapse was to ZERO hog uses -- before any question of placement
    # quality, the policy has to learn that a quiet board is when the deck's plan gets played.
    success=lambda e, s: _hog_crossed(e, s),
    failure=lambda e, s: (float(e.elixir[0]) >= 9.99 and not _hog_sent(e, s)),
    time_limit=12.0,
    randomise=("lane", "elixir"),
    graded_by=("wincon_exec", "leak"),
    prereq=(),
    reference=((("hog_rider", 0.194, 0.5625, 0.6)),),
    notes="Only became scorable once hog_bridge_y was floored at the action grid's front row -- "
          "before that every legal send was billed -1.0 and this drill was unpassable.",
))

register(Scenario(
    name="hog_never_into_the_push",
    goal="Never send the Hog into a committed enemy push -- the owner's hard rule.",
    tier="foundational",
    # THE HOG IS IN HAND -- he has to be REFUSED, not merely undrawn -- and so are the answers.
    # Dealt the whole deck the reference defence was usually not in the opening hand, and the
    # outcome went bimodal: held cleanly when the cards showed up, and exactly the do-nothing
    # number when they did not. That measures the deal rather than the decision.
    hand=("hog_rider", "tesla", "mighty_miner", "skeletons"),
    elixir=8.0,
    spawns=(("giant", 1, 0.30, 0.44, 0.0), ("musketeer", 1, 0.30, 0.40, 0.0)),
    # THE INVERSE DRILL, and the reason it is worth its own scenario: the answer is a defensive
    # card, and sending the win condition is the failure however good the lane was. Success needs
    # the tower actually held, so "do nothing" cannot pass it either -- measured, an unanswered
    # giant+musketeer takes the princess well past the threshold inside the limit.
    #
    # SURVIVING THE WINDOW COUNTS, rather than requiring the push to be wiped. Demanding a clean
    # board scored the doctrinally-correct line at 28% because a Giant simply outlasts an 18s
    # drill; the rule being rehearsed is "hold the Hog and do not lose the tower", so that is what
    # is scored. The Hog veto is still absolute -- it lives in the failure predicate.
    success=lambda e, s: (not _hog_sent(e, s) and not princess_hp_lost(e, s, 600.0)
                          and (not _enemy(e)
                               or (float(e.t) - float(s.get("t0", 0.0))) >= 17.4)),
    failure=lambda e, s: _hog_sent(e, s) or princess_hp_lost(e, s, 900.0),
    time_limit=18.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("wincon_exec", "threat_response"),
    prereq=("hog_send_on_a_quiet_board",),
    reference=(("mighty_miner", 0.30, 0.60, 0.6), ("tesla", 0.50, 0.62, 2.0),
               ("skeletons", 0.30, 0.66, 4.0)),
    notes="Pairs with hog_send_on_a_quiet_board so the policy learns a CONDITION, not a reflex: "
          "one drill rewards the send, the other punishes it, and only the board separates them.",
))

register(Scenario(
    name="tesla_pulls_the_wincon",
    goal="Plant the Tesla so an enemy win condition is dragged off the tower path.",
    tier="foundational",
    hand=("tesla",),
    elixir=6.0,
    spawns=(("hog_rider", 1, 0.81, 0.44, 0.0),),
    success=lambda e, s: (not _enemy(e, "hog_rider") and not princess_hp_lost(e, s, 80.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 80.0),
    time_limit=16.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=(),
    reference=((("tesla", 0.5, 0.645, 0.6)),),
    notes="A building ATTRACTS, it does not intercept: the skill is committing early enough that "
          "the pull has room to work, not placing it on top of the hog.",
))

register(Scenario(
    name="log_the_ground_swarm",
    goal="Roll the Log THROUGH a ground swarm -- not past it, not beside it.",
    tier="foundational",
    hand=("the_log",),
    elixir=4.0,
    spawns=(("skeleton_army", 1, 0.19, 0.44, 0.0),),
    success=lambda e, s: (not _enemy(e) and not princess_hp_lost(e, s, 60.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 120.0) or spent_more_than(e, s, 4.0),
    time_limit=12.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "spell_waste"),
    prereq=(),
    reference=((("the_log", 0.194, 0.6, 0.6)),),
    notes="The Log is a CORRIDOR that rolls FORWARD from the cast point: anything behind the cast "
          "is untouched. A miss is unambiguous here because the swarm simply survives.",
))

# ---------------------------------------------------------------------------------------------
# TIER 2 -- COMPOUND: two cards, an order, and a timing window.
# ---------------------------------------------------------------------------------------------

register(Scenario(
    name="eq_clears_the_hogs_building",
    goal="Earthquake the building that is holding the Hog, so he gets his hits.",
    tier="compound",
    hand=("earthquake",),
    elixir=6.0,
    # Our Hog is already committed and their Cannon is already down: this rehearses the SPELL, not
    # the send (hog_send_on_a_quiet_board rehearses that). Cannon 824 HP dies to all three quake
    # ticks -- it is the honest target for a solo Earthquake at these levels.
    spawns=(("hog_rider", 0, 0.19, 0.44, 0.0), ("cannon", 1, 0.26, 0.36, 0.0)),
    # SUCCESS IS THE HOG CONNECTING, not the building dying -- and the measurement is why. Scored
    # on "cannon dead" the drill passed 88% of the time by doing NOTHING, because a Hog chews
    # through an 824 HP Cannon unaided. But that is not the play working, it is the play failing
    # slowly: measured, without the quake he kills it at t=4.2s with 132 HP left and dies to the
    # tower without ever landing a hit. With the quake the Cannon is gone at 2.4s, he still has
    # 808 HP, and he connects at 4.8s. The elixir buys TEMPO AND HIS HEALTH BAR, so the predicate
    # has to read the thing downstream of both.
    success=lambda e, s: enemy_tower_hp_lost(e, s, 0.0),
    failure=lambda e, s: (not _our(e, "hog_rider")) or spent_more_than(e, s, 4.0),
    time_limit=16.0,
    randomise=("lane", "timing"),
    graded_by=("wincon_exec", "spell_waste"),
    prereq=("hog_send_on_a_quiet_board",),
    reference=((("earthquake", 0.26, 0.36, 0.6)),),
    notes="THE DECK'S NAMESAKE COMBO, and until the anywhere_ids fix it was an action the policy "
          "could not take at all: Earthquake aimed at their building was clamped back to our own "
          "front row, so the quake landed ~10 tiles behind the thing it was meant to kill.",
))

register(Scenario(
    name="hog_punish_the_back_investment",
    goal="They committed a tank at the back -- send the Hog at the OTHER lane immediately.",
    tier="foundational",
    hand=("hog_rider",),
    elixir=6.0,
    # A GOLEM AT THEIR BACK is the punish window in one card: nine elixir spent, nothing left in
    # hand, and a long walk before it threatens anything. The lane is the whole decision.
    spawns=(("golem", 1, 0.194, 0.14, 0.0),),
    success=lambda e, s: enemy_tower_hp_lost(e, s, 0.0),
    failure=lambda e, s: (not _hog_sent(e, s)
                          and (float(e.t) - float(s.get("t0", 0.0))) >= 6.0),
    time_limit=22.0,
    randomise=("lane", "elixir"),
    graded_by=("wincon_exec",),
    prereq=("hog_send_on_a_quiet_board",),
    reference=(("hog_rider", 0.806, 0.5625, 0.6),),
    notes="Scored on the Hog actually CONNECTING rather than on the cell he was put in: a send "
          "into the tank's own lane is answered on arrival and never chips anything.",
))

register(Scenario(
    name="hog_over_the_ignorable",
    goal="A lone Skeletons is not a push -- send the Hog and let the tower have them.",
    tier="foundational",
    hand=("hog_rider", "the_log", "skeletons", "ice_spirit"),
    elixir=6.0,
    spawns=(("skeletons", 1, 0.30, 0.46, 0.0),),
    # THE TRICKLE IS BAIT, and the veto in _hog_wincon has to NOT fire on it. This is the same
    # triage tier the icebow drill rehearses, seen from the attacking side: the question is not
    # "can I answer that" but "is that a reason to cancel my plan".
    success=lambda e, s: (_hog_crossed(e, s) and not played(s, "the_log", "skeletons", "ice_spirit")),
    failure=lambda e, s: (played(s, "the_log", "skeletons", "ice_spirit")
                          or (not _hog_sent(e, s)
                              and (float(e.t) - float(s.get("t0", 0.0))) >= 6.0)),
    time_limit=12.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("wincon_exec", "threat_miss_idle"),
    prereq=("hog_send_on_a_quiet_board",),
    reference=(("hog_rider", 0.806, 0.5625, 0.6),),
    notes="Pairs with hog_never_into_the_push: same card, same question, opposite answer, and only "
          "the SIZE of what is on the board separates them.",
))

register(Scenario(
    name="mm_blocks_the_tank",
    goal="Mighty Miner goes ON the tank's path -- he is the block, not a chaser.",
    tier="foundational",
    hand=("mighty_miner",),
    elixir=6.0,
    spawns=(("pekka", 1, 0.194, 0.44, 0.0),),
    success=lambda e, s: (not _enemy(e, "pekka") and not princess_hp_lost(e, s, 600.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 600.0),
    time_limit=22.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=(),
    reference=(("mighty_miner", 0.194, 0.60, 0.6),),
    notes="A PEKKA that reaches the tower costs several times what the Miner does, so the drill is "
          "really about committing early enough that the block happens up the lane.",
))

register(Scenario(
    name="firecracker_never_alone",
    goal="Firecracker is SUPPORT -- never played by herself on a quiet board.",
    tier="foundational",
    hand=("firecracker", "hog_rider", "skeletons", "tesla"),
    elixir=8.0,
    spawns=(),                     # quiet: there is nothing for her to support and nothing to fear
    # THE OWNER'S RULE, and an inverted drill by construction: the correct action is either the win
    # condition or nothing, and the failure is the habit -- a lone Firecracker at the bridge, where
    # she is answered by anything and buys nothing.
    success=lambda e, s: (not played(s, "firecracker")
                          and (float(e.t) - float(s.get("t0", 0.0))) >= 9.4),
    failure=lambda e, s: played(s, "firecracker"),
    time_limit=10.0,
    randomise=("lane", "elixir"),
    graded_by=("support_alone",),
    prereq=(),
    notes="No reference line: the correct play here is to not play her, which the do-nothing "
          "column already measures. Kept as the negative half of firecracker_escorts_the_hog.",
))

register(Scenario(
    name="firecracker_escorts_the_hog",
    goal="Hog FIRST, Firecracker a beat later and behind him -- never the other way round.",
    tier="compound",
    hand=("hog_rider", "firecracker"),
    elixir=9.0,
    spawns=(("archers", 1, 0.194, 0.30, 2.0),),
    # ORDER IS THE SKILL. She is 3 elixir of glass: ahead of the Hog she is the first thing shot,
    # behind him she snipes what comes to answer him. The board looks nearly identical either way
    # a second later, which is exactly why it needs its own drill and an ORDER predicate.
    success=lambda e, s: (played_before(s, "hog_rider", "firecracker")
                          and enemy_tower_hp_lost(e, s, 0.0)),
    failure=lambda e, s: (played_before(s, "firecracker", "hog_rider")
                          or (n_plays(s) >= 2 and not played(s, "hog_rider"))),
    time_limit=20.0,
    randomise=("lane", "timing"),
    graded_by=("wincon_exec", "support_alone"),
    prereq=("hog_send_on_a_quiet_board", "firecracker_never_alone"),
    reference=(("hog_rider", 0.194, 0.5625, 0.6), ("firecracker", 0.194, 0.62, 2.4)),
    notes="The escort gate reads `u.y < hog_bridge_y`, so she is only legal once he has actually "
          "crossed -- the beat in 'a beat later' is the deploy time plus his walk to the river.",
))

register(Scenario(
    name="eq_kills_the_spawner",
    goal="Earthquake the building -- it is the one card that reaches what the Hog cannot.",
    tier="foundational",
    hand=("earthquake",),
    elixir=6.0,
    # A TOMBSTONE (529 HP) dies to the quake's three ticks with room to spare, so a miss is
    # unambiguous: the building either fell or it did not. It also keeps producing skeletons while
    # it stands, which is what makes leaving it alive expensive rather than merely untidy.
    spawns=(("tombstone", 1, 0.26, 0.36, 0.0),),
    success=lambda e, s: (not _enemy(e, "tombstone") and played(s, "earthquake")),
    failure=lambda e, s: ((float(e.t) - float(s.get("t0", 0.0))) >= 11.0
                          and bool(_enemy(e, "tombstone"))),
    time_limit=14.0,
    randomise=("lane", "timing"),
    graded_by=("wincon_exec", "spell_waste"),
    prereq=(),
    reference=(("earthquake", 0.26, 0.36, 0.6),),
    notes="Only became a reachable action at all once spells were allowed past the river -- before "
          "that the quake was clamped to our own front row, ten tiles short of the target.",
))

register(Scenario(
    name="log_resets_the_charge",
    goal="Roll the Log into a charging Battle Ram -- the knockback is the point.",
    tier="foundational",
    hand=("the_log",),
    elixir=5.0,
    spawns=(("battle_ram", 1, 0.194, 0.46, 0.0),),
    success=lambda e, s: (not _enemy(e, "battle_ram") and not princess_hp_lost(e, s, 300.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 300.0),
    time_limit=14.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=("log_the_ground_swarm",),
    reference=(("the_log", 0.194, 0.62, 1.2),),
    notes="A connected charge costs a large chunk of tower; the same ram stopped early costs two "
          "elixir. The HP threshold is what separates the two outcomes.",
))

register(Scenario(
    name="skeletons_are_enough",
    goal="One elixir of Skeletons answers a lone Knight -- the cheapest sufficient answer.",
    tier="foundational",
    hand=("skeletons", "tesla", "mighty_miner", "firecracker"),
    elixir=6.0,
    spawns=(("knight", 1, 0.194, 0.46, 0.0),),
    # SPENT IS PART OF SUCCESS. A Tesla also answers a Knight, and it answers it for four elixir
    # and a building slot the deck needs for their win condition. Triage is about the cheapest
    # thing that WORKS, which is a different question from what works.
    success=lambda e, s: (not _enemy(e, "knight") and float(s.get("spent", 0.0)) <= 1.5
                          and not princess_hp_lost(e, s, 500.0)),
    failure=lambda e, s: spent_more_than(e, s, 3.0) or princess_hp_lost(e, s, 500.0),
    time_limit=18.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=(),
    reference=(("skeletons", 0.194, 0.66, 1.2),),
    notes="counters.yaml names this row (knight -> skeletons, surround) and the reward charges it "
          "-1.0, because profile('skeletons').dps is below the tank-answer bar. Drill kept as-is: "
          "the doctrine is right and the referee is wrong, which the pass rate will show.",
))

register(Scenario(
    name="hog_then_eq_in_order",
    goal="Hog FIRST, quake second -- the spell is spent on what is actually holding him.",
    tier="compound",
    hand=("hog_rider", "earthquake"),
    elixir=9.0,
    # THEIR CANNON IS ALREADY PLANTED. Quaking it before the Hog is committed spends three elixir
    # on a building they have not yet had to use; sending the Hog first makes the quake answer a
    # commitment instead of a guess. Same two cards, same board, opposite value.
    spawns=(("cannon", 1, 0.26, 0.36, 0.0),),
    success=lambda e, s: (played_before(s, "hog_rider", "earthquake")
                          and enemy_tower_hp_lost(e, s, 0.0)),
    failure=lambda e, s: played_before(s, "earthquake", "hog_rider"),
    time_limit=20.0,
    randomise=("lane", "timing"),
    graded_by=("wincon_exec", "spell_waste"),
    prereq=("eq_clears_the_hogs_building",),
    reference=(("hog_rider", 0.194, 0.5625, 0.6), ("earthquake", 0.26, 0.36, 2.4)),
    notes="The order predicate is the drill: a board three seconds later looks the same either "
          "way, and only the sequence says whether the elixir bought anything.",
))

register(Scenario(
    name="mm_leads_the_hog",
    goal="Mighty Miner goes FIRST and eats the building's attention; the Hog follows behind him.",
    tier="compound",
    hand=("mighty_miner", "hog_rider"),
    elixir=10.0,
    spawns=(("tesla", 1, 0.26, 0.36, 0.0),),
    # THE PAIR ONLY WORKS ONE WAY ROUND. A Hog sent first is what the Tesla locks onto, and he
    # dies to it; behind a Mighty Miner the building is already busy and he walks past.
    success=lambda e, s: (played_before(s, "mighty_miner", "hog_rider")
                          and enemy_tower_hp_lost(e, s, 0.0)),
    failure=lambda e, s: played_before(s, "hog_rider", "mighty_miner"),
    time_limit=22.0,
    randomise=("lane", "timing"),
    graded_by=("wincon_exec",),
    prereq=("hog_send_on_a_quiet_board", "mm_blocks_the_tank"),
    reference=(("mighty_miner", 0.194, 0.5625, 0.6), ("hog_rider", 0.194, 0.5625, 2.4)),
    notes="`_hog_wincon`'s c0 branch already prices 'behind the mini-tank'; this is the board it "
          "was written for, at a size where the pass rate can see it.",
))

register(Scenario(
    name="tesla_late_not_early",
    goal="A building has a lifetime. Hold it until their win condition is actually coming.",
    tier="compound",
    hand=("tesla",),
    elixir=9.0,
    spawns=(("hog_rider", 1, 0.194, 0.44, 9.0),),
    success=lambda e, s: (not _enemy(e) and (first_play_t(s, "tesla") or 0.0) >= 7.0
                          and not princess_hp_lost(e, s, 120.0)),
    failure=lambda e, s: (((first_play_t(s, "tesla") or 99.0) < 5.0)
                          or princess_hp_lost(e, s, 400.0)),
    time_limit=22.0,
    randomise=("lane", "elixir"),
    graded_by=("building_waste", "threat_response"),
    prereq=("tesla_pulls_the_wincon",),
    reference=(("tesla", 0.50, 0.645, 8.4),),
    notes="Evo Tesla lives 25s, so one planted on an empty board is most of the way through its "
          "life before the push arrives. The failure predicate is the CLOCK, not the outcome.",
))

register(Scenario(
    name="ice_spirit_denies_the_hit",
    goal="One elixir of freeze, spent on the thing that is already swinging at our tower.",
    tier="foundational",
    hand=("ice_spirit",),
    elixir=4.0,
    spawns=(("hog_rider", 1, 0.194, 0.60, 0.0),),
    # THE SPIRIT IS A TEMPO CARD, not an answer: it does not kill the Hog, it costs him swings
    # while the tower keeps firing. So the drill is scored purely on tower HP.
    # THRESHOLDS FROM MEASUREMENT: the tower loses 1584 HP to this Hog unaided and 1267 with a
    # well-timed spirit -- almost exactly one hog hit, which is what one elixir of freeze is worth.
    # The first draft's 620 bar sat below both, so it failed a perfect line and read as impossible.
    success=lambda e, s: (not _enemy(e, "hog_rider") and not princess_hp_lost(e, s, 1400.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 1550.0),
    time_limit=16.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "chip_defence"),
    prereq=(),
    reference=(("ice_spirit", 0.194, 0.72, 0.6),),
    notes="Cheapest sufficient answer, at the extreme: one elixir that buys two hits. Played early "
          "the freeze expires before the swing, which is why the threshold is tight.",
))

register(Scenario(
    name="firecracker_answers_the_air",
    goal="She is the deck's only air answer -- and she is played to DEFEND, not at the bridge.",
    tier="foundational",
    hand=("firecracker",),
    elixir=6.0,
    spawns=(("minions", 1, 0.194, 0.50, 0.0), ("minions", 1, 0.24, 0.54, 0.0)),
    success=lambda e, s: (not _enemy(e) and not princess_hp_lost(e, s, 700.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 1100.0),
    time_limit=18.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=("firecracker_never_alone",),
    reference=(("firecracker", 0.194, 0.70, 0.6),),
    notes="The legitimate half of the never-alone rule: with air on the board she is not support, "
          "she is the answer, and holding her is the mistake.",
))

register(Scenario(
    name="eq_the_pump_on_sight",
    goal="An Elixir Collector is a clock -- quake it before it pays for itself.",
    tier="foundational",
    hand=("earthquake",),
    elixir=6.0,
    spawns=(("elixir_collector", 1, 0.30, 0.16, 0.0),),
    # THE QUAKE REACHES IT ONLY BECAUSE SPELLS MAY CROSS THE RIVER NOW. Before that fix this was
    # a cast clamped to our own front row, roughly ten tiles short of the pump.
    success=lambda e, s: (not _enemy(e, "elixir_collector") and played(s, "earthquake")),
    failure=lambda e, s: ((float(e.t) - float(s.get("t0", 0.0))) >= 13.0
                          and bool(_enemy(e, "elixir_collector"))),
    time_limit=16.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("wincon_exec", "spell_waste"),
    prereq=("eq_kills_the_spawner",),
    reference=(("earthquake", 0.30, 0.16, 0.6),),
    notes="Pump denial has no reward term in this deck at all -- icebow prices it through "
          "_pump_rocket and hogeq has no equivalent. See HANDOFF SS6.0a.",
))

register(Scenario(
    name="split_lane_needs_the_centre",
    goal="One building answers BOTH lanes only if it is dead centre.",
    tier="compound",
    hand=("tesla",),
    elixir=7.0,
    spawns=(("royal_hogs", 1, 0.40, 0.44, 0.0),),
    success=lambda e, s: (not _enemy(e) and not princess_hp_lost(e, s, 600.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 900.0),
    time_limit=20.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "chip_defence"),
    prereq=("tesla_pulls_the_wincon",),
    reference=(("tesla", 0.50, 0.62, 0.6),),
    notes="Royal Hogs split on arrival, so a Tesla planted in one lane watches the other half "
          "walk past -- the centre tile is the only placement that answers the card at all.",
))

register(Scenario(
    name="hold_the_cheap_answers",
    goal="Spend NOTHING on a trickle the tower eats for free.",
    tier="foundational",
    hand=("the_log", "skeletons", "ice_spirit", "firecracker"),
    elixir=6.0,
    spawns=(("skeletons", 1, 0.30, 0.46, 0.0),),
    # NO REFERENCE LINE ON PURPOSE: the correct play is to play nothing, which the do-nothing
    # column already measures. Triage is the tier ABOVE every counter rule and the one both decks
    # kept violating, so it gets its own scenario on each of them.
    success=lambda e, s: (not _enemy(e) and float(s.get("spent", 0.0)) <= 0.0),
    failure=lambda e, s: spent_more_than(e, s, 0.0),
    time_limit=10.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_miss_idle", "elixir_trade"),
    prereq=(),
    notes="hogeq's twin of icebow's ignore_the_ignorable. The Log prior used to spend itself here "
          "because its swarm rule counted BODIES -- one 1-elixir card is three of them.",
))
