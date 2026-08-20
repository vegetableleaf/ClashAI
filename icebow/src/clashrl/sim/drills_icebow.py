"""ICEBOW DRILLS. Each one rehearses a single interaction; see `scenarios.py` for the design.

Coordinates are the engine's: OUR side is HIGH y (princesses ~0.80, king ~0.91), the enemy is LOW
y (~0.20), the river is ~0.50, and the bridges sit at x ~0.25 / ~0.75.

This file is the SEED of the curriculum -- the first tier, proven end to end. The full researched
list lands alongside it; each entry here is meant to be read as the template for the rest: a board,
a scripted opponent, two engine-readable predicates, and a declared list of what varies per rep.
"""
from __future__ import annotations

from .scenarios import (Scenario, both, either, princess_hp_lost, register, spent_more_than,
                        targets_our_king, targets_our_princess)

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
    notes="The Log is a CORRIDOR that rolls FORWARD from the cast point: anything behind the cast "
          "is untouched, which is the 'played too high, hit nothing, scored a hit' bug. Here a "
          "miss is unambiguous because the swarm simply survives.",
))

register(Scenario(
    name="ignore_the_ignorable",
    goal="Spend NOTHING on a lone Skeletons -- the tower handles it.",
    tier="foundational",
    hand=(),                      # the whole deck: the temptation has to be available
    elixir=10.0,
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
