
# ENGINE pillar plan: making the training simulator 99.9% accurate, and proving it

## Recommendation

Use **option (b): switch to crforge**, gated by a 6-day pilot measured on our own real matches.

- **Option (a), RoyaleSim:** build fin16 once as the interim training engine and fallback, then stop adding laws to it.
- **Option (c), crforge as oracle for RoyaleSim fixes:** fallback only, if crforge fails the throughput or integration gates.

Why not (a):
- RoyaleSim cannot reach 99.9% by fixing laws one at a time. Each round moves J1 by +0.0002 to +0.002, no mechanism explains more than 13% of failures, and about 32% of failures are unexplained (FIN15.md section 9.2).
- J1 needs about +0.07 raw to reach its ceiling. That is 35 to 350 rounds.
- RoyaleSim uses 18,000 units per tile against the game's 1,000, with its own pass order (royale_env.py SCALE). An engine built that way cannot be tick-exact.

Why crforge:
- It reads Supercell's tables and the game's own replay format.
- It models the game's random number generator: the battle source is an xorshift (`BattleRandom.java`), and the deck deal uses a variant of the Mersenne Twister seeded with "battle draw + the player's account low word" (`DeckShuffle.java`, `LadderMatch.java:304`, `ReplayBattle.java:43`).
- Its CI claims 10k/10k battles reproduced tick-exact, but that dataset is private. Its 10k claim does not count as evidence for us; only our own measurement below can make the switch.

## 1. What "99.9% accurate" will mean (the definitions I'd commit to)

**M-SME, seeded match exactness. This is the headline number.**
- **Item:** one held-out real ladder match on the current data version (16.402.22).
- **Engine inputs:**
  - both decks with forms and per-card levels (the reader's `level` and `max_hp`), king and tower levels, and tower troops;
  - the deal order of both sides;
  - the battle seed;
  - every play of both sides, with tick and tile.
- **Pass:** on every reader frame until the match ends, every observable matches exactly, with zero tolerance. Both sides are integers in the same 1,000-per-tile units. Observables are:
  - each body's card, side, x/y and hp;
  - tower hp and king state;
  - projectiles (x/y and target) and effects (x/y and `remaining_ms`);
  - our elixir to 1e-4, our hand and next card;
  - on phase-3 captures, also attack target and attack progress.
- **SME** = exact matches divided by matches.
- **Certificate:** one-sided 95% Clopper-Pearson lower bound of at least 0.999. That needs 0 failures in 2,996 matches, at most 1 in 4,744, or at most 2 in 6,296.
  - SME on a match is stronger than any per-fight score: an exact match makes all of its ~35 fights exact.
- **Two strata, reported separately and then frequency-weighted:**
  - **RNG-free matches** (no random draw after the two deal draws): no seed is needed, only the deal orders.
  - **RNG matches:** need a seed (G1 below).
- **How the reader ceiling is handled. There is no modelled ceiling here; the reader's own error is measured directly:**
  - frames the reader flags itself (`failure` set or `coherent` false) are excluded and counted, and matches with more than 1% such frames leave n and are counted;
  - an artefact filter (for example the twin Hero IW row and the card-less rows near tower slots) is fixed on the dev split only, with no per-match exemptions on held-out matches;
  - the cheap gate G-R2 records one match live and again in the replay viewer: the real client against itself bounds the reader's own error.
- **Play-tick ambiguity:** the 2-tick frames leave each play's tick within one tick. Each play gets two candidate ticks, and the engine picks the one consistent with the following frames. That is about 60 bits of freedom against thousands of exact integers per match. We record how many plays were ambiguous.
- **Held-out split:** by date, fixed before any fixing. A held-out match that fails becomes dev data after the attempt closes, and the next attempt uses fresh matches.

**M-CARD, per card.**
- A card passes with at least 30 zero-failure SME matches containing it (95% lower bound 0.905); at 150 matches the bound is 0.98.
- Proving 99.9% per card would need about 3,000 matches containing that card. That cannot be measured from real data for rare cards, so each card is reported with its own bound, and cards short of supply are listed as untested by us.

**M-STATIC.** The engine's parsed stats equal the device pull of 16.402.22 (`apktables/compare.py`) on 100% of records.

**Legacy series, so the history stays comparable.**
- J7 seeded crown sequence, raw. With seed and exact plays its ceiling is about 1, so raw is close to normalised.
- J7 unseeded with a K=8 ceiling (deploy tick jittered within the frame gap, RNG reseeded) on both engines.
- J1 on RoyaleSim, frozen at its last value. J1 is not ported to crforge: its mid-match state injection has no core API in crforge, and SME supersedes it.

**What is not available.** No independent tick-exact engine exists on 16.402 for us:
- RoyaleSim is not exact;
- the native sandbox is build 15.535.29, so its mechanics and tables differ;
- the v8 oracle is excluded.

The real client, read through our reader, is the reference. It is stronger than any engine-to-engine differential.

**Coverage of states self-play reaches but real matches never do.** Count the mechanic keys (card x card, spell x victim) per self-play update against the set SME has verified, and report the uncovered share. Above 5%, queue optional lab battles (two-account friendly battles, needs the owner's OK).

## 2. Stages

### Stage 0 (days 0-2): interim engine and cheap gates
1. **Build fin16** with `scratchpad/gauntlet/L74/parity/fin16/fin16_chain.sh` (patches already written, commit 406ffd1).
   - Run the R3 A/B: c13 must be byte-identical and c22 must go up.
   - Add `fin16-linux` to `pipeline/royale_runtime.py` and `pipeline/royale_heroiw.py`. Training moves to fin16 at the next run boundary.
   - No further RoyaleSim law rounds after this.
2. **Pin crforge** at commit ad8ef3a or newer on one pod: JDK 17, `:env:installDist`, a one-time copy of the 16.402.22 table cache.
   - Delete `C:\Users\benpe\crforge_eval` from the laptop once the pod copy is verified (the laptop has about 26 GB free).
3. **G0, RNG census (2 h):** count `BattleRandom.next` calls per card after the deal, over 300 random legal decks plus our 16.402.22 deck census.
   - This sizes the RNG-free stratum and says which matches need a seed.
4. **G1, seed recovery from data we already have (1 day).**
   - Our live logs record our own hand with `deck_index` from tick 150 (decision events), so our deal permutation is observed: 8! orders, 15.3 bits.
   - Our player word is the low word of our account id. Brute force over the 2^28 possible draws, reusing crforge's own `DeckShuffle.order`: about 5-10 s per match on a 54-vCPU pod.
   - Inverting the xorshift gives about 106k candidate seeds per match.
   - The opponent's deal, from their account word (their tag from our battle log via the official API) and their play sequence, cuts this to about 60 (b).
   - The RNG-dependent events in the trace pick the final seed.
   - **Pass:** a unique verified seed on at least 90% of matches that have a tag.
   - From now on, poll our own battle log after every live match. `crapi.py` already holds the key pattern; our battle log keeps only 25 matches.
5. **Optional device checks (owner OK, about 15 min each):**
   - **G-R2:** record one match live and again from the battle-log replay viewer, then compare the reader traces.
   - **G-R3:** after watching a replay, list the client files that changed (read-only adb, the apktables precedent). Does the device cache the official replay file? If yes, crforge's `ReplayScenario` reads it directly: exact inputs with the seed, for every match.

### Stage 1 (days 2-8): pilot, which produces the decision data
1. **Input extractor and replay driver.**
   - Live log in, crforge inputs out: decks, levels, troops, words, seed or observed deal, plays with tile and candidate ticks.
   - Reuse fights.py's level read-off, `seen_casts` and `drill_surface`, and `replay_rec/convert.py`'s hand path for replay-viewer recordings.
   - Battle setup goes through crforge's own replay builder, `ReplayBattle.build`.
   - The per-tick state dump reuses the fields of crforge's `SmokeObserver`.
2. **Same inputs, three engines:** J7 crown sequence, result and falls on at least 300 post-10-19 live matches, for crforge, fin16 and fin15.
3. **SME** on at least 50 seeded matches (or RNG-free matches if G1 fails), with a first-divergence census for each failure: tick, entity, quantity.
4. **Robustness:** 20k IL_Replay sequences through crforge, deals inferred by `deal_order`. Measure the fault and refusal rate.
5. **Throughput:** engine plus facade cost per match on a 4090 pod, with 24 JVMs running at once and our deck census.

### Decision point D1 (day 8)

| Check | Go number |
|---|---|
| J7 crown sequence, crforge minus fin16, same inputs | at least +0.15, and the match-bootstrap 95% CI of the difference above 0. fin15 is 0.506 raw. The real game code with guessed seed, deal and levels reproduced only 74.7% of the pro corpus, so the seeded score should be well above that |
| SME on the pilot cohort | at least 45/50 (lower bound about 0.80), with failures traced to 5 or fewer mechanisms |
| Faults and refusals on IL_Replay (event cards excluded) | 0.5% or less |
| Engine plus facade cost | 1.5 core-s per match or less; 16 GB per pod or less for 24 actors |
| M-STATIC | 100% |

What each outcome means:
- **All pass:** (b). Start Stage 2.
- **J7 and SME pass, cost between 1.5 and 4 core-s per match:** still (b), plus a batched `VectorEnv` rework (+4-6 days).
- **Cost above 4 core-s per match, or JPype blocked on pods:** (c). The 99.9% target is then formally out of reach, with J1 and J7 normalised as the only targets.
- **J7 difference below +0.05:** crforge is no better on our data. Stay on fin16 and port crforge-confirmed laws one by one, citing crforge's file and commit. Report the 99.9% target as unmet, with the numbers.
- **J7 passes, SME below 0.9:** still (b). The fix loop runs on our crforge fork, with fixes offered upstream.

### Stage 2 (days 8-22, about 14 engineer-days): switch training to crforge
1. **New `pipeline/crforge_core.py`:** a facade with the same face as RoyaleSim's `RustEngine`, over JPype, so nothing downstream changes.
   - It provides `reset`, `step(DeployCommand)`, `state()` (players, entities and spells as the pipeline reads them), `cards()`, `unit_types()`, `card_table_stamp()`, and `save_state`/`load_state` (crforge `fork`, about 1 ms). These cover `branching.py`, `search_s0.py`, `cf_credit.py`, `reward_shaping.py` and `projectile_observation.sim_objects`.
   - It emits coordinates x18, so `SCALE` and everything downstream are unchanged.
   - The JVM starts lazily in each process. The actors already use spawn (`rl_royale.py:3038`), so there is no fork-after-JVM problem.
2. **One small Java shim in our repo:** tower troops per side and per-card levels (the core supports both), seed and word setup, and the trace dump.
   - Mid-match starts (W15 `start`) are deferred until an active arm needs them. They have no core API and no conformance coverage.
3. **`pipeline/royale_env.py`:** one seam, replacing `self.core = RustEngine(**heroiw.engine_options())` with a factory picked by the runtime. `REGEN_SCHEDULE` comes from the core.
4. **`pipeline/royale_runtime.py`:** runtime id `crforge-<sha12>-linux`, with a manifest of jar sha256s, the tables' content sha and the JDK version, checked in `activate()`.
5. **`pipeline/royale_heroiw.py`:** Hero IW press through crforge's ability action, with the public identity mapping.
6. **Pod setup:** setup and smoke scripts on the `setup_fin15.sh` / `smoke_fin15.py` pattern.
7. **D2 gates (day ~22):**
   - `rl_royale --smoke` passes;
   - update u0 rows are identical across two runs;
   - seconds per update are at most 1.15x fin16 on the same pod;
   - CLXIII re-baselined on crforge, SIM gates recalibrated;
   - SME on dev at least 0.98.

### Stage 3 (from day 3, certificate attempt around days 30-45): measurement pipeline
1. **Nightly job:** each new live log plus the battle-log poll goes through seed recovery, crforge replay and SME scoring. Results go into METRICS.md.
2. **Fix loop:**
   - each failure's first divergence becomes a minimal crforge scenario;
   - patch our crforge fork;
   - re-run all dev matches and crforge's 2,140 core tests;
   - offer the fix upstream.
3. **Supply.** Live play alone is too slow: 11-100 matches a day gives 30 to 270 days for 3,000. The realistic route is TV Royale harvesting:
   - `replay_rec/harvest.py` is built; the menu templates and the owner's D2 approval are missing;
   - both hands are visible, about 40 replays an hour at 4x, up to about 800 new replays a day across channels;
   - this feeds the RNG-free stratum with no seed needed;
   - optionally, a reader field for the battle RNG state or the account ids (owner D3) makes TV replays usable for the RNG stratum too;
   - battle-log replays of our own matches add the opponent's elixir and exact ability presses, as elixir drops with no card.

## 3. RL throughput

**Today, measured.** A pod does one update of 256 games in about 200 s, roughly 4,600 matches an hour; four pods run about 18,000 an hour (`tonight1020/PREP.md:120-132`, `distrib/DISTRIB.md`). The policy and Python cost about 13 actor-seconds per match. The learner step (about 42 s) is the floor.

**Requirement:** at least 4,000 matches an hour per pod, which means the engine plus observation costs 1.5 core-s per match or less.

| Option | Engine cost per match | Meets it? |
|---|---|---|
| (a) / (c) RoyaleSim | about 0.3-0.4 core-s (laptop 0.1.17 measured; fin15 not measured) | yes |
| (b) crforge | about 0.65 core-s measured (1.5 matches/s per core, loaded laptop, our deck), plus the facade conversion (target 0.5 ms per observation, about 1,200 observations per match) | yes, expected; this is D1 check 5 |
| JVM memory for 24 actors | 0.33-0.5 GB each, 8-12 GB per pod | fits |

## 4. Risks

- **crforge's claim is unverifiable:** SME on our data decides; nothing rests on its CI.
- **Bus factor of one and fast API churn:** pin the commit and keep our own fork branch. It is Apache-2.0 and we can carry it ourselves.
- **A required game update** closes crforge's supported client range. Nightly SME detects it within a day, and fin16 stays pinned as the fallback runtime.
- **Seed recovery fails** (the shuffle model is wrong or tags are missing): fall back to the RNG-free stratum plus the optional reader RNG field. G0 sizes this risk on day 1.
- **Observation contract drift** through the facade (kind 12 deploying, status flags, Hero IW identity) would silently change the policy's inputs. Run the same scripted match on fin16 and on crforge and compare the shape and ranges of the observation dicts. Then fine-tune and re-gate; no checkpoint resumes across engines (the existing `require_same` rule).
- **Opponent champion presses on live logs** (Golden Knight has no visible press burst): infer each press from its effect, the engine searching the onset within 1-2 ticks, and report the share of excluded matches. Replay-viewer recordings remove this problem.
- **The certificate depends on owner-gated data:** pod use, API polling, TV harvesting.

## 5. Timeline

| Days | Milestone |
|---|---|
| 0-2 | fin16 built and A/B'd; crforge on a pod; G0, G1 |
| 2-8 | pilot; **D1 on day 8** |
| 8-22 | integration; **D2 around day 22**; training moves to crforge at a run boundary |
| 3-45 | SME pipeline and fix loop; first 2,996-match certificate attempt around days 30-45, depending on TV supply; per-card bounds as supply allows |

Engineer effort: pilot about 6 days, integration about 14, measurement pipeline about 4, plus the ongoing fix loop. All heavy work runs on pods; the laptop stays as it is.

### Critical files for implementation
- `C:\Users\benpe\ClashBot\pipeline\royale_env.py` (the one-line core seam)
- `C:\Users\benpe\ClashBot\pipeline\royale_runtime.py` (`fin16-linux` and the crforge runtime id with its manifest)
- `C:\Users\benpe\ClashBot\pipeline\crforge_core.py` (new: the facade, plus the Java shim beside it)
- `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\parity\metrics\replay_metrics.py` (SME and seeded J7 scoring, reusing `j7()`) and `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\parity\fights.py` (input extraction reused)
- `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\parity\fin16\fin16_chain.sh` and `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crapi\crapi.py` (interim engine; opponent tags for seed recovery)
