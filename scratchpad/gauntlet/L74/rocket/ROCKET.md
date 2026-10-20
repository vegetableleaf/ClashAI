# W10: Rocket use in context, baselines, and one learned lever (owner 10-20)

Labels: **(a)** measured (number given), **(b)** plausible but untested (the test is named), **(c)** contradicted.
Every slice below is one code path (`rocket_slices.py`) over three sources. Pro and our numbers are DECISIONS in the
same situation cluster, never matchup-blind averages. Full tables: `slices_all.out` (live + pro + 2 SIM sets),
`slices_live.out`, `slices_pro.out`, `slices_v0.out` (SIM), `habit_rockets.out` (vs E4).

## Bottom line

1. **CLX barely Rocket-cycles, in the SIM and live alike, in every cluster where pros do. (a)**
   - Hostile clusters (EQ / HOG / BEATDOWN with the X-Bow answer ready or short): chip-Rocket share of investment plays
     (bridge X-Bow / defensive X-Bow / chip tower Rocket) is pros **0.38**, CLX live **0.01** (n 100), CLX SIM 0.05 (vs C1 u50
     and vs gen d40). Bridge X-Bows: pros 0.43, ours 0.79-0.84.
   - After a failed bridge X-Bow, a chip Rocket within 30 s: pros **18.4%** [17, 20] (n 2,466), CLX live **1.6%** [0, 4]
     (n 187). SIM: not measurable (logging owed, below).
   - Heavy push (>= 10 elixir) with Rocket in hand: Rocket in the answer, pros **7.6%** [7, 9] (n 2,553), live 1.9% [0, 4]
     (n 263), SIM 0.8% / 0.5%.
   - Overtime at even crowns, chip Rockets per Rocket-opportunity-minute: pros **2.79** [2.61, 2.98], live 0.44 [0.14, 0.83],
     SIM 0.55 / 0.60. 2x elixir even: pros 0.93, live 0.37, SIM 0.10 / 0.16.
   - Per match: chip Rockets live 0.18, SIM 0.17-0.18, pros 1.37. The SIM habit and the live habit are the same number,
     so the habit is learned in the SIM and transfers: the SIM is where it must change.
2. **The calibrated opponent (C1 u50) does NOT make Rocket cycling pay in the SIM. (a, association)**
   - CLX vs C1 u50 (1,920 games): win with 0 chip Rockets 0.696 [0.68, 0.72] (n 1,663), with 1: 0.582 [0.51, 0.64], 2+: 0.592.
   - In matches with >= 0.5 min in a hostile cluster: 0 chips 0.805 [0.74, 0.87] (n 154), >= 1 chip 0.538 [0.35, 0.69] (n 26).
   - Tiebreak matches (n 282): 0.497 vs 0.484. vs gen d40 and vs E4 the same sign (E4: 0.792 vs 0.706, n 1,660 / 218).
   - Pros (real results): 0 chips 0.392 [0.35, 0.43] (n 638), 1: 0.528, 2+: **0.564** [0.52, 0.60] (n 580); hostile
     0.434 vs 0.617. Live CLX: 0.610 (n 118) vs 0.800 [0.60, 0.93] (n 15).
   - Association only, confounded both ways (pros chip when safe; the bot chips when behind / in OT). But it is the only
     SIM evidence there is, and it gives a win-only learner no reason to Rocket-cycle. That RL vs C1 would learn it on its
     own is therefore **(b) unlikely, untested** (the test: the arm below vs a same-seed control, both vs C1).
3. **A potential-form tower credit does not move Rocket use. (a)** Factorial factor E (`shaping: tower_score`, a tower-HP
   potential with Phi = 0 at the end) on 15/16 runs: unforced princess Rockets per match E+ 0.44 vs E- 0.49, late Rockets
   0.61 vs 0.66 (`doctrine/factorial_analyze.out`). This matches W6's point: a terminal-zero potential is policy-invariant.
4. **Lever chosen: (b) investment-value credit in the PENALTY/BONUS form, Rocket only** -- `rocket_tower: true`
   (pipeline/reward_terms.py). It pays enemy PRINCESS HP our Rocket removed, on the row that decided the Rocket. Details
   and the reasons against (a) and the X-Bow half are below. Whether it raises the live WIN rate is **(b)**: SIM bar, then
   live A/B.

## Data

| source | what | n |
|---|---|---|
| live CLX@4858 | Mark CLX: PARITY, graded, our princess max HP 4858 (since 10-19 14:02), one BADDELTA dropped (`build_live_clx.py` -> `index_clx.json`) | 138 (= OPP_MODEL's 138) |
| pro | icebow8 Path of Legend sides (invlib.pro_matches): decisions + results real, frames = native re-drive | 1,629 |
| SIM CLX vs C1 u50 | W7 O4 rows (CLX 5d212358 vs oppC1 u50 38328249, T .1, decide 40, all16, 4 seed blocks; `--crown-log` + o3_plays) | 1,920 |
| SIM CLX vs gen d40 | W7 option-A baseline rows, same telemetry | 1,920 |
| SIM CLX vs E4 | O0 t16 rows (13k opp table): own plays + habits only, no opponent plays / Rocket aims | 1,920 (habit counts only) |

## What the SIM eval rows record (and what is missing)

- Usable now (rows with `--record-plays --habit-log --crown-log` + the pod-local **o3_plays** patch): own accepted plays
  (decision / landing tick, card, elixir at decision), X-Bow y (habits), Rocket aims + tower flag (crown.rockets), exact
  princess falls (crown.falls), the opponent's plays [tick, card] (o3_plays). From these: matchup, the answer context
  (opponent cycle + elixir counter), our hand (exact after the 4th play) and elixir (logged at the play + the engine regen
  schedule), heavy pushes, chip vs finishing Rockets, phase x crown state, combos (timing only).
- **Logging owed (opt-in, absent = identical):**
  1. **X-Bow life + enemy tower HP in reach while it lives** (CrownTracker: own X-Bow uid -> first / last stop, foe
     princess HP drop in reach): needed for "failed X-Bow" and the SIM's ready-answer lock penalty (W5's open question).
  2. **`--crown-log-rockets`** in search_s0: set `learner_cfg['crown_track'] = 'rocket_dmg'` and copy `rocket_hits` into
     crown_log. The tracker already supports it (this change); 3 lines + the run.json falsy-key list.
  3. **o3_plays upstream**: today a pod-local patch (`opp_model/pod/o3_patch.py`); every eval needs it for the context slices.
- Rows without these are refused by name (`refused` in the header line), never guessed.

## The lever

**Choice: `rocket_tower: true`**, weight `rocket_tower_w` (default 0.5 per princess tower of HP), cap 0.3 per match.

- Measured per Rocket by `CrownTracker(rocket_dmg=True)`: enemy princess HP inside the Rocket's blast (catalog radius 2.0 +
  the tower's radius, the engine's edge rule), from the last stop the Rocket was seen in flight to the first stop after
  the one where it is gone (the impact shows one tick late). King damage never pays (owner doctrine: never the king). A
  felled tower pays its remainder. ponytail: stop resolution, so an X-Bow bolt landing in the same <= 2 stops counts too.
- A ~0.11 chip pays 0.055 (= 2.75 elixir at spell_value's 0.02 / elixir; a Rocket costs 6): it refunds part of the Rocket,
  it does not make Rocketing free. The critic scale 1.5 covers 1 + 0.3.
- Why the PENALTY/BONUS form: the potential form cannot change the optimum (W6), and its tower version was tried
  (factor E: no Rocket movement). The SIM's win reward shows no payoff for chips even vs the calibrated opponent (point 2).
  So only a term that changes the optimum can create the gradient. Deliberate, like W6's R1 / W7's princess_take.
- Why Rocket only, not X-Bow damage too: we already place 1.3-3.9x the pros' bridge X-Bows in these clusters (W5), and
  whether the SIM punishes X-Bows into ready answers is untested (logging owed, item 1). Paying X-Bow damage would push
  the wrong way wherever the SIM lets X-Bows lock too easily. Add the X-Bow half only after item 1 shows the SIM penalty.
- Why not (a) scenario curriculum: rl_royale has no mid-match start states (a new subsystem, not feasible tonight), and
  with no SIM payoff for Rocket cycling, more hostile states teach nothing new. It becomes the right lever once the SIM
  is shown to pay Rocket cycling.
- Risks: over-Rocketing (spending 6 elixir with a push coming); the win reward still prices that. Guard slices for the
  arm's eval: chip-Rocket share in hostile clusters, S1 heavy-push Rocket, own princess loss, SIM win (bar: CI top >= 0
  vs control). Not a pro-average target: success = SIM not worse + the slices move + live A/B.
- Not hard-coded for live: a training reward only; live decoding is unchanged.

## Code, tests, identity

- `pipeline/reward_terms.py`: term `rocket_tower` (TERMS / DEFAULTS / bound / row_terms / match_summary / batch_stats) +
  `CrownTracker(..., rocket_dmg=False)` -> `rocket_hits` only when on.
- `pipeline/rl_royale.py`: actor_base sets `crown_track = "rocket_dmg"` only when the term is on (else True, as before);
  actor_cfg passes the value through. `pipeline/e1_eval.py`: `CrownTracker(env, L, rocket_dmg=cfg crown_track == "rocket_dmg")`.
- `pipeline/tests/test_rocket_tower_1020.py` (17 tests): absent / null / false = PRE 2a3da3b (config hash of rl_royale.yaml +
  the L16 recipe with the PRE module, crown_cfg None, tracker result without rocket_dmg and every non-Rocket field with
  it, earlier terms' row_terms / bound / summary / batch_stats / crown_log, actor_cfg, collate byte-identical + adv_cfg,
  SelfPlayMatch play byte-identical); on: tracker hit / lag / king / felled tower / match end, row credit, cap, unmapped,
  refusal without the tracker, validation, bound, hash, the arm yaml = recipe + one key, collate, one gae update.
- Passed: 17/17 in the shared working tree (with W7's uncommitted edits) and 17/17 in a clean worktree of HEAD + this patch.
  pyflakes: no undefined names (2 old warnings in e1_eval).
- Pre-existing failures, identical at HEAD without this patch (checked in the clean worktree): test_reward_terms_1020
  `test_updates_identical`, test_rl_gae `test_one_update_identical`, test_league 2 `TestSelfPlayCounters` tests. Two runs of
  the SAME PRE module already differ in the 9th digit after 2 updates on this laptop, so whole-update byte identity is not
  a usable proof here; collate byte identity is used instead.
- The trainer hunks are HEAD + W10 only (W7's princess_take / league_opp_live edits stay uncommitted). They were staged as
  blobs and swept into W8's commit b386aaf by the shared index before the W10 commit; checked byte-identical to the
  worktree-tested versions. The W10 commit carries the tests, the arm yaml and this directory.

## Smoke

- Laptop: **the recipe smoke is UNVERIFIED** -- it cannot run here (laptop royalesim 0.1.13 has no Hero IW runtime:
  `smoke/laptop_smoke.log`; the recipe's init and league checkpoints are pod-only).
- Laptop wiring check (default rl_royale.yaml + `league=true rocket_tower=on`, gen_v32_s0 init, `smoke/laptop_smoke_g32.log`):
  update 0 ran end to end in the real engine with the term on (actor_base -> crown_track "rocket_dmg" -> tracker ->
  row_terms -> monitors: `rocket_reward_per_match`, `rocket_princess_dmg_per_match`, `rocket_unmapped` in the train log),
  then hit the 15-min cap (exit 124) before SMOKE PASS. Its 8 matches had 0 Rockets, so the hit measurement itself is
  covered only by the unit tests until the pod smoke runs.
- **Pod (UNVERIFIED until run):**
  ```
  # laptop, after the W10 commit C:
  bash scratchpad/gauntlet/L74/rocket/pod/ship.sh <C> 14009 64.247.206.76
  # pod:
  setsid nohup bash /workspace/w10/ship/w10_smoke.sh > /dev/null 2>&1 < /dev/null &
  #   -> /workspace/w10/RESULT (SMOKE_PASS / SMOKE_FAIL), tests.log, smoke.log, run.log (rocket_reward_per_match)
  #   fin15: RUNTIME=fin15-linux PY=/workspace/venvf15/bin/python setsid nohup bash ... (same)
  ```
  It works on an isolated hard-link copy of /workspace/cb_stepd with the shipped files replaced (cb_stepd untouched).
  If cb_stepd's other pipeline modules are older than 2a3da3b, the smoke shows it (import / signature errors).

## Arm yaml and rebase

- `stepd/cfg/stepd_l16_rocket_s74.yaml` = `stepd_l16_s74.yaml` + `rocket_tower: true` (test-enforced).
- Rebase onto tonight's base B (fin15 runtime, W7's opponent keys, ...): `(cat B.yaml; printf 'rocket_tower: true\n') >
  B_rocket.yaml`, then `pytest -k arm_yaml` after pointing `L16` / `ARM` in the test at B / B_rocket (or check
  `load_config(B_rocket) == {**load_config(B), "rocket_tower": True}`). It composes with W7's princess_take (separate keys);
  shaping_critic_scale must stay >= 1 + the summed term bounds (1.3 with this term alone).
- Run it against a same-seed control of B (one change per experiment).

## Pod eval commands

- CLX vs E4 with the full telemetry (the missing baseline; ~1 pod-h, 1,920 games):
  `setsid nohup bash /workspace/o3/opp_eval.sh w10_E4_CLX icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt 0.1 - - 741200 742000 743000 744000 > /dev/null 2>&1 < /dev/null &`
- The arm and its control: the same with LEARNER = their checkpoints and OPP = C1 u50
  (`icebow/data/pipeline/o2/w7/rlarm_oppC1_icemix_s74_u0050.pt 0.1 40 -`) and E4. Then on the laptop:
  `python -B -X utf8 rocket_slices.py --sim "arm=<dir>" "control=<dir>" --out arm.out`.

## Files (`scratchpad/gauntlet/L74/rocket/`)

| file | what |
|---|---|
| `rocket_slices.py` | the scorer (live / pro / SIM adapters -> one record; S1-S5 + V) |
| `build_live_clx.py` -> `index_clx.json`, `build_live_clx.out` | the live CLX@4858 index (caches in habits/cache) |
| `habit_rockets.py` -> `habit_rockets.out` | Rocket habit counts for rows without opponent telemetry (E4) |
| `slices_*.out` | outputs (all / live / pro / SIM v0) |
| `pod/ship.sh`, `pod/w10_smoke.sh` | pod smoke from a commit |
| `smoke/` | laptop smoke attempts |

`investment/invlib.py`: `live_matches(index=...)` (another index file; default unchanged).

## Foreman record (Codex gpt-6-astra, decision-tree tickets in .foreman/w10/)

- T1 build_live_clx.py run -> 138 matches (DONE; checked against OPP_MODEL n 138).
- T2 pro slices run (DONE; 1,629 matches).
- T3 test suites + pyflakes (DONE; the 4 failures were then shown pre-existing at HEAD by the lead).
- T4 the combined slices run -> `slices_all.out`.
All judgment, the scorer, the lever, its code and tests were done by the lead.
