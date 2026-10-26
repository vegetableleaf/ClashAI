# crforge evaluation: should training move off RoyaleSim fin15? (2026-10-25)

Grades: **(a)** measured here (number + source), **(b)** plausible but untested, **(c)** contradicted.
Scope: laptop only, short jobs, all at BelowNormal priority. No pods, no live, nothing in ClashBot changed except this file.
Clone and scratch work: `C:\Users\benpe\crforge_eval\` (repo, a portable JDK 17, game-table cache, `scripts\`). About 0.66 GB. Delete it when done; the C: drive is 98% full.

## Verdict: NOT NOW for switching training. Run a measurement pilot now.

crforge passed every spot check we could check against live values. Two of those (Tornado crown damage, Earthquake on a hidden Tesla) are numbers our RoyaleSim 0.1.35 got wrong. Its CI reports 10,000 out of 10,000 real battles reproduced tick for tick on data version 16.402.22, which is the 10-19 balance patch. That claim is far stronger than anything RoyaleSim has. But it rests on private data, recorded by a method nobody has disclosed. Our own test, fight parity on our captured live matches, has not been run on crforge. Integration is weeks of work, not days. Switching tonight would also break the comparison with the fin15 training run already in flight.

**Do this now, about 4-7 engineer-days, laptop or one pod:**
1. Point the parity harness (`L74/parity/fights.py` driver) at crforge.
2. Rescore the 145 captured matches and the J1-J4 metrics against fin15.
3. In parallel, use crforge as the differential oracle the v8 native sandbox never became: generate scenarios, run fin15 and crforge on each, find the first divergence.

## Deciding facts

1. **Every live value we checked matches exactly (a).** That covers princess HP, Rocket, Log, X-Bow, Tornado crown damage, Earthquake on a hidden Tesla, and the king-activation rule (table below). RoyaleSim 0.1.35 was off on two of these (HANDOFF 10-17, spell-damage audit).
2. **CI reports 100% tick-exact replay of 10,000 real battles each on 16.402.21 and 16.402.22, plus 1,733 on 16.402.19 (a, CI output; b, independently).** Sources: the `badges` branch, written by github-actions, and the public CI jobs of run 40214121670 ("coverage (16.402.22, k)" ×10, all success).
   - Every tick is compared with zero tolerance: the RNG state, every entity's id, side and x/y (projectiles and area effects included), each character's row, state, HP and shield, and each side's elixir, hand, queue and refill timer (`conformance/.../SmokeObserver.java:77-159`).
   - The same set improved from 83.1% to 100% between 10-13 and 10-15. Where the set id changed, the outcome counts were identical before and after (98.2% both sides on 16.402.21), so it was repacked, not re-sampled. That argues against cherry-picking.
   - We cannot reproduce it. The battles live in a private dataset that needs a token. How "the game's own trace" is recorded is never stated. The docs mention "a studied client binary" (`docs/compatibility.md`), which suggests reverse engineering.
3. **Our own decisive metric is untested (b).** We have no crforge number for fight parity on our 145 captured matches. The reader's noise ceiling (raw about 0.955) applies to any engine, so even a perfect simulator will not score 1.0 there.
4. **Integration costs about 15-30 engineer-days for a full switch (b, estimate below).** The env does not expose things our trainer uses today:
   - tower troops: always Princess towers (`LadderEnv.java:545`);
   - per-card levels: one level for every card (`EnvConfig`);
   - mid-match starts: `start_tick`, tower HP, elixir, `hand_first`.

   The core supports the first two. The third has no API at all.
5. **Speed is not the deciding factor, but it is no win either (a, loaded laptop).** Both engines were measured back to back on the same loaded laptop. Single-thread with our deck, crforge ran about 6,000-6,400 ticks/s, against 13,100-14,200 for the laptop's old RoyaleSim 0.1.17. That is 0.45x, and still about 1.5 matches/s per core. The policy dominates our cost anyway, at about 16 s of CPU per match (royalegym-engine note).
6. **Project risk (a).**
   - One human author: voonhous, 1,117 commits.
   - 652 commits in the last 30 days.
   - Observation schema at v4 since 10-18, with three schema changes on 10-18 alone.
   - Java 17 and a JVM inside our Python stack (JPype).
   - 12 stars, 1 fork, 0 human issues.

## Repository facts (a)

| | |
|---|---|
| Evaluated commit | `ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0` (main, 2026-10-25 15:32 EDT) |
| License | Apache-2.0. NOTICE disclaims any Supercell affiliation. The README asks ports to cite the file and commit (a request, not a license condition). |
| Language / build | Java 17, Gradle 9.7.1 (Kotlin DSL), LibGDX for the visualizer, Python package `crforge-env` (JPype, gymnasium, pettingzoo) |
| Size | working tree 24 MB without `.git` (GitHub reports 35 MB). Lines (main / test): core 94,972 / 85,306; env 8,295 / 5,845; tables 3,009 / 700; conformance 2,660 / 2,363; desktop 11,888 / 5,395; python 2,612 / 1,999 |
| Activity | first commit 2026-01-23; 652 commits in the last 30 days (642 voonhous, 10 "voon"). Busiest days 10-04 (89 commits), 10-05 (73), 10-13 (61) |
| Contributors | voonhous (751 + 366 under a second name, same email), github-actions 171, dependabot 35, "Claude" 4 |
| Open issues | 5, all dependabot PRs. GitHub: 12 stars, 1 fork |
| Game data | not shipped. `:tables:gameTables -Pcrforge.assetSource=cdn` fetches about 28 MB of `csv_logic`/`csv_client` from `game-assets.clashroyaleapp.com`, SHA-1 checked, and builds data versions 16.402.18 / .19 / .21 / .22. 16.402.22 is the 10-19 mid-season balance data (`docs/game-versions.md`) |

## Architecture and mechanics (read in depth)

- **Tick model (a, docs + code).**
  - Each step is 50 ms (20/s) of integer milliseconds.
  - A tick is a series of passes over the whole entity list: all targeting, then all movement, then all state visits, over a snapshot ordered by id.
  - Commands run before the entity tick. A play runs 20 ticks after it is given (`PLAY_DELAY_TICKS`), the client's delay.
- **Stats (a).** Read straight from the game's own tables under their own column names; nothing is hand-tuned. Level scaling uses the rarity multipliers. Any column or class the core does not model is refused with an `UnsupportedOperationException`, never guessed.
- **Card coverage on 16.402.22 (a, `census.py`).**
  - 153 card rows; 145 have a cost and a rarity; 122 after dropping event rows (Super*, Global*, chess, Snowball, TriWizards...).
  - 43 cards list an evolution; 18 list a hero form, Ice Wizard among them.
  - 8 ladder champions; 4 tower troops in the data (Princess, Cannoneer, Dagger Duchess, Chef).
  - All 8 icebow cards are present: Xbow, Tesla (+EV1), Knight (+EV1, +hero), Skeletons (+EV1), IceWizard (+hero), Tornado, Rocket, Log.
  - The hero Ice Wizard's freeze and its cube-on-kill are modelled. There is a reference case `new-content-v2/hero_icewizard`, and the battle-core doc covers the rider freeze.
- **Spells (a, docs).**
  - Tornado pull: AttractPercentage times the unit's speed, toward the centre. It averages with the collision pushes and does not reset route, reference or state. The buff stacks.
  - Log: a thrown projectile spawns the rolling one; each body takes one hit plus a push of 700.
  - Rocket and Log tower shares come from `CrownTowerDamagePercent`.
- **King activation (a, docs + test).**
  - The condition is the data's own expression, `king_tower_damaged() || tower_destroyed() || ...`.
  - Once it holds, a 3,300 ms activation run starts, so the king's first visit is 70 ticks later.
- **Elixir (a, tables).**
  - Default timeline: Normal 180 s, then Overtime 120 s.
  - Rates: 1x for 120 s (28 s a bar), 2x for 120 s (14 s a bar), 3x for 60 s (9.3 s a bar). Start 6 elixir; plays open at 4.5 s.
  - Path of Legends replays play as a Ladder match. 2v2 and event modes are not modelled.
- **Determinism (a, run here).** Same seeds and actions give an identical observation SHA-256 on 1 thread and on 4: 8 battles × 1,500 decisions, `det.txt`. Forks and lookahead copy a battle in about 1 ms (b, their number).
- **API (a).**
  - `VectorEnv` steps N battles on a thread pool behind direct buffers, which Python reads without a copy.
  - Per seat: 7,024 int32 observations (header plus 200 entity rows of 34) and a mask of 2,307 actions.
  - Actions: wait, 4 slots × 576 tiles, and 2 ability taps (champions and heroes).
  - It also offers slot flags (evolution 1, hero 2), fault isolation per battle with replay bundles, `replayJson`, and a replay labeller for imitation.
  - The observation is a fog-of-war view: enemy HP is -1 unless the health bar shows, and enemy elixir is counted from what is seen.
  - Coordinates are 1,000 units a tile on an 18,000 × 32,000 board, the same frame as `pipeline/obs_contract.py`.
- **Tests in the repo.**
  - Unit tests write their own rows or read shipped rows and do their own arithmetic.
  - The fidelity evidence is two private suites: `:conformance:referenceTest` (1,036-1,045 targeted cases per version, all `diagnostic_match` in `reference-expectations/*.json`) and `coverageScore` (the 10k sets).
  - We cannot run either one.

## Build and test suite (a)

`./gradlew --max-workers=4 :env:installDist :core:test :env:test :tables:test :conformance:test` took 8 min 54 s (`C:\Users\benpe\crforge_eval\test_run.log`).

| module | tests | failed | skipped |
|---|---:|---:|---:|
| core | 2,140 | 3 | 2 |
| env | 108 | 0 | 0 |
| tables | 51 | 0 | 4 (need the private data repo) |
| conformance | 68 | 0 | 0 |

All 3 failures are `FidelityLedgerTest`, and the cause is Windows-only: `FidelityLedger.toBinaryName` does `.replace('/', '.')` on a Windows path, so the class scan comes back empty. It is a tooling test, not a mechanics test. The desktop and Python suites were not run; the Python job passes in public CI.

## Our probes (scripts in `C:\Users\benpe\crforge_eval\scripts`, `Probe.java` against the core/env jars, tables 16.402.22)

| Check | crforge | Live / real reference | Grade |
|---|---|---|---|
| Princess tower HP, L11 / L15 / L16 | 3,052 / 4,424 / 4,858 | 3,052 / 4,424 / 4,858 (account-guard memory, HANDOFF) | (a) match |
| King tower HP L16 | 7,728 | no live record | (b) |
| Rocket on a princess tower, L15 / L16 (L11) | 497 / 546 (342) | 497 / 546 (HANDOFF 10-09 lethal rules) | (a) match |
| Log on a princess tower, L15 / L16 (L11) | 51 / 56 (35) | L15 51 | (a) match |
| X-Bow damage per hit, L11 / L16 | 61 / 98. 26 hits in 10 s (HitSpeed 400). First tower damage 4.25 s after the play runs; the tower falls inside 40 s | owner's in-game L11 reading 61 | (a) L11 match; timing (b) |
| Tornado crown damage per hit, L11 / L15 / L16 | 25 / 36 / 40, 1 hit per cast | live 25 / 36 / 40; **RoyaleSim 0.1.35 gave 26 / 37 / 41** | (a) match; RoyaleSim was off |
| Earthquake on a hidden Tesla, L11 / L16 | 3 hits of 286 / 458 | live 286 / 458; **RoyaleSim 0.1.35 did 0** | (a) match; RoyaleSim was off |
| Hog L16 dragged by our Tornado L16 at (7000,5500) | hog lands at (7001,5889), retargets the king, first king hit at tick 164, king awake at tick 234: **70 ticks** after the first damage | real rule: wake on king damage or princess loss | (a) behaviour; the 70-tick delay vs live (b) |
| Same at (7000,7000) and (8000,4500), plus no-Tornado control | the hog goes back to the princess; the king never takes damage and never wakes | as the rule says | (a) |
| Log L16 over 3 Skeletons L16 and a Knight | all Skeletons die; the Knight takes 429 and moves 518 units net in the log's direction | kill is real; no push record | (a) kill; push (b) |
| Refusals: 300 random legal L16 decks from the 122 Ladder cards, random evo/hero slots, random play | 0 faults; 5 decisions with a NOT_MODELLED play. With event cards included: 85 of 200 faulted, all on event-only rows | | (a) |
| JVM memory | 326 MB peak for 1 battle, 526 MB for 16 (`-Xmx1g/2g`) | | (a) |

The probes cover the deterministic stats and a few rules, and our deck behaves on them. They are not a fidelity measurement of whole fights. That needs the parity pilot.

### Throughput (a)

The laptop was at about 94% CPU load from MuMu, live Python and Roblox Studio. Each engine ran single-thread at BelowNormal priority, back to back and alternated twice: `b_cf_*`, `b_cfstd_*`, `b_rs_*`.

| engine, workload | ticks/s | matches/s | matches/h |
|---|---:|---:|---:|
| crforge: icebow (evo Knight, evo Tesla, hero IW) vs 4 meta decks, L16, random plays 3 in 10, 16 battles | 5,944 / 6,398 | 1.5 / 1.6 | about 5,400-5,800 |
| crforge: their benchmark mirror deck, L11 | 12,288 / 14,170 | 3.1 / 3.5 | about 11-12.8k |
| RoyaleSim 0.1.17 (laptop runtime, not fin15): icebow vs Hog, includes Python and `state()` every decision | 13,098 / 14,230 | 3.0 / 3.3 | about 10.8-11.8k |

crforge reports about 104,000 ticks/s per thread on a quiet Apple M4 Pro (`docs/performance.md`). We did not reproduce that here (b). Machine load, the laptop CPU and our heavier deck explain the gap; we did not measure how much each contributes. We also did not measure multi-thread scaling, so as not to starve live; they report 3.1-3.9x on 4 threads.

At about 1.5 matches/s per core, 64 cores give about 345k matches/h engine-only, which is not our bottleneck. fin15 has more laws than 0.1.17, so its own speed may be lower (b).

## What fidelity means on each side

| | RoyaleSim fin15 (ours) | crforge |
|---|---|---|
| Metric | fight outcomes on our captured live matches, tolerant, with a noise ceiling | exact equality of every entity, every tick, plus RNG state, on replays with their true seed |
| Numbers | fight parity 0.941 normalised on 145 captured matches (10-17)<br>fin15 J1 0.927 on 14,188 fights; J2 0.917; J3 0.933; J4 elixir 0.991<br>W19 overall 0.920 [0.916, 0.923] against the 0.975 goal<br>Tornado/king: same-situation activation 0.81-0.85<br>upstream RoyaleSim: 56.5% of unit-ticks within 1/4 tile (09-23) | 100% of 10,000 battles to the end on 16.402.21 and 16.402.22 (CI, 10-15 and 10-25)<br>1,036-1,045 targeted reference cases per version, all matching |
| Data access | ours, reproducible | private, provenance undisclosed |

These two metrics cannot be compared directly. Only the pilot puts them on one scale.

## Integration cost (b, rough engineer-days)

| Item | Days |
|---|---:|
| `pipeline/crforge_env.py` adapter with RoyalePoolEnv / RoyaleSelfPlayEnv's interface (reset, act, advance_to, costs, done, outcome, `raw()` into the `from_engine` dict incl. status flags, deploy kind 12, v4 projectiles/effects, hero identity) via JPype on the core API | 4-6 |
| Java shim for what the env lacks: tower troops per side (core `Towers(spawnGroup, kingLevel, level)`); per-card levels (core `play(..., level, ...)`); mid-match starts (`start_tick`, tower HP fractions, elixir, `hand_first`; no core API, built from setters and `Hand.rearrange`; these starts are not covered by conformance) | 2-4 |
| Card names / vocab (same internal names as RoyaleSim's "engine spelling": IceWizard, Xbow, Log, Assassin, DarkWitch...) | 0.5-1 |
| Hero IW press (learned `gae_ab` head plus the live rule) through ability actions / `useAbility` | 1-2 |
| Rewards and opponent model reading the new state (rocket_cycle, king_redirect, W7/W18 pools) | 2-3 |
| Pods: JDK 17 + JPype per venv, tables per data version (copy the cache, do not hit the CDN from 8 pods). One JVM per worker costs about 0.33 GB each (about 21 GB for 64 workers); otherwise rework rollouts around one batched `VectorEnv` per pod (+4-6) | 1-2 (+4-6) |
| Parity harness port plus rescore (the pilot) | 3-5 |
| Re-baseline: CLXIII on crforge, recalibrated SIM gates, LIVECAL predictiveness, drift tests | 2-4, plus pod compute |
| **Total** | **pilot 4-7; full switch about 15-30** |

**fin15 laws.** None port over, and none should. Our engine laws are patches to RoyaleSim:
- the elixir floor
- the Tornado pack cap and uncapped pull mean
- tiebreak regen
- the Skeleton formation
- Tornado crown order
- Earthquake hidden split
- Evo Knight deploy protection
- tower troops

crforge models each from the game's data, so each needs re-checking through the ported harness, not re-implementing. Harness and reader fixes (the H- class, spawn timing) stay in the harness and carry over. Checkpoints keep the same observation contract, but the engine shift means a fine-tune or retrain and fresh gates.

## What would change the recommendation

- **Switch** if the pilot shows crforge's raw fight parity lower CI above fin15's on the same 145+ captured matches, with Hero IW, X-Bow, Tornado and Log not worse, and J4 at 0.99 or better. Budget the full integration then.
- **Switch sooner** if the author gives access to the coverage/reference data or documents how traces are recorded, and an independent rerun reproduces the 100%.
- **Stay on fin15 and use crforge only as an oracle** if the pilot shows crforge is not better on our harness. That would mean the reader ceiling or our harness dominates. Keep porting crforge-confirmed laws into fin15, citing the crforge file and commit as its README asks.
- **Watch** for a later client range. crforge tracks one client range, 16.402.12 onward, and needs new tables and references at each required update. Check how fast it moves when the next range starts.
- **Risk flags:** bus factor 1; fast API churn (pin a commit); `DeepCopy` relies on `sun.misc.Unsafe` (JDK 17 only); game data comes from Supercell's CDN and must not be redistributed, the same position as our `apktables`.

## Reproduce (laptop, about 15 min)

```bash
cd /c/Users/benpe/crforge_eval/repo
export JAVA_HOME=/c/Users/benpe/crforge_eval/jdk/jdk-17.0.20.1+1 GRADLE_USER_HOME=/c/Users/benpe/crforge_eval/gradle-home
./gradlew --max-workers=4 :tables:gameTables :env:installDist -Pcrforge.assetSource=cdn -Pcrforge.cache=C:/Users/benpe/crforge_eval/cache
cd .. && jdk/jdk-17.0.20.1+1/bin/javac -d probe_build -cp "repo/env/build/install/env/lib/*" scripts/Probe.java
jdk/jdk-17.0.20.1+1/bin/java -cp "repo/env/build/install/env/lib/*;probe_build" Probe cache/tables/16.402.22 <towers|rocket|log|xbow|tornadotower|eqtesla|hogtornado|logskel|determinism|pool 300 2000|bench 16 1 2500 16>
python -I scripts/badge_history.py repo; python -I scripts/expectations.py repo/conformance/reference-expectations
```
