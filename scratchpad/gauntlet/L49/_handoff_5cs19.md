

### §5cs.19 -- compound-drill instrument read (2026-09-04, L49) + a drill-GRADING bug found on the way: the "no enemy alive" predicates count the distractor, on BOTH decks, in the running c2r

**Question.** `sim.drill_compound_frac` has been 0.0 in every config since compounds were written (never enabled). Before
proposing them as a repair arm: does the compound verdict fire, how long do boards run, what does the doctrine oracle
score, and do the two live checkpoints differ from it. Instrument: `scratchpad/gauntlet/L49/compound_probe.py` -- forces
`drill_compound_frac 1.0` and `drill_play_out False` IN-PROCESS (no config file touched), builds `DrillEnv` with the
anchor scenario (every reset composes 2-3 hand-declaring scenarios via `compose_components`, drill_env.py:94), runs
nothing / `doctrine_policy` / `_drill_policy_from_checkpoint` (greedy masked, gate threshold `sim.ppo_gate_threshold`
0.25), tallies the verdict and each component's grade from `compound_verdict` (drill_env.py:153). Config VALUES:
pass_frac 0.5, hp_frac 0.25, n 3. Files: `compound_s5.json`, `compound_s6.json`, `compound_s5_full.json`.

**Compound instrument (a) measured, reps 48 per policy per seed.**
- The verdict fires on every board: 0 timeouts across 4 policies x 2 seeds (2 boards on seed 6 ended by the
  `last_verdict or "ended"` path at drill_env.py:828 = no compound verdict recorded; minor). Boards run ~12-13 s of
  game time, 2-3 components each (seed 5: 24 two- / 24 three-component; seed 6: 25/23).
- Pass rate, seed 5 / seed 6 / pooled n=96: nothing 2.1 / 0.0 / ~1%; doctrine 35.4 / 35.4 / 35.4%; c2r_m20k 22.9 /
  29.2 / 26.0%; gatec2_m10k 31.2 / 27.1 / 29.2%. Seed-to-seed band on the same policy 4-6pp at n=48, so the two
  checkpoints are indistinguishable from each other, and the doctrine sits 6-12pp above both. The instrument is live
  (nothing ~1%) and the ceiling is low (doctrine 35%).
- Per component, the doctrine's SPELL/LOG components collapse: log_the_ground_swarm 0/7, rocket_the_pump 0/5,
  hold_the_spell 0/8, log_rolls_forward 0/7, nado_king 0/5 -- while bank_to_six 7/8, knight_guards 7/8, ice_wizard 5/5.
  The same doctrine passes those drills single at 76 / 92 / 100 / 80 / 8% (L46, `scratchpad/gauntlet/L46/drills_c2r_m10k.txt`).
- Scarcity (c) contradicted: `--full-elixir` (every board starts at 10 elixir, seed 5): doctrine 31.2%, the same
  components still 0/N. It is not that the doctrine cannot afford the second answer.

**Root cause: component-local grading is dead code.** `compound_verdict` sets `eng._drill_component = tag` before
calling each component's `success`, and `scenarios.enemy_units(eng)` (scenarios.py:153) honours that tag and hides
`drill_noise` units. But `drills_icebow.py` never calls `enemy_units`/`all_enemies_dead` (0 hits); 22 of 29 scenarios
read `e.units` directly, and 12 success predicates are the board-global
`not any(u.team == 1 and u.hp > 0 for u in e.units)` (lines 103, 133, 164, 199, 287, 310, 391, 650, 744, 839, 880,
927). On a compound board a "kill the swarm" component can only pass once EVERY component's enemies are dead -- the
per-component grades are one grade with different timeouts. That is why the fast-kill components (log, rocket, nado)
read 0/N: their success window closes while the other component's units are still alive.

**The same helper is the only distractor-hiding, so this is bigger than compounds.** `_add_noise` (drill_env.py
284-307) gives ~50% of drill episodes a distractor at `sim.drill_noise 0.5`, team 1 with p 0.75, in the OPPOSITE lane,
tagged `u.drill_noise = True`; its own docstring says `enemy_units()` hides it "from every predicate". Nothing calls
`enemy_units()`. `drill_noise: 0.5` is ON in `config/config.yaml:1702` and in the RUNNING c2r's frozen
`data/bench/c2r_run.yaml:1677`. hogeq: identical -- `_enemy(eng)` in `drills_hogeq.py:29` reads `eng.units`, 0 uses of
the helper, `drill_noise: 0.5` at `hogeq/config/config.yaml:1447`.

**Size of the effect on single drills (a) measured** -- `scratchpad/gauntlet/L49/noise_grading.py`, doctrine oracle,
seed 5, reps 25 per drill, the 10 drills whose success is the global predicate (log_the_ground_swarm,
ignore_the_ignorable, hold_the_spell_for_a_target, log_rolls_forward_not_backward, knight_blocks_the_charge,
hold_the_tesla_for_their_wincon, split_lane_needs_the_centre, bow_defends_from_the_centre, matchup_hog_cycle,
matchup_bridge_spam), pooled n=250 per arm:
- noise 0.0: 78.0%; noise 0.5 (c2r's value): 66.8%; noise 0.5 with the success predicate evaluated through a view that
  hides `drill_noise` units (what the helper would do): 70.4%.
- So the GRADING bug is worth ~3.6pp of doctrine pass on these drills (~1.2 SE at this n -- real in sign, small);
  the other ~7.6pp is BEHAVIOURAL: the far-lane distractor changes the board and the doctrine's answer stops
  being sufficient (bow_defends_from_the_centre 72 -> 44 -> 44; matchup_bridge_spam 48 -> 20 -> 20; the fix does
  not recover those). Per drill the fix recovers log_the_ground_swarm 88 -> 96, log_rolls_forward 84 -> 100,
  knight_blocks 88 -> 92, split_lane 88 -> 92; ignore_the_ignorable is 8% in all three arms (a doctrine gap, not
  noise).
- What this does NOT establish: the effect on the LEARNER. The c2r's drill pass reads 46% all / 41% last 300 over
  a different drill mix and a policy, not the doctrine; the per-drill split in training was not measured. The
  3.6pp is the grading-only term for the doctrine; a learner that has learned to also kill the distractor pays a
  different (unknown) price. Not measured: whether the behavioural 7.6pp is "noise doing its job" (robustness to a
  second lane) or a drill whose intended lesson is now unlearnable at 0.5 -- that is a doctrine judgement per drill.

**Fix candidate (NOT landed -- c2r depends on the drill files; workers import once so a file edit would not touch the
live process, but a `--resume` would).** In `drills_icebow.py`, replace the 12 global predicates with
`all_enemies_dead(e)` / `enemy_units(e)` from scenarios.py; on a single board with noise 0 the helper returns every live
enemy, so the single-drill report at noise 0 must be byte-identical before and after (that is the regression check).
Same edit in `drills_hogeq.py:_enemy`. This is a drill-grading change = its own experiment; it also makes compound
per-component grading real, which is the precondition for compounds as an arm. Both queued behind the m30k verdict.

**c2r state at 13:20:** 27,325 eps, 0.5 ep/s (my probes cost it a core; unloaded it ran 0.55), 17 python procs,
winrate 14% / 4% on the last two lines (not a discriminator), drills 46% pass all / 41% last 300, 21% of eps, 30% of
steps. Last-epoch `GATE drift: PLAY steps` -1.078, the largest magnitude of the last 12 epochs (series: -0.26 -0.35
-0.51 -0.54 -0.54 -0.10 -0.58 -0.51 -0.21 +0.01 -0.62 -1.08) -- one epoch, watch-only; the m30k 3-seed >=6 probe is
the decision (owner's pre-registered collapse rule, HANDOFF line ~10140). m30k ~14:50.

**Traps found.** (1) Compound boards are NOT paired across policies at the same seed: the episode consumes rng, so the
component draws differ per policy -- the numbers are population estimates, not paired comparisons. (2) A drill's
distractor is visible to its grader unless the predicate goes through `enemy_units()`; grep a deck's drills file for
`e.units`/`eng.units` before trusting any pass rate with `drill_noise` > 0. (3) `Scenario` is a frozen dataclass --
override a predicate with `dataclasses.replace`, not attribute assignment.
