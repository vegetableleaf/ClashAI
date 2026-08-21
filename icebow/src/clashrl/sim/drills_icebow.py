"""ICEBOW DRILLS. Each one rehearses a single interaction; see `scenarios.py` for the design.

Coordinates are the engine's: OUR side is HIGH y (princesses ~0.80, king ~0.91), the enemy is LOW
y (~0.20), the river is ~0.50, and the bridges sit at x ~0.25 / ~0.75.

This file is the SEED of the curriculum -- the first tier, proven end to end. The full researched
list lands alongside it; each entry here is meant to be read as the template for the rest: a board,
a scripted opponent, two engine-readable predicates, and a declared list of what varies per rep.
"""
from __future__ import annotations

from .scenarios import (Scenario, both, either, enemy_tower_hp_lost, first_play_t, n_plays,
                        played, played_before, play_xy, princess_hp_lost, register,
                        spent_more_than, targets_our_king, targets_our_princess)

# ---------------------------------------------------------------------------------------------
# TIER 1 -- FOUNDATIONAL: one card, one question.
# ---------------------------------------------------------------------------------------------

register(Scenario(
    name="nado_king_activation",
    goal="Tornado a lone attacker into our own King Tower so it retargets the king.",
    tier="foundational",
    hand=("tornado",),
    elixir=6.0,
    # THE ATTACKER MUST BE A TOWER-BOUND WIN CONDITION, and the measurement is why. Sweeping all
    # 432 action cells against the engine, the number that actually end with the attacker on our
    # king is: Hog Rider 8, Balloon 13, Knight 0-4, Miner 1. A Knight was the first draft and is
    # the worst possible case -- it re-picks the NEAREST tower when the pull breaks its lock, and
    # from anywhere the pull can reach, the princess is still nearer, so the window collapses to a
    # knife edge no policy could find. A Hog ignores troops and towers alike until it reaches a
    # BUILDING, so dragging it into king range genuinely redirects it. That is also exactly the
    # set doctrine's own gate selects (`building_only or y > 0.55`), so the drill now rehearses
    # the play the deck actually has rather than one the engine cannot express.
    spawns=(("hog_rider", 1, 0.25, 0.46, 0.0),),
    # SUCCESS is the attacker going for the KING -- the project owner's correction, and the
    # reason this is not `king.active`: the king also wakes from ordinary chip damage, so testing
    # the flag alone would score a FAILED pull (king awake, attacker still on the princess) as a
    # win. FAILURE is the mirror: it is still going for the princess.
    # FAILURE IS SUSTAINED DAMAGE, not merely "it is aiming at the princess". A tower-bound
    # attacker aims at a tower from the moment it spawns, so a targeting test failed the drill
    # before the agent could cast anything. The owner's own wording is the right one: it fails if
    # the troop "reaches the ally tower and CONTINUES DAMAGING it after the attempted tornado".
    #
    # THE THRESHOLD IS THREE HOG HITS (~264 each), and that number is load-bearing. At 220 the
    # drill ended on the FIRST connection, which left no interaction to rehearse: measured against
    # the engine, the pull only becomes physically available once the attacker is close enough for
    # a spot in front of the king to reach it -- which for a Hog is the moment it arrives at the
    # princess. The real king activation is cast on an attacker that is ALREADY chewing on the
    # tower (that is the board where the sweep found 8 winning cells, against 0-4 for one still
    # walking), so the drill has to let it arrive and then punish it for staying.
    success=targets_our_king,
    failure=lambda e, s: princess_hp_lost(e, s, 800.0),
    time_limit=14.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("nado_king_activate", "nado_clump"),
    prereq=(),
    reference=((("tornado", 0.472, 0.771, 3.6)),),
    notes="The single highest-value Tornado in the deck and one the live model has never once "
          "attempted. doctrine.nado_king_cell already knows WHERE; this teaches WHEN.",
))

register(Scenario(
    name="tesla_pulls_the_wincon",
    goal="Place the Tesla so a building-targeting win condition is dragged off the tower path.",
    tier="foundational",
    hand=("tesla",),
    elixir=6.0,
    spawns=(("hog_rider", 1, 0.75, 0.44, 0.0),),
    # The hog must DIE to the pull, and our tower must barely feel it. A hog that connects even
    # once has beaten the placement.
    # TIGHTENED after measuring the do-nothing baseline at 7/15: a lone Hog sometimes dies to the
    # tower unaided, so "the hog died" proves nothing about the pull. A Hog that CONNECTS even
    # once costs far more than this, so the HP bar is what separates a real pull from luck.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 and u.spec.base == "hog_rider"
                                  for u in e.units)
                          and not princess_hp_lost(e, s, 80.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 80.0),
    time_limit=16.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=(),
    reference=((("tesla", 0.5, 0.645, 0.6)),),
    notes="The centre-pull geometry already exists (reward.tesla_pull_cell); this rehearses "
          "committing to it early enough that the pull has room to work.",
))

register(Scenario(
    name="log_the_ground_swarm",
    goal="Roll the Log THROUGH a ground swarm -- not past it, not beside it.",
    tier="foundational",
    hand=("the_log",),
    elixir=4.0,
    spawns=(("skeleton_army", 1, 0.25, 0.44, 0.0),),
    # TIGHTENED after measuring the do-nothing baseline at 15/15: the tower kills a swarm on its
    # own given long enough, so "they all died" is not evidence that the Log did anything. The
    # swarm must die WITHOUT the tower paying for it, which only a landed roll achieves.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 60.0)),
    failure=lambda e, s: either(lambda ee, ss: princess_hp_lost(ee, ss, 120.0),
                                lambda ee, ss: spent_more_than(ee, ss, 4.0))(e, s),
    time_limit=12.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "spell_waste"),
    prereq=(),
    reference=((("the_log", 0.25, 0.6, 0.6)),),
    notes="The Log is a CORRIDOR that rolls FORWARD from the cast point: anything behind the cast "
          "is untouched, which is the 'played too high, hit nothing, scored a hit' bug. Here a "
          "miss is unambiguous because the swarm simply survives.",
))

register(Scenario(
    name="ignore_the_ignorable",
    goal="Spend NOTHING on a lone Skeletons -- the tower handles it.",
    tier="foundational",
    # THE TEMPTATION MUST BE A COUNTER, not the whole deck. Dealt everything at 10 elixir the
    # doctrine oracle opened with the X-Bow -- which is CORRECT icebow play on a quiet board and
    # has nothing to do with the trickle -- and the drill billed it as a failure, because the
    # failure test is "did you spend". Restricted to the cards you would actually be tempted to
    # throw at a couple of Skeletons, a spend can only mean answering them, which is the thing
    # being rehearsed. The elixir comes down for the same reason: at 10 the drill also measures
    # leak pressure, and one drill should ask one question.
    hand=("the_log", "skeletons", "knight", "ice_wizard"),
    elixir=6.0,
    spawns=(("skeletons", 1, 0.25, 0.46, 0.0),),
    # Success is the tower resolving it while we kept our elixir. Triage is a tier ABOVE every
    # counter rule and the one the deck kept violating, so it gets its own drill.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and float(s.get("spent", 0.0)) <= 0.0),
    failure=lambda e, s: spent_more_than(e, s, 0.0),
    time_limit=10.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_miss_idle", "elixir_trade"),
    prereq=(),
    notes="Deliberately inverts the usual objective: the RIGHT play is no play. Guards against a "
          "curriculum that only ever teaches 'answer everything'.",
))

# =============================================================================================
# TIER 0 -- PRIMITIVES. What every later drill assumes. A failure here is a broken fundamental,
# not bad judgement.
# =============================================================================================

register(Scenario(
    name="hold_the_spell_for_a_target",
    goal="Do not cast into empty ground -- wait for something to be under it.",
    tier="foundational",
    hand=("the_log",),
    elixir=6.0,
    # NOTHING for the first stretch, then a real target. Both halves are needed: a drill that only
    # says "do not whiff" is passed by doing nothing forever, which teaches a policy to never cast
    # at all. Requiring the late target to actually die makes holding the ONLY winning line -- you
    # cannot pass it by being passive, and you cannot pass it by being trigger-happy.
    spawns=(("goblin_gang", 1, 0.194, 0.44, 5.0),),
    # THE TOWER MUST NOT PAY FOR IT. Without the HP clause the drill was passed 80% of the time by
    # doing nothing: the gang walks in, the tower grinds it down, and "no enemy alive" comes true
    # on its own. Requiring the tower to come through untouched means only a landed roll passes,
    # while the early-cast failure below still punishes the trigger-happy line.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 120.0)
                          and n_plays(s) <= 1 and float(e.t) - float(s.get("t0", 0.0)) > 5.0),
    failure=lambda e, s: (n_plays(s) >= 1
                          and (first_play_t(s, "the_log") or 99.0) < 4.5),
    time_limit=14.0,
    randomise=("lane", "timing"),
    graded_by=("spell_waste", "elixir_trade"),
    prereq=(),
    reference=((("the_log", 0.194, 0.6, 5.4)),),
    notes="The hallucinated-cast failure in its simplest form: the board is empty, the spell is in "
          "hand, and the only correct action is to keep holding it.",
))

register(Scenario(
    name="log_rolls_forward_not_backward",
    goal="The Log is a CORRIDOR that rolls forward -- cast BEHIND the group, never in front of it.",
    tier="foundational",
    hand=("the_log",),
    elixir=6.0,
    # TWO BODIES AT DIFFERENT DEPTHS in one lane. Only a cast behind BOTH catches the pair, so a
    # roll aimed at the leader -- the natural mistake, and the "played it too high" report -- takes
    # one and leaves the other. The pair is what makes the geometry legible in the pass rate.
    # SKELETONS, NOT ARCHERS. Archers have 304 HP and The Log deals ~240, so the first draft asked
    # for a kill the card cannot make and was unwinnable however well the roll was aimed -- the
    # drill measured the card's damage, not the player's geometry. Skeletons die to it, so the
    # question goes back to being "did the corridor cover both groups".
    # THREE GROUPS, and the count is measured rather than chosen: with two, the tower cleared them
    # unaided inside the limit and the do-nothing baseline passed 8/8 -- the drill was scoring the
    # tower. With three it is 0/8 doing nothing and 8/8 for a roll cast behind all of them.
    spawns=(("skeletons", 1, 0.194, 0.52, 0.0), ("skeletons", 1, 0.194, 0.60, 0.0),
            ("skeletons", 1, 0.194, 0.68, 0.0)),
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and n_plays(s) <= 1),
    failure=lambda e, s: princess_hp_lost(e, s, 200.0) or spent_more_than(e, s, 4.0),
    # SHORT ON PURPOSE: given long enough the tower clears a trickle by itself, and then the pass
    # rate stops being about the roll at all.
    time_limit=8.0,
    randomise=("lane", "timing"),
    graded_by=("spell_waste", "elixir_trade"),
    prereq=("hold_the_spell_for_a_target",),
    reference=((("the_log", 0.194, 0.72, 0.6)),),
    notes="Archers rather than a swarm on purpose: two bodies, two depths, and the tower cannot "
          "clean them up inside the limit, so only the roll can.",
))

register(Scenario(
    name="bank_to_six_then_bow",
    goal="A 3.5-cycle deck BANKS. Hold, then spend the bank on the win condition.",
    tier="foundational",
    # THE TEMPTATION HAS TO BE DEALT. The failure branch below names the cards you would dump the
    # bar on, and once `hand` actually restricted the hand they stopped being dealt -- so nothing
    # could fail the drill and it passed 60/60. Same reasoning ignore_the_ignorable already records:
    # a restraint drill has to hold the thing you are being asked not to spend on. X-Bow first, so
    # the card the drill is named for is in the opening hand.
    hand=("x_bow", "knight", "skeletons", "ice_wizard", "tesla"),
    elixir=2.0,
    spawns=(),                     # a quiet board is the whole board
    # Success is the bow going down at all -- from 2 elixir that cannot happen until the bank has
    # filled, so the wait is implicit and does not need its own predicate. The failure side is what
    # makes it a discipline drill: dumping the bar on anything else, or sitting past the leak point.
    success=lambda e, s: any(u.team == 0 and u.spec.base == "x_bow" for u in e.units),
    failure=lambda e, s: (played(s, "knight", "skeletons", "ice_wizard", "tesla")
                          or float(e.elixir[0]) >= 9.99),
    time_limit=26.0,
    randomise=("lane", "elixir"),
    graded_by=("wincon_exec", "leak"),
    prereq=(),
    reference=((("x_bow", 0.5, 0.62, 0)),),
    notes="Banking is correct play for THIS deck (3.5 cycle, not 2.9) and the reward's leak term "
          "pushes the other way, so the discipline needs rehearsing explicitly.",
))

# =============================================================================================
# TIER 1 -- SINGLE-CARD FUNDAMENTALS.
# =============================================================================================

def _wake_the_king(env):
    """The king is already up: the activation branch cannot fire, so the drill measures the PULL."""
    kt = env.eng.towers[0][2]
    kt.active = True


# REMOVED -- `nado_drag_off_the_tower`. Measured with and without a well-placed pull, our tower
# lost 950 HP either way: the Hog dies to the princess on the same clock whether or not it was
# dragged, so the total damage converges and the drill could not tell a correct pull from no pull
# at all. The play is real icebow doctrine (mitigation once the king is already awake) and the
# engine simply does not express its value on this board -- so it is recorded as an open question
# rather than kept as a scenario that measures nothing. See HANDOFF SS6.0.
register(Scenario(
    name="nado_clump_for_the_wizard",
    goal="Pull a spread group onto one point so splash can answer all of it.",
    tier="compound",
    hand=("tornado", "ice_wizard"),
    elixir=9.0,
    # SPREAD ON PURPOSE -- three bodies far enough apart that no single splash reaches two of them.
    # Clumping is the entire play, so the board has to start un-clumped or the drill measures the
    # spawn instead of the pull.
    spawns=(("minions", 1, 0.14, 0.44, 0.0), ("minions", 1, 0.30, 0.46, 0.0),
            ("minions", 1, 0.22, 0.40, 0.0)),
    # SCORED IN TOWER HP, not in bodies. Every minion dies in every line -- the tower gets them
    # eventually -- so counting corpses measured nothing. What the pull actually buys is how much
    # the tower paid on the way: measured, doing nothing costs 3204 HP, a Tornado into the Ice
    # Wizard costs 854, and the same two cards in the wrong order cost 1068. That spread is the
    # skill, and it is invisible to a body count.
    success=lambda e, s: (played(s, "tornado") and not princess_hp_lost(e, s, 1500.0)
                          and not any(u.team == 1 and u.hp > 0 for u in e.units)),
    failure=lambda e, s: princess_hp_lost(e, s, 2200.0) or spent_more_than(e, s, 9.0),
    time_limit=16.0,
    randomise=("lane", "timing"),
    graded_by=("nado_clump", "nado_combo", "elixir_trade"),
    prereq=("nado_king_activation",),
    reference=(("tornado", 0.22, 0.5, 1.2), ("ice_wizard", 0.25, 0.62, 1.8)),
    notes="Minions are air, so the Log cannot answer and the Tornado's pull is genuinely the "
          "enabling card rather than one of several ways through.",
))

register(Scenario(
    name="knight_blocks_the_charge",
    goal="Put a body in the path of a charging attacker before it reaches the tower.",
    tier="foundational",
    hand=("knight",),
    elixir=6.0,
    spawns=(("prince", 1, 0.194, 0.44, 0.0),),
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 400.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 400.0),
    time_limit=18.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=(),
    reference=((("knight", 0.194, 0.62, 0.6)),),
    notes="A Prince that connects costs far more than the Knight does, so the trade is only good "
          "if the block happens BEFORE the charge lands -- which is what the HP bar measures.",
))

register(Scenario(
    name="skeletons_kill_the_miner",
    goal="One elixir answers a Miner on the tower -- the cheapest sufficient answer.",
    tier="foundational",
    hand=("skeletons",),
    elixir=4.0,
    spawns=(("miner", 1, 0.194, 0.76, 0.0),),
    # SPENT <= 1 IS PART OF SUCCESS. The Miner dies to almost anything; the skill is answering him
    # with the cheapest thing that works instead of the first thing in hand, which is the tier the
    # deck kept skipping.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and float(s.get("spent", 0.0)) <= 1.5
                          and not princess_hp_lost(e, s, 350.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 350.0) or spent_more_than(e, s, 3.0),
    time_limit=12.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=(),
    reference=((("skeletons", 0.194, 0.78, 0.6)),),
    notes="The Miner arrives AT the tower rather than up the lane, so this also rehearses "
          "answering a threat that skipped the whole approach.",
))

register(Scenario(
    name="bow_never_into_the_push",
    goal="Never send the X-Bow forward into a committed push, however full the bar is.",
    tier="foundational",
    # THE BOW IS IN HAND -- it has to be REFUSED, not merely undrawn -- and so are the answers.
    # Dealt the whole deck, the reference defence simply was not in the opening hand in most reps
    # and the drill's outcome went bimodal: 0 damage when the cards showed up, and exactly the
    # do-nothing 2496 when they did not. That is measuring the deal, not the decision.
    hand=("x_bow", "tesla", "knight", "ice_wizard"),
    elixir=10.0,
    # TEN ELIXIR IS THE TRAP, not an oversight: the leak penalty makes spending feel urgent and the
    # bow is the most expensive thing in hand. This is the measured -276.0 failure put on a board
    # small enough to see.
    spawns=(("giant", 1, 0.194, 0.44, 0.0), ("musketeer", 1, 0.194, 0.40, 0.0)),
    # THRESHOLDS FROM THE BEST LINE AVAILABLE. A Giant plus a Musketeer is genuinely expensive to
    # hold, and at 800 the drill failed even a correct knight-then-Tesla-then-Ice-Wizard defence --
    # it was scoring "did you defend perfectly" when the rule being rehearsed is "did you refuse
    # the bow". The Hog... the BOW veto stays absolute in the failure predicate; the HP bar just
    # has to sit where a competent defence lands rather than where a flawless one does.
    success=lambda e, s: (not played(s, "x_bow") and not princess_hp_lost(e, s, 1400.0)
                          and (not any(u.team == 1 and u.hp > 0 for u in e.units)
                               or (float(e.t) - float(s.get("t0", 0.0))) >= 17.4)),
    failure=lambda e, s: played(s, "x_bow") or princess_hp_lost(e, s, 1900.0),
    time_limit=18.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("xbow_into_push", "threat_response"),
    prereq=(),
    reference=(("knight", 0.30, 0.60, 0.6), ("tesla", 0.50, 0.62, 1.8),
               ("ice_wizard", 0.35, 0.70, 3.5)),
    notes="Pairs with bow_punish_the_commitment: same card, opposite verdict, and only the board "
          "tells them apart. Trained alone, either one becomes a reflex.",
))

register(Scenario(
    name="bow_punish_the_commitment",
    goal="They spent it all at the back -- put the bow in the OTHER lane, now.",
    tier="foundational",
    hand=("x_bow",),
    elixir=8.0,
    # A GOLEM AT THEIR BACK is the punish window in one card: nine elixir committed, nothing left
    # to answer with, and a long walk before it threatens anything.
    spawns=(("golem", 1, 0.194, 0.14, 0.0),),
    success=lambda e, s: enemy_tower_hp_lost(e, s, 0.0),
    failure=lambda e, s: (not played(s, "x_bow")
                          and (float(e.t) - float(s.get("t0", 0.0))) >= 9.0),
    time_limit=24.0,
    randomise=("lane", "elixir"),
    graded_by=("wincon_exec", "xbow_lock", "chip_linear"),
    prereq=("bank_to_six_then_bow",),
    reference=((("x_bow", 0.72, 0.56, 0.6)),),
    notes="Scored on the bow actually CHIPPING, not on where it was put: a technically good spot "
          "that never locks a tower is the failure this deck kept producing.",
))

register(Scenario(
    name="rocket_the_two_for_one",
    goal="Rocket a support that is standing next to their tower -- damage plus a kill.",
    tier="foundational",
    hand=("rocket",),
    elixir=8.0,
    # A WITCH BESIDE THEIR PRINCESS: 839 HP, comfortably inside a rocket, and close enough that the
    # same blast reaches the tower. The whole play is noticing that one aim point buys both.
    # BESIDE THE TOWER, not merely near it. At 2.4 tiles from the princess no single aim point
    # reaches both -- the blast is 2.0 -- so the drill was asking for a play the board did not
    # contain. A sweep of every action cell at this spawn finds cell 93 killing her AND landing
    # 342 on the tower, which is the 2-for-1 the drill is named after.
    # BESIDE THEIR PRINCESS, and the y matters: a Witch WALKS. Spawned deeper she is 2.6 tiles
    # from the blast by the time anyone can cast, and the rocket that reaches the tower misses
    # her -- which is how the first version came to fail even a scripted perfect line. Beside the
    # tower she is inside the same 2.0-tile blast for the whole opening window: measured 6/6 with
    # a rocket in the first 1.8s, 0/6 doing nothing.
    spawns=(("witch", 1, 0.194, 0.19, 0.0),),
    # SCORED ON THE WITCH, not on an empty board: she spawns skeletons for as long as she lives
    # and the ones already out keep walking after she dies, so "no enemy alive" was unachievable
    # no matter how good the rocket was. Measured, the play was working the whole time.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 and u.spec.base == "witch"
                                  for u in e.units)
                          and enemy_tower_hp_lost(e, s, 250.0)),
    failure=lambda e, s: (n_plays(s) >= 1 and not played(s, "rocket")) or spent_more_than(e, s, 6.5),
    time_limit=12.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("wincon_exec", "elixir_trade"),
    prereq=(),
    reference=((("rocket", 0.194, 0.229, 0.6)),),
    notes="Both halves are required, which is what separates this from 'rocket a troop': killing "
          "the witch in open ground is a fair trade, not the play.",
))

register(Scenario(
    name="rocket_the_pump_on_sight",
    goal="An Elixir Collector is a clock -- rocket it before it pays for itself.",
    tier="foundational",
    hand=("rocket",),
    elixir=8.0,
    spawns=(("elixir_collector", 1, 0.30, 0.16, 0.0),),
    # ON SIGHT MEANS ON SIGHT. The first cut allowed 11 seconds, which is not the play: a pump
    # generates 1 elixir every 8.5s over a 70s life, so every second it stands is elixir already
    # banked and unrecoverable. The owner's rule -- rocket it AS IT IS PLACED -- is a TIMING skill,
    # so the clock is in the predicate: the cast has to be away inside 3s of the pump appearing,
    # and a pump still standing at 5s has already paid for part of itself.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 and u.spec.base == "elixir_collector"
                                  for u in e.units)
                          and (first_play_t(s, "rocket") or 99.0) <= 3.0),
    # THE CAST BAR AND THE KILL BAR ARE DIFFERENT CLOCKS. Owner's correction: a rocket takes real
    # time to reach a pump at the far end of the board, so demanding the kill by 5s was failing the
    # travel, not the decision. The DECISION is still gated at 3s -- that is the skill being drilled
    # -- while the pump gets the full 11s to actually die.
    failure=lambda e, s: (((float(e.t) - float(s.get("t0", 0.0))) >= 11.0
                           and any(u.team == 1 and u.hp > 0 and u.spec.base == "elixir_collector"
                                   for u in e.units))
                          or ((first_play_t(s, "rocket") or 0.0) > 3.5)),
    time_limit=14.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("wincon_exec",),
    prereq=("rocket_the_two_for_one",),
    reference=((("rocket", 0.3, 0.16, 1.2)),),
    notes="Deliberately a TIMED drill: a pump rocketed late has already paid for the rocket, so "
          "the failure predicate is the clock rather than the board.",
))

register(Scenario(
    name="log_the_barrel_on_landing",
    goal="Keep the Log for the barrel -- and roll it the moment the goblins land.",
    tier="compound",
    hand=("the_log",),
    elixir=6.0,
    # THE BAIT COMES FIRST. A Princess at the bridge is the card the Log is always tempted by, and
    # spending it there is exactly why the barrel connects two seconds later. Rotation discipline
    # is the skill and it only exists when the temptation is on the board first.
    spawns=(("princess", 1, 0.194, 0.42, 0.0), ("goblin_barrel", 1, 0.194, 0.78, 4.0)),
    # THRESHOLDS FROM MEASUREMENT, not from taste. Doing nothing costs 1926 HP; a Log rolled as
    # the goblins land costs 672. The first draft's 300 bar sat below BOTH, so it failed a perfect
    # line and read as "impossible". 1000 separates them with room on either side.
    success=lambda e, s: ((first_play_t(s, "the_log") or 0.0) >= 3.5
                          and not princess_hp_lost(e, s, 1000.0)
                          and not any(u.team == 1 and u.hp > 0 and u.spec.base == "goblins"
                                      for u in e.units)),
    failure=lambda e, s: princess_hp_lost(e, s, 1300.0),
    time_limit=16.0,
    randomise=("lane",),
    graded_by=("elixir_trade", "spell_waste"),
    prereq=("log_rolls_forward_not_backward",),
    reference=((("the_log", 0.194, 0.88, 4.3)),),
    notes="The Princess is deliberately left alive in the success test: answering her is not the "
          "job, and a drill that rewarded killing her would teach the very habit it exists to stop.",
))

# =============================================================================================
# TIER 2 -- COMPOUND: two cards, an order, and a timing window.
# =============================================================================================

register(Scenario(
    name="rocket_then_tornado",
    goal="ROCKET FIRST, then Tornado -- the blast has to land inside a live pull.",
    tier="compound",
    hand=("rocket", "tornado"),
    elixir=10.0,
    # A SPREAD MEDIUM GROUP: three bodies too far apart for one blast, each worth killing. The
    # Tornado is what makes them one target, and the rocket is what kills them -- so the order is
    # the entire play and the board a second later looks nearly the same either way.
    spawns=(("musketeer", 1, 0.14, 0.44, 0.0), ("musketeer", 1, 0.30, 0.46, 0.0),
            ("archers", 1, 0.22, 0.40, 0.0)),
    success=lambda e, s: (played_before(s, "rocket", "tornado")
                          and sum(1 for u in e.units if u.team == 1 and u.hp > 0) <= 1),
    failure=lambda e, s: (played_before(s, "tornado", "rocket")
                          or princess_hp_lost(e, s, 900.0)),
    time_limit=16.0,
    randomise=("lane", "timing"),
    graded_by=("wincon_exec", "nado_clump", "nado_combo"),
    prereq=("nado_clump_for_the_wizard", "rocket_the_two_for_one"),
    reference=(("rocket", 0.22, 0.44, 1.2), ("tornado", 0.22, 0.44, 1.8)),
    notes="R6 in one board. The reward's own rocket+nado bonus reads eng.vortices at ROCKET-cast "
          "time and needs a live vortex, so under the doctrinal order there is none yet -- see "
          "HANDOFF SS6.0a. This drill is where that contradiction becomes a number.",
))

register(Scenario(
    name="knight_guards_the_bow",
    goal="The Knight goes IN FRONT of our X-Bow, between it and what is coming for it.",
    tier="compound",
    hand=("knight",),
    elixir=6.0,
    # OUR BOW IS ALREADY STANDING and a melee answer is walking at it. Everything the bow is worth
    # depends on how long it keeps firing, so the bodyguard is the play -- and "in front" is a
    # real constraint: a Knight dropped behind the bow watches it die.
    spawns=(("x_bow", 0, 0.26, 0.56, 0.0), ("valkyrie", 1, 0.24, 0.42, 0.0)),
    success=lambda e, s: (any(u.team == 0 and u.hp > 0 and u.spec.base == "x_bow" for u in e.units)
                          and not any(u.team == 1 and u.hp > 0 for u in e.units)),
    failure=lambda e, s: not any(u.team == 0 and u.hp > 0 and u.spec.base == "x_bow"
                                 for u in e.units),
    time_limit=20.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "xbow_lock"),
    prereq=("knight_blocks_the_charge",),
    reference=(("knight", 0.26, 0.50, 0.6),),
    notes="Scored on the BOW SURVIVING, which is the thing the Knight is bought for -- killing the "
          "Valkyrie in open ground somewhere else would be a fair trade and the wrong play.",
))

register(Scenario(
    name="nado_the_sneaky_lock",
    goal="Drag the defender off our X-Bow so the bow re-locks onto the tower.",
    tier="compound",
    # THE KNIGHT IS PART OF THE LINE, so it has to be part of the hand. The reference plays
    # both and the notes say why -- the pull converts the bow's attention, the body keeps it
    # alive long enough to matter -- but `hand` named only the Tornado. That was harmless
    # while a declared hand merely reordered the cycle; now that it restricts, an undeclared
    # card would make the drill's own answer unplayable.
    hand=("tornado", "knight"),
    elixir=6.0,
    # THIS PLAY DID NOT EXIST until spells were allowed past the river: the bow stands AT the
    # river and the cast has to land next to it, which `deploy_clamp` used to haul back into our
    # own half. It is also the cheapest way to convert a stalled bow into tower damage.
    spawns=(("x_bow", 0, 0.26, 0.53, 0.0), ("knight", 1, 0.26, 0.47, 0.0)),
    success=lambda e, s: enemy_tower_hp_lost(e, s, 150.0),
    failure=lambda e, s: not any(u.team == 0 and u.hp > 0 and u.spec.base == "x_bow"
                                 for u in e.units),
    time_limit=22.0,
    randomise=("lane",),
    graded_by=("nado_retarget", "xbow_lock", "chip_linear"),
    prereq=("nado_king_activation", "knight_guards_the_bow"),
    # THE BOW NEEDS A BODYGUARD TOO. A lone Tornado re-locks the bow and then watches it die: the
    # Valkyrie kills it before it lands a shot, so the drill scored 0 for every cast on its own.
    # The doctrine passes this by ALSO playing a Knight, which is the honest line -- the pull
    # converts the bow's attention, the body keeps it alive long enough to matter.
    reference=(("tornado", 0.26, 0.40, 1.2), ("knight", 0.26, 0.56, 2.4)),
    notes="`nado_retarget` cannot pay for this -- it requires the pulled unit to be building_only "
          "AND tower-locked -- and `nado_bad` can actively charge for it. A sampler-only play, "
          "which is exactly the kind a drill is for.",
))

register(Scenario(
    name="hold_the_tesla_for_their_wincon",
    goal="A building has a lifetime. Do not spend it on an empty board.",
    tier="compound",
    hand=("tesla",),
    elixir=9.0,
    # THE WINCON ARRIVES LATE, and a Tesla planted at t=0 is most of the way through its lifetime
    # by then. The user's own report: a Tesla in a good spot, dead of old age before the push came.
    spawns=(("hog_rider", 1, 0.194, 0.44, 9.0),),
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and (first_play_t(s, "tesla") or 0.0) >= 7.0
                          and not princess_hp_lost(e, s, 120.0)),
    failure=lambda e, s: (((first_play_t(s, "tesla") or 99.0) < 5.0)
                          or princess_hp_lost(e, s, 400.0)),
    time_limit=22.0,
    randomise=("lane", "elixir"),
    graded_by=("building_waste", "threat_response"),
    prereq=("tesla_pulls_the_wincon",),
    reference=(("tesla", 0.50, 0.645, 8.4),),
    notes="The failure predicate is the CLOCK, not the board: an early Tesla can still kill the "
          "Hog and would score a win on outcome alone, which is how the habit survives.",
))

register(Scenario(
    name="nado_pull_the_flock_back",
    goal="Pull an air swarm BACKWARD, into our own tower's range -- direction is the play.",
    tier="compound",
    hand=("tornado",),
    elixir=6.0,
    # ALREADY PAST THE GUNS. The generic clump rule aims at the centre band, which for a flock at
    # this depth is FORWARD of them -- it drags them away from the towers that are supposed to
    # kill them. For air swarms the pull DIRECTION, not the clump centre, is the whole play.
    spawns=(("minions", 1, 0.16, 0.66, 0.0), ("minions", 1, 0.24, 0.70, 0.0)),
    # SCORED IN TOWER HP. Every minion dies in every line -- the towers get them eventually -- so
    # a body count measured nothing at all. What the pull buys is what the towers paid for them:
    # measured, 3311 HP doing nothing against 2029 for a correct backward pull.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 2400.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 2900.0),
    time_limit=16.0,
    randomise=("lane", "timing"),
    graded_by=("nado_clump", "nado_bad"),
    prereq=("nado_clump_for_the_wizard",),
    reference=(("tornado", 0.20, 0.78, 0.6),),
    notes="`nado_bad` fires when survivors end up CLOSER to our princesses, which is precisely "
          "what this play does on purpose -- so a correct tornado-back is charged -0.3. Drill "
          "kept as the measurement of that disagreement.",
))

register(Scenario(
    name="never_rocket_their_king",
    goal="Rocket the PRINCESS side. Waking their king for chip damage is a gift.",
    tier="foundational",
    hand=("rocket",),
    elixir=8.0,
    # TWO TARGETS, one of them a trap: a support parked behind their KING (where a rocket wakes
    # the tower we least want awake) and an identical one beside a princess. Same card, same
    # elixir, opposite value.
    spawns=(("musketeer", 1, 0.50, 0.15, 0.0), ("musketeer", 1, 0.194, 0.19, 0.0)),
    success=lambda e, s: (enemy_tower_hp_lost(e, s, 250.0)
                          and not e.towers[1][2].active
                          and played(s, "rocket")),
    failure=lambda e, s: bool(e.towers[1][2].active),
    time_limit=12.0,
    randomise=("lane", "elixir"),
    graded_by=("wincon_exec",),
    prereq=("rocket_the_two_for_one",),
    reference=(("rocket", 0.194, 0.229, 0.6),),
    notes="Reads their king's `active` flag directly, so the drill fails the moment the blast "
          "touches it -- no inference from where the cast was aimed.",
))

register(Scenario(
    name="split_lane_needs_the_centre",
    goal="One building answers BOTH lanes only if it is dead centre.",
    tier="compound",
    hand=("tesla",),
    elixir=7.0,
    spawns=(("royal_hogs", 1, 0.40, 0.44, 0.0),),
    # ROYAL HOGS SPLIT on arrival, so a Tesla planted in one lane watches the other half walk past.
    # The centre tile is not a preference here, it is the only placement that answers the card.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 600.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 900.0),
    time_limit=20.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "chip_defence"),
    prereq=("tesla_pulls_the_wincon",),
    reference=(("tesla", 0.50, 0.62, 0.6),),
    notes="`threat_response`'s building branch pays the same anywhere in 0.50 <= ny <= 0.80, so "
          "the centre-vs-lane decision this rehearses is invisible to the reward.",
))

register(Scenario(
    name="ice_wizard_behind_the_line",
    goal="The Ice Wizard goes BEHIND the engagement -- he is 3 elixir of glass with a slow.",
    tier="compound",
    hand=("ice_wizard",),
    elixir=6.0,
    # A TANK PLUS A SPLASH BODY. Played in front the Ice Wizard is the first thing killed and the
    # slow never lands; played behind, he slows the whole push for its entire walk. Same card,
    # same second, and the only difference is a couple of tiles of depth.
    spawns=(("knight", 1, 0.194, 0.44, 0.0), ("baby_dragon", 1, 0.194, 0.40, 0.0)),
    success=lambda e, s: (any(u.team == 0 and u.hp > 0 and u.spec.base == "ice_wizard"
                              for u in e.units)
                          and not princess_hp_lost(e, s, 1100.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 1600.0),
    time_limit=22.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=(),
    reference=(("ice_wizard", 0.194, 0.72, 0.6),),
    notes="Scored on HIM SURVIVING as well as the tower holding: an Ice Wizard who traded himself "
          "for the slow has not done the job the card is in the deck for.",
))

register(Scenario(
    name="skeletons_stop_the_wall_breakers",
    goal="Wall Breakers die to one cheap body placed in the right spot -- never to a Rocket.",
    tier="foundational",
    hand=("skeletons", "rocket", "the_log", "knight"),
    elixir=8.0,
    # THE THRESHOLDS, NOT THE DEPTH, WERE THE PROBLEM. Unanswered from here they cost 391 HP,
    # which sat just UNDER the first draft's 400 bar -- so doing nothing passed 100% and the drill
    # was scoring the tower. Pushed deeper they cost 782 but the Skeletons no longer arrive in
    # time, and nothing passed. Here, with the bodies placed in front of the tower, a correct
    # answer costs **0** against 391 -- which is the user's own note that Skeletons handle Wall
    # Breakers with the tower's help, if they are placed correctly.
    spawns=(("wall_breakers", 1, 0.194, 0.56, 0.0),),
    # THE ELIXIR TRADE IS THE POINT. Rocketing a 2-elixir card is the exact play the counters work
    # was commissioned to stop, so the drill fails on the SPEND even when the outcome is fine.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and float(s.get("spent", 0.0)) <= 2.5
                          and not princess_hp_lost(e, s, 200.0)),
    failure=lambda e, s: (played(s, "rocket") or spent_more_than(e, s, 4.0)
                          or princess_hp_lost(e, s, 300.0)),
    time_limit=14.0,
    randomise=("lane", "timing", "elixir"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=("skeletons_kill_the_miner",),
    reference=(("skeletons", 0.194, 0.70, 0.6),),
    notes="The user's own example of an unrealistic counter: rocketing Wall Breakers is a "
          "horrible trade the advisor kept proposing. Here it is a hard failure.",
))

register(Scenario(
    name="bow_defends_from_the_centre",
    goal="A DEFENSIVE bow anchors the centre, where it covers both lanes and outranges the push.",
    tier="compound",
    hand=("x_bow",),
    elixir=8.0,
    spawns=(("giant", 1, 0.194, 0.44, 0.0),),
    # THE OTHER HALF OF bow_never_into_the_push: the bow is not forbidden while a push is coming,
    # it is forbidden FORWARD. Placed back and centre it is a defensive building that happens to
    # threaten. Getting only the veto drilled would teach "never play your win condition".
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 900.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 1400.0),
    time_limit=24.0,
    randomise=("lane", "timing"),
    graded_by=("wincon_exec", "xbow_lock"),
    prereq=("bow_never_into_the_push",),
    reference=(("x_bow", 0.50, 0.66, 0.6),),
    notes="Pairs with the veto drill so the policy learns WHERE rather than WHETHER -- the two "
          "differ only in the row the bow lands on.",
))

register(Scenario(
    name="matchup_hog_cycle",
    goal="A full Hog-cycle sequence: answer each wave without ever falling behind on elixir.",
    tier="matchup",
    hand=(),
    elixir=7.0,
    # A REAL ROTATION rather than one card: hog, then the cheap follow-up, then the next hog. The
    # tier exists to check that the Tier 1 and 2 skills survive contact with a deck that keeps
    # coming, which a single-interaction drill cannot show.
    spawns=(("hog_rider", 1, 0.194, 0.44, 0.0), ("skeletons", 1, 0.194, 0.46, 5.0),
            ("hog_rider", 1, 0.806, 0.44, 11.0), ("musketeer", 1, 0.806, 0.40, 13.0)),
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 1400.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 2200.0),
    time_limit=34.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "elixir_trade", "chip_defence"),
    prereq=("tesla_pulls_the_wincon", "ignore_the_ignorable"),
    # NO REFERENCE LINE: a matchup is a 30s sequence of waves, and four fixed taps cannot
    # answer it -- a scripted line scored 25% where the doctrine scores 62-94%. Here the
    # doctrine column IS the reference, and a policy is measured against it rather than
    # against a strawman.
    notes="Both lanes, two win conditions and a trickle in between -- the trickle is there to see "
          "whether triage survives when there is also something real to answer.",
))

register(Scenario(
    name="matchup_lavaloon",
    goal="Air only: the Tesla takes the hound, everything else goes on the Balloon.",
    tier="matchup",
    hand=(),
    elixir=9.0,
    spawns=(("lava_hound", 1, 0.194, 0.30, 0.0), ("balloon", 1, 0.194, 0.40, 7.0)),
    # THE BALLOON IS THE CARD THAT MATTERS. The hound does nothing on its own; every elixir spent
    # on it is elixir absent when the loon arrives, which is the mistake this rehearses.
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 and u.spec.base == "balloon"
                                  for u in e.units)
                          and not princess_hp_lost(e, s, 1200.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 1800.0),
    time_limit=30.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "chip_defence"),
    prereq=("tesla_pulls_the_wincon",),
    # NO REFERENCE LINE: a matchup is a 30s sequence of waves, and four fixed taps cannot
    # answer it -- a scripted line scored 25% where the doctrine scores 62-94%. Here the
    # doctrine column IS the reference, and a policy is measured against it rather than
    # against a strawman.
    notes="The Log and the Knight are both dead cards here, so the drill also rehearses NOT "
          "playing them -- a hand full of ground answers against an all-air push.",
))

register(Scenario(
    name="matchup_bridge_spam",
    goal="A PEKKA behind a charging Ram: reset the charge, then kite the tank.",
    tier="matchup",
    hand=(),
    elixir=9.0,
    spawns=(("battle_ram", 1, 0.194, 0.46, 0.0), ("pekka", 1, 0.194, 0.42, 3.0)),
    success=lambda e, s: (not any(u.team == 1 and u.hp > 0 for u in e.units)
                          and not princess_hp_lost(e, s, 1500.0)),
    failure=lambda e, s: princess_hp_lost(e, s, 2300.0),
    time_limit=32.0,
    randomise=("lane", "timing"),
    graded_by=("threat_response", "elixir_trade"),
    prereq=("knight_blocks_the_charge", "log_rolls_forward_not_backward"),
    # NO REFERENCE LINE: a matchup is a 30s sequence of waves, and four fixed taps cannot
    # answer it -- a scripted line scored 25% where the doctrine scores 62-94%. Here the
    # doctrine column IS the reference, and a policy is measured against it rather than
    # against a strawman.
    notes="config.yaml names PEKKA bridge spam as the dominant top-1000 deck, so this is the "
          "matchup the sim's opponent pool is most likely to be wrong about.",
))
