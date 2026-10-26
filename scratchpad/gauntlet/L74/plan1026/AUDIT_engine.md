# ClashBot simulator fidelity: current state (read-only audit, 2026-10-26)

**Bottom line.** The fork we actually use, fin15, scores 0.920 raw on fight parity (lower CI 0.916) against the owner's 0.975 goal. Whole-match replays are far lower: the same crown sequence comes out in only 0.506 of matches. With the data we have today, **99.9% cannot be measured**. Our live logs have a noise ceiling of about 0.992, we hold no per-tick recordings with a known seed, and fin15 is still on the card table from before the 10-19 balance patch.

All HANDOFF line numbers refer to `git show HEAD:HANDOFF.md` (15,474 lines).

---

## 1. The engines

| | What it is | Measured accuracy | How Python drives it |
|---|---|---|---|
| **RoyaleSim upstream** (`research/ext/Royale/RoyaleSim`, Rust, MIT) | A friend's reimplementation. Our local copy is 0.1.33 (`cacb7005`, 10-12). Upstream is at **0.1.42** (`b21765e5`, 10-22), fetched 10-25. 0.1.40 added the 10-19 card table `client160402017_20261019`. 0.1.37-0.1.42 added about 10 more measured laws (charge-hit timing, Royal Ghost invisibility, dash-immune push, guard birth, press re-routes, tower hold). | **56.7%** of non-tower unit-ticks within 1/4 tile (09-23), on a private set of 73 battles recorded every tick (27 whole battles plus 40 prefixes). Source: `docs/replay-parity.md`. The author refused to share the recordings (HANDOFF L3720-3721). | PyO3 wheel `royalesim`: `Battle(...)`, `reset(...)`, `step(cmds, n)`. The board is 18 SIM units per native millitile (18,000 per tile). |
| **Our fork "fin15"** (worktree `C:/Users/benpe/rsfork_w8`, branch `fin15`) | Upstream 0.1.36 (`04ba4e75`, 10-16) plus **27 commits**: about 23 measured laws, the tower-troop API `set_tower_troops`, one load fix and docs. Head `305aaafc`, wheel sha `88f3fdcb…` (`FIN15.md` L5-14). The laws cover elixir floor, uncapped Tornado pull mean, tiebreak regen, Tesla hide/hold, Earthquake hidden split, Tornado crown order, buff pulses, Evo Knight, Evo Mega Knight uppercut, dash/axe slow, Goblin Machine, sparks. Patch list: `fin15/patches/`, `parity/fin16/patches/`. **fin16** (fin15 plus the 10-19 table) has patches written in commit `406ffd1` but was **never built or scored**. | See section 2. | `ROYALE_RUNTIME=fin15-linux`; `pipeline/royale_runtime.py` checks a frozen manifest. The training env is `pipeline/royale_env.py` (RoyalePoolEnv / RoyaleSelfPlayEnv). The parity harness `fights.py` uses `ROYALE_RUNTIME` or `PARITY_SIM_PATH`. The fork builds on Linux only; the laptop uses the upstream 0.1.36 Windows wheel. |
| **RoyaleGym** (`research/ext/Royale/RoyaleGym`) | Gymnasium / PettingZoo wrappers around RoyaleSim (0.1.23 is paired with 0.1.33). It has no physics of its own. | Not applicable. | Through `pipeline/royale_env.py`. |
| **crforge** (`L74/crforge/EVAL.md`, clone at `C:\Users\benpe\crforge_eval`) | Java 17. One author, 1,117 commits, evaluated at commit `ad8ef3a`. It reads Supercell's own `csv_logic`/`csv_client` tables directly (versions 16.402.18 / .19 / .21 / .22) and refuses anything it does not model. It covers 122 ladder cards, 43 evolutions, 18 heroes, 8 champions and 4 tower troops. | Its CI claims **10,000 / 10,000** battles tick-exact on 16.402.21 and on .22. Every tick is compared with zero tolerance: RNG, every entity, HP, elixir, hand (EVAL L19-21). The data is private and nobody can reproduce it. Our spot probes all matched live (EVAL L103-116), including two that RoyaleSim 0.1.35 got wrong: Tornado crown damage 25/36/40 vs 26/37/41, and Earthquake on a hidden Tesla 286/458 vs 0. **It has never been run on our harness.** | Its own `crforge-env` package (JPype, VectorEnv, 7,024 int32 observations and 2,307 actions per seat). **Not integrated** (there is no `pipeline/crforge_env.py`). Estimated cost: 4-7 days for a pilot, 15-30 days for a full switch (EVAL L144-156). It runs at 0.45x RoyaleSim's speed on the loaded laptop. |
| **Native sandbox** (`research/ext/cr-native-sandbox`) | The real game logic (`libg`), run headless in an emulator. It is the **old build 15.535.29** (runtime 150535029). | It was used to replay the pro corpus (section 3). | `native_core` worker. |

The owner's v8 oracle ruling is in memory `exact-simulator-priority.md`. v8 means running the live 160402012 build. The project notes say: the 10-13 run hit a startup crash (HANDOFF L3804-3818); 10-16 says "v8 line stays declined" (L2696); the oracle VM's status has been unknown since then (L1986). I did not look into it further.

## 2. How fidelity is measured today

**Metric definitions** (`parity/metrics/METRICS.md` L92-216, `CEILING.md`):

- **J1, fight parity.** For each play, the SIM is rebuilt from the live frame just before it and every live deployment in the next 12 s is replayed. The fight agrees when deaths match in order within 10 ticks (10% slack for swarms) and tower damage is within max(100 hp, 10%).
  - **Raw** = live vs SIM.
  - **Ceiling** = SIM vs 8 SIM runs with the unseen state redrawn (attack phase, ambiguous target, Tesla state, shield, deploy tick).
  - **Normalised** = raw / ceiling.
  - "Stamped" means the match has the reader-3b creation tick of every body; "strict" means the fight passes `fights.is_clean`.
- **J2** spell effect: the body ends within 0.5 tile.
- **J3** king activation: trigger within ±10 ticks.
- **J4** own elixir within 0.1 on every frame, open loop.
- **J5a** deploy time within 3 ticks; **J5b** card cycle order.
- **J6** river crossing: same lane, within 10 ticks.
- **J7** whole-match open-loop replay: tower HP per minute, crown sequence, result, king wake.
- **J8** match end: winner, and tiebreak end tick within 5.
- **Static check:** SIM table vs the device tables and live hp.
- **Goals:**
  - Fight parity (`fight-parity-goal.md`): raw lower CI ≥ 0.975 overall and ≥ 0.95 per card (n ≥ 30), tier-B coverage ≥ 90%, at least 100 stamped matches.
  - Owner 10-19: ≥ 95% on **every** metric, for all cards.
  - `exact-simulator-priority.md`: ≥ 99% of 1,000 full matches tick-identical, with 100% identical results.

**Latest numbers** (fin15 `305aaafc`, harness from 10-22; `FIN15.md` §6 L241-261 and §9.1 L495-502):

| Metric | Value [95% CI] | Notes |
|---|---|---|
| **J1, all graded matches (latest)** | **0.920 [0.916, 0.923]** | 43,867 fights / 1,152 matches; ceiling 0.993 |
| J1, older cohort c13 (to 10-18) | 0.927 [0.921, 0.933] | |
| J1, newer cohort c22 (10-18 to 10-21) | 0.917 [0.912, 0.921] | |
| Tier-B coverage | 0.160 (c13 alone 0.237) | Goal 0.90 |
| J2 spell effect | 0.917 [0.909, 0.925] | Strict-clean fights 0.951 |
| J2 Tornado | 0.880 [0.855, 0.902] | |
| J3 king activation | 0.947 [0.939, 0.955] | The wake law itself is exact: 1107 / 1107 |
| **J4 elixir** | **0.991 [0.986, 0.994]** | Meets goal; 3x phase 0.961 [0.937, 0.979] |
| J5a deploy / J5b cycle | 0.989 / 0.996 | |
| J6 river crossing | 0.718 [0.697, 0.737] | Pathing alone 0.838 |
| **J7 crown sequence** | **0.506** | Ceiling 0.834, normalised 0.61. Result 0.518, falls in time 0.476, trajectory 0.898 (normalised 0.93) |
| J8 winner | 102 / 102 regulation, 17 / 18 tiebreak | Tiebreak end tick 15 / 18 |
| Static: device vs SIM | 524 / 526 records | |
| Static: live hp at observed level | 768 / 791 triples | 0 confirmed mismatches |

- **History.** The "0.941" figure is **normalised**, on the old 145-match cohort (raw 0.900; HANDOFF L1964-1985). crforge's EVAL proposes rescoring "the 145 captured matches", but that cohort is out of date.
- **Per card, J1 own.** These are FIN13 numbers (HANDOFF L740-743), except Skeletons on c22, which comes from W19:

  | Card | J1 |
  |---|---|
  | Tornado | 0.978 (meets) |
  | Log | 0.971 (meets) |
  | X-Bow | 0.968 (meets) |
  | Hero Ice Wizard | 0.940 |
  | Rocket | 0.940 |
  | Knight | 0.939 |
  | Tesla | 0.930 |
  | Knight evo | 0.911 |
  | Tesla evo | 0.911 |
  | Skeletons | 0.874; 0.838 on c22 |

  Level-16 Ranked era: own Skeletons 0.803 / 0.750, opponent Skeletons 0.764 (FIN15.md L532-537).
- **Worst opponent cards** (FIN5): Skeleton Army 0.650, Bats 0.747 (later 0.812), Hog Rider 0.815, Dart Goblin 0.818, Witch 0.847.
- **Rare cards:** Goblin Drill evo 0.04, Zap evo 0.61, Little Prince 0.62, Minion Giant 0.68. Hero Electro Wizard and Spirit Empress cannot be scored at all.
- **Why J1 is stuck** (FIN15.md §9.2-9.5, L506-592):
  - 943 of 1,030 failures have none of the 8 perturbed SIM runs agreeing with live, so they are systematic, not noise.
  - Hits: 972,567 equal vs 14,108 different, so damage values are right.
  - No single mechanism explains more than about 13% of failures. Each fix round has moved J1 by +0.0002 to +0.002.
  - About **32% of failures are still unexplained** (c13 329 / 1,030; c22 797 / 2,456).

## 3. The data we have

- **Live logs** (`L68/live_reader/live_play_*.jsonl`): **5,495 files, 34 GB**, including stub files from 9-25 to 10-26.
  - Memory note (10-13): 1,364 main-account + 554 second-account usable matches since 10-05.
  - Census: 2,054 matches since 10-07; 1,207 frame-logged and 1,102 extended logs (10-15 to 10-20).
  - Each frame (every **2 ticks**, about 10 Hz, 96.8% of gaps) records:
    - bodies `[side, x, y, card, hp, max_hp, kind, address]`;
    - per-body state (idle, moving, engaged, deploying, jump, tunnel, hero cast…), projectiles with source and target, effects;
    - **own elixir only** (exact to 1e-4); the tick;
    - phase-2 data: buffs and own hero ability.
  - Events: decision, play, confirmed (spawn point, latency), end.
- **Phase-3 captures** (`icebow/data/p3_captures/`): **2,014 substantive captures, 39 GB**. Of these, 1,783 have the reader-3b creation ticks (since 10-17 11:17), 1,109 are after the 10-19 patch, and **598 since 10-21 16:13 have not been scored yet**.
  - Each frame (`mumu_live_frame` v2, also every 2 ticks) adds: attack target and previous target, attack progress and load timer, deploy timer, shield, life-drain carry, spawner timers and wave index.
  - **No per-tick capture exists.** About 1.1% of bodies live for less than one frame gap (`READER_PHASE3C.md`).
  - There is **no RNG seed**, and the opponent's hand and elixir are never read (owner rule).
  - Graded so far: c13 = 638 logs, c22 = 786.
- **Pro replays.** The training dataset (`gen_dataset_v32_fv5.json`) uses 14,661 replays from 6 corpora (`scratchpad/gauntlet/ext/corpus_gen_pilot/s0-s3_public_v1`, `corpus_v6/{icebow,hogeq}_public_v1`). There are 44,454 `replay_*.json` files in all variants. Aggregate counts: 14,818 replays, 1.08M plays driven.
  - Each replay is a **RoyaleAPI play sequence re-run on the old native build 15.535.29**, at level 11, seed 424242, with a guessed card deal.
  - Frames are recorded **every 10 ticks** (entities, towers, projectiles, effects, both sides' elixir), plus a frame at each play.
  - **It is not real game state.** The re-run gives the real match's crowns in only **74.7%** of replays (11,066 / 14,818); 98.8% of plays are accepted.
- **RoyaleAPI crawls** (`ext/crawl_hf_icebow`, `crawl_hf_hogeq`): play sequences only (tag, tick, x/y, card, side, ability flag). 252,238 replays were scanned, keeping 766 icebow and 523 hogeq. More crawl tooling is in `L74/crapi` and `L74/crawl`.
- **Game files.**
  - Live client: APK build 160402012. Content 16.402.21, then 16.402.22 from 10-19 06:00 EDT. The table change was 13 values, with no code change (`patch1019/PATCH1019.md`).
  - Device table pulls: `L74/apktables/out/device_update_20261012` (693 files, 73 tables; the other 351 fall back to the APK) and `device_update_20261022T160606Z_688171` (16.402.22). They are decoded by `apktables/check_build.py`.
  - RoyaleSim tables: `data/derived/` holds `cards-15.535`, `cards-160402017-20261006` (the table training and parity use), arena and globals.
  - crforge's copy of the official tables: `crforge_eval/cache/tables/16.402.18 / .19 / .21 / .22`.
  - Notes on decompiled logic exist (the "redump Ghidra" mention in memory, `ext/cr_sandbox_internals.md`, the private `gameapp_re/`). I only noted that they exist.

## 4. Gaps, with measured size

Sources: `FIN15.md` §8.2 and §9, `METRICS.md` §5.

- **Balance patch 10-19:** the fork is still on the 10-06 table. Parity fell from 0.926 to 0.913 at the change.
  - Skeleton SummonRadius changed 400 → 500. Placing own Skeleton members at their live points would gain +0.507 pp on c22.
  - Also stale: Dart Goblin, Cannon Cart (including mass), Minion Giant, Rune Giant, Hero Electro Wizard, Electro Dragon, Flying Machine, Void, Skeleton Barrel and its evo, and the Evo Electro Giant NoClones rule.
- **Targeting:** the SIM makes the same retarget only 84.6% of the time (Firecracker 61%, Goblin Cage 25%). X-Bow first target: tower live vs unit in the SIM in 77 / 807 cases.
- **Pathing:** J6 0.718. Worst special movers: Goblin Drill 0.00, Barbarian Hut 0.45, Mega Knight 0.50, Golden Knight 0.55, Tombstone skeletons 0.27.
- **Collision:** Tornado pull in packs is fixed (Royal Hogs 0.32 → 0.72). Still open:
  - Evo Royal Hogs 0.41;
  - Golden Knight 0.67;
  - Skeleton Warriors 0.62;
  - a suspicion, never tested, that RoyaleSim's 18,000 units/tile cannot match the game's rounding.
- **Spells:**
  - Log on packs: Royal Hogs 0.67, Barbarians 0.88.
  - Tornado-to-king in the same situation: 0.81-0.85, measured on the upstream wheel only.
  - Opponent spells seen late or not at all explain 58 failures in c13 and 122 in c22.
  - Clone copies deploy 0 / 60.
- **King activation:** the wake law is exact. Damage-triggered wakes after our Tornado agree only 0.641.
- **Elixir:** the 3x phase is at 0.961. There are 245 elixir drops with no matching play.
- **Spawned bodies:** many timing or presence offsets: Elixir Golem 436, Witch 254, Goblin Barrel 461 live-only and 306 SIM-only, Skeleton King souls 190 live-only, Clone 148 SIM-only.
- **Evolutions:**
  - The Evo Goblin Drill relocation is not implemented.
  - Evo Knight fortify: live 48 vs SIM 122.
  - Knight evo and Tesla evo are both at 0.911.
- **Heroes:** Hero Electro Wizard is refused by the fork. Hero Ice Wizard's ice cube matches the device rules; its J1 is 0.940.
- **Champions:** presses are never replayed for Golden Knight (1,143 fights), Boss Bandit (567), Archer Queen (376) and Goblinstein (297). Replayed: Skeleton King 0.875, Monk 0.924, Mighty Miner 0.996.
- **Tower troops:** in the fork and the harness, but SIM opponents never field them. crforge's env is Princess-only.
- **Level scaling:** correct on the static checks. Level 17 (Mirror, Hero Tombstone) is unmapped. The opponent princess tower is sometimes read one level high.
- **Start-state and early divergences:** H10 + H11 cover about 36% of failures, mostly limited by what the reader can see.

## 5. What it would take to measure 99.9%

- **Sample size:**
  - Zero failures in about **3,000** independent items gives a 95% bound of 99.9% (rule of three).
  - If the true rate is 99.95%, you need about **7,700** items for the lower CI to clear 0.999, before adjusting for fights clustering within matches.
  - Per card (tier B is 55 cards) that is at least 3,000 items each, about 165k in total. Most cards today have 200-1,000 graded plays.
- **The live-log fight metric cannot get there.** Its ceiling is 0.992-0.993, so a perfect engine would also score about 0.99. To raise the ceiling to ≥ 0.9995 the reader would need per-tick capture (about 38 MB per match; the C: drive is 98% full), the RNG seed and every opponent cast. Full-match J7 is capped even lower, at 0.834.
- **What a 99.9% claim actually needs** is seeded truth recorded every tick, on build 16.402.22, for about 3,000 or more full matches, compared field by field with zero tolerance (the crforge / upstream method). We have **none** of that. The candidates are crforge's private 10k (needs the author's access), the upstream 73 (refused), or a native oracle on the live build (status above).
- **Cheaper first step (EVAL L11-14):** use crforge as a differential reference through the existing DIFFSIM harness (`L74/diffsim`, already self-checked 1000/1000). Separately, rescore the 1,152 matches plus the 598 unscored captures on crforge and on fin16. That gives a relative ranking of the engines on one scale, but it does not prove 99.9%.
