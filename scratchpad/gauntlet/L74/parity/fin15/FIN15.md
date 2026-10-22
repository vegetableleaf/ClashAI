# fin15: engine parity fixes on the RoyaleSim fork (W8, 2026-10-20)

Every number carries its label: **(a) measured** (with n), **(b) plausible but untested**, **(c) contradicted**.
Cohort for every before/after: the 638 caplogs13 logs (the FIN13 / METRICS_J cohort), on pod P2 (64.247.206.80:40548).
"Before" = fork fin14c (clashbot36 427597d3, tree 7ff40f45, METRICS_J on 19899 and its P2 rebuild).

## 0. Deliverable

- **Wheel `fin15`**: `royalesim-0.1.36-cp310-abi3-manylinux_2_34_x86_64.whl`, sha256
  **88f3fdcbebabe3e81d64954b48861ccabe03457b2d92fd5e34eb2f56a607f5ab**.
  - The fork commit compiled into it: 305aaafceb7b28bf5108c9fe028fafae97d32676, clean.
  - The first candidate earlier on 10-20 (a144f8fe..., pin c6887a69, 2 laws) is superseded: it is the same fork without
    TIEBREAK_REGEN.
  - Copies: the laptop's `/tmp/claude/parity1016/fin15/` and P2's `/workspace/w8/wheels/rsfork_fin15/`.
- **Landed laws** (fin14c + 3):
  1. `match.MANA_REGEN_STEP = client16402_floor_10000` (elixir per tick floored in 1/10000).
  2. `collision.ATTRACT_CONTACT_MEAN = client16402_in_mean_uncapped` (a Tornado pull in a contact mean is not capped at 150).
  3. `match.TIEBREAK_REGEN = client16402_stops_after_end` (the elixir bar stops after the step into t6003 under the drain).
- **Install on a training pod** (the setup_fin13.sh pattern; `ROYALE_RUNTIME=fin15-linux`, venv `/workspace/venvf15`):

```bash
# laptop -> pod: the wheel, and a code tree at the W8 commit (royale_runtime.py knows fin15-linux; parity/fin15/ has the manifest)
scp /tmp/claude/parity1016/fin15/royalesim-*.whl <pod>:/workspace/in/fin15/
# pod (CB = that code tree):
FIN15_SHA=88f3fdcbebabe3e81d64954b48861ccabe03457b2d92fd5e34eb2f56a607f5ab FIN15_PIN=305aaafceb7b28bf5108c9fe028fafae97d32676 \
  CB=/workspace/<code tree> bash $CB/scratchpad/gauntlet/L74/parity/fin15/setup_fin15.sh   # -> /workspace/stepd/fin15/FIN15_OK
# train / eval on it: /workspace/venvf15/bin/python + ROYALE_RUNTIME=fin15-linux where stepd_chain.sh (and the other launchers)
# say /workspace/venvf13 + fin13-linux
```

- **The smoke** (smoke_fin15.py) checks three things:
  - `activate()` passes against the frozen manifest (provenance 305aaafc clean, embedded card table, tower-troop API);
  - the Hero IW adapter is on;
  - the elixir unit is 10000, and a 600-tick battle runs.
- **Verification (fin15 READY checklist, all on P2 = 64.247.206.80:40548):**
  - the cargo gate passes and each plant is red (section 7);
  - J1 FIN15 + the J-suite METRICS_J15 ran on the 638-log cohort (section 6), plus the 10-20 battles;
  - `setup_fin15.sh` (FREEZE, then the plain second-pod path) ended in FIN15_OK: activate() pins 305aaafc clean with the embedded
    table, the Hero IW adapter is on, the unit is 10000 and a 600-tick battle ran; venvf36 is intact;
  - a real `python -m pipeline.rl_royale --smoke` on stepd_l16_s74.yaml under ROYALE_RUNTIME=fin15-linux with /workspace/venvf15 on the FINAL wheel: **SMOKE PASS** (u0000 W/L/D 3/5/0, the round trip identical, the resume check all True).
  - The manifest `build_manifest_fin15.json` (30 files) is frozen from P2's venvf15 and committed here.
- **Trap**: on a pod that has the wheel's BUILD checkout (P2: `/workspace/w8/src_rsfork_fin15`), the wheel reads that checkout's
  data and `activate()` refuses it. setup_fin15.sh checks for this.

## 1. Per-fix table

| # | fix | kind | mechanism (label) | patch | gate | targeted metric before -> after | J1 |
|---|---|---|---|---|---|---|---|
| 1 | elixir truncation | S, LANDED | the regen accrues whole 1/10000 a tick (178 / 357 / 537); the fork used the exact rational (a) | `match.MANA_REGEN_STEP` (4167f972) | green, plant red | J4 open loop on the final harness 0.878 -> **0.990**; on the cap-dated harness 0.812 -> 0.912 (cap-dated harness; 0.840 -> 0.909 on W1's harness); 1x 0.897 -> 0.938, 2x 0.685 -> 0.895, ot2x 0.714 -> 0.871, 3x 0.683 -> 0.787 | section 6 |
| 1b | J4 harness | H, LANDED | a spend from a full bar was dated at the frame (a); unmatched / double-matched drops; the Elixir Golem's pay-outs not credited (a) | H-J4-CAPDATE, H-J4-DROPCOST, H-J4-GAIN (replay_metrics.py) | selftest OK | J4 0.912 -> **0.990 [0.985, 0.993]**: GOAL MET (3x phase 0.937) | - |
| 2 | tower damage drift | DIAGNOSED, no patch | not one law: 14 / 39 hit-phase offsets, 23 / 39 downstream of unit divergences, 2 / 39 from units outside the tower window (a); "one engine law" (c) | - | - | J7 unchanged by design; it moved only through fix 3 (section 6) | - |
| 3 | Tornado on packs | S, LANDED | in-mean pull capped at 150: packs of fast units under-pulled (a) | `collision.ATTRACT_CONTACT_MEAN = client16402_in_mean_uncapped` (c6887a69) | green, plant red | J2 Tornado 0.821 -> **0.880**; mass 1 0.59 -> 0.75, mass 2 0.66 -> 0.81, mass 4 0.82 -> 0.88; Royal Hogs 0.32 -> 0.72; Hog Rider 0.81 -> 0.93 | section 6 |
| 4a | tiebreak drain timing | H, LANDED (harness) | 2 of 5 misses were sudden-death matches labelled tiebreak (a); the drain law fits within 2-3 ticks | H-J8-CLASS (replay_metrics.py) | selftest OK | J8 tiebreak end tick 15 / 20 -> 15 / 18 | - |
| 4b | Clone copy deploy | not patched | the SIM holds copies for the same 10 ticks; J5a compares a flag (b) | - | - | - | - |
| 4c | river crossing / lane | DIAGNOSED (round 2), no engine law | of 30 failing own crossings, 24 are in fights J1 flags unclean (missing in-flight Graveyard / Goblin Barrel spawns, fight outcomes); 0 crossing law (a) | - | - | J6 0.692 -> 0.694; strict-clean 0.838 | - |
| 4d | elixir past overtime's end | S, LANDED (round 3) | under the drain the live bar stops after the step into t6003; the SIM regenerated on, up to 6.9 elixir above (a, 3 of 3 matches) | `match.TIEBREAK_REGEN = client16402_stops_after_end` (305aaafc) | green (1966 / 0 / 3), plant red | J4 3x phase 0.937 -> **0.961 [0.937, 0.979]**; J4 0.990 -> 0.991 [0.986, 0.994] | none by construction (no play after t6000) |
| 5 | Goblin Drill play point | H, LANDED (round 3) | the dig and the building it leaves are two bodies; the harness replayed the drill at the tap (own: the game moves 49 of 93 corner taps one tile) or at the dig's first-seen point near the opponent's king (opponent drills) (a) | H-DRILL-SURFACE (fights.py `drill_surface`; PARITY_DRILL_TAP=1 restores) | parity selftest OK | J1 stamped 0.9271 -> **0.9289** (+24 / -0), full 0.9226 -> 0.9242 (+35 / -0); opp Goblin Drill 0.00 -> 0.84; 10-20: own drill 0.34 -> 0.61, opp 0.00 -> 0.74 | J1 up |

## 2. Fix 1: elixir regen truncation (LANDED, `match.MANA_REGEN_STEP = client16402_floor_10000`)

**Mechanism (a).**
- The game keeps elixir in 1/10000 units and adds floor(TICK_MS x 10 x 10000 / regen_ms) a tick: 178 / 357 / 537 at 1x / 2x / 3x.
  - The ledger's own reading (truth.elixir_raw of the replay corpus): 178 on 59,276 of 59,318 rising 1x pairs, 357 on 6,278 of
    6,283 2x pairs, 537 on 255 of 255 3x pairs.
  - The live reader agrees: 0.0178 / 0.0357 / 0.0537 a tick (METRICS.md J4).
- The fork made one elixir lcm(28000, 14000) = 28000 units and added 500 / 1000 a tick: 178.571 / 357.143 of the game's unit, so
  it ran 0.32 % fast at 1x (0.04 % at 2x); the 3x step was 1505 of 28000 = 537.5 (0.09 % fast).
- The 2x / 3x switch ticks are already right (a): the live switch fits the step into t2401 on 53 of 54 logs
  (analysis/x2.py); the SIM probe (probe_2x.py) steps 178 into t2400, 357 from t2401, 537 from t4801.

**Patch** (fork commit 1, `4167f972` on branch fin15): a new ledger key with the old arm `exact_lcm` kept; the shipped arm makes the
unit 10000 and floors every step (state.rs `BattleState::new`). Snapshots carry their own unit and steps; format-3 migration
inserts the old arm. Test `tests/mana_regen_step.rs` (1x steps 178, 2x 357, 6 -> 10 fills on tick 225 vs 224) + plant
`mana_regen_exact` (red: 1 passed 1 failed). `state::tests::mana_is_exact_over_a_full_bar` now pins both arms.
Hash continuity was re-recorded at the change (both tables): the elixir unit is part of the hashed state, so every battle's hash
moves from tick 0; no card plays differently.

**A harness bug found on the way (H-J4-CAPDATE, fixed in `metrics/replay_metrics.py`).** J4 deducted a live spend at the frame
tick. A spend from a FULL bar lands between frames, and the live bar regenerates from the spend tick, so the SIM lost (tb - td)
steps on every such spend: 0.018-0.036 at 1x, 0.071 at 2x, 0.107 at 3x (20261017_114921 t2843: live 4.0714, SIM 4.0000; the
error then stays for the rest of the 2x phase). The fix dates the spend td = tb - (eb - (10 - cost)) / step inside (ta, tb] when
the bar was full at ta. `--no-cap-date` reproduces the old harness.

**J4 before / after, 634 matches, all frames (a):**

| engine \ harness | old (W1) | H-J4-CAPDATE | round 2: + H-J4-DROPCOST + H-J4-GAIN |
|---|---|---|---|
| fin14c (exact rate) | 0.840 [0.820, 0.858] | 0.812 [0.791, 0.830] | 0.878 [0.863, 0.892] |
| fin15 floor | 0.909 [0.891, 0.926] | 0.912 [0.894, 0.928] | **0.990 [0.985, 0.993]** |

| phase (cap-dated) | fin14c | fin15 | perfect matches, clean* fin14c -> fin15 |
|---|---|---|---|
| 1x | 0.897 | 0.938 | 330 -> 532 of 583 |
| 2x | 0.685 | 0.895 | 326 -> 511 of 565 |
| overtime 2x | 0.714 | 0.871 | 350 -> 478 of 529 |
| 3x | 0.683 | 0.787 | 40 -> 64 of 113 |

\* clean = no unmatched live drop (583 of 634 matches). On those the floor law gives 0.936 of frames (0.831 before); the 51
matches with an unmatched drop score 0.642 (b: an unmatched drop is never deducted in the open loop, so the SIM stays high until
the cap; what those drops are is untested). The old harness's lost regen at each spend from a full bar partly cancelled the
exact rate's +0.32 %, which is why fin14c reads lower on the fixed harness.

**Round 2 harness (a).** Two more fixes, made after checking the worst matches:
- H-J4-DROPCOST: every live drop is deducted by its own size rounded to whole elixir. Costs are whole and the regen inside a frame
  gap is <= 0.11, so the rounding is exact. Before:
  - drops with no confirmed play were never deducted (an 'unconfirmed' tap the game took; a Hero IW press with no event);
  - two drops beside one play were both charged its cost (20261017_021702 t4812).
- H-J4-GAIN: live rises beyond the regen are credited in 0.5 steps. The opponent's Elixir Golem pays us 1 / 0.5 / 0.5 per golem,
  golemite and blob: 20261016_213647 rose +4 over t328-t514, and the open loop had no units to pay it.
- Result: the worst match went from 0.05 to |d| <= 0.16. The engine law's own share on the final harness is
  0.878 -> 0.990 (fin14c vs fin15).
- `--no-drop-cost` / `--no-gain` restore the older harness.

**J1 effect:** none expected: the fight harness tops elixir up at setup (fights.py). Measured in the FIN15 re-score (section 6).

## 3. Fix 2: tower damage drift within one push (DIAGNOSED: no single engine law; not patched)

**Question.** J7 (METRICS.md): the first tower to diverge in an open-loop whole-match replay is already 482-1,206 hp off. Is
that one engine law (a tower-damage law) we can patch?

**Census of every first divergence (a)** (fin14c METRICS_J: 500 of the 573 J7 matches diverge; analysis/j7div_fin14c.txt):
- The first divergence comes at a median of tick 1,754 (quartiles 968 / 2,715). It is on our towers in 355 matches and on
  theirs in 145.
- Their towers: the SIM dealt MORE damage in 115 of the 145. The difference comes in fixed sizes:
  - -490 in 58 matches and +490 in 17. 490 is 5 bolts of our level-16 X-Bow (floor(24 x 409 / 100) = 98 each).
  - -546 in 19. 546 is one level-16 Rocket crown hit (2,372 x 23 %).
  - -646 in 19. 646 is the two together.
  - The J7 tolerance on a 4,858-hp tower is 486 hp, so ONE volley or ONE Rocket landing at a different time crosses it.
- Our towers: no dominant size (-507 x 17, -520 x 8, ...). These are opponent troop hits.

**Mechanism per match (a).** j7diag.py on 40 sampled failing matches, 39 usable (K = 0; every frame from 300 ticks before to
120 ticks after the first divergence; bodies within 9 tiles of the tower; analysis/j7sum_39.txt):
- **14 / 39 are a hit-phase offset.** The two tower series agree again within 60 ticks: the same damage, a few ticks apart.
  Examples: 20261017_000559 (a Royal Giant hit for 490 one swing earlier in the SIM), 20261018_084025 (X-Bow volleys).
- **23 / 39 follow an earlier UNIT divergence near the tower.** A body's hp or presence already differs before the tower does:
  - 20261017_000559's Royal Giant had 899 hp in the SIM against 1,889 live;
  - a Tesla 425 vs 858; a Mega Knight 1,206 vs 532;
  - a Hog Rider or Witch present only in the SIM.
  This is J1's fight term compounding in the open loop.
- **2 / 39 show only the tower changing inside the 9-tile window.** Both trace to a unit outside it:
  - 20261017_175947: our X-Bow kept shooting in the SIM after the live one died at t1273. It took less damage from a Blowdart
    Goblin in the SIM.
  - 20261017_185911: a Cannon Cart present only in the SIM shot our tower from range.
- **No tower-damage law was found.** The claim that J7 is one engine law is (c) contradicted on this sample. Tower hits, X-Bow
  bolts and Rocket crown hits have the table's values on both sides. What differs is WHEN a unit hits and WHICH units are alive.
  Nothing was patched for J7.

**What would move J7 (b, untested):**
- the J1 unit-fight laws (the gap map);
- a time-tolerant J7 trajectory (the best match within +-20 ticks). It would stop scoring the 14 / 39 hit-phase offsets as
  divergences.
- The Tornado law below raised one part of J7's king-wake term: J3 damage triggers after our Tornado, 0.569 -> 0.641.

## 4. Fix 3: Tornado on light units

**Mechanism (a).**
- **What METRICS_J shows** (fork fin14c, J2 Tornado by victim; analysis/torn_fin14c.txt; "live pull x" = live pull / SIM pull on
  bodies starting >= 3 tiles out):

  | victim | agree (n) | live pull x |
  |---|---|---|
  | Royal Hogs | 0.32 (47) | 1.41 |
  | Evo Royal Hogs | 0.28 (32) | 2.0 |
  | Goblin Gang | 0.76 | 1.07 |
  | Minion Horde | 0.71 | 1.06 |
  | Hog Rider (alone; same Speed 120) | 0.81 | 1.00 |

  So **packs** were under-pulled, not light or fast units as such.
- **The engine law** (collision.ATTRACT_CONTACT_MEAN = client15535_in_mean):
  - A pulled unit WITH a contact takes the pull as one entry of its contact mean, and the mean is capped at 150 (move16402
    `collision_mean`).
  - The ledger left open whether that cap applies to a mean holding a pull ("never reached in the corpus"; 16.402 unread).
  - A Speed-120 unit's Tornado pull is 432 a tick. In a pack the mean always hits the cap, so the step toward the centre is 150
    minus the walk: about 30.
- **Live** (j2diag.py, 9 Tornado casts on Royal Hogs, 36 hogs; analysis/royalhogs_steps.txt):
  - Hogs in contact close on the centre at 80-150 a tick. A lone hog moves ~310 (432 minus its walk).
  - The engine's hogs move 25-65. Example: 20261017_040555 t1304-t1320, live 115-143 against SIM 30.
  - That fits an uncapped mean ((432 + push) / 2 - walk, about 100) and not the capped one.

**Patch** (fork commit 2, `c6887a69`):
- A third arm, `client16402_in_mean_uncapped`, is shipped. It takes the same mean, but a mean holding a pull is not cut to 150
  (state.rs `cap_back`).
- The old arms are kept. CLIENT15535_ARMS keeps client15535_in_mean for 15.535.29 captures.
- Test `tests/attract_mean_uncapped.rs`: Hog Riders in contact under a Tornado; the uncapped step goes further toward the centre.
  Plant `attract_mean_capped` turns it red.
- Hash continuity is unchanged: no scripted battle holds a pull.

**A/B (a).** law_ab.sh: the same fin15b wheel for both arms, arm B set with PARITY_OVERRIDES, K = 0, all 638 logs. Arm A
reproduces METRICS_J's J2 exactly.

| metric | A (capped) | B (uncapped) |
|---|---|---|
| J2 Tornado (1,540 bodies) | 0.821 [0.792, 0.850] | **0.880 [0.855, 0.902]**; median error 78 -> 19 mt |
| J2 all spells (8,540) | 0.904 [0.894, 0.914] | 0.914 [0.906, 0.923] |
| Tornado, victim mass 1 / 2 / 3 / 4 | 0.59 / 0.66 / 0.89 / 0.82 | 0.75 / 0.81 / 0.90 / 0.88 |
| victim mass 5 / 6 / 8 / 10 / 18 | 0.93 / 0.89 / 0.87 / 0.71 / 0.88 | 0.93 / 0.91 / 0.90 / 0.74 / 0.90 (no class lower) |
| Royal Hogs / Evo Royal Hogs | 0.32 / 0.28 | 0.72 / 0.41 |
| Hog Rider (the Tornado-to-king case) | 0.81 (54) | 0.93 |
| Minion Horde / Goblin Gang | 0.71 / 0.76 | 0.82 / 0.86 |
| J3 king wake, damage trigger after our Tornado | 0.569 (181) | 0.641 (184) |
| J3 all / J6 / J5a | 0.931 / 0.692 / 0.989 | 0.933 / 0.694 / 0.989 |

Per card (analysis/torn_ab_*.txt): two cards lost one body each (Mini P.E.K.K.A. hero 0.89 -> 0.83 of 18; Valkyrie 0.87 -> 0.80
of 15). No card lost more. J1 is checked in the FIN15 re-score (section 6).

**Open (b):**
- The Evo Royal Hogs stay at 0.41. Their winged fall is a separate law.
- These frames do not separate whether 16.402 removes the cap or only raises it: there is no raw collision accumulator live.

## 5. Fix 4 items

- **J8 tiebreak drain timing (a: a harness issue, not an engine law).** METRICS_J has 5 misses in 20 (SIM end minus live end:
  6, 12, 21, 62, 68):
  - **2 are not tiebreaks.** 20261018_072302 and 100712 ended on a sudden-death fall at t5969 / t5928; their last frames (6050 /
    6009) are the result screen running past 6000. Fixed in the harness (H-J8-CLASS: a tiebreak only when last - 81 >= 6000).
  - **1 is the probe's snapshot** (20261018_005636, +68). The probe resets from the t5990 tower hp, and a tower lost ~1,600 hp
    between t5990 and the board clear at t6001; live ended at t6074, 7 ticks into the drain (b).
  - **2 are genuine:** +6 (113652) and +12 (025652, which also flips the winner).
  - The engine's drain law fits the other 15 within 2-3 ticks. The live drain starts between t6065 and t6067 (20261018_123807:
    40 a step, every 2 ticks, from 530); the SIM's starts on t6067.
  - The constant +2 on 14 matches is inside the 5-tick tolerance. Whether it is the drain's start or the end event's latency is
    untested (b). No engine patch.
- **Clone copy deploy (b: a representation difference, not behaviour).**
  - Live copies read as deploying for 9-10 ticks. The SIM's are born deployed (`spells.CLONE_COPY_DEPLOY = deployed`), but the
    Clone's hold keeps them for the same 10 ticks with no target and no attack (`CLONE_HOLD_TARGETS`; `CLONE_COPY_STATE` = fresh:
    a copy takes its first target on C + 11, measured on 15.535.29).
  - So J5a's 0 / 60 compares a flag, not an action. The fix is for J5a to read the SIM's hold as deploying.
  - Not patched: whether a live copy can be targeted during those ticks is untested.
- **River crossing / lane choice (J6 0.69):** not attempted today.
  - The worst cards are special movers: Goblin Drill 0.00 (n 11), Barbarian Hut 0.45, Mega Knight 0.50, Mega Minion hero 0.54,
    Golden Knight 0.55. These are tunnel, jump and dash crossings, each a separate law.
  - The Tornado law moved J6 0.692 -> 0.694.

## 6. J1-J8 before / after

**Runs.** Before = METRICS_J and FIN13 (fork fin14c, W1 harness, 19899 / P3). After = the FINAL fin15: METRICS_J15F and FIN15F
(fork 305aaafc + the W8 harness, P2). The intermediate METRICS_J15 / FIN15 (2 laws, older harness) are in the round log.
Both cover the same 638 caplogs13 logs, the same exports and K = 8. The W8 harness fixes are marked; each one's effect is shown
on both engines where it matters.

| metric | before (fin14c, W1 harness) | after (FINAL fin15 = 305aaafc + the W8 harness) | goal 0.95 (lower CI) |
|---|---|---|---|
| **J1 fight, stamped** (FIN13 -> FIN15F) | 0.926 [0.920, 0.932] (13,049 fights / 403 matches) | **0.929 [0.923, 0.935]** (13,053); cmp.py 0.9263 -> 0.9289, 42 fights up / 7 down | no (owner's 0.975) |
| J1 fight, full | 0.9217 | 0.9242 (77 up / 20 down) | no |
| J1, the laws alone (FIN15, W1 harness) / + H-DRILL-SURFACE (FIN15d) / + TIEBREAK_REGEN (FIN15F) | - | 0.9271 / 0.9289 / 0.9289 (FIN15d -> FIN15F: 0 fights moved) | - |
| J1 own cards that MEET | Log, X-Bow, Tornado | the same: Log 0.971, X-Bow 0.968, Tornado 0.978 (0.976 before) | - |
| J1 coverage, tier B (coverage.py, same census) | 0.278 | 0.278 | no (0.9) |
| **J2 spell effect** (H-J2-REACH from FINAL on) | 0.904 [0.894, 0.914] | **0.917 [0.909, 0.925]**; strict-clean fights 0.951 [0.942, 0.960] | point yes on strict-clean, lower CI no |
| J2 Tornado | 0.821 [0.792, 0.850] | **0.880 [0.855, 0.902]**; strict-clean fights 0.939 | no |
| **J3 king activation, all** | 0.931 [0.922, 0.940] | 0.933 [0.925, 0.942]; strict-clean fights 0.973 | strict: yes |
| J3 positives / damage triggers after our Tornado | 0.851 / 0.569 | 0.856 / 0.641 | no |
| J3 wake law given the SIM trigger | 1090 / 1090 | 1107 / 1107 | yes |
| **J4 own elixir, open loop** (W1 harness) | 0.840 [0.820, 0.858] | 0.909 (fin15 laws, W1 harness) | - |
| J4, final harness (CAPDATE + DROPCOST + GAIN) | 0.878 [0.863, 0.892] | **0.991 [0.986, 0.994]** | **YES** |
| J4 by phase, final harness | 1x 0.951, 2x 0.752, ot2x 0.802, 3x 0.799 | 1x 0.995, 2x 0.985, ot2x 0.977, **3x 0.961 [0.937, 0.979]** | 3x: point yes, lower CI no |
| J5a deploy (fights / FIN bodies) | 0.989 / 0.992 | 0.989 / 0.992 | yes |
| J5b card cycle | 0.996 | 0.996 | yes |
| **J6 river crossing** | 0.692 [0.672, 0.712] | 0.697 [0.677, 0.717]; pathing proper 0.828; strict-clean fights 0.838 (pathing proper 0.904) | no |
| **J7 whole match, 573 matches** | trajectory 0.896, crown sequence 0.483, falls in time 0.454, result 0.496, king wake 0.771 | trajectory 0.898, crown sequence **0.506** (ceiling 0.834), falls 0.476, result 0.518, king wake 0.778 | no (J7 is graded normalised from 10-20: crown sequence 0.61; section 8) |
| **J8 regulation / tiebreak winner** | 102 / 102, 19 / 20 | 102 / 102, 17 / 18 (H-J8-CLASS) | yes |
| J8 tiebreak end tick | 15 / 20 | 15 / 18 | no |

**What the "strict-clean" rows mean (a, new).** J1 scores only the fights its harness can set up: `fights.is_clean`. That excludes a
fight where, for example, a spell is in flight at the start, an opponent ability went unobserved, a child unit was skipped in the
set-up, or a body was still deploying. The J-suite grades EVERY fight.

On the J1-clean subset of the same replays (analysis/clean_split.py, fin15):
- J2 0.949, Tornado 0.939;
- J3 0.973;
- J6 0.838 (pathing proper 0.904).

So a large share of the J2 / J3 / J6 gap sits in fights the harness already knows it cannot set up.

Owner / lead decision (b): grade J2 / J3 / J6 on J1's clean cohort, as J1 is graded, and report the full cohort beside it. The
table keeps both.

**J6 diagnosis (round 2, a).** j6diag.py on 33 matches: 30 failing crossings of our own units (Knight, Skeletons, IW hero),
classified by analysis/j6cause_clean.py.
- 24 / 30 are in fights J1 flags as unclean:
  - 15 have an enemy near the live body that the SIM lacks: Graveyard skeletons (28000010) and Goblin Barrel goblins
    (28000004). Each spell was in flight, or its area was running, at the fight start.
  - 8 are fight outcomes.
- 6 / 30 are in clean fights: 3 fight outcomes, 1 missing enemy, and 2 Skeletons that split from the live ones on the 12th tick
  among Royal Hogs and crossed 25 ticks late.
- No river-crossing or lane law was found; the lane disagrees on only 15 of 7,974 pathing-proper crossings.
- J6's lever is the harness's set-up of in-flight spawning spells (H, round 3), plus J1.

**The 10-20 classic-challenge parity battles:** the owner's 10-20 battles (a).

**The logs.** 40 logs with phase-3 captures (export20.py; caplogs20), run20.sh, the same K = 8, fin14c and fin15:
- 4 are ladder icebow matches (06:02-06:40, level 16).
- 3 are record-only stubs with no own decisions (skipped).
- 33 are classic-challenge battles at level 11. The BOT plays three rare-card decks:
  1. Goblin Drill evo, Little Prince, Minion Giant, Ice Spirits evo, Merge Maiden, Fire Spirits, Skeletons, Tesla;
  2. Barbarian Barrel hero, Goblin Barrel evo, Zap evo, Princess, Valkyrie, Firecracker, Ice Spirits, Skeletons;
  3. Electro Wizard hero, Goblin Drill evo, Snowball evo, Knight, Cannon, Poison, Fire Spirits, Skeletons.

**Harness changes needed to score them.**
- The J1 harness skipped every one of the 33 as `not_main_account`: no X-Bow in the hand, capped towers. The opt-in
  `PARITY_ANY_DECK=1` (fights.py) lets them in.
- Code tree cb20 = cb13's harness catalog + MinionGiant (26000107) only. W9's other in-progress catalog edits were left out, so
  the identities match the 638-log cohort.
- The Hero Electro Wizard form was tried and taken out again: the fork refuses it ("ElectroWizard has no loadable hero form:
  ability ElectroWizardHero_Ability"), which errored 91 of 122 fights of 20261020_100134.
- Spirit Empress has no identity in any catalog.

**Results.**

| metric (37 scored matches) | fin14c | fin15 (2 laws) | FINAL fin15 + H-DRILL-SURFACE |
|---|---|---|---|
| J1 strict, raw | 0.873 [0.840, 0.905] (832 fights) | 0.873 [0.840, 0.905] | **0.888 [0.858, 0.916]** |
| J1 all, raw | 0.689 [0.648, 0.731] (2,591 fights) | 0.689 [0.648, 0.731] | **0.700 [0.662, 0.739]** |
| J4 elixir (round-2 harness) | 0.891 [0.834, 0.942] | **0.999 [0.998, 1.000]** | 0.999 |
| J2 (447 bodies) / Tornado (25) | 0.803 / 0.920 | 0.803 / 0.920 | 0.803 / 0.920 |
| J3 all | 0.916 | 0.916 | 0.916 |
| J6 | 0.522 | 0.521 | 0.528 |
| J7 crown sequence (32 matches) | 0.250 | 0.219 (7 vs 8 of 32: inside the noise; n small) |

These decks hold few Tornados, so only J4 moves.

**The 11 rare cards** (J1 raw on these battles, fin15; "all" = every fight, "strict" = J1-clean; n = fights / matches):

| card | J1 all | J1 strict | J-suite (PERCARD.md) | note |
|---|---|---|---|---|
| Goblin Drill evo (own) | **0.00** (24 / 18); FINAL 0.04 | 0.00 (12 / 9) | J5a 0.81 (42), J6 0.65 (23) | tower damage, not deaths: live 110 / 270 / 747 vs SIM 395 / 395 / 0 on the first three fights. Round 3: the base drill's tower-damage gap was the replayed play point (H-DRILL-SURFACE: base own 0.34 -> 0.61). The evo's own gap is its relocate action, which the fork does not implement. Live, it is seen to dig and resurface twice in 1 of 7 evo drills (at about 2/3 and 1/3 hp, ~15 ticks later, round its tower); another dropped below 2/3 without moving. (b: data-limited) |
| Little Prince (own) | 0.615 (26 / 4) | 1.0 (3) | J2 0.77 (13), J5a 1.00 (33), J6 0.60 (5) | strict n too small |
| Minion Giant (own / opp) | 0.632 (19) / 0.689 (45); FINAL 0.684 / 0.694 | 0.714 (7) / 0.750 (16) | J2 0.83 (24), J5a 1.00 (62), J6 0.57 (14) | identity added for this run only |
| Zap evo (own) | 0.609 (31 / 11) | 1.0 (8) | - | - |
| Ice Spirits evo (own) | 0.824 (17) | 1.0 (5) | J5a 1.00 (27) | - |
| Snowball evo (own) | 1.0 (1) | 1.0 (1) | - | n = 1 |
| Goblin Barrel evo, Barbarian Barrel hero | no fight anchored on them | - | - | (b) plays not confirmed, or a labelling gap; untested |
| Electro Wizard hero | not scorable | - | - | the fork refuses the form (W9 item 1) |
| Spirit Empress (both forms) | not scorable | - | - | no identity |

No rare card reaches n >= 30 strict fights: one battle day is far below the per-card goal's n. Per-card raw values come from
FIN_20_fin15/CEILING_{all,strict}.txt and METRICS_20_fin15/PERCARD.md on P2.

## 7. Fork bundle, files, reproduction

**The fork.**
- Branch `fin15` of the RoyaleSim fork (worktree C:/Users/benpe/rsfork_w8, same repository as rsfork36): clashbot36 427597d3
  (fin14c) + 3 commits.
  - `4167f972` match.MANA_REGEN_STEP
  - `c6887a69` collision.ATTRACT_CONTACT_MEAN
  - `305aaafc` match.TIEBREAK_REGEN
  - head 305aaafceb7b28bf5108c9fe028fafae97d32676, tree d56d7717.
- As round 7 handled fin14:
  - the commits are tracked here as `patches/000{1,2,3}-*.patch` (git format-patch 427597d3..fin15);
  - the bundle is not tracked: `/tmp/claude/parity1016/clashbot36_fin15.bundle` (laptop, sha256 7bbd9a35...) and
    P2 `/workspace/w8/in/fin15.bundle`;
  - clashbot36 itself was not moved; the lead fast-forwards it if wanted.
- Rebuild anywhere: `git am patches/*.patch` on clashbot36 427597d3, or clone the bundle, then `fork_build.sh`.

**Gate (a)** (fork_build.sh, `cargo test --profile gate --no-fail-fast`): fin14c 1960 / 0 / 3 ignored ->
**fin15 1966 passed / 0 failed / 3 ignored** (363 suites). Each plant turns its own test red (`1 passed; 1 failed`):
- mana_regen_exact -> mana_regen_step;
- attract_mean_capped -> attract_mean_uncapped;
- attract_after_mean -> attract_contact_mean (the existing plant, still red);
- tiebreak_regen_runs -> tiebreak_regen.

**Files in this folder.**

| file | what |
|---|---|
| FIN15.md | this report |
| patches/ | the three fork commits |
| fork_build.sh | P2 build: bundle -> wheel -> runtime dir, cargo gate, plants |
| fin15_pod.sh, fin15_laws.sh | FIN15 (J1, K = 8) + the J-suite's fights / whole, and beside it elixir / laws + the scores |
| law_ab.sh | a one-wheel law A/B through PARITY_OVERRIDES (J2 / J3 / J6 / J5a, optionally J1), K = 0 |
| setup_fin15.sh, freeze_fin15.py, smoke_fin15.py, build_manifest_fin15.json | the training-pod install (section 0) |
| j7diag.py, j2diag.py, probe_2x.py, probe_j4.py | the diagnosis replays and probes (pod: PARITY_SIM_PATH=...) |
| analysis/ | the laptop analyses and their outputs (J7 census + classes, Tornado per card / A/B, J4 split, Royal Hog steps) |

**Harness edits** (`../metrics/replay_metrics.py`; selftest METRICS_SELFTEST_OK):
- H-J4-CAPDATE (`--no-cap-date` restores the old one);
- H-J8-CLASS;
- `score` no longer crashes on a K = 0 run.

**Runtime selector:** `pipeline/royale_runtime.py` gains the opt-in `fin15-linux`; `pipeline/royale_heroiw.py` enables the Hero IW
adapter under it. Unset or another id keeps its behaviour: `pipeline/tests/test_royale_runtime_rt35.py::test_fin15_selection` and
`test_fork_ids_unchanged_by_fin15` pass. The file's 5 older failures fail identically on the laptop with and without this edit
(laptop-venv paths).

## 8. Open items

### 8.1 Round log (owner 10-20: iterate per metric until the lower CI is >= 0.95, or until a confirmed plateau)

| round | metric | change | value [95% CI] | verdict |
|---|---|---|---|---|
| R0 | J4 elixir | fin14c, W1 harness | 0.840 [0.820, 0.858] | - |
| R1 | J4 | S-ELIXIR-TRUNC (engine) + H-J4-CAPDATE | 0.912 [0.894, 0.928] | gain; below goal |
| R2 | J4 | H-J4-DROPCOST (every drop deducted by its own rounded size) + H-J4-GAIN (credit live rises: the opponent's Elixir Golem pays us) | **0.990 [0.985, 0.993]** (fin14c on the same harness: 0.878) | **GOAL MET** overall; the 3x phase is 0.937 [0.914, 0.956] (n 135 matches): round 3 |
| R0 | J2 spell effect | fin14c | 0.904 [0.894, 0.914] | - |
| R1 | J2 | S-TORNADO (uncapped pull mean) | 0.914 [0.906, 0.923]; Tornado 0.821 -> 0.880 | gain (Tornado CIs separate); below goal |
| R2 | J2 | H-J2-REACH (no air body under a ground-only spell); strict-clean cohort reported | 0.917 [0.909, 0.925]; strict-clean 0.951 [0.942, 0.960] | strict: point meets, lower CI 0.942; round 3: the Log on packs (Royal Hogs 0.67, Barbarians 0.88 on clean fights; no push-direction bias, so no one magnitude law) |
| R0 | J3 king activation | fin14c | 0.931 [0.922, 0.940] | - |
| R1 | J3 | via S-TORNADO | 0.933 [0.925, 0.942]; strict-clean 0.973 | strict-clean point meets (its CI is not computed here); full: no |
| R0 | J6 river crossing | fin14c | 0.692 [0.672, 0.712] | - |
| R1 | J6 | via S-TORNADO | 0.694 [0.674, 0.714] | no gain (inside the CI) |
| R2 | J6 | diagnosis (j6diag, 33 matches) | strict-clean 0.838 / pathing proper 0.904 | no crossing law; the lever is the set-up of in-flight spawning spells (H, round 3) + J1 |
| R0 | J7 whole match | fin14c | crown sequence 0.483 | - |
| R1 | J7 | diagnosis + via S-TORNADO | crown sequence 0.499; trajectory 0.896 | no single law (section 3); 14 / 39 first divergences are hit-phase offsets the metric scores as misses |
| R0 / R1 | J8 tiebreak end tick | H-J8-CLASS | 15 / 20 -> 15 / 18 | the drain law fits within 2-3 ticks; the remaining 3 are probe-snapshot / small (section 5) |
| R0 / R1 | J1 | both laws | 0.926 -> 0.927 stamped (+18 / -7) | no regression; below goal |
| R3 | J4 | S-TIEBREAK-REGEN (engine) | 0.991 [0.986, 0.994]; 3x phase 0.961 [0.937, 0.979] | goal met overall; 3x lower CI 0.937 (n 135) |
| R3 | J1 | H-DRILL-SURFACE (harness) | stamped 0.9289 (+24 / -0); full 0.9242 (+35 / -0) | gain; below the owner's 0.975 |
| R3 | rare cards (10-20) | H-DRILL-SURFACE | own Goblin Drill 0.34 -> 0.61, opp 0.00 -> 0.74; evo drill 0.00 -> 0.04 | the evo needs its relocate action in the engine (not implemented in the fork; no device parameters on hand) |
| R4 | J3 / J6 / J2 (all fights) | H-PRESPELL=spawn (fights.py opt-in: a fight starts before an in-flight Goblin Barrel / Graveyard cast, so the spell is replayed) | J3 0.933 -> **0.947 [0.939, 0.955]**; J6 0.697 -> 0.718 [0.697, 0.737] (pathing proper 0.828 -> 0.838); J2 0.917 -> 0.917 | gain on J3 / J6; DEFAULT since 10-20 |
| R4 | J1 | the same, on the J1 cohort | stamped 0.9289 -> 0.9273: 0 fights moved, 304 newly clean fights join at a lower agreement (own Tornado 0.978 -> 0.959 on 24 more) | ADOPTED as the default grading (lead, 10-20); J1 reported both ways above |
| R5 | J1 coverage | H-CHAMP-CASTS (fights.py): an opponent champion press is dated from its live state-10 burst (Skeleton King, Monk, Mighty Miner; the Golden Knight shows none) and replayed through the ability slot | stamped fights 13,356 -> 14,188 (+832; 0 existing fights moved); raw 0.9273 -> 0.9268 [0.921, 0.933]; newly graded: opp Mighty Miner 0.996 (60), Monk 0.924 (36), Skeleton King 0.875 (57) | DEFAULT since 10-20 (same rule as H-PRESPELL: it measures more of the real game); PARITY_CHAMP_CASTS=0 restores |
| - | J5a, J5b, J8 winner, J3 wake law | - | >= 0.98 | meet |

Section 6 has the full values. No metric has reached a confirmed plateau (two rounds with no CI-significant gain plus a written
diagnosis): J4 met the goal in round 2, and every other metric has had at most two rounds.

**Round 4 decision (lead, 10-20): H-PRESPELL=spawn is the DEFAULT grading from now on** (fights.py; `PARITY_PRESPELL=off`
restores the old cohort). J1 on the final fin15, reported both ways once so the series stays comparable:

| J1 cohort | stamped raw [95% CI] | stamped fights | full raw | full fights |
|---|---|---|---|---|
| old definition (FIN15F, PARITY_PRESPELL=off) | 0.9289 / 0.929 [0.923, 0.935] | 13,052 | 0.9242 | 20,711 |
| new definition, round 4 (FIN15P: + H-PRESPELL) | 0.9273 / 0.927 [0.921, 0.933] | 13,357 (+304) | 0.9225 | 21,328 (+617) |
| **new definition, round 5 (FIN15C: + H-CHAMP-CASTS) = the series from now on** | **0.9268 / 0.927 [0.921, 0.933]** | 14,188 (+832) | 0.9215 | 22,590 (+1,262) |

- Not one existing fight moved (0 up / 0 down). The gap is the 304 newly gradable fights, set up from before the in-flight
  Goblin Barrel or Graveyard cast; their agreement is lower.
- These are real gaps, not noise, so the series continues on the new definition.
- J-suite on the new definition: J3 0.947 [0.939, 0.955]; J6 0.718 [0.697, 0.737] (pathing proper 0.838); J2 0.917.

### 8.2 Queue for round 5 (fin16), biggest lever first

0. **NEW TOP LEVER (a, counted 10-20 on FIN15F): the opponent's champion ability presses are never replayed.**
   - Every fight with an opponent champion is flagged `opp_ability_unobserved` and left out of J1-strict. For 3,692 of the 36,078
     fights it is the ONLY blocker: Golden Knight 1,143, Boss Bandit 567, Mighty Miner 518, Skeleton King 452, Archer Queen 376,
     Monk 318, Goblinstein 297, Little Prince 21.
   - Round 5 (landed, H-CHAMP-CASTS) covers the three champions with a state-10 burst: Skeleton King, Monk, Mighty Miner.
     Still open: Golden Knight 1,143, Boss Bandit 567, Archer Queen 376, Goblinstein 297.
   - The fix for the rest: infer each press from its visible effect, as `seen_casts` already does for hero casts. Examples: the Skeleton King's
     soul copies appearing, the Golden Knight's dash chain, the Archer Queen's cloak.
   - This is also the 'unpaired summoned skeletons' item: 1,144 SkeletonKing-labelled bodies are unpaired because the SIM never
     pressed the ability.
1. **J4 (MET in round 2: 0.990).** Left:
   - the 3x phase, 0.937 [0.914, 0.956] (n 135 matches). The live switch tick is right: 2x -> 3x on the step into t4801 on 72 of
     78 logs (analysis/x3.py), the SIM's too. Median |d| is 0.018 = one 3x-minus-2x step, so a spend dated one tick off at 3x
     is the next suspect (b).
   - the 245 drops with no confirmed play: since round 2 they are deducted by their own size. Their source (an 'unconfirmed'
     tap the game took, a Hero IW press without its event) is a reader / logging item.
2. **J2 Tornado** (0.880):
   - Evo Royal Hogs 0.41 (n 32): the winged fall;
   - Golden Knight 0.67 and mass 10 at 0.74: the dash under a pull;
   - Skeleton Warriors 0.62.
3. **J6 crossings** (0.69; strict-clean 0.838). Round 2 found no crossing law. The lever is the harness:
   - set up the spawning spells that are in flight or whose area is running at a fight's start (Graveyard, Goblin Barrel);
     today they are missing in the SIM, and J1 calls those fights unclean;
   - then the special movers: Goblin Drill 0.00, Mega Knight 0.50.
4. **J7 / J3 positives:** both are driven by J1's unit fights (section 3).
   - **J7's goal is out of reach as a raw score (a).** Its own noise ceiling sits below 0.95 (fin15, 573 matches): SIM vs perturbed
     SIM, with only the deploy tick redrawn inside its frame gap, gives crown sequence 0.834, falls in time 0.819, result 0.838.
     So a perfect engine would still score about 0.83 raw on these three.
   - **Decision (lead, 10-20): J7's goal is now the NORMALISED score** (raw / SIM-vs-SIM ceiling), not the raw one. On the final
     wheel: crown sequence 0.506 / 0.834 = 0.61; falls in time 0.476 / 0.820 = 0.58; result 0.518 / 0.838 = 0.62; trajectory
     0.898 / 0.970 = 0.93.
   - The trajectory's ceiling is 0.970 (normalised 0.924). It also needs a time tolerance, or the 14 / 39 hit-phase offsets
     (section 3) keep failing a perfect engine.
5. **W9's ranked SIM gaps** (identities/IDENTITIES.md) and the owner's facts:
   - Skeleton King souls: the engine ALREADY puts its soul copies down at 1 hp (state.rs `soul_pass`: `cloned = true`; the
     15.535.29 reading "each 1 hitpoint"). W9's "119-130" is the static row check (SkeletonKingSkeleton 32 x the ladder), so "the
     SIM gives them 119-130 hp" is (c) contradicted for the engine.
   - The live/SIM gap is elsewhere. In FIN15, 1,144 SkeletonKing-labelled bodies are unpaired against 755 paired: the summoned
     skeletons carry the King's card id live and the copy's in the SIM, and the opponent's ability press has to be replayed.
     That is a harness pairing / press item (b, untested).
   - Hero Electro Wizard: the fork refuses the form ("ElectroWizard has no loadable hero form: ability
     ElectroWizardHero_Ability"); the 10-20 battles hit it in 91 of 122 fights of one match. Its `surge` ability needs an engine
     implementation. The owner rates it rare outside PEKKA bridge-spam, so it comes after the higher-frequency items.
   - Clone 1-hp bodies and Clone deploy (section 5); level 17 (Mirror of a level-16 card); Evo Electro Giant's one table field.

### 8.3 Other open items

- The 18:00 checkpoint wheel is this fin15. The lead decides whether tonight's successor trains on it; switching means
  `ROYALE_RUNTIME=fin15-linux` + venvf15 in stepd_chain.sh and the scripts that hardcode fin13-linux.
- The FIN re-score could not run on 19899: it was busy all day with W7 / O3 evals. Everything ran on P2.
- The setup smoke and the trainer smoke ran on P2 after its build checkout was removed (section 0).
- HANDOFF is not updated in this commit (worker rule: never stage the working copy); the lead adds the entry.

## 9. W19 (10-22): why J1 has plateaued -- diagnosis, hypothesis ledger, rounds

Labels as above: **(a) measured**, **(b) plausible but untested**, **(c) contradicted**. Pod 157.157.221.29:33591; fin15 wheel
88f3fdcb (pip --target, PARITY_SIM_PATH); harness = HEAD parity tree + the W19 edits below. Tools: `parity/w19/` (cls.py
first-divergence classifier; hits / births / speeds / retarget / xbow_lock / form_census censuses; explain.py ledger pass and
the other laptop analyses in `w19/analysis/`; base_run.sh = chunked runner, 8 chunk dirs per cohort with one export each, so 48
workers fit in the pod's 62 GB).

### 9.1 Cohorts and baselines (a)

| run | cohort | K | stamped strict fights / matches | J1 raw [95% CI] |
|---|---|---|---|---|
| BASE8 (reproduces FIN15C) | c13 = caplogs13, 638 logs 10-16 .. 10-18 13:15 | 8 | 14,252 / 404 | **0.927 [0.921, 0.933]**, ceiling 0.992 |
| BASE0 | c13 | 0 | 14,252 / 404 | 0.928 [0.922, 0.934] |
| BASE0 | **c22 = 786 new captured logs 10-18 13:19 .. 10-21 16:13** (no 10-22 log exists) | 0 | 29,615 / 748 | **0.917 [0.913, 0.921]** |
| BASE0 | union c13 + c22 | 0 | 43,867 / 1,152 | 0.9205 [0.9170, 0.9239] |

### 9.2 Why the plateau: what the remaining failures are (a)

- **Systematic, not noise.** Of the 1,030 failing c13 fights (live vs the unperturbed SIM), 943 have 0 of 8 perturbed SIMs
  agreeing with live; only 87 (8.4 %) sit inside the modelled hidden-state noise. The ceiling (0.992) says the replay is
  deterministic, not that it is right.
- **Not tolerance edge.** Re-scoring the c13 failures with a looser death tolerance: 15 / 20 / 30 / 60 ticks pass 14 / 26 / 41 /
  59 % of them (raw 0.938 / 0.947 / 0.957 / 0.970); tower tolerance x2 passes 4 %. Even 3 s of tolerance stays below 0.975.
- **Damage values are right.** Hit census over every strict fight (same frame gap, same body, both runs in step): 972,567 equal
  drops vs 14,108 different; of the drops > 30 hp, 329,253 equal vs 4,652 different, mostly two attackers coinciding. Real but
  small leads: the Evo Knight fortify state (live 48 vs SIM 122), an opponent princess tower read one level high (158 vs 173).
  Our level-16 tower shots on troops: 14,521 of 14,616 equal.
- **Divergences are everywhere; only EARLY ones predict failure.** First-divergence classifier (pass 3) on all 14,252 c13 fights:
  65.6 % of PASSING fights also diverge somewhere. Late first divergences (> 40 ticks) are as common in passing as in failing
  fights (P(fail) 0.064-0.094 vs base 0.072). Divergences within 40 ticks of the start are 2-3x enriched: set-up body target
  P(fail) 0.219, hp 0.212, position 0.160; early position 0.164, hp 0.122, target 0.133.
- **The tail is long.** No mechanism found holds more than ~13 % of a cohort's failures; most hold 1-6 %. That is why each round
  since FIN12 moved J1 by +0.0002 to +0.002: one law fixes one mechanism, i.e. 5-40 of ~1,000 failures.
- Classifier artefacts found and removed: 380 of 518 pass-1 'target' first divergences were "live target = crown tower, SIM
  none" (the reader names the tower a unit walks to; the SIM sets target_uid on lock); building decay rounds 1 hp apart
  (2096 vs 2097) -> hp tolerance 5 from pass 3.

### 9.3 The level-16 step (a: located; a cause found for own Skeletons)

The new data is worse, and it is a step: our-tower level-15 era 0.926 [0.921, 0.930] (25,229 fights) vs level-16 era (our towers
4424 -> 4858 at 10-19 13:56) 0.913 [0.907, 0.919] (18,638). Per live segment (the same model, CLX, before and after):

| segment | ALL | own Skeletons | opp Skeletons | opp Hog Rider |
|---|---|---|---|---|
| CLX, our towers L15 (10-19 00:20-08:47) | 0.921 | 0.879 (381) | 0.950 | 0.955 |
| CLX, L16 ladder (10-19 13:56-10-20 10:43) | 0.919 | 0.822 (533) | 0.903 | 0.851 |
| CLX, L16 Ranked (10-20 13:28-10-21 14:28) | 0.910 | 0.803 (975) | 0.764 | 0.902 |
| CLXI, L16 Ranked | 0.910 | 0.750 (88) | 0.793 | 0.844 |

- Within-card, not card mix (the L16 per-card rates on the pre-era mix: 0.910); across every opponent card present and every fight
  context (even with no enemy on board, own Skeletons 0.966 -> 0.829).
- Ruled out (a/c): our card levels in the replay (read per match from max_hp: Skeletons 16 in both eras; IW 14/15 -> 16, Log 15
  -> 16, towers 15 -> 16, all read right); tower damage (equal) and fire rate (16 ticks at L15 and L16 live); deploy durations
  (exact in both eras); walk speed (SIM/live 0.998-1.000 in both eras); frame cadence (2 ticks, unchanged); tower troop (Princess
  in both eras); reader binary (unchanged since 10-17 18:00); tap vs spawn point (median < 160 mt in both eras).
- **Found (a): the fork's 3-Skeleton FORMATION.** 35.5 % of own Skeleton members stand > 30 mt off live on their first frame
  (Knight 2.7 %, X-Bow / Tesla 0.1 %). Failing fights carrying it: c13 15 / 1,030, **c22 323 / 2,456**. The L16-era model plays
  Skeletons at taps that expose it, e.g. behind the king at x 8,500: the SIM stands the right member at x 8,956 (live 9,003), so
  it walks to the LEFT lane in the SIM and the RIGHT lane live (6 of 6 dossiers identical: 20261020_204741@1210, 232823@1689,
  20261019_200142@1631, 20261020_163959@2940, 20261019_183336@3921, 20261020_150323@1883). The formation census (fork deploy vs live
  first frame, same tap) shows two live ring shapes for 3 members (symmetric r ~580: (-503, -288), (-1, +579), (+498, -288); and a
  lane-mirrored one: (-516, +261), (-1, -612), (+456, +259)) and a river-edge clamp of the inner member that the SIM always applies
  and live applies in ~45 % of identical taps (independent of queued taps and lag: (b) an observation phase or a rule not yet found).
- The opp Skeletons / Hog drops are plausibly the cascade of our Skeletons walking in the other lane (b). Ranked adds a further
  opp-Skeletons drop (0.903 -> 0.764): (b), not separated.

### 9.4 Hypothesis ledger

| # | hypothesis | test | failing fights it explains (measured) | status |
|---|---|---|---|---|
| H1 | failures are hidden-state noise | K=8 perturbed SIMs agreeing with live | c13 87 / 1,030 | (a) 8.4 % only |
| H2 | failures are tolerance-edge near misses | re-score at looser tolerance | c13 145 at 15 ticks, 269 at 20 | (a) characterisation, not a cause |
| H3 | wrong damage values / levels | hit census; per-match level read-off | < 1.5 % of same-gap hits differ | (c) as a family; EK fortify, opp tower level open |
| H4 | the 10-19 step = our card / tower levels in the replay | levels per match, hit census by era, fire rate | 0 | (c) |
| H5 | the 10-19 step = the model's play mix | segments: CLX at L15 = earlier models (own Skel 0.879) | 0 | (c) as the whole story; the model's TAPS expose H6 |
| H6 | 3-Skeleton formation law (fork) | probe + formation census + 6 dossiers | signature in c13 15, c22 323 | (a) mechanism; oracle arm (9.6) sizes it |
| H7 | unseen / late opponent splash spells | live group death the SIM does not match | c13 58, c22 122 (first-signature) | (a) signature; reader-limited (Log seen after impact x17, Arrows x3) |
| H8 | spawned-body timing / presence | birth census + first divergence | c13 61, c22 112 | (a) family; per-card laws open (Elixir Golem split 436 timing offsets; Witch 254; Goblin Barrel goblins 461 live-only / 306 SIM-only; Skeleton King souls 190 live-only; Clone 148 SIM-only) |
| H9 | spawner timers under an Ice Wizard slow | live wave intervals vs slowed share (140 -> 155 at 32 %, 177 at 70 % = SIM 140 / (1 - 0.3 s)) | R1 +11 / -4 | (a) engine right, harness set-up wrong -> R1 kept |
| H10 | start-state: a set-up body diverges within 10 ticks | classifier + passing control | c13 197, c22 421 (after H1-H8) | (a) family: route / target / attack phase of set-up bodies (reader-limited) |
| H11 | other early divergences (<= 40 ticks) | classifier | c13 176, c22 401 | (a) family: retarget, pathing at bridge edges, kamikaze retarget onto deploying units (dossiers) |
| H12 | retarget rules | retarget census (live switches, old target alive) | SIM makes the same switch 84.6 % (walkers to fresh deploys 93.5 %; Firecracker 61 %, Goblin Cage 25 %) | (a) per-card leads |
| H13 | the SIM wakes the king late (W18) | live wake - trigger | princess-triggered: 70 ticks live = SIM law (569/569 own, 757/758 opp) | (c); damage-triggered wakes vary live (246/351 at 70): (b) source-dependent |
| H14 | the SIM king takes more damage after our princess falls (W18) | replayed fights after a fall | SIM/live 0.991 [0.950, 1.037] strict | (c) (W18 withdrew the premise) |
| H15 | the X-Bow ignores tower-front blockers (W18) | xbow_lock census (1,104 fights) | blocker 8-11.5 t: first target 289/297; ends on tower live 28.6 % vs SIM 22.2 % | (c); lead: no blocker, live tower vs SIM unit first target 77/807 |
| H16 | pocket deploy rule (W18) | fork probe + live census | fallen lane only (live 1,766 vs 5 standing-lane plays); depth <= 4.5 tiles in both | (c) |
| H17 | walk speed / frame cadence / reader / tap point changed at 10-19 | censuses | 0 | (c) |

### 9.5 Unexplained share after each pass (explain.py; a fight counts under its first matching signature)

| pass | c13 unexplained (of 1,030) | c22 unexplained (of 2,456) |
|---|---|---|
| noise (K=8) | 943 (0.916) | K=8 pending |
| formation (H6) | 928 (0.901) | 2,133 (0.868) |
| unseen / late spell (H7) | 870 (0.845) | 2,011 (0.819) |
| spawn timing / presence (H8) | 809 (0.785) | 1,899 (0.773) |
| start-state <= 10 ticks (H10) | 612 (0.594) | 1,478 (0.602) |
| early <= 40 ticks (H11) | 436 (0.423) | 1,077 (0.439) |
| near miss <= 15 ticks (H2) | 329 (0.319) | 797 (0.325) |

These are attributions by signature, not proofs: only an arm proves a cause. The remaining ~32 % is spread over the own deck (IW
hero, Tesla, Knight, X-Bow) and opponent swarms. **Not a confirmed plateau**: every family above still holds untested laws.

### 9.6 Rounds

| round | law | kind | metric before -> after (stamped strict, K=0, paired by fight) | kept? |
|---|---|---|---|---|
| R1 | H-SPAWN-SLOW: a set-up spawner's elapsed cycle counts 35/50 for every tick the live buff rows show it under an Ice Wizard slow (start_state, both the last-wave and the H-SPAWN-BORN path) | harness | c13 0.9277 -> 0.9279, +0.00021 [-0.00014, +0.00059], +6 / -3; c22 0.9170 -> 0.9171, +0.00014 [0.00000, +0.00030], +5 / -1; **union +0.00016 [0.00000, +0.00032], +11 / -4** | **kept** (default on, PARITY_SPAWN_SLOW=0 restores; the mechanism is measured live; the 4 downs are not dossiered (b)) |
