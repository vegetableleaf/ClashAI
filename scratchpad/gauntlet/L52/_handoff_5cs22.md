

### §5cs.22 -- SIM-PARITY ORACLE STEP 1b (2026-09-04, L52): tick-level diff of two clips finds three measured mechanic divergences (spell blast-to-edge, corner-placed buildings, hidden Tesla as a pathing target) and each fixes ITS clip -- but all three together move the 211-match crowns-match from 26.1% to 26.5% (null). The hog-damage candidate is contradicted (317 = 316.8). The bulk of the gap sits in swarm/bait fights: 20 sim matches end 3-0 for the opponent before 120 s (real set: 20 three-crown matches in total, at any time), skeleton-army in 8 of the 20, skeleton-king 5/9, witch 5/10, goblin-gang 5/17, minion-horde 4/13

**What ran.** `scratchpad/gauntlet/L52/tick_diff.py` (engine frame record `scratchpad/gauntlet/ext/replay_<tag>_run1.json`
vs `sim_replay_drive.py --record` per-0.1 s dump: per-card L11 HP, tower HP timelines + first-fall ticks, per-play
unit cohort lifetimes) on the two clips the engine batch recorded per tick (08CPVRRR8PYC, 00LYPLJLC80L);
`sim_replay_drive.py --patch {spell_edge,corner_buildings,hidden_pull}` -- the driver's `ParityEngine` subclass now
carries three mechanic patches (driver-only; engine.py untouched, c2r depends on it); five 211-match arms
(`L52/simbatch_<arm>/`, `L52/compare.py`); `L52/damage_attrib.py` (tower damage per side engine vs sim, HP/s, excess
by opponent card). c2r at 16:21: 32,675 eps, 0.5 ep/s, 17 procs, 4 GB free, untouched.

**(a) measured.**
- Hog hit on a tower: engine 317, sim 316.8. Rocket 1484 on units / 342 on crown towers (sim 341); fireball crown
  chip 172 both. The L51 "hog damage" candidate is (c) contradicted. Rocket flight time differs (engine 28 ticks at
  short range, 49 at long; sim 21/23) -- real, small, unpatched.
- Divergence 1, spells measure to the target's collision EDGE: engine rocket 2.24 tiles from an X-Bow kills it
  (1561 -> 71); sim rocket radius 2.0 centre-to-centre leaves it untouched (1600 -> 116 only after `spell_edge`,
  which sets `blast_edge` on every damaging thrown spell; engine.py sets it only for death bombs, line ~3824).
- Divergence 2, Tesla and Goblin Drill sit on tile CORNERS in the crawl (x_units 1789/1789, 60/60 = whole
  tiles + 0.0), the sim snaps every deploy to a tile centre (0.71-tile offset); `corner_buildings` places
  `tesla`/`goblin_drill` at `round(x*18)/18`.
- Divergence 3, a HIDDEN Tesla is a pathing target for building-targeters: the engine's hog turns toward the tesla
  on the placement tick at 6.18 / 7.13 tiles (tesla surfaces at deploy+1 s); sim `_valid_foe` returns False for
  `e.hidden`, so the hog walks past. `hidden_pull` lets building-only units target a hidden building.
- Each patch fixes its clip: 00LYPLJLC80L with `hidden_pull` matches real (0-1); 08CPVRRR8PYC with edge+corner
  matches (0-1 at 200 s).
- Population, 211 matches, crowns-match: base 55/211 = 26.1%; spell_edge 26.5; corner_buildings 26.5; edge+corner
  28.0; hidden_pull 26.5 (9 matches changed at all); all three 26.5% (winner 46.9%, wins s0/s1 171/19, crowns
  per side 1.38/0.15, sim==engine 67 vs 61). NULL. Two clips fixed, the population did not move.
- Where the damage goes (base run, engine `final.towers` vs sim): sim damage rate on the icebow (side 1) towers
  32.2 HP/s vs engine 16.2; on the opponent's towers 4.2 vs 15.2 -- icebow's offence a quarter, its defence half.
  Median match 180 s vs 276 s. Mean sim-minus-engine excess damage on icebow towers by opponent card: skeleton-army
  5010, mini-pekka(-hero) 4100-4300, ice-golem 4021, goblin-barrel-ev1 3926, dart-goblin 3868, skeleton-army-ev1
  3612 (n=24); negative for x-bow, royal-ghost-ev1, giant-skeleton, mighty-miner.
- Early collapses (all3 arm): 20 sim matches end 3-0 for the opponent before 120 s (fastest 40 s); the real set
  has 20 three-crown matches in total at any time (engine 18). Opponent-card share in those 20 vs the whole set:
  skeleton-army 8/20 vs 32/211 (2.6x), skeleton-king 5 vs 9 (5.9x), witch 5 vs 10 (5.3x), goblin-gang 5 vs 17
  (3.1x), minion-horde 4 vs 13 (3.2x), goblin-barrel 4 vs 19, dart-goblin 4 vs 18, night-witch 3 vs 14.
  Swarms and spawners; barbarian-barrel (5 vs 74) and lightning (3 vs 43) UNDER-represented.
- The evo Skeleton Army clip 08QPVCPC9QQU (real and engine 0-1, sim 3-0 at 39.6 s): sim ghosts (hp 1, untargetable,
  indestructible, `army_ghosts` rule at engine.py ~3496) accumulate 1 -> 7 while General Gerry (81 hp + 81 shield)
  walks untouched from (2.5,13.5) to (2.7,17.6); knight_evo 1468 -> dead by tick 504, ice wizard placed at tick 506
  is dead by 520 (0.7 s), princess 2679 -> 0 by tick 640, king 4824 -> 0 by ~792. The wiki (api.php) confirms the
  modelled rule text (shadows unlimited HP, untargetable by troops/buildings/towers, spells hurt them, vanish when
  Gerry dies) -- so the model is right and the DEGREE is wrong.

**(b) what this does NOT establish.** (1) The three patches are correct on their clips but their population
effect is null, so promoting any of them into engine.py is a doctrine change without a measured payoff -- park.
(2) The swarm ranking is an association over open-loop replays: a swarm the pro answered on the real board is
unanswered on the diverged sim board, which inflates exactly these cards. It says WHERE to look, not what is
wrong. (3) For evo skarmy the candidates are (i) how fast Gerry dies in the real game (tower / splash targeting
reaches him; the wiki says he walks "closer to the shadows", the sim keeps him at the back), (ii) shadow damage
vs towers, (iii) body-blocking: the sim lets 13 skeletons swing at one knight. Settling it needs the engine's
per-tick record of a skarmy match (emulator, after c2r), e.g. 08QPVCPC9QQU, 00LYPLJLYQCR, 020YPYYVJR0V,
02JY9GPPVPPG, 00GYPYPYUQQY, 022YYL8R2GG0, 092PPVY2CGG8 (all skeleton-army-ev1, all sim 3-0 before 100 s).
(4) Single seed per arm, but the driver has no policy noise (same caveat as §5cs.21).

**Ruling applied.** §6 oracle item 2 gets a priority list: record the swarm/bait mismatches first, then the rest
of the 135 clean matches. Nothing here touches c2r.

**Traps found.** (1) Bash cwd persists across calls: `cd icebow && ...` fails once the shell is already inside
icebow -- always `cd /c/Users/benpe/ClashBot` absolutely. (2) The engine frame record is per-tick early and
every-2-ticks with ODD ticks later (2410, 2411, 2413, ...), and some frames lack `projectiles`: index by tick
range and `f.get("projectiles")`, never `by_tick[t]`. (3) Two fixed clips are an existence proof, not a
population result -- the whole loop's patches were fitted to the clips that had records; the 211-match arm is
what saved the conclusion. (4) `plays_ext.csv` x_units can be the string `None`.
