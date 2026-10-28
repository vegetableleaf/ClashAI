# crforge Stage 0 (plan1026 Pillar 1): pin, G0 random-draw census, G1 seed recovery (2026-10-27)

Labels: **(a)** measured here (number + source), **(b)** plausible but untested, **(c)** contradicted.
Pod 33920 (54 vCPU quota, `cpu.max` 5440000/100000), CPU only; `/workspace/scale` and the GPU not touched.
Laptop: read-only use of `C:\Users\benpe\crforge_eval` (nothing deleted there; the plan's "delete it once the pod copy
is verified" is left to the lead).

## Verdict
- **Pin: done (a).** crforge `ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0`, OpenJDK 17.0.20.1, `:env:installDist`, tables
  16.402.18/.19/.21/.22, smoke passes. The determinism hash matches the laptop's.
- **G0: about 60% of our Ranked matches have no random draw after the deal (a, under crforge's RNG model).**
  - Only 4 Ladder cards draw: Arrows, Princess, Hunter and Skeleton King. Our icebow deck draws nothing.
  - 89 of 223 opponents carry one of the four.
- **G1: the pass bar is not met (a).** A unique seed was recovered on 0 of the 223 tagged matches from live logs, and on 0 of the 1 replay recording; the bar is ≥ 90%.
  - **Replay recording**, both full deals: 2 candidate seeds.
  - **Live logs only**: at least 1,756 candidates wherever any fit. Even a perfect opponent play list leaves 8,244.
  - So the plan's "about 60" (b) is **contradicted (c)**. The deal holds too few bits.
  - A unique seed needs the trace check described under "Route" (Stage 1 inputs). The seed-free 60% need no seed at all.

## 1. Pin and smoke (a)
| item | value | source |
|---|---|---|
| commit | `ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0` (same as EVAL.md) | `git log -1` on pod `/workspace/crforge` |
| JDK | openjdk 17.0.20.1 (apt `openjdk-17-jdk-headless`) | `java -version` |
| build | `./gradlew --no-daemon --max-workers=8 :env:installDist`: BUILD SUCCESSFUL in 46 s | `/workspace/crforge_build.log` |
| tables | copied from the laptop cache (not refetched from the CDN), 28 files in 16.402.22 | `/workspace/crforge_cache/tables/` |
| smoke `Probe towers` | princess towers 4,858 at L16 (= live main account), king 7,728 | pod run |
| smoke `Probe determinism` | IDENTICAL on 1 vs 4 threads; observation sha256 `a0bd88c41f98b46d`, **the same as the laptop's `det.txt`**, so it is deterministic across machines | pod run vs `crforge_eval/det.txt` |

Reproduce: `crforge/pod_setup.sh`.

## 2. G0, random-draw census
How draws are counted, with no change to crforge:
- Count the xorshift steps between the battle random state before and after each tick or decision (`Census.java` `steps()`).
- A draw with range < 1 does not step the state, so it cannot matter for a seed.
- The deal draws come before the count starts: the state is read right after `reset`.

### 2a. Per card form, solo (a): `crforge/g0_solo.tsv`
Setup:
- 183 rows: the 122 Ladder cards plus their `_EV1` and `_hero` forms.
- Each is played twice by side 0 at L16, answered by two Knights, for 60 s with the towers attacking.
- A Knight-only baseline draws 0.

Results:
- **Non-zero:** Princess 20, Princess_EV1 28, Hunter 190, Hunter_EV1 285, Arrows 60 (draws per 2 plays).
- **Zero:** every other form that ran. That includes all 8 icebow forms (Xbow, Tesla/EV1, Knight/EV1/hero, Skeletons/EV1, IceWizard/hero, Tornado, Rocket, Log) and Graveyard, Witch, Tombstone, Goblin Hut, Goblin Barrel/EV1, Firecracker/EV1, Lightning, Poison and Earthquake.
- **6 forms could not run outside a match:** Goblins_hero, MegaMinion_hero and BarbLog_hero (champion slots), Elixir Collector, Mirror and MergeMaiden.

Champion abilities only run in a match, so the pool below covers them.

### 2b. 300 random legal battles (a): `crforge/g0_pool.tsv`, `crforge/pool_attr.py`
Setup: 600 decks (EVAL.md's legal-deck rule), random plays 3 in 10 decisions (ability taps included), L16, first episode only.

Results:
- 0 faults.
- **121 of 300 battles drew after the deal; 179 were RNG-free.**
- Arrows, Princess and Hunter explain 110 of the 121.
- All 11 others contain Skeleton King. With it added, **0 battles draw without one of the 4 drawing cards.**
- 1 battle held a drawing card but drew nothing (the card was not played or never fired).

### 2c. Our matches: 223 Ranked battle-log deck pairs, 10-08 to 10-27 (a): `crforge/live_attr.py`
Data:
- Decks come from the official API in slot order.
- The API card order equals the in-game deck slot order: checked on the 10-26 replay, both sides 8/8 (a).
- Each pair ran 3 times with random plays: 669 battles, 0 faults.

Results:
- **Our icebow deck holds no drawing card (0/223).**
- **Opponent decks with a drawing card: 89/223 = 39.9%** (Arrows 54, Princess 28, Hunter 9, Skeleton King 4).
- **RNG-free by deck: 134/223 = 60.1%.** This is a lower bound, since a drawing card may go unplayed.
- In the random-play runs, 135 pairs never drew and 88 drew at least once. None drew without a drawing card.
- **RNG-free matches need no seed (a, by construction):** no draw ever reads the state after the deal.
  - Given the plays, the deal itself only gates which plays are legal.
  - So these matches need neither seed nor opponent deal (b: no mechanic reads hand-slot order; worth a one-line check in the Stage 1 extractor).

**Caveat (b).** The census measures crforge's RNG model.
- crforge says its model is "held by the random state every reference battle observes on every tick" (`BattleRandom.java` @Fidelity).
- That rests on its private CI (EVAL.md fact 2).
- A draw the real game makes but crforge does not model would move matches out of the RNG-free stratum. Only the Stage 1 SME pilot will show it.

## 3. G1, seed recovery
### Model, read from crforge (a, code)
1. `ReplayBattle.java:38-52`: `world.seed(seed)`, then 2 × `addPlayerData(1)` (each `next(1)` returns 0 but steps the state).
2. `LadderMatch.java:302-304`: then for side 0, then side 1, `draw = next(0x0fffffff)` and `order = DeckShuffle.order(deck, draw + word)`.
3. The word is the low word of the account id.

So with s3 = the state of side 0's deal draw, side 1 draws from step(s3), and the seed is 3 steps before s3.

**Finding (a).** The xorshift's middle shift is arithmetic (`s >> 17`), so one step is **2-to-1 onto half of the states**: bit 31 after `s ^= s>>17` is always 0.
- Not every state can be s3: one with no 3-step preimage cannot follow any seed through the 2 player-data draws. This filter roughly halves the candidates.
- It assumes exactly 2 player-data draws in the live game, which comes from crforge's replay translator (b).

### Tool (a): `seeds/SeedSearch.java`, built against the pinned jars
- **Search:** brute force over all 2^28 - 1 draws through crforge's own `DeckShuffle.order` and `BattleRecords.matchCard` (force/omit flags read from the tables). Then:
  - expand each fitting draw to its 16 states;
  - check the other side's deal: a full order, or a play list with a misfit count;
  - apply the preimage filter;
  - invert to the seeds.
- **Cost:** 23-26 s on 54 threads (about 1,300 core-s) per new (word, flag layout).
- **Batch mode:** caches a 512 MB rank table per word, then takes **0.2 s per further match**. Every match with our account shares one table.
- **`selftest`:**
  - `unstep(step(t))` holds on 1,000,000 random states.
  - A battle dealt by crforge itself (seed 424242, both words set) gave 3 states fitting both deals, 2 of them valid.
  - The true s3 (1459981381) and the seed 424242 were among them.
  - This checks the tool's reading of crforge, not the real game.
- **Inputs:**
  - `seeds/gen_jobs.py`: battle log × live logs, 223 jobs.
  - `seeds/rec_job.py`: replay recording to job. On 10-26 it reproduces the hand-built job exactly.
  - Tags become words by base 14 over `0289PYLQGRJCUV` with id = low<<8 | high: the community decoding (b).

### Results
**Replay recording `rec_20261026_130926` (live match `live_play_20261026_130453`, both full deal orders, both tags) (a):**

| variant | deal fits | valid survivors |
|---|---:|---:|
| standard words (low word from tag) | 4 | **2** (s3 = -1462933474, -1043283422) |
| control: words swapped between sides | 0 | 0 |
| control: raw low 32 bits as word | 0 | 0 |
| control: words 0 | 3 | 0 |

How strong is this evidence?
- A wrong model fits about 2^32 / 40,320² = 2.64 states by chance, about 1.3 after the preimage filter. So it gives ≥ 1 survivor about 70% of the time (b, Poisson).
- One match plus 3 empty controls is **weak (b) support** for the model plus the tag decoding.
- More recordings sharpen it: a correct model never gives 0.
- **Unique: no.** 2 candidates remain, and this match's opponent has Princess, so it is an RNG match.

**Our deal from live logs alone is exact (a):**
- The decision events' `own_hand.deck_index` at the first decision, plus the order cards enter, gives [5,3,7,0,6,2,4,1].
- This equals the replay's tick-0 deal (1/1).

**The opponent from live logs (a):**
- Plays read from new bodies and spell projectiles/effects (`gen_jobs.opp_plays`): 37 plays.
- The replay's hand changes give 35 true plays. The 2 extra are evolved Skeleton Army bodies born later.
- The true deal has misfit 2 against the extracted list. At misfit ≤ 2 there are 8,244 + 15,958 + 8,361 candidates.
- **With the PERFECT opponent play list (from the replay): 8,244 valid survivors, the true pair included** (`seeds/results/live1026_truthplays.out`).
  - Plays never show hand-slot positions (4! = 24 orders look the same) or most of the queue order.
  - So the opponent's plays remove only about 1/13 of the 107k states. The plan's "about 60" (b) is **contradicted (c)**.

**All 223 tagged Ranked matches, live inputs (a)** (`.foreman/scratch/seeds/pod/batch.log`, summary `seeds/batch_sum.py`):

| play misfit allowed | matches with ≥ 1 candidate | unique |
|---:|---:|---:|
| 0 | 60 | 0 |
| 1 | 77 | 0 |
| 2 | 92 | 0 |
| 3 | 108 | 0 |

- Where any candidate fit, the fewest was 1,756.
- 115 of 223 had no fit at misfit ≤ 3 (play-extraction errors).

**Unique-verified-seed rate: 0/223 live-only, 0/1 replay-recorded (a). The G1 bar (≥ 90%) is not met.**

### Route (b, untested)
1. **RNG-free stratum, about 60%: no seed needed** (section 2c). Stage 1 can start SME on these now.
2. **RNG matches: check candidates against the trace.**
   - A battle is identical for every candidate up to its first draw after the deal.
   - So simulate once to that tick, then fork per candidate RNG state (`LadderEnv.reseed` / a world.seed fork). Forks cost about 1 ms (crforge's own claim, EVAL.md).
   - Compare the first RNG-dependent observable: the impact points of the Arrows / Princess volley, or the Hunter pellets.
   - Replay-recorded matches have 2 candidates, so this is cheap.
   - Live-only matches have 2k-16k candidates. That is still cheap per fork, but the comparison window must hold enough RNG-dependent events to make one candidate unique.
   - This needs Stage 1's exact play extraction (tick, tile, form). It cannot be done before then.
3. **More replay recordings** (procedure below) give both full deals: 2 candidates instead of thousands. They also test the model + tag decoding: a correct model never gives 0 survivors.

## 4. Replay recording procedure (for the lead; not run: the owner's live Ranked run holds the device)
Menu facts are from `plan1026/devcheck/REPORT.md`. **Only the first frame matters**: the tick-0 frame holds both deals.
1. Owner OK. The live run is stopped (supervisor.log tail checked), MuMu is on the main account, and the main screen is showing.
2. On the laptop, start the recorder first:
   `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/recorder.py --device --max-seconds 20`
3. Menu (820,170) → Battle Log (540,110) → Watch (750,765 for the newest entry).
   - Older entries need a scroll; their coordinates are not measured (b).
   - The battle log keeps the last 25 matches, so record at least every 25 matches.
4. After about 5 s of replay, back out. The recorder ends on idle, tick stall or `--max-seconds`.
5. Note the entry's time against `own_battlelog.jsonl` to get the opponent tag (the own_poll.sh poller keeps it). Then build the job and run it on the pod:
   - `python -I scratchpad/gauntlet/L74/seeds/rec_job.py --tables <tables/16.402.22> --rec icebow/data/replay_rec/rec_<stamp>.jsonl --tags '#20Q0UV0GPQ' '#<OPP>' --out <job>.txt`
   - then `java -cp "$L/*:build" SeedSearch $T <job>.txt 54` on pod 33920 (`/workspace/seeds`).
6. About 30-60 s per match including navigation (b). Prefer RNG matches, where the opponent has Arrows, Princess, Hunter or Skeleton King: the seed-free 60% gain nothing from a recording.

## Files
- `crforge/Census.java`: G0 counter (modes solo / pool / decks).
- `crforge/g0_solo.tsv`, `crforge/g0_pool.tsv`: G0 results.
- `crforge/pool_attr.py`, `crforge/live_attr.py`: attribution helpers (pod python3).
- `crforge/pod_setup.sh`: the pin.
- `seeds/SeedSearch.java`, `seeds/gen_jobs.py`, `seeds/rec_job.py`, `seeds/batch_sum.py`: G1 tools.
- `seeds/results/*.out`: the 10-26 match runs.
- Local only, not committed (built from the git-ignored battle log):
  - `.foreman/scratch/seeds/jobs/` (223 jobs, manifest, deck pairs);
  - `.foreman/scratch/seeds/pod/` (g0_live.tsv, batch.log, rec jobs).
- Pod: `/workspace/crforge`, `/workspace/crforge_cache`, `/workspace/seeds` (build/, jobs/, live/).

## Pin update 2026-10-27: upstream sync passed the gate (a)
Procedure: `crforge/fork/upstream_sync.sh`, rerunnable weekly. Outputs on pod 33920 are in
`/workspace/upstream_sync/20261027/`.

**New pin: `008aa626ef465003dff429505b741be06b25f9e2`** (upstream `main`, 2026-10-27 19:00 +0800). It sits on fork
branch `clashbot-upstream-20261027` in `/workspace/crforge_fork`. The determinism hash is unchanged:
**`a0bd88c41f98b46d`**, IDENTICAL on 1 vs 4 threads.

**Upstream since `ad8ef3a`: 5 commits, none touching mechanics.**

| commit | what it changes | type |
|---|---|---|
| `4b235e52` (#731) | client range minimum checked 10-26 | docs |
| `c52b76c8` (#732) | play / replay guide in the README | docs |
| `1d32619a` (#733) | closes the 16.402 client range, records client 16.635.1 | docs |
| `51b5bd14` (#734) | builds the tables of data version 16.635.3: `data-versions.json`, `schema/16.635.1.json` (+12,689 lines), `crforge-data.lock`, `ClientSchemaTest` | tables |
| `008aa626` (#735) | splits the version tables | docs |

- The `core` and `env` sources are unchanged.
- The merge onto `clashbot-fix` was conflict-free; `clashbot-fix` carries no patch yet. Round 3.2's Valkyrie case
  needed none (`pilot/sme/SME.md`).

**Gate, all three passed:**
1. **Core tests:** 2,140 tests, 0 failures, 0 errors, 2 skipped.
2. **SME live pilot**, current extract (`/workspace/pilot/inputs_v2`) against pin run12:
   - 31 / 109 → 31 / 109, 0 regressions, 0 gained;
   - exact frames 220,450 → 220,450;
   - 138 / 138 matches identical.
3. **J7 crown sequence**, crforge_force arm on the deck8 subset (401): **0.808 [0.768, 0.845]**, as on the pin.
   The crforge_force lo / hi run files are byte-identical to the pin's (sha `e5b09a00…` / `0a68da92…`).

**What changes for us:** nothing on the 16.402.22 tables our pre-update matches use. The gain is the 16.635.3
table build for the new client (160635001); building it needs `-Pcrforge.assetSource` pointed at the 16.635
assets, which this sync did not run.

**Not done:** `/workspace/crforge` itself was left at `ad8ef3a` (never modify the pin directory). J7 / SME workers
still load it, which is identical in behaviour on 16.402.22. Switching the runtime path to the fork build is a
one-line `SME_LIB` / J7 `L=` change, left to the lead.
- **SME runs now use the fork build (A2c round 4, 2026-10-27):** `/workspace/pilot/lib_008aa626` (a frozen copy of
  `crforge_fork/env/build/install/env/lib` at `008aa626`). run13 on it equals run12 on the pin on 138 / 138 matches.

## Tables for client 16.635 (build 160635001): what a build needs (no build run; 2026-10-27)
- **Our matches since 10-27 ~06:58 are client 160635001 (a):** every live log from `live_play_20261027_065824` on
  reads phase-2 `build` 160635001 (117 logs that day, the last 40 all 160635001). The logs carry **no data version or
  content sha (a)**, so whether a match ran data 16.635.1 (shipped, `5ad888ef…`) or 16.635.3 (update, `dae6c6cc…`)
  is not known from them. 16.635.3 is the likely one (b): first seen the same day as the client.
- **crforge side, at `008aa626` (a):** `data-versions.json` pairs 16.635.3 with client schema 16.635.1 and content sha
  `dae6c6cc7e9126338da0c606e47e48a9ef80462c`; the schema file is in the tree. **16.635.1 (shipped) is not paired**, so
  it cannot be built without adding it. `crforge-data.lock` still says `version=16.402.22`, and the battle rules still
  follow client 16.402.17: upstream says moving the battle core to 16.635 is "a later step". Whether the core runs on
  16.635.3 tables at all (new classes, `PushBackDamage` now a damage-type reference) is untested (b): the first check
  is `:core:test -Pcrforge.dataVersion=16.635.3`.
- **Which assets:** the files under `csv_logic/`, `csv_client/` and `data_manifest.toml` that the content sha's
  `fingerprint.json` lists, each SHA-1-checked against it. For 16.402.22 that is **425** of the fingerprint's 10,720
  files, all of them in the laptop cache `C:/Users/benpe/crforge_eval/cache/assets` (a).
- **From where, two routes:**
  1. `-Pcrforge.assetSource=cdn`: the game's asset CDN by content sha. That is how the 16.402 tables were built on the
     laptop (EVAL.md: about 28 MB from `game-assets.clashroyaleapp.com`). One gradle call:
     `:tables:gameTables -Pcrforge.dataVersion=16.635.3 -Pcrforge.assetSource=cdn -Pcrforge.cache=...`. It is an
     outbound download, so it needs the owner's go.
  2. `file://` source laid out as the CDN: `<dae6c6cc…>/fingerprint.json` plus `<dae6c6cc…>/<path>` for the 425-odd
     files, built from a device pull plus the 160635001 APK.
- **Does the reader's device pull cover it? Not alone (a).** `apktables/pull_device_update.sh` pulls the game's
  `update/` folder. The 10-22 pull (data 16.402.22) has the right `fingerprint.json` (version 16.402.22, sha
  `97869d43…`) and its table files match the fingerprint's SHA-1s (81 / 81), but it holds **82 of the 425** files
  crforge needs; the rest come from the APK (apktables: "APK fallback"). No 160635001 APK kit is on the laptop
  (`share/` has none), and no device pull since the update exists. So route 2 needs a fresh pull **and** the
  160635001 APK's `csv_*` assets, with their SHA-1s checked against the pulled fingerprint (untested, b: the APK
  files may be stored in the same LZMA form the CDN serves).

## 16.635.3 tables built; crforge's core refuses them (A2c round 5, owner go 2026-10-27)
- **Built (a):** pod 33920, fork `008aa626`, `./gradlew :tables:dataVersionTables -Pcrforge.dataVersion=16.635.3
  -Pcrforge.assetSource=cdn -Pcrforge.cache=/workspace/crforge_cache` (3 min 35 s; log `/workspace/t16635/build.log`).
  - `tables/16.635.3/build.properties`: data_version 16.635.3, client_version 16.635.1, content_sha
    `dae6c6cc7e9126338da0c606e47e48a9ef80462c`, decoder 1. 28 table files (4.6 MB), as for 16.402.22.
  - Fingerprint `fingerprints/dae6c6cc….json`: version 16.635.3, 11,467 files, 433 of them table files
    (`csv_logic/`, `csv_client/`, `data_manifest.toml`); 423 asset files in the pod cache (SHA-1 named, shared files
    once).
- **Our client runs 16.635.3 (a):** the MuMu live instance's `update/fingerprint.json` (read-only `adb shell`) says
  version 16.635.3, sha `dae6c6cc…`, the same content sha as the built tables. 16.635.1 (shipped) is not what it runs.
- **Core on 16.635.3: refused by design (a).** `:core:test -Pcrforge.dataVersion=16.635.3`: 2,140 tests, **1,053
  failures**, 0 errors, 2 skipped (`/workspace/t16635/coretest.txt`). 986 failure messages are the core's version guard:
  "the battle models the rules of game client 16.402.17, which runs data versions [16.402.18, 16.402.19, 16.402.21,
  16.402.22]; it does not play tables of data version 16.6…". One more is the schema change upstream named:
  `BattleRam_EV1_PushBack sets PushBackDamage to a table of BaseDamage, Flags where a number is read`.
  - So **no SME on the 160635001 matches is possible on this core** (b for anything after the guard): crforge refuses
    to battle on 16.635 data until upstream moves the battle core to client 16.635. Bypassing the guard would run
    16.402.17 rules on 16.635 data, which is not exactness.
  - The pin's own tests on 16.402.22 are unchanged (2,140 / 0 failures, gate of 2026-10-27).
- **What it takes next:** an upstream crforge release for the 16.635 range (watch `docs/compatibility.md`), then the
  same gate (core tests, SME pilot, J7). Extraction of today's matches is not the blocker.

## A2c round 6.4-6.5 (2026-10-27): no RageDamage fork patch (diagnosis contradicted); 16.635 measured in a scratch copy
Files: `crforge/fork/r6465/`. Pod 33920 scratch dir `/workspace/r64/` (`/workspace/crforge_fork` and the pin untouched;
no branch was added to the fork, since no patch was written).

### 6.4: RageDamage is not created a tick late by crforge; our Rage casts were dated a tick late (a)
- **Game rule, from the reader's countdowns (a, `chaintally.py`).** All 16 Rage areas in the 138 matches, at first sighting:
  - remaining 4,500 ms (not yet updated): **RageDamage absent on that frame, 6 / 6**;
  - remaining 4,450 ms (one update done): **RageDamage present (remaining 1 ms, the next generation id), 10 / 10**.
  - So the game, like crforge, creates the chained area on the parent's **first update**, not when the parent is made.
    A chain-at-creation patch would add a RageDamage to the 6 frames where the game has none: **(c) for the ticket's cause**.
- **crforge on `200616` (a, `simareas.py`, run20 plan):** at 2545 the sim shows Rage at 4,500 and no RageDamage; at 2546
  Rage 4,450 plus RageDamage. The game shows Rage 4,450 plus RageDamage at 2545. The whole Rage is one tick late, not
  its chained area. At 1014 (game 4,500 first, no RageDamage) the sim matches the game.
- **Cause: extraction (a).** `extract.table_shims.life('Rage')` returns None, because Rage has no `AreaEffectObject`: its
  area comes from `RageBottle`'s `DeathAreaEffect`. `fights.deployments` then dates the area at its first sighting
  instead of `first - (4500 - remaining)/50`. That is 1 tick late whenever the first frame is 4,450 (10 of 16 casts).
- **Measured (a), input-only, run `r64_rage`** (`shift_inputs.py`: inputs_v5 with those 10 Rage commands 1 tick earlier;
  same engine `lib_008aa626`, `repr_v2`, `SME_TORN_STEP=1`):
  **40 / 109 -> 43 / 109, exact frames 227,262 -> 228,990, 0 regressions.** Gained: `200616`, `224041`, `020134`.
  The 3 "Rage RageDamage 1 tick late" onsets of run20 are gone. Traces deleted.
- **Not done (outside this ticket's write set):** the extract fix. In `table_shims.life`, for a spell without
  `AreaEffectObject`, follow `SummonCharacter` -> `buildings.DeathAreaEffect` -> `LifeDuration`. Then regenerate the inputs.
  `bottle_lag` stays as it is. Core tests and J7 do not apply: no crforge change.

### 6.5: crforge on the 16.635.3 tables, guard bypassed in a scratch clone (measurement only, nothing adopted)
Scratch: `git clone /workspace/crforge_fork /workspace/r64/cf635` at `008aa626`; `GameVersions.CLIENT_16_402_17_DATA`
gets `"16.635.3"` (`r6465/guard_bypass_SCRATCH_ONLY.diff`, first hunk).

**(a) Core tests, `-Pcrforge.dataVersion=16.635.3`, guard bypassed: 2,140 tests, 47 failures, 0 errors, 2 skipped**
(`r6465/coretest_16635_bypass.txt`), against 1,053 with the guard. So **1,006 of the 1,053 were the guard**. The 47 left
are all crforge refusing a changed table row as "not modelled". None is a wrong value:

| n | table change (16.402.22 -> 16.635.3) | crforge |
|---:|---|---|
| 19 | new action class `ActionAbilityDelivered` (`*_ability_delivered` added to the hero Giant / Valkyrie / Golden Knight / Balloon / Ice Wizard ability groups) | "the battle does not have" |
| 12 | `MegaKnight_EV1_uppercut` sets `GameTagsToSet` NO_ATTACK, NO_MOVE_ALLOW_ATTRACT (the root: NO_MOVE -> NO_MOVE_ALLOW_ATTRACT); 11 refusals + 1 assertion | not modelled |
| 8 | global `V16_PROJECTILE_DAMAGE_BUG` removed (crforge reads it, `BattleWorld.java:822`: Hunter volley damage) | "no global" |
| 3 | `BattleRam_EV1_PushBack.PushBackDamage` 83 -> {BaseDamage 83, Flags NoCounter} | mistyped field |
| 3 | buffs `Cannon_EV1_barrage_damage_buff`, `FirecrackerFireworks_EV1`: PlayerSpecificBuff -> `CastIdSpecificBuff` | not modelled |
| 2 | `ElectroWizardHero` attack sequence entries add `CustomBuffOnDamageTime` 600 | not modelled |

**Rule content of 16.635 (a, `tdiff.py` / `adiff.py`):** 19 rows added, 4 removed, 18 changed across 28 tables, plus 46
actions added, 1 removed (`ElectroWizardHero_Forbid_Movement`) and 13 changed.
- **No stat change:** 0 changed rows in buildings, projectiles, spells_buildings, spells_hero_form, damage_types or
  card_groups.
- **New content:** Giant evolution (`Giant_EV1`, 5 `GiantEvoRage*` areas, 35 `giant_evo_*` / `Giant_EV1_*` actions, 4 variables)
  and Mirror evolution.
- **Hero abilities:** `RefundWindow` 50 -> none, `RefundUntilDelivered` true, on 5 hero abilities.
  - crforge reads `RefundWindow` and falls back to the trigger delay. No test catches this, so it is a **silent change (b)**.
- **Bug globals:** `V16_AEO_OWNERSHIP_BUG`, `V16_PROJECTILE_DAMAGE_BUG` and `V16_RUNE_GIANT_VISUAL_BUG` removed. New flags
  `FIX_RESET_CHARGE_DURING_PUSHBACK_WHEN_MOVEMENT_DISABLED` and `LOGIC_SKIP_KAMIKAZE_ON_DISCARDED_HIT` (true).
  - crforge reads none of the new flags, so they are **game-code rule changes the core does not model (b)**.
- **Small changes:**
  - `ElectroGiant_EV1_Pulse_AEO` filter: NoClones -> plain;
  - `SkeletonDuplication_EV1` `NotCloned`;
  - `PassiveForcedHitGroundCharacters` adds DashImmune;
  - Electro Wizard hero `ForbidMovement` link removed;
  - Mega Knight evolution uppercut tags.
- **Ranked mode:** `Ranked1v1_NewArena2` arena -> `Arena_competitive`.

**(b) Extraction and SME on client-160635001 matches (a).**
- `extract.py` (unedited; `r6465/ext635.py` swaps its `TABLES` to 16.635.3) extracted **91 / 91** Ranked battles since
  10-27 06:58. All are build 160635001, with 0 skips. 47 are RNG-free, 33 of them unflagged. Inputs stay local and on the
  pod (`/workspace/r64/inputs635_rngfree.jsonl`), not in git.
- **SME, guard bypass only (`sme635_run`): 47 / 47 matches refused.**
  - 42 on `IceWizardHero_ability_delivered`: our own hero Ice Wizard press, so every match with a press refuses;
  - 2 on the Mega Knight evolution;
  - 1 each on Golden Knight, Valkyrie and Firecracker evolution.
- **SME with two scratch stubs (`sme635_stub`)**: `ActionAbilityDelivered` as an inert action, `CastIdSpecificBuff` as a
  known column; the second and third hunks of the diff.
  - **17 / 33 unflagged exact apart from torn, 66,363 exact frames**; 7 matches still refuse on the Mega Knight evolution.
  - First divergence of the 14 failing: 4 body position, 3 body missing in the sim, 3 own elixir 1 frame early, 2 hp only,
    1 spell area timing, 1 sim body missing in the reader (`cmp_635_vs_402.txt`).
- **Control, the same 47 matches on the unpatched fork with the 16.402.22 tables (`ctl402`): 47 / 47 run, 17 / 33 exact,
  69,314 exact frames.**
  - **On the 40 matches both ran: 40 / 40 identical** (counts and first divergence).
  - The 7 Mega Knight evolution matches all diverge early on 16.402.22 (first divergence at 178-654).

**(c) How much rule change 16.635 holds (a for these 47 matches; b beyond them):** for our matches, very little.
- Swapping 16.402.22 for 16.635.3 tables changes nothing on 40 / 40 matches.
- The 160635001 matches are as exact under 16.402.17 rules as under the new tables: 17 / 33.
- What 16.635 adds:
  - new evolutions (Giant, Mirror) and the hero `ability_delivered` refund hook;
  - the Mega Knight evolution uppercut tags (7 / 47 of our matches);
  - the removed bug globals and new fix flags, whose game-code effect only an upstream core change can model.
- The pin stays on 16.402.22. This bypass is not exactness for those 7 or for any match where the refund or flag rules
  bite (b), and nothing here is adopted.

## F635c (2026-10-27/28): fork rebased onto upstream's 16.635 move (e5462c82); both client ranges played
Labels as above. Files: `crforge/fork/f635/` (`patches/0009-0010`, `patches_up/0001-0005`, `results/f635c_*`,
`results/coretest_{c7,c8,up0,g2,g4}.txt`, `results/bppc_up1_counts.txt`, `pod/{ctboth,ctup,buildsnap,smerun85,bppc}.sh`).
Pod 30408, `/workspace/f635/crforge_fork`; the pin and the other branches untouched (upstream fetched into
`upstream/main` only).

**New branch head: `clashbot-up-e5462c82` = `bec5811a51fcbc55bd4112b4f9fe30c23b5e29d8`** (upstream e5462c82 + 5 commits).
**Determinism hash (Probe determinism, lib of that head): 16.402.22 `a0bd88c41f98b46d` (= the pin's), 16.635.3
`575c99887ba28802`, IDENTICAL on 1 vs 4 threads (a).** Core jar sha256 `63b78b8a1b743ef2`.

- **Upstream moved the battle to client 16.635.1 overnight (a):** 13 commits 008aa626..e5462c82, each traced from the
  16.635.1 client. They cover F635-1 (#739), F635-2 (#738), F635-3 (#747), F635-4 (#744), F635-6 (#745), F635-8 (#742),
  7a (#743) and 7b (#741), plus #740 (DashImmune RespectDodgingDamageCooldown), which we had not listed. Upstream
  refuses 16.402 data (b40c4a36).
- **Branch:** from `clashbot-upstream-20261027` (= 008aa626), fast-forwarded to e5462c82. Upstream's version kept for
  every overlap; ours kept only where upstream has none:
  - `cbdec89e` F635-5 (by-id press promise, PlayerCommands; facade ee9982b needs it);
  - `e54769fe` F635-7 (Elite Archer side shots with no root; upstream still refuses);
  - `1d338603` F635c-10 guard: `GameVersions.MODELLED_DATA` = 16.402.18-22 + 16.635.3;
  - `822d27f7` F635c-11 and `bec5811a` F635c-12, below.
- **Two upstream changes alter 16.402 play in code (a, our frames):** upstream e5462c82 + ours, SME old client
  88 -> 81/109.
  - 5 regressions start at a MegaKnight_EV1: #738 dropped the uppercut's coded hold.
  - 2 start at a BossBandit: #740's column default is on.
  - F635c-11 and F635c-12 restore 16.402.17's rule on 16.402 data only (`BattleWorld.client16402`, filter default off).
  - The two were measured together, so attributing the 2 BossBandit matches to F635c-12 rests on the unit (b).
  - Upstream itself reports the same for #738: 55 of its 16.402.22 references went to mismatch.
- **Differences, ours (dropped) vs upstream (kept).** Our 47 new-client frames do not tell any of them apart:
  c7_new (our F635-1..9 line) vs the branch, 47/47 identical, so each is (b) on our evidence. Upstream traced each
  from the client.

  | item | ours | upstream |
  |---|---|---|
  | F635-6 (#745) | read the dropped global as clear | kept the set test: queued damage vs hp + shield. Ours was the wrong side (c, by upstream's trace) |
  | F635-3 (#747) | cast match also by side | cast id = the king's play count, no side check (the same count from the other side matches) |
  | F635-8 (#742) | NoCounter not read | NoCounter: a counter (Ronin parry) skips the hit |
  | F635-4 (#744) | entry time only, any order length | entry buff and time, order of two or more |
  | F635-1 (#739) | last copy leaving refunds | the cost rides on the unit, refunded capped as the slot is; a building paid so is refused |
  | 7a (#743) | (ticket assumed the charge is left alone) | the charge is RESET during a pushback while movement is disabled (c for the ticket's reading) |
  | 7b (#741) | (ticket: discarded hit already returned before the kill) | crforge ran hitEnded for a missed hit (c); the flag skips it, the Kamikaze unit lives on |
- **Gates of the branch head (a):**
  - Core tests: 16.635.3 2182/0 (6 skipped); 16.402.22 2182/0 (29 skipped). Upstream alone on 16.402.22: 1,006 guard
    refusals + 21 others.
  - 16.635-only upstream tests assume 16.635 data: ReplayScenarioEveryFieldTest, 1 CastIdSpecificBuff case and the 4
    uppercut / DashImmune 16.635.1-rule cases.
  - SME old client, a2c6's round-7 config (= its r78: inputs_v19, repr_v2, TORN_STEP STEP_CLOCK TORN_CMD3 KIND_T
    BP_MIXPH BP_SNAP SnapRun2 BP_FITNEXT), with clashbot-bp TickProbe 0001 + 0002 applied for the build only
    (`buildsnap.sh`, scratch, not committed): **88/109, 261,135 exact frames, 138/138 identical to a2c6's r78, 0
    regressions.** The lib_bp2 control on 30408 is also 138/138 identical to r78.
  - SME new client (47 RNG-free, 33 unflagged): 17/33, 70,198 exact frames, 47/47 identical to the F635 line.
  - Forced-button sweep (26 forms x 40; ButtonProbeP): 16.635.3 1,037/1,040 none, 3 on the press-timing rule below;
    16.402.22 1,033/1,040 none, 7. **No 16.635.3 row is refused.**
- **Giant evo / Mirror evo (items 8-9): not modelled.** In 16.635.3, `Giant_EV1` and `Mirror_EV1` are NotInUse +
  NotVisible (a). The 43 in-use evolution rows are exactly the 43 evolutions seen in our battle logs. So they are
  shipped-ahead, unreleased forms.
- **GiantBuffer_hero (Rune Giant hero): not a real form; excluded.** The row has no `CardForm: HeroForm`.
  `forms_decks.py` now takes only CardForm HeroForm rows (27 -> 26 forms; GiantBuffer_hero is the one dropped).
  `new_client_forms.py` drops its item.
- **Press-timing refusals (F635b concern), cause read from the code (a by code, not traced per episode):**
  - The rule is `PlayerCommands.tryAbility`. A press is given within +-2 ticks (DROP_WINDOW) of the 60-tick expiry of
    an earlier refused play's promise, and the elixir gate's answer differs with and without that promise.
  - It is the client's exact promise-expiry tick, not traced, not a press bug.
- clashbot-635 got 7a/7b too (`5cc4067d`, `ea9a9bf4`, cherry-picks of #743/#741; SME for 7a: old 67/109 and new 17/33
  identical), and is superseded by `clashbot-up-e5462c82`.

## CF-CLONE (2026-10-28): Clone on an evolved Skeleton carrying its duplication; Clone sweep of every census form
Labels as above. Files: `crforge/fork/cfclone/` (`patches/0001`, `CloneProbe.java`, `sweep_sum.py`, `grades_cmp.py`,
`rowgrep.py`, `pod/`, `results/`). Pod 30408, worktree `/workspace/cfclone/crforge_fork`, **branch `clashbot-cfclone` =
`62558795`** (= `clashbot-up-e5462c82` bec5811a + 1 commit). The `/workspace/f635/crforge_fork` checkout
(clashbot-f1fix) was not touched.

- **The crash (a):** d2t1 actor 11, "c65_1_0 is cloned carrying SkeletonDuplication_EV1, whose spawner's copy is not
  modelled" (`BuffComponent.copyFrom`, upstream #228 c8472e81). Upstream main (7cec0492) still refuses it.
- **Tables (a, `rowgrep.py`):**
  - `SkeletonDuplication_EV1`: SpawnObject Skeleton_EV1, SpawnInterval 50, SpawnLimit 1, SpawnNumber 1,
    SpawnerAliveRequired. 16.635.3 adds `NotCloned: true`; 16.402.22 has none. It is the only buff row whose NotCloned
    changed between the two versions.
  - `Skeleton_EV1`: BuffAfterHits SkeletonDuplication_EV1 for 500 ms, `ClonedVersion: Skeleton` (its clone is a plain
    Skeleton, with no duplication of its own).
  - Clone: area 3000 radius, 1000 ms, OnHitAction CloneAction -> SpawnCloneBufAction (the Clone buff for 500 ms,
    SpawnSpeedMultiplier -100). Both versions are the same.
  - Spawner buffs in both versions: DropBomb, MysteryBuff_Spawn_Skeleton, MysteryBuff_Spawn_Hog,
    SkeletonDuplication_EV1. No census form carries the first three (sweep below).
- **Game evidence: none direct.**
  - Live (a): 0 of the 3,281 matches in `loss_review/matches.jsonl` have an opponent with both Clone and Skeletons; 0
    of the 138 SME frame files contain a Clone.
  - HF (a): IL_Replay holds plays only, no unit frames, so it cannot show a clone's children.
  - The x86_64 libg.so in `research/ext/cr-native-sandbox` has no section headers, an entry point in an extra LOAD
    segment, and no plain column-name strings, so its code was not read. No decompiler is configured for REA.
- **Model (b, not traced from the client):** a clone's copy takes the instance's spawner as it stands: the timer, the
  firings of its wave and the firings left (`BuffInstance.copy`). The refusal is removed.
  - Why: the copy already carries every other counter of the instance (hitCounter included).
  - Effect: the duplication fires on the buff visit after the hit, so the copy is spent and the clone makes nothing.
    An instance listed and not yet visited fires on the clone too, and its child is a clone.
  - On 16.635 data the row is NotCloned, so the copy is removed in `copyFrom` before any visit (a, by code + test). The
    choice between this and a fresh spawner matters on 16.402 data only.
  - The other reading is a fresh spawner from the row. With it, every clone made within 500 ms of a hit would make one
    1-hp evolved Skeleton clone, even under the Clone buff, because a timer of 0 fires at a spawn rate of 0. That
    reading is just as untested (b). Supercell making only this row NotCloned in 16.635 fits either reading.
- **Red/green (a):** two new BattleSkeletonsEvoTest cases: a spent copy listed with no child, and the NotCloned copy
  removed. Before the fix, 2/6 failed on both versions with the refusal. After, 6/6 pass on both.
- **Core tests (a):** 16.402.22 2184/0 (29 skipped); 16.635.3 2184/0 (6 skipped). The base was 2182 on each.
- **SME dev set (a):** h11b's command (sme11, inputs_v29, a10G1 flags, WORKERS 48) on pod 32657 with `lib_cfclone`
  (bec5811a + CF-CLONE + TickProbe 0001/0002), run `cf1`, scored against h11b:
  - **109/109 -> 109/109, 0 regressions**; exact frames 250,797 / 278,872, the same as h11b;
  - plant suite 65,874 plants, 0 missed;
  - `results.jsonl` byte-identical to h11b (sha256 `1e7e893fd09858ef`).
  - The control build of the same worktree without the commit gives core jar `3db370f4fa878c03`, which is
    `lib_f635c`'s. So the libs differ only by this change.
- **HF re-drive fault sample (a):** D1-C `faults.sh --limit 20000` with `CRFORGE_LIB=lib_fix`, compared to f20k on 30408:
  - summary identical (8 / 19,995 faults; 5 Mirror, 3 engine);
  - 20,000 / 20,000 replays identical on the keys both runs write. The pod's faults.py now also writes crowns,
    hf_crowns and tower_hp.
  - So the HF sample never reached this refusal.
- **Clone sweep (a, `CloneProbe`, both table versions):**
  - Set-up: 335 forms (every census card plus its _EV1 / _hero row where the tables hold one) x a Clone at
    T = 30..600 step 10, plus a second Clone 30 ticks later. That is 19,430 scenes per version. No ability presses:
    outside a match each press is refused, which ended 25 forms' scenes before the Clone in the first run.
  - "cloned carrying ... / spawner's copy" refusals: **Skeletons_EV1 only, 4 scenes per version; 0 after the fix.**
    In 1 of those 4 scenes (T=60) a clone made a child on 16.402. The same scene on 16.635, where the copy is
    removed, has 0, so the child came from a copy not yet fired.
  - Other Clone refusals in census forms are other mechanisms. None is a spawner-buff copy, and none is modelled here:
    - "cloned with a deploy countdown and carries riders": GoblinGiant (+EV1, hero), RamRider (+hero), IceWizard_hero;
      only at T=30, a Clone landing during the deploy;
    - "cloned with a deploy countdown and its clone's row spawns an area object or a push as it deploys": MegaKnight
      (+EV1, hero); T=30 only;
    - "moves apart from its clone without its movement component": GoblinDemolisher (+hero), T=120-170. The HF fault
      `6f7a74b7` ("c82_0_clone0 moves apart ...") is probably this one (b, the card was not checked).
  - The Witch, Night Witch, Tombstone, Goblin Hut, Furnace and Graveyard scenes ran with no Clone refusal. Their
    clones' children were made: 3,097 clone children in total on 16.402.
- **Not done:** the d2t deterministic-CUDA u0001 rollout was not re-run on the new lib (b: the refusal it hit no
  longer exists in the code).

### CF-CLONE-2 (2026-10-28): Clone on a unit still deploying; Clone on the kamikaze Goblin Demolisher
Supersedes the "not modelled here" list above. **Branch `clashbot-cfclone` = `bac75659`** (62558795 + 1 commit;
`patches/0002`).
- **Deploying unit (b, not traced; no live, HF or table evidence):** both deploy-countdown refusals are removed.
  - The tables hold no Clone or deploy column that decides it.
  - The model is crforge's own creator order plus the setter's entry into the deploying state:
    - A carrier's clone (Goblin Giant, Ram, hero Ice Wizard) is set up before its countdown. It never enters the
      deploying state and makes no riders. Each rider's clone takes its rider's countdown and is attached to it.
    - Any other clone enters the deploying state through its setter before its setup. So a Mega Knight's clone pushes
      again from where it stands (SpawnPushback 1000 / radius 1000).
- **Goblin Demolisher (a, cause measured):** the clone is of `GoblinDemolisher_kamikaze_form` (LifeTime 20000).
  - The kamikaze form's lifetime drain step is set from its full maximum when it is made; the clone setter then cuts
    it to 1 of 1. The clone's registration visit drains that 1 point, so it dies (hp 0) before `startCloneMove`.
  - The refusal came from the death switching its movement component off. A unit that its registration visit has
    ended now takes no move apart; a living unit without movement is still refused.
  - (b): the instant death follows crforge's drain step and is not traced for a clone. The building refusal ("whose
    lifetime the hit points' visit counts differently for a clone") hints the game may count a clone's lifetime
    differently.
- **HF fault 6f7a74b7 is this card (a):** the opponent's deck holds Goblin Demolisher and Clone. Event 82 (= facade
  command c82, no skips in that replay) is the opponent's goblin-demolisher at tick 4563; event 89 is the opponent's
  Clone at tick 4811; the fault is at 4830.
  - With CF-CLONE-2 the replay runs all 133 inputs to the end, and crforge's crowns match HF's (1-0).
- **Red/green (a):** BattleCloneTest gets 3 cases: a deploying carrier with its riders (replaces the refusal test), a
  deploying Mega Knight's clone pushing, and the Demolisher clone with no move apart. On the base code 3/37 fail
  with the three refusals on both versions; after the fix 37/37 pass on both.
- **Core tests (a):** 16.402.22 2186/0 (29 skipped); 16.635.3 2186/0 (6 skipped).
- **SME (a):** run `cf2` (h11b's command, `lib_cfclone2` = bac75659 + TickProbe, core jar `71a0b072`) gives 109/109,
  0 regressions, exact frames 250,797 / 278,872, plants 65,874 with 0 missed. `results.jsonl` is byte-identical to
  h11b (`1e7e893fd09858ef`).
- **HF fault sample (a, `lib_fix2`):** faults 8 -> 7 (engine 3 -> 2; the Goblin Demolisher fault is gone). 19,999 /
  20,000 replays are identical on common keys; the one that differs is 6f7a74b7, fault -> ran.
- **Clone sweep, both versions (a):**
  - Scene mode (as before): **0 Clone refusals in 19,430 scenes per version.**
  - What is left are not Clone refusals, and they end their scenes before the Clone:
    - the Mirror alone;
    - Elixir Collector, a building;
    - hero forms whose own actions refuse outside a match: Goblins_hero, MegaMinion_hero, BarbLog_hero;
    - non-forms: Arrows_hero, Graveyard_hero;
    - Giant_EV1, unreleased, 16.635 only.
  - A match mode (`CLONEPROBE_MATCH=1`: a Ladder match, the form dealt into the first hand, the scene 100 ticks later)
    covers the hero forms:
    - Goblins_hero 17, MegaMinion_hero 20 and BarbLog_hero 11 of 58 scenes have a clone, with no refusal.
    - **One new Clone refusal: Fisherman (+EV1, hero), "leaves a pulled state for a clone's setup, not modelled"**
      (`GridStateSetter.exitPulled`). It occurs in 1 of 58 scenes, a Clone at T=150 while his hook drags him. The
      Fisherman is in 5 of the 223 census decks. **Not modelled** (a third mechanism, outside CF-CLONE-2's two items).
    - Caveat: in a match an evolution slot's first play is not evolved, so match mode does not cover evolved forms;
      scene mode does.
    - The 16.402 and 16.635 match-mode outputs are byte-identical. The forms the two versions treat differently
      (Skeletons_EV1, Giant_EV1) are played plain there.

### CF-CLONE-3 (2026-10-28): Clone on a pulled unit (Fisherman); Mirror and evolved forms in the Clone sweep
**Branch `clashbot-cfclone` = `3ebb4115`** (bac75659 + 1 commit, `patches/0003`). Commits 62558795 and bac75659 are not
rewritten; it is meant to be merged (CF-MAIN cherry-picks everything past bac75659).
- **Model (b, no evidence):** `GridStateSetter.exitPulled` no longer refuses a clone's setup. A Clone reaching a pulled unit
  sets it up from its pulled state:
  - the exit runs as for any other state, and the setup's entry empties the route;
  - the unit then follows the hook no more. A hook on a building drags its owner only while he is in his pulled state,
    so it is let go; a pulled troop's hook flies back without it and is let go short of the Fisherman.
  - Evidence searched: our live logs have 3 matches with an opponent Fisherman and Clone. Only 1 has reader frames;
    its one clone (a 1-hp entity) is of another unit. HF holds plays only.
- **Red/green (a):** BattleFishermanTest has 2 new scenes (a dragged Fisherman cloned, a pulled Knight cloned); the old
  refusal test is removed. On the base code 2/31 fail with the refusal on both versions; after the fix 30/30 pass on
  both.
- **Core tests (a):** 16.402.22 2187/0 (29 skipped); 16.635.3 2187/0 (6 skipped). Libs: `lib_fix3` core
  `d0123ab362d9cf14`, `lib_fix3snap` `e0aa99d84517cf31`.
- **Sweep red/green (a):** the old match-mode probe's Fisherman scenes (Fisherman, _EV1, _hero at T=150) are refused
  with lib_fix2 and OK with lib_fix3, on both versions (`results/cfclone3_fisherman_redgreen_probe.txt`).
- **Sweep, 4 modes x 2 versions (a, `results/cfclone3_cp3_summary.txt`):** **0 Clone refusals in all 8 runs.**
  - The modes: scene; match (evolution slot forced to evolve through reflection on `MatchSide.evolutionCounts`, probe
    only); cm = Clone after a Mirror; mc = Mirror of a Clone. In the Mirror modes the cards are put into the first
    hand with `Hand.rearrange`, because the Mirror is never dealt into a first hand.
  - All 43 census-deck evolved forms played evolved in match mode. The 62-63 EV1 forms not played evolved are all
    NotInUse rows (`results/cfclone3_nf*.txt`).
  - What remains is not a Clone refusal:
    - non-form rows (a hero slot holding a card with no hero form);
    - the Mirror played as the first card;
    - the forms refused outside a match (scene mode only);
    - Giant_EV1 on 16.635 (unreleased);
    - in cm, a Clone card refused with match code 4 (OVER, the match already decided) for Balloon / InfernoDragon_EV1
      at late T.

- **SME (a):** run `cf3` (h11b's command, `lib_cfclone3`) gives 109/109, 0 regressions, exact frames
  250,797 / 278,872, plants 65,874 with 0 missed. `results.jsonl` is byte-identical to h11b (`1e7e893fd09858ef`).
- **HF fault sample (a, `lib_fix3`):** 7 faults, the same as CF-CLONE-2; 20,000 / 20,000 replays identical to
  f20k_cfclone2 on common keys.
  - The first attempt hung at shard 36/80 under a pod load of 160: workers idle on futexes. It was stopped by its exact
    PIDs and resumed, and finished the other 44 shards (log `f20k_cfclone3.part1.log`).

#### STATUS (CF-CLONE-3)
- **DONE.** All gates pass. Fork head `3ebb4115` on clashbot-cfclone (pod 30408), to be merged.
- Done: fork commit 3ebb4115; core tests; the sweeps; SME cf3; HF faults.
- Ran (finished):
  - SME `cf3` on pod 32657 (`/workspace/pilot/harden/cf3.sh`, lib `/workspace/pilot/lib_cfclone3`; result
    `sme_live/cf3.cmp.txt`; restart = `bash harden/cf3.sh`).
  - HF faults on pod 30408 (`/workspace/d1c/f20k_cfclone3`, log `f20k_cfclone3.log`; resumable: rerun
    `CRFORGE_LIB=/workspace/cfclone/lib_fix3 bash /workspace/d1c/cb/scratchpad/gauntlet/L74/plan1026/d1c/faults.sh
    /workspace/d1c/f20k_cfclone3 --limit 20000 --workers 48`).
- Next: none for CF-CLONE. Not done: the d2t deterministic-CUDA rollout re-run.

## CF-MAIN (2026-10-28): one branch, clashbot-main; new pin for SME, training held (details: `fork/MAIN.md`)
Labels as above. **Pin: `clashbot-main` = `624eeb45183e1fe981252dd18f99225877595d2b`** (pod 30408 fork
`/workspace/f635/crforge_fork`, worktree `/workspace/cfmain/crforge_fork`) = `bec5811a` + CF-CLONE `62558795`,
CF-CLONE-2 `bac75659`, F1FIX-1 `c99784e4`, F1FIX-2 `89b93932`, CF-CLONE-3 `3ebb4115`, cherry-picked without conflict.
**Determinism hash (Probe, plain and TickProbe libs): 16.402.22 `a0bd88c41f98b46d`, 16.635.3 `575c99887ba28802`,
IDENTICAL on 1 vs 4 threads (a)**, both unchanged. Core jar sha256: plain `d1bba465afef9808`, TickProbe `de16981de9c74277`.
- **Gates (a):** core tests 2188 / 0 on both versions; SME dev (H2's command) 109 / 109, 0 regressions, plants 0 missed,
  results byte-identical to H2; FRESH1 6 / 7, byte-identical to HF2; Clone sweep 0 Clone refusals (scene, match, cm, mc,
  both versions).
- **HF 20k fault sample: FAIL (a).** On the 17,000 replays of 68 / 80 shards (m0 = the same code minus CF-CLONE-3):
  328 faults vs 7 for CF-CLONE-2's run; 319 are F1FIX's Rune Giant enchant reaching paths crforge refuses (an attack
  sequence that launches: Little Prince 117, evolved Angry Barbarian 130, hero Bowler 18, ...; the maker-left walk 23).
  F1FIX-1 made the Rune Giant find friends at all, so these paths are newly reached; SME's 138 + FRESH1 never reach them.
- **So:** SME uses `/workspace/crforge_main/624eeb45/tickprobe/lib` (all four pods). Facade / training / re-drive stay on
  their current libs until the Rune Giant enchant paths are modelled (or a lib without F1FIX is chosen).
- `fork/upstream_sync.sh` now merges upstream onto clashbot-main (pod 30408).

## F1FIX-3 STATUS (2026-10-28, stopped for account switch; NOT finished, gates 1-6 not run on a final head)
Labels: (a) measured, (b) plausible untested, (c) contradicted. Fork branch `clashbot-f1fix3` on pod 30408 (`/workspace/f1fix3/crforge_fork`,
head `ea7f623f` WIP, off clashbot-main `624eeb45`); full diff in `crforge/fork/f1fix3/f1fix3_vs_624eeb45.patch`; tools in `fork/f1fix3/tools/`.
Not pushed to any remote (none set up); `current` link untouched on all pods; no lib switched.
**Code (4 files + test `BattleRuneGiantEnchantTest`, 14 tests green on 16.635.3, 7 of them also on 16.402.22; BattleAbilityTest and BattleThreeMusketeersTest green):**
- Sequence units (Little Prince, Angry Barbarian EV1 / EV1_2, Bowler hero, Elite Archer hero, Musketeer EV1, Archer EV1, Princess EV1): the refusal now holds only for an entry with DoAttackAction / CustomOnAttackAction (Three Musketeers' bayonet, Electro Wizard hero stay refused).
  Little Prince = (a): live 10-22_112113 (5 enchants, 2000/2002 exact, first_div none) and 10-27_204937 (3020/3023 exact) run exact on lib `lib_w1`; control with the added damage zeroed on LittlePrinceProjectile diverges at 866 / 3658 (`ctl_lp2`).
  Others: (b) only, no live frame exists in any log (none of the 28 Rune Giant logs enchants them); support = the game's own multiplier table lists the hero Elite Archer power-shot entry (340) and omits the rest, the unit test shows the 3-hit pattern on all, and the direct-hit (Inferno Dragon, F1FIX-2) and projectile (Archer, LP) paths are each live-held.
- Attached riders (Goblin Giant, GoblinGiant_EV1, Ram): copies left out because every rider row they hit through (SpearGoblinGiantProjectile, RamRiderBola) has multiplier 0 in the shipped row; refused otherwise (test). Live Ram matches 10-23_022345 / 10-23_061811 run exact with a Ram enchanted (only Princess RNG windows, healed), but no Ram add occurred (add log), so (b) for the add.
- Maker left (23 faults): run ends at once (like a cause with no object); refused unless unit hit interval x2 >= FinishIfInstigatorDies (500 ms), so no damage can tell it from the 500 ms countdown. (b). Test green.
- Berserker (3): index set skipped because its 3 entries are identical (checked at run time); live 10-19_225649 not usable (unhealed MergeMaiden divergence from 1709). (b).
- Still refused, unevidenced: Three Musketeers (~9 faults per 17,000), Electro Wizard hero. Expect HF faults ~7 + 9 unless evidence is found.
**Tooling:** `parity/fights.py` flags `SME_CHAMP_OWN=1`, `SME_CHAMP_EXTRA=LittlePrince` (default off) make the extractor emit Little Prince plays and ability presses (it dropped them as children of the 2556 hp guardian); `fork/f1fix3/tools/regen_lo.sh` (live-only extraction); SME inputs `rg_lp3.jsonl` and frames on pod 32657 `/workspace/f1fix3/rg1/`; run: `cd /workspace/pilot/f1fix && WORKERS=4 bash runH.sh NAME /workspace/crforge_cache/tables/16.402.22 /workspace/f1fix3/rg1/rg_lp3.jsonl /workspace/f1fix3/rg1/frames SME_LIB=/workspace/f1fix3/lib_w1/tickprobe/lib`.
**Next (in order):** (1) HF replica for 33920: tar copy 30408 `/workspace/d1c/{hf,cb,pylib,build_new}` -> 33920 `/dev/shm/d1c` (2 MB/s via laptop, was ~40% done, the laptop-side pipe may have died; check `du -sm /dev/shm/d1c` on 33920, else HF dataset VanguardX101/IL_Replay) + `/workspace/cfspeed/pylib`; `ln -s /dev/shm/d1c /workspace/d1c` (33920 disk is 97% full); 30408 has only ~12 GB container headroom (P4 training holds 50 GB), so do NOT run HF there. Then `CRFORGE_LIB=<lib>/plain/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 bash <d1c/cb>/scratchpad/gauntlet/L74/plan1026/d1c/faults.sh OUT --limit 20000 --workers 32`; tally with `fork/main/pod/hf_tally.py`. Plain lib of WIP3 is on 30408 `/workspace/f1fix3/lib_w3/plain` (needs rebuild for `ea7f623f`: `cd /workspace/cfmain && bash build_main.sh ea7f623f... OUT [tp]`). (2) Fix whatever new refusals HF shows. (3) Gates 1-6 via `fork/main/pod/gates30408.sh` (NO_HF=1), `sme_gate.sh` (32657), `clone_sweep.sh` (33920). (4) Squash to one commit with these sources cited, report.
