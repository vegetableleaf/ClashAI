# Fight parity as the goal's instrument: tolerant card scores and a noise ceiling (2026-10-16)

**Goal (owner, 10-16).** SIM fight parity above 95% overall and above 90% for every card, judged on the tolerant,
card-level metric below and normalised by the SIM's own noise ceiling.

**Status.** Built, unit-tested, and prototyped on a laptop subset. **No card has enough n in the subset to be judged.**
The goal verdict needs the full pod run (command at the end).

Runtime for every number here: royalesim **0.1.35**, the laptop's `cp310-abi3-win_amd64` wheel (`PARITY_SIM_PATH`, the
same wheel as `DIAG_1016.md`). Raw outputs are in `output/ceiling_proto/` (gitignored).

## 1. The tolerant card metric (`fights.card_view`, `fights.card_agree`)
There is one score per card play: the fight's anchor deployment, own or opponent. Each run (the live frames, or one
SIM replay) gives a **card view**:

- **Own bodies.** These are the bodies of the anchor's side and card that are not on the board at t0, born from the
  anchor tick − 2 until the next play of the same card (or the window end). Children (a Witch's skeletons, Elixir Golem
  pieces) count, because the reader and the SIM both label them with the parent card. Each body's outcome is its death
  tick, or alive at the window end (12 s).
- **Tower damage it causes.** Every tower hp drop between two frames is split evenly over the distinct cards with a
  body in reach of that tower at the earlier frame: range + own radius + 1.4 tiles (king radius). The anchor's bodies
  count as one card. This heuristic is the same for live and SIM.
- **Own spells (Log, Tornado, Rocket).** Within 60 ticks (3 s) of the cast:
  - **Bodies hit:** enemy bodies with a one-gap drop of at least d/2, or that vanish in one gap with hp ≤ d within the
    spell's reach of the cast point. d is the spell's body damage at the match's inferred spell level
    (`Engine.spell_damage`).
  - **Outcome per hit body:** killed by the spell (gone within 2 frames of its first hit, with that tick) or not. A
    later death is other cards' doing.
  - **Tower damage:** the spell's crown damage, d × crown%, for each enemy tower in reach whose largest one-gap drop
    in the window is at least 80% of it.

**Agreement of two views** (live vs SIM, or SIM vs SIM) requires both parts:

- **Bodies.**
  - For troops and buildings, the two sorted lists of death ticks are matched in order. Matching by sort order means
    the identity of swarm members does not matter.
  - For spells, the hit bodies are the union of both runs' hit sets, keyed by live id.
  - A pair agrees when both bodies survive, or both die with `|Δt| ≤ DEATH_TOL = 10 ticks (0.5 s)`. A body present on
    one side only is a miss.
  - The bodies pass with at most `floor(SWARM_SLACK·n)` misses, where `SWARM_SLACK = 0.1`. So 1 of 10 to 19 Skeleton
    Army members may differ, and any card with fewer than 10 bodies must match exactly.
- **Tower.** `|T_a − T_b| ≤ max(TOWER_FLOOR, TOWER_REL·max(T_a, T_b))`, with `TOWER_FLOOR = 100` hp (one X-Bow bolt
  is 98; one Log crown hit is 51) and `TOWER_REL = 0.10`.

The whole-fight outcome from `fight_verdict` (all focus bodies, first death and every tower within max(150, 15%)) is
kept as a second number: "whole-fight outcome".

## 2. The noise ceiling (`fights.perturb`, `fights.engagement`, `fights.jitter_tick`; `--ceiling K`)
For every fight the SIM is replayed K more times (K = 8). Each replay reloads the fight's setup state and redraws only
what the reader cannot see. Every range comes from the live frames of the 3 s before t0:

| hidden state | how it is redrawn |
|---|---|
| attack phase / cooldown (every body **and tower**) | An enemy in reach at t0 for e ticks: swing progress uniform over [0, HitSpeed) if e·50 ms ≥ HitSpeed, else over [0, LoadTime + e·50 + 100]. No enemy in reach, but one was r ticks ago with r·50 < LoadTime: reload uniform over [0, LoadTime − r·50]. Otherwise the setup default (fully reloaded) is kept. |
| current target where ambiguous | Uniform over the enemies in reach at t0, respecting air, ground and building-only. A tower lock (`tower_locks`) is kept. |
| Tesla hidden state | Taken from history: Rising if in reach for less than UpTime, Up if in reach (or out of reach for less than HideTime), else Hidden. The timer gets ±100 ms. |
| shield hp (unknown when hp is full) | Uniform over [0, shield] on a body that had an enemy within 8 tiles. Worn bodies already have 0 shield (DIAG §4). |
| deploy tick | First-seen plays: uniform over the frame gap (prev frame … first seen − 1). Frames are 2 ticks apart in 23,749 of 24,924 gaps, so this is ±1 tick. Own spells and Hero IW presses: tick + a draw from this match's own troop tap residuals, clipped to −3…+3 (p5..p95 of the 10-15 matches; 87% within ±2). |
| hidden opponent spells | **Not injected**, as specified. Core/all fights with an unseen spell therefore sit below the ceiling for a reason the ceiling does not model. |

**Not redrawn:** facing, Prince/Dark Prince charge, jump/leap state, Inferno ramp (progress is drawn within one
HitSpeed only), spawner timers (Witch/Tombstone/Furnace), evo counters, hero buttons. Each of these makes the ceiling
**higher** (stricter) than the truth for the cards that carry it. The subset applied 2,696 swing redraws, 552 ambiguous
target draws, 208 reloads and 344 Tesla states; `perturb_not_set` = 0.

**Scores per fight (`card_scores`):**
- `a0` is live vs the unperturbed SIM (the old reference replay).
- `aK` is the mean of live vs each perturbed SIM.
- `ceil` is the mean over the 28 perturbed pairs.

**Per card (`ceiling_table`):**
- agreement = mean `aK`;
- ceiling = mean `ceil`;
- **normalised = agreement / ceiling**.

**95% CIs come from a bootstrap that resamples matches** (2,000 draws). Fights in a match share windows and hidden
state, so resampling fights alone would understate the CI.

**Flag:**
- `insufficient n` if n < 30;
- `MEETS` if the normalised lower CI is ≥ 0.90;
- else `below`.

The overall line uses the same test against 0.95.

Normalised can exceed 1. Read it together with the raw agreement and the ceiling: a noisier metric or wider
perturbations would push both toward the same low number and the ratio toward 1.

## 3. Harness fix found by the instrument: tunnelling Miner (H, fixed)
**The bug.** The reader shows a Miner while it tunnels (active rows, moving about 1 tile per tick) before it surfaces
(deploying rows). The first-seen centroid was therefore the opponent's side. The SIM played it there and the Miner
walked from near its own king.

**Before the fix (subset):** 5 of 6 opp Miner plays did 0 SIM tower damage, against 93 to 342 live
(`180141@1978`: live surfaced at (1500, 25500), SIM spawned at (9500, 5500)).

**The fix.** The play point is now where the track first turns deploying, for `DIGGERS = {Miner, GoblinDrill}`. It is
keyed by card because 31 of 531 Knight tracks also show active → deploying. That flags 16 of 16 Miner plays in the 84
matches and nothing else.

**After the fix:** SIM tower damage equals live in 4 of the 4 Miner fights where live dealt any (124 = 124, 93 = 93,
171 = 171; 342 vs 171).

Test: `test_a_tunnelling_miner_is_played_where_it_surfaces`.

The ceiling and card views add no change to the unperturbed replay (`--ceiling 0` output is byte-identical to HEAD
on `145128`, 85 of 85 fights). The Miner fix does change it, for Miner plays only.

## 4. Subset prototype (laptop, ≤ 4 workers)
- **Command:** `fights.py run --files 'live_play_20261015_1[5-8]*.jsonl' --stride 6 --max-fights 30 --ceiling 8 --workers 4`.
- **Coverage:** 7 frame-logged matches and 198 fights (42 strict, 139 core), run in 3 min 11 s.

| set | n | agree unperturbed | agree (live vs perturbed) [95% CI] | ceiling | normalised [95% CI] | goal | whole-fight outcome | body miss live / ceiling | tower fail live / ceiling |
|---|---|---|---|---|---|---|---|---|---|
| strict | 42 | 0.857 | 0.878 [0.801, 0.976] | 0.906 | **0.969 [0.940, 1.005]** | below 0.95 at the lower CI (n = 42) | 0.762 | 0.080 / 0.055 | 0.048 / 0.016 |
| core | 139 | 0.806 | 0.808 [0.777, 0.842] | 0.900 | 0.897 [0.850, 0.941] | below | 0.719 | 0.119 / 0.069 | 0.058 / 0.026 |
| all | 198 | 0.753 | 0.753 [0.681, 0.816] | 0.881 | 0.855 [0.783, 0.921] | below | 0.606 | 0.224 / 0.090 | 0.086 / 0.027 |

Cards with n ≥ 10 in core. All of them are flagged `insufficient n` (< 30) in the subset:

| card (core) | n | agree [95% CI] | ceiling | normalised [95% CI] | body miss live / ceiling |
|---|---|---|---|---|---|
| own IceWizard hero | 13 | 0.779 [0.455, 0.978] | 0.901 | 0.864 [0.560, 0.999] | 0.333 / 0.088 |
| own Log | 12 | 0.833 [0.667, 1.0] | 0.896 | 0.930 [0.832, 1.0] | 0.027 / 0.064 |
| own X-Bow | 11 | 0.909 [0.625, 1.0] | 1.000 | 0.909 [0.625, 1.0] | 0.091 / 0 |
| own Skeletons | 11 | 0.807 [0.667, 0.975] | 0.984 | 0.820 [0.687, 0.975] | 0.091 / 0.005 |
| own Tesla | 10 | 0.662 [0.523, 0.844] | 0.861 | 0.770 [0.575, 1.054] | 0.300 / 0.139 |
| own Knight | 10 | 0.713 [0.466, 0.917] | 0.971 | 0.733 [0.504, 0.939] | 0.300 / 0.029 |

The full per-card tables are `output/ceiling_proto/CEILING_{strict,core,all}.txt` (`ceiling_*.json`).

## 5. Which cards look below goal, and why (subset: hypotheses until the pod run)
- **n is the binding reason.** No card reaches n = 30 in the subset. On the full cohort, the strict set will give
  about 1,200 fights, and only own X-Bow, Tesla, Log, Skeletons, Hero IW and Knight will clear n = 30 strict
  (they are played about 1.2 times a match, DIAG §1). Most opponent cards will stay `insufficient n` in strict; core
  roughly doubles n.
- **Hidden opponent actions (core/all), not the SIM.**
  - Every core-only fight that fails live while the SIM agrees with itself (ceiling ≥ 0.75, aK < 0.5) carries an
    unseen opponent button or spell. That is 10 of 10: Mighty Miner, Skeleton King, Balloon, Knight hero, Mini Pekka
    and Wizard buttons, and a seen Rocket.
  - Own Knight, Tesla and Hero IW lose bodies live only (body miss 0.30 / 0.30 / 0.33 against a ceiling of 0.03 to
    0.14). This matches DIAG §8 (IW deaths live-only 191 vs SIM-only 39 in core).
  - The ceiling does not inject these, by design. So in core, these cards will read "below" for a logging reason
    (DIAG §1 logging list), not a SIM-law reason.
- **Strict: inside the noise.** Live body miss is 0.080 against a ceiling of 0.055, and tower fail 0.048 against 0.016.
- **The one strict live-only failure with a high ceiling:** opp Goblin Gang at `182623@1914`. Deaths match, but tower
  damage is 3,527 live vs 1,619 SIM. Untested whether this is attribution (several cards at one tower) or a real
  divergence.
- **Low ceilings (the metric is chaotic for the card, not wrong):**
  - Royal Hogs: ceiling 0.32. The hogs' paths flip on whether a Tesla is up.
  - Minions: 0.43.
  - Hog Rider: 0.57.
  - Their normalised scores swing above and below 1 on n = 1 or 2.

## 6. Pod run (full 84 matches, K = 8)
The pod checkout needs this `fights.py` and `run_fights_pod.sh`; they are not committed, and the runner refuses an old
`fights.py`. The frame logs from the FIGHTS35 run are already on the pod.
```bash
# laptop -> pod (same paths under /workspace/cb_rt35)
scp scratchpad/gauntlet/L74/parity/{fights.py,run_fights_pod.sh} <pod>:/workspace/cb_rt35/scratchpad/gauntlet/L74/parity/
# pod
cd /workspace/cb_rt35 && CEILING=8 nohup bash scratchpad/gauntlet/L74/parity/run_fights_pod.sh > /dev/null 2>&1 < /dev/null &
# -> /workspace/results/FIGHTS35_CEIL8/{CEILING_strict.txt,CEILING_core.txt,CEILING_all.txt,ceiling_*.json,
#    SCOREBOARD_*.txt,scoreboard_*.json,matches/,run.log,DONE}
```
- **Expected duration.**
  - Measured on the laptop: 2.4 to 3.1 core-s per fight at K = 8 (616 core-s for 198 fights, 4 workers in parallel).
  - That is 9 replays per fight. A K = 0 fight costs 0.15 core-s.
  - 4,434 fights on 14 workers comes to about **13 to 16 min**, under 35 min even if Linux is 2× slower.
  - The longest match (118 fights) is about 6 min on one worker.
- **Rescore without the SIM:** `python fights.py score --out <dir>` rewrites every SCOREBOARD and CEILING file from
  `matches/`. The tolerance constants are at the top of `fights.py`.

## 7. Limits
- **Tower attribution is a heuristic.** When several cards are in reach of one tower, the drop is split evenly. It is
  symmetric, so it cancels where positions agree. It has not been validated against true per-hit attribution; the SIM
  exposes no damage log in `save()`: `dmg.hits` is empty between steps.
- **The ceiling covers only the hidden state listed in §2.** Everything that is not redrawn keeps the SIM more
  self-consistent than the truth, which makes normalised scores harsher for cards that depend on it: charge, leap,
  facing, spawner timers and hidden opponent spells.
- **Same-card children from a setup body are counted as anchor bodies.** For example, a Witch on the board at t0
  spawns skeletons after a new Witch play inside the window. I have not counted how often this happens; it is rare
  (a same-card replay within 12 s).
- **Spell tick spread.** The draw uses the match's troop residuals (−3…+3). The 13 casts that DIAG §2 found 8 or more
  ticks late (unknown cause) sit outside this range.

## 8. Reader fields in the replay (ext frame logs, 2026-10-16)
`fights.py` now uses the 10-16 reader fields wherever a frame log carries them (`ents_state`, `proj`, `fx`; READER_VALIDATION_1016.md) and the phase-2 buffs when `re_phase2/validation/*/run.json` names the log. Logs without the keys replay exactly as before: on 3 old logs (`20261015_151727`, `_155027`, `_162215`, 121 fights, K = 8, `PYTHONHASHSEED=0`) every SCOREBOARD/CEILING txt+json file is byte-identical to HEAD, and each `matches/*.json` differs only in the wall-clock `seconds` field.

| item | what the replay does now (ext logs only) |
|---|---|
| hero casts | `seen_casts`: an opponent (or own) hero's first state-10 frame of a burst, or for an instant hero its ability effect row, is a press at mid-gap - 1 (SIM probe: press at t -> casting / spent at t+1). `opp_ability_unobserved` is no longer set for heroes; champions keep it (untested on video) |
| spells, both sides | `seen_casts`: projectile spells at the first shot's target point (throw + roll = one cast), effect spells at the effect's point with the cast tick from remaining_ms (life from the card table), played at creation - 1. A Goblin/Barbarian Barrel's bodies are left to the SIM; an own tap with a seen cast is not added again. `opp_spell_seen` is no longer used; a seen spell still flying / an area still on the board at t0 is `spell_in_flight_at_start` (Freeze excepted: its state is set as stuns) |
| targets | `seen_targets` replaces the guessed `tower_locks`: the latest projectile in the 20 ticks to t0 whose shooter and target are on the board sets the shooter's target (locked) |
| Tesla / charge / jump | `start_state`: Tesla state 0 -> Hidden, 2 -> Up (the ceiling keeps the seen state); a charger walking: charged at >= 1.6x walk speed, else `charge_progress` = walked mt x 4 (SIM probe); state 3 / 5 / 6 at t0 -> new strict blocker `setup_mid_jump` (no SIM setup for a body mid-dash, mid-river-jump or underground) |
| status at t0 | phase-2 buffs: `Freeze`, `Tesla_EV1_WithDamage` -> `stun_ms`; every other buff is counted as `status_unset:<name>` (informational). Without phase 2: a seen Freeze still running -> `stun_ms` on bodies and towers within its radius at the cast |

**Owner matches** (`20261016_115958/_121354/_122204`, level-11 classic towers 3052). HEAD skips all three (`not_main_account`); an ext log now counts when the own hand holds the X-Bow. "Before" = HEAD with only that gate relaxed. K = 8, laptop, 3 workers.

| run | fights strict / core / all | strict: n, agree unperturbed, agree [CI], ceiling, normalised [CI] | all: n, agree [CI], ceiling, normalised [CI] |
|---|---|---|---|
| before (HEAD + gate) | 43 / 69 / 105 | 43, 0.605, 0.634 [0.475, 0.823], 0.858, 0.739 [0.610, 0.886] | 105, 0.606 [0.524, 0.794], 0.872, 0.695 [0.605, 0.829] |
| after | 70 / 70 / 126 | 70, 0.700, 0.727 [0.505, 0.961], 0.903, 0.805 [0.558, 0.961] | 126, 0.703 [0.589, 0.886], 0.901, 0.780 [0.645, 0.931] |

Core = strict after: every hidden-information exclusion in these matches is now replayed. +21 fights, mostly new seen-spell anchors (own Log 9, own Tornado 4: own spells in these dry-run logs had no tap events). Remaining blockers (fights; sole blocker): `spell_in_flight_at_start` 27 (13), `setup_child_skipped` 18 (9), `ability_active_at_start` 8 (7), `setup_mid_jump:6` 8 (4), `setup_spawn_refused` 5, `sim_game_over` 4 (2), `play_refused:OUT_OF_TERRITORY` 2 (2; a first-seen own Ice Wizard in the mixed-control match 2), `setup_mid_jump:3` and `:5` 1 each. Every n per card is < 30: no goal verdict.

## 9. Attack target / phase inference (opt-in: `run --infer target,phase`, env `PARITY_INFER`)
SIM probe (0.1.35): `attack_ms` advances 50 ms a tick while engaged and a hit lands (melee) or launches (ranged) at each multiple of HitSpeed (`Cooldown` that tick, `attack_load_ms` reset to LoadTime). `infer_attacks` finds each t0-board attacker's last hit in the 100 ticks before t0: a victim's one-gap hp drop equal (+-1) to exactly one in-reach enemy's SIM per-hit damage (or +-2 to exactly one pair), less projectile travel; on ext logs a ranged attacker's launches are its projectiles' first sightings. Setup then gets target = that victim (locked) and `attack_ms` = elapsed mod HitSpeed, reload left = LoadTime - elapsed; skipped when no hit for > 1 cycle (> 2 for a projectile attacker). The ceiling redraws an inferred swing only within the last hit's frame gap.

Validation against the projectile truth (ext logs, ranged attackers, drop-only inference vs seen launch, n = 132): same victim 120 (0.909); phase mod HitSpeed within 100 ms in 117 (median 50 ms). The raw last-hit tick is a cycle early in most cases (the newest shot is still in flight at t0), which is why the stale limit is 2 cycles for projectile attackers. **Melee phase has no ground truth** (phase-3 RE).

| set | run | bodies with inferred phase / target (of setup) | strict: agree unperturbed, agree, ceiling, normalised | all: agree, ceiling, normalised |
|---|---|---|---|---|
| owner 3 | off | - (418) | 0.700, 0.727, 0.903, 0.805 | 0.703, 0.901, 0.780 |
| owner 3 | on | 209 / 52 (stale 59) | 0.714, 0.720, 0.939, 0.767 | 0.704, 0.934, 0.754 |
| old 3 | off | - (479) | 0.781, 0.777, 0.868, 0.895 | 0.671, 0.836, 0.803 |
| old 3 | on | 89 / 94 (stale 48) | 0.812, 0.809, 0.920, 0.879 | 0.682, 0.866, 0.788 |

Reading: agreement moves up 0 to 3 pp (inside every CI), the ceiling up 3 to 5 pp because the perturbation is narrowed, so normalised scores fall. Not a parity gain on this n; keep it opt-in until the pod cohort (84 matches) says otherwise. Outputs: `.foreman/scratch/fights_newkeys/` (local).
