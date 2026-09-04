

### §5cs.21 -- SIM-PARITY ORACLE STEP 1 (2026-09-04, L51): the SAME 211 real command timelines that the real engine reproduces at 77.7% crowns-match, our sim reproduces at 26.1%; the miss is one-directional -- the X-Bow side (211/211 the crawl's `team`) loses in the sim 188 of the 211 matches it won 129 of; mirror test proves the sim is symmetric, so this is deck mechanics, not a side bug

**What ran.** `scratchpad/gauntlet/L51/sim_replay_drive.py` -- drives `data/royaleapi/crawl2/plays_ext.csv` timelines
through `SimEngine` with the SAME conversion `research/sandbox_tools/replay_drive.py` used for the engine (§5ay): both
sides level 11 (cards AND towers -- a `ParityEngine` subclass rebuilds all six towers at 11 after `reset()`; the sim's
tower tables give princess 3052 / king 4824 HP, byte-equal to the engine's), 20 Hz ticks -> `tick/20` s, `sub_dt` 0.1,
tile snap + field-shape rules as in training, ability rows skipped (266 in this set), elixir slack up to 40 ticks,
tail cap 360 s, engine side 0 = sim team 0 (`x = x_units/18000`, `y = 1 - y_units/32000` -- the engine's side 0 sits
at LOW rows, the sim's team 0 at HIGH y, verified from the engine frame's tower rows 3000/6500 vs 29000/25500).
Play rows carry the BASE slug (`tesla`), the deck the variant (`tesla-ev1`): the variant spec is used for every play
of that slot (the sim has no evo-cycle counter). Side 0 = RoyaleAPI red = `opponent_*` columns, as in the engine.
Same 211 tags as the engine batch (`scratchpad/gauntlet/ext/batch/`), 19,488 plays = the engine's count exactly.
Outputs: `L51/simbatch/` (per-tag JSON with the full play log + `summary.jsonl`), `L51/aggregate.py` -> the numbers
below, `L51/simbatch_mirror/` (the side-swap run). 0.14 s per match; 31 s for the set beside c2r on one core.

**(a) measured.**
- **Crowns match RoyaleAPI: sim 55/211 = 26.1%; winner 93/211 = 44.1%.** Engine on the same 211 (recomputed from its
  batch files): 164/211 = 77.7% / 169/211 = 80.1%. Sim crowns == engine crowns in 61/211 = 28.9%. 2x2: both match 44,
  engine-only 120, sim-only 11, neither 36. On the engine's 135 fully-clean matches: sim 38/135 = 28.1% / 63 = 46.7%.
- **The miss has ONE direction.** Real winners: side 1 in 129, side 0 in 82. Engine: 111 / 100. **Sim: 23 / 188.**
  Of the 156 sim mismatches: sim side 0 wins where the real side 1 won 112, the reverse 6, same winner different
  crown count 38. Crowns per side, sim 1.49 / 0.11 vs real 0.54 / 0.70 (engine 0.61 / 0.60). Total crowns per match
  sim 1.60 vs real 1.24 (engine 1.21); 3-crown matches sim 58 vs real 20 (engine 18). Sim matches end at
  regulation (180.0-180.9 s) in 99, before it in 57, in overtime 55; median terminal 180.1 s vs the engine's 275.8 s
  -> the sim's games are decided earlier and more lopsidedly than the real ones.
- **Side 1 is the X-Bow player in 211/211** (`x-bow` in `team_deck` 211, in `opponent_deck` 8): the crawl is the
  icebow crawl. So "side 1 loses" = "the icebow deck loses" = the deck we train.
- **Mirror test (`--mirror`: side 0 <-> 1, x -> 18000-x, y -> 32000-y): crowns 60/211 = 28.4%, winner 45.0%, crowns
  per side 0.12 / 1.45, identical-when-swapped outcome in 154/211.** The bias follows the DECK across the mirror,
  so it is not a team-index / orientation bug in the driver or a team-0 advantage in the sim. (The remaining 57
  non-identical mirrors are the sim's own left/right + simultaneous-order asymmetries; a per-card mirrored-deploy
  probe in this loop showed the sim symmetric one-sided for hog/knight/musketeer/minions and Giant 18% slower for
  team 1 -- small, not this effect.)
- Not the cause: hero abilities (matches with zero ability rows: 18/78 = 23%, same as the whole); elixir accounting
  (1.2% of plays needed slack: 188 delays, 40 rejections of 19,222, 69% of them in single elixir, both sides
  equally -- the engine needed 0 delays, so the sim IS ~1 elixir short at times, a separate small gap); play count
  (19,488 = engine); tower HP (3052/4824 both).
- A worked mismatch (092PPVY899LL, real 0-1, sim 3-0): side 0's balloon-hero + miner at t=38 s at the bridge, the
  real tesla-ev1 (t=39.6) + skeletons (41.4) + tornado (47.6) responses replayed at their recorded spots; in the sim
  the balloon takes the princess by 60 s and the king to 2848 by 75 s. The recorded defence held in the real game
  and in the real engine; in our sim it does not.

**(b) what the number does NOT establish.** A replayed timeline is OPEN-LOOP: the pro's defensive plays were answers
to the REAL board, so once the sim's state diverges, recorded defences land against a different board and stop
being answers, while recorded attacks (a balloon at the bridge) stay valid. Open-loop replay therefore penalises
the reactive deck first -- part of the 26-vs-78 is that asymmetry, not "every mechanic is 3x wrong". But the real
engine ran the SAME open-loop timelines and stayed on the real board closely enough for those defences to still
work in 164/211; our sim leaves the real board early enough that they fail in 156/211. That is the gap the oracle
was built to size, in the only outcome-level unit we have, and it is large. WHICH mechanics diverge first (tesla
pull / balloon targeting / tornado / skeleton distraction / x-bow lock / rocket cycle) is exactly what step 2 (the
engine's per-tick dump + diff, emulator, after c2r) attributes; nothing here ranks them. Also untested: whether the
sim's always-on evolutions (both sides have them) shift the balance, and the sim-vs-real timing of first tower
loss (no engine per-tick record in the batch files).

**(c) contradicted.** The working reading behind L50's answer to the owner ("the sim's mechanics are probably a
small part of the gap; the sandbox is a calibration tool") is contradicted: on identical inputs the sim reproduces
1/3 as many real outcomes as the engine and its error is deck-directional against icebow. Mechanics are a large,
now-measured part of the gap, and the direction matters for training: a sim in which the icebow deck's recorded
defences fail and its opponents' attacks land is a sim that teaches the policy that defence does not hold -- (b)
plausible, untested, but it is the first mechanism-level candidate for the aggressive / non-banking policies this
project keeps producing that is NOT the gate.

**Ruling applied.** §6 oracle block item 2 is now warranted by item 1's own criterion ("far below" -> per-tick
oracle becomes the main line). Emulator work stays after c2r (owner ruling). c2r at 15:33: 31,325 eps, 0.5 ep/s,
17 procs, drills 46% pass, untouched by this loop.

**Traps found.** (1) `sim.my_tower_level` is the REFERENCE level of the tower profile, not a knob for "play at
level N": setting it to 11 relabels the L15 HP (4424) as L11 (the first smoke run). Rebuild the towers via
`_make_tower(..., level, ...)` with the ref left at 15. (2) The crawl's play rows carry base slugs, decks carry
`-ev1`/`-hero` variants -- key the spec table by base slug. (3) Sim results are deterministic per tag at a fixed
`random.Random` seed; the numbers above are single-seed but the driver has no policy noise, so a second seed only
moves the sim's own RNG (untested). (4) A Bash heredoc whose body contains `'''` breaks the surrounding command
when another quoted heredoc follows it -- write long sections with the Write tool.
