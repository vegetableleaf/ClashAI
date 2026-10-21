# W15 -- levers 2 and 3 of CLX_RANKED.md, prepared for the next round (2026-10-21)

Labels: **(a) measured** (number given), **(b) plausible, untested** (measurement proposed), **(c) contradicted** (evidence
given). Neither arm has been launched. Each arm yaml = `tn_base_s74.yaml` + ONE key (`diff` shows only that key and its comment).

## 0. What landed

| piece | file | what |
|---|---|---|
| L3 key | `pipeline/rl_royale.py` `league_deck_weights` | {engine card base name: multiplier} on the OPPONENT deck draw (census pool and the W7-exploiter pool); the learner's deck draw is unchanged |
| L2 key | `pipeline/rl_royale.py` `ot_start_share` | that share of league matchups starts at clock 3590, 0-0, from a live Ranked state (`draw_ot_start`) |
| env | `pipeline/royale_env.py` `RoyaleSelfPlayEnv.reset(start=)` | MatchSetup `start_tick` / `tower_hp` / `elixir_milli`; `scenario_start` on the env |
| match | `pipeline/e1_eval.py` | `SelfPlayMatch` maps spec["start"] to sides; the opponent-elixir counter starts at the start tick; result `seconds` / `plays_per_min` count played time only |
| counter | `pipeline/public_observation.py` `PublicObserver.start_at` | the v4 counter's start (inert unless called: the live path never calls it) |
| data | `nextround/ot_states.py` -> `ot_states.json` | the 132 live Ranked 0-0 overtime states |
| check | `nextround/beat_mass.py` -> `beat_mass.out` | how much draw mass L3 moves |
| arms | `stepd/cfg/tn_tank3x_s74.yaml`, `stepd/cfg/tn_otstart_s74.yaml` | tn_base_s74 + `league_deck_weights` (x3, 14 cards) / + `ot_start_share: 0.25` |
| test | `pipeline/tests/test_levers23.py` | 10 tests (section 4) |

Absent (or null) = the HEAD c7e56df trainer: the same matchup rows and rng state, the same `load_config` dict and the same
`config_sha` (test_levers23 `TestAbsentIsPre`, run against `git show c7e56df:pipeline/rl_royale.py`).

## 1. Lever 3: tank / bridge-spam deck weight (`league_deck_weights`)

**Rule.** A deck's draw weight is multiplied by the largest multiplier among its cards (`Giant@hero` counts as `Giant`; 1 if
none), then renormalised. It applies to both opponent pools tn_base draws from: the census (`decks_rl.json`, 70% of matchups)
and the W7 exploiter's `decks_live_train.json` (30%). A card name that no pool deck holds stops the run at start (a typo would
weight nothing).

**The arm's set** = W13's BEAT set (report.py), x3: Giant, ElectroGiant, RoyalHogs, BattleRam, Pekka, Golem, GoblinGiant,
LavaHound, RoyalGiant, ElixirGolem, GiantBuffer (= Rune Giant, slug `rune-giant`), GiantSkeleton, ThreeMusketeers, BossBandit.
CLX_RANKED L3 named six of them; the ticket said "and the others listed there", so the arm uses all 14. Trimming it to the six
is a yaml edit.

**(a) What it moves** (`beat_mass.out`, pool weights at tn_base's alpha 1 / floor 0):

| pool | BEAT mass now | with x3 | L3's six cards only, now |
|---|---|---|---|
| census `decks_rl.json` (999 decks) | 0.663 | 0.855 | 0.432 |
| W7 exploiter `decks_live_train.json` (895) | 0.486 | 0.739 | 0.268 |
| tn_base mix (0.7 / 0.3) | 0.610 | 0.820 | - |
| live Ranked (CLX_RANKED section 3) | 83 / 233 = 0.356 | - | - |

- **(c) "BEAT decks are rare in RL training" is contradicted.** BEAT is already 61% of the opponent draws, against 35.6% on
  Ranked. x3 takes it to 82%.
- So L3 does not add exposure to a rare matchup. It shifts a majority further, and the rest of the decks drop from 39% to 18%
  of draws.
- CLX_RANKED's own caveat fits this better: the SIM's BEAT opponents are too easy (SIM 57.5% vs Ranked 25.3%). The gap is
  in how well the SIM opponent plays those decks, not in how often they are drawn.
- **(b) untested:** whether more draws of easy BEAT opponents move the live BEAT cell at all. The "rest" cell may get worse from
  18% exposure. Both are in CLX_RANKED's "worked if".
- The census copy measured here is `share/data_20261020/decks_rl.json`, sha b43dd085. It equals the laptop's drift copy of
  `icebow/data/rltest/decks_rl.json`. That the pods hold the same file is (b).

**Rule vs W13's measurement rule.** The key uses "contains"; W13's BEAT cell uses `anatomy.wincon` (the deck's first card in
WINCON priority). The two differ by mass 0.021 (census) / 0.093 (live pool). An example is MK + PEKKA decks: they count as BEAT
here and as `mega_knight` in W13. No deck is BEAT under W13 and missed here. **Score the arm's per-win-condition breakdown with
W13's rule**, so it matches the live cell.

**Overlap with W14.**
- W14's opponent-model arm B (`opp_model/w14/beat3_decks.py`, committed b864645) applies x3 to BEAT decks too, but in a deck
  file and under W13's wincon rule, for the OPPONENT model's training.
- If both land, the learner trains on a BEAT x3 mix against an opponent that was itself trained on BEAT x3. That is two
  changes in one comparison.

## 2. Lever 2: overtime-state starts (`ot_start_share`)

### 2.1 Does the engine support it? Yes, without a fork change (a)

- **royalegym.** `MatchSetup` has `start_tick`, `elixir_milli` and `tower_hp` (`[team][TowerSlot]`), already in the laptop's
  0.1.15. `RustEngine.reset` passes them to `Battle.reset`.
- **fin15 fork, pin 305aaafc.**
  - `crates/royalesim/src/py.rs:1816`: `reset(seed, decks, shuffle, start_tick, elixir_milli, tower_hp, spawns, forms, levels,
    tower_levels)`.
  - `state.rs:35761` `scenario_set_tick`: sets the overtime flag from the tick.
  - `scenario_set_tower_hp`, `scenario_set_elixir_milli`.
  - The deploy lockout compares the ABSOLUTE tick (`state.rs:34668`), so it is already past at 3590.
- **Measured on the laptop runtime** (royalesim 0.1.13; test `TestEnvStart`):
  - after a start at tick 3590 the state reads tick 3590, tower hp = fraction x max in TowerSlot order, and elixir_milli
    4000 / 7500 as set;
  - with no plays, the match runs through overtime, and the tiebreak drain ends it after tick 6000 against the side with the
    lowest tower.
- **(b) on fin15 itself:** the same API is in the pinned source, but it has not run there (it is a Linux wheel). That is the
  pod smoke in section 4.
- `parity/fights.py` uses the same `Battle.reset(..., start_tick, [10000, 10000], tower_hp, spawns)` to seed its fights. The
  env reuses the MatchSetup path, not fights.py's raw battle.

### 2.2 The start state

- **Source (a).** `ot_states.json`: all 132 CLX Ranked matches that were 0-0 at clock 3590 and went to overtime (W13 rows.json,
  0 dropped).
  - Behind by > 0.10 of a tower: 50.0%. Ahead by > 0.10: 31.1%. These equal CLX_RANKED T3b's 50.0 / 31.1.
  - CLX won 50.8% of them live.
  - Our elixir at 3590: median 4.13, mean 4.33.
- **Tick 3590 (clock 2:59.5).** This is W13's measurement tick, 10 ticks before overtime, so the engine crosses into OT
  itself.
- **Towers.** Kings full. Princesses = the row's fractions x that tower's max at the match's levels (all16 -> level-16 max;
  read off a plain reset first).
- **Lanes.**
  - The row's `own` [L, R] -> the learner's [LEFT, RIGHT].
  - The row's `opp` is in our screen frame, so it is reversed into the opponent's own frame (royalegym: Red's frame is
    rotated 180 degrees).
  - This keeps the lane pairing: our weak tower faces their tower on the same lane.
- **Elixir.**
  - Learner = the row's own elixir.
  - Opponent = another row's own elixir, drawn independently. (b) Opponent elixir is not observed live, so this assumes it
    has the same distribution as ours.
- **Stream.**
  - Each matchup draws from its own crc32 stream (as `draw_tower_troop` / `draw_live_levels`).
  - The arm's matchups (opponents, decks, seeds, sides) are therefore exactly tn_base_s74's; 25% of them also get a start.
  - Test: every other field is identical to the key off, and the learner's rng state too.
- **Counter.**
  - The opponent-elixir counter (v4 `PublicObserver` and the older `opp_counter`) starts at 3590 at the TRUE opponent
    elixir.
  - Without this it would start at 6 at tick 0 and regenerate to the cap: 10, against a true mean of 4.33.
  - (b) The live counter at 3:00 has its own error; the true value is the closest stand-in available.
- **Bookkeeping.** For a started match, result `seconds` and `plays_per_min` count played time only. The plays/min guard
  compares against update 0 of the same mix, so it was not at risk; the logs were.

### 2.3 Fidelity gaps of a jump start: read before launching (a)

- **No opponent history.** Live at 3590, a median of **8** distinct opponent cards have been revealed (92.4% of the states
  have >= 7). The SIM start has none.
  - `opp_past` / `opp_cycle` start empty, and so does the own-ability history.
  - The policy sees an overtime clock with an opening's history.
- **Empty board.** The SIM start has no units. Live at 3590 the board holds a median of 2 bodies (14.4% of the
  states are empty). Pushes in progress at 3:00 are missing.
- **(b) untested:** whether a policy trained on these states plays the same states, reached in a real match, better. The gate
  below measures it on a fixed set of starts. That set has the same gaps, so it can overstate the gain.
- **Two ways to close the gaps** (not built; they change the design, so this is the lead's call):
  1. **Played prefix.**
     - Play the match normally and unrecorded to 3590, then set tower hp and elixir from the drawn row, and record from 3590.
     - History and board are real.
     - Needs a mid-match state edit: the fork has `Battle.save` / `load` (py.rs:2134 / 2142; fights.py edits a save through
       `mechanics.load_edited`). It also needs a record-from-tick gate in the actor, so trajectory rows and GAE start at
       3590.
     - Cost: about 3 unrecorded minutes per started match.
  2. **Seeded history.**
     - Give the observer a synthetic, cycle-consistent history of the opponent's 8 cards: the hand as the older plays, the
       queue as the latest 4.
     - Cheap, but the ticks and positions are made up.

### 2.4 Order and gate (CLX_RANKED L2)

- **Order.** CLX_RANKED puts L2 after L1. Against the W7 opponent the SIM's OT is too lenient (77.5% vs 52.6%), so OT starts
  there may teach lenient OT play.
- `tn_otstart_s74.yaml` uses tn_base's W7 opponent because the ticket asked for tn_base + one key. Moving it onto the L1
  opponent is a one-line change.
- **Gate.** P(win) on a FIXED set of OT starts, paired, in the "behind" stratum, CI low > 0 vs CLX; full-match evals not
  clearly worse (CI top >= 0).
- `SelfPlayMatch` now takes `spec["start"]`, so an eval can pass the same 132 states to both models. That eval entry point is
  not built.

## 3. Arm yamls

```
diff stepd/cfg/tn_base_s74.yaml stepd/cfg/tn_tank3x_s74.yaml  -> + the league_deck_weights block (14 cards, 3.0) + 2 comment lines
diff stepd/cfg/tn_base_s74.yaml stepd/cfg/tn_otstart_s74.yaml -> + ot_start_share: 0.25 + 2 comment lines
```

## 4. Verification

| check | result |
|---|---|
| `pytest pipeline/tests/test_levers23.py` (laptop) | **10 passed** (13 s, on the final ot_states.json) |
| related suites: 14 files (league, exploit x2, adaptive opponents, l16 levels, league_opp_live, royale_selfplay, public_observation, e1_opp_counter, opp_tempo, rl_royale, follow_up_selfplay, gen_v31, royale_forms) | 199 passed, 2 failed: `test_league TestSelfPlayCounters` x2 ('x_bow' vs 'x-bow'). **The same 2 fail with HEAD's four modules** (`.foreman/scratch/w15_head_runner.py`), so they predate W15 |
| pyflakes on the 4 trainer files + test + scripts | 0 undefined names (the 2 other warnings are at HEAD too) |
| laptop `--smoke`, keys absent (default yaml) | **SMOKE PASS**, config sha 001dcc181306 |
| laptop `--smoke` with BOTH keys on (league true, init gen_v32_s0, `league_deck_weights` 4 cards, `ot_start_share` 0.5) | run 1: **SMOKE FAIL on a stop rule**: the held-out outlived-the-script win share was 0.278 vs init 0.083 + 0.15 |
| the same, with that one guard off (`outlived_pp=100`) | **SMOKE PASS**: config sha accdd0c41d48; resume check all True (league state included); u0000 and u0001 identical to run 1 (5/3/0 and 2/6/0 W/L/D, 1324 / 1396 rows), so the run is deterministic. League rollouts' mean played time was 121.8 s / 129.7 s per match: started matches ran |
| fin15 pod smoke of the two arm yamls | **UNVERIFIED** (pods busy until ~13:00; the lead runs it) |

Pod smoke (fin15 venv; code tree at the W15 commit, `setup_fin15.sh` done, pod idle):

```bash
cd $CB && unset ROYALE_HEROIW_PRESS && export PYTHONPATH=$CB ROYALE_RUNTIME=fin15-linux ROYALE_HEROIW_FORM=hero \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
D=scratchpad/gauntlet/L74/stepd/cfg; O=/workspace/stepd/smoke_w15; mkdir -p $O
for A in tn_tank3x_s74 tn_otstart_s74; do rm -rf scratchpad/gauntlet/L68/rl/smoke_$A icebow/data/bench/rl_royale/smoke_$A
  /workspace/venvf15/bin/python -m pipeline.rl_royale --config $D/$A.yaml --run smoke_$A --smoke > $O/$A.log 2>&1 & done; wait
grep -c "SMOKE PASS" $O/tn_*.log; grep -ho "config sha [0-9a-f]*" $O/tn_*.log
```

- **(b) The guard trip in run 1.**
  - The outlived guard reads the held-out GHOST screens (`RoyalePoolEnv` entries). Neither key enters those matches.
  - But the u0001 policy differs from a keys-off run's, so a no-key control smoke of this config is the attribution test.
    It was not run: the laptop budget was spent.
  - The fin15 pod smoke uses each arm's own yaml and guards.

Artifacts (laptop-local, `.foreman/` is excluded): `.foreman/scratch/w15_test.out`, `w15_related.out`,
`w15_head_league.out` (+ `w15_head_runner.py`), `w15_pyflakes.out`, `w15_smoke_off.log`, `w15_smoke_on.log`,
`w15_smoke_on2.log`.
