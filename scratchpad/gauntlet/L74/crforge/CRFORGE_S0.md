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
