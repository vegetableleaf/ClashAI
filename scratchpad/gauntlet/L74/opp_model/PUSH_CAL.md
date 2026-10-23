# PUSH_CAL -- are SIM opponent pushes softer than live? (opponent-model worker, 10-23)

Grades: **(a) measured** (number given), **(b) plausible, untested** (the test named), **(c) contradicted** (evidence given).
Tool: `opp_model/push_cal/push_cal.py` (one push definition for both sides; `report` prints every table below).
Tables: `push_cal/report.out` (E4, I u40, I u40 at tau .55, live) and `push_cal/report_gate.out` (+ the gate arms).

## 0. Short answer

- **The headline gap was a counting bug (a).** EXPLOIT's "SIM pushes carry 13.4 elixir vs 7.7 live, and do less than half
  the damage per elixir" came from `exploit/ape_punish.py`'s SIM body value (`sim_value`), not from the opponents.
  - In the SIM board rows, a body's engine name is its OWNER CARD: a Witch's skeletons are named `Witch`, a Furnace's
    spirits `FirespiritHut`, Golemites `Golem`. Live card_ids work the same way.
  - The live rule knows this: a body under 45% of its card's biggest max HP is a child worth 1/3 elixir.
  - The SIM rule did not: every child was worth the whole card. One Witch push scored 58.9 elixir instead of 7.6.
  - With ONE rule on both sides, E4's pushes are 8.18 elixir vs live 7.61 (1.07x), not 13.5.
- **After the fix there are two smaller, opposite gaps (a):**
  - **E4** (the SIM eval / promotion-gate opponent) is about 20-25% SOFT. Same push size, but 0.76x the tower damage
    per push elixir and 0.81x the conversion rate. Almost all of it is in 1x.
  - **I u40** (W14's opponent; one of the long run's training opponents, "vs W14 I u40" in its train.log) is about 25-30% HARD. Pushes are 1.27x bigger with
    the same damage per elixir, so 1.30x the damage per push. It punishes our low-elixir moments 1.3x harder than live.
    The excess is in 1x.
- **Cause: opponent policy, not the engine (a for E4 vs the engine; b for the exact E4 behaviour).**
  - Same engine and same CLX: I u40 reaches live damage per elixir in every archetype and every push-size bucket.
  - One-card pushes under E4 do live damage: Hog 359 vs 381 HP, Goblin Barrel 612 vs 612, Valkyrie 113 vs 88,
    Royal Hogs 470 vs 500.
  - E4 is softer than live at matched push value, matched defence spend and matched answer time.
  - Composition, concentration, spread, placement and timing against our elixir all sit within ~10% of live.
    The exact E4 behaviour is not found yet (b).
- **The soft-push premise for the long run is (c) contradicted for its training opponent.**
  - I u40 is not soft. It is harder than live, and hardest exactly when we are low on elixir:
    conversion 0.353 vs 0.268 live, and 1,210 vs 842 HP lost per push.
  - That fits EXPLOIT's (b) "banking elixir to defend pays in training". The gate opponent (E4) pays for that banking
    less than live does.
- **The same bug sits in `ape/ape_score.py`, which the drift gate uses (a).**
  - CLXII's SIM "defence trade -0.55" (EXPLOIT 1b, "same direction as live") is an artefact: on one rule it is +0.07.
  - The idle-on-threat drift survives: +0.023 becomes +0.020.
- **Two more measurement problems (a), fixed inside push_cal:**
  - The SIM board recording never contains the tower fall that ends the match.
  - The live end tick is read 1.5-3 s late.
  - Pushes whose window reaches the decided end are dropped on both sides (5.3% SIM, 5.1% live).
- **Step 3 verdict: no opponent training launched (stopped at the proposal).**
  - Three eval-time knobs were gate-run (960 games each): none moves push size the right way (a).
    - I u40 at tau .55: 9.64 elixir / push vs 9.66.
    - I u40 at decide 60: 9.94, worse.
    - E4 at T .03: 8.12 vs 8.22, and weaker.
  - The training knob that matches the I u40 gap (W18 R3 play_cost, a config) is already running in W18's lane on 33401.
  - The E4 softness is a gate-definition question (owner / lead).
  - What is ready: `push_cal/gate_eval.sh` + `push_cal.py report` = a push gate that any opponent snapshot can be scored on.

## 1. Data and the one definition

**Data:**
- Live = CLX's 473 main-account matches that ape_punish scored: 327 Ranked (from 20261020_132855, clx_ranked's rule) +
  146 ladder. EXPLOIT's "433" is this set (`exploit/data/punish_live.txt` says n 473).
  - Source: the habits-cache pickles (412 existing + 61 built by `push_cal/build_extra.py` into `push_cal/cache_extra/`).
  - The overall Ranked-only numbers differ from all-473 by < 5% (report.out column live_ranked), so "live" = all 473
    unless marked. Per-archetype Ranked cells are noisier (n 29-102).
- SIM E4 = `/workspace/ckev/out/clx_rb/e4`: CLX (5d212358) D3, 4 seed blocks, 1,920 board-recorded games vs E4 (CAL set c, T .1).
- SIM I u40 = `/workspace/exploit/ev/clx_rb/iu40`: 2 blocks, 960 games vs W14 I u40 (4ff9fe93; T .1, decide 40).
  - `/workspace/ckev/out/clx_rb/iu40` has no board rows.

**Push (ape_punish.score section 4, unchanged):**
- A push = enemy troops crossing onto our half, grouped from the first crossing until our half is clear (>= 6 s, <= 20 s).
- Value = each crossing body's elixir at its first sample on our half (hp-scaled). Counted if >= 3 elixir.
- Lost = our tower HP from 1 tick before to 2 s after.
- Spend = our plays on our half.

**What push_cal makes equal:**
1. **One body-value rule: the live rule `ape_punish.body_value`** on the card key (the SIM engine name -> `vocab.engine_key`).
   - Buildings and their children = none.
   - Role children (< 45% of the card's top max HP) and spell bodies outside BODY_COUNT = 1/3 elixir.
   - Else cost / BODY_COUNT.
   - Reproduction check (a): with ape_punish's own SIM rule, push_cal gives 6.93 pushes / match, 13.54 elixir / push,
     36.6 HP per elixir, trade +5.54 = EXPLOIT's table.
2. **One sample grid:** live frames (>= 6 ticks) resampled to the SIM's 20-tick grid on the game clock (live tick - 78).
   - Sensitivity, live at its native 6 ticks (`PUSH_STEP=6`): 6.88 pushes / match, 7.52 elixir / push, 569 HP / push,
     75.7 HP / push elixir, conversion 0.189 (vs 6.52 / 7.61 / 607 / 79.7 / 0.202 on the 20-tick grid).
   - So the grid moves the live cells by <= 6%. The SIM only has the 20-tick grid, so 20 ticks is the matched choice.
3. **Placeholders dropped:** entities with max HP < 20 (spawn / effect stubs; 5.3 / match SIM, 8.5 live).
4. **Our plays at landing:** SIM land tick; live confirmation tick = the game's elixir drop.
5. **Towers:** a reader gap keeps the last reading.
6. **Decided end:** a push whose window reaches the decided end is dropped (section 5).

## 2. The apples-to-apples table (complete pushes; 95% match-bootstrap CI)

| metric | E4 (1,920) | I u40 (960) | live (473) | EXPLOIT's old SIM / live |
|---|---|---|---|---|
| pushes / match | 6.44 [6.33, 6.57] | 6.86 [6.68, 7.06] | 6.52 [6.24, 6.82] | 6.93 / 6.85 |
| elixir / push | **8.18** [8.05, 8.30] | **9.67** [9.45, 9.86] | **7.61** [7.37, 7.89] | 13.4 / 7.7 |
| our spend / push | 8.63 | 8.97 | 7.73 | 7.9 / 7.6 |
| defence trade / push (value - spend) | -0.45 [-0.57, -0.34] | +0.69 [+0.52, +0.89] | -0.12 [-0.33, +0.10] | +5.5 / +0.1 |
| tower HP lost / push | 494 [476, 514] | 786 [747, 822] | 607 [568, 649] | 495 / 620 |
| tower HP lost / push elixir | **60.4** [58, 63] | **81.4** [78, 85] | **79.7** [75, 85] | 37 / 81 |
| conversion (>= 1,000 HP lost or a princess fell) | 0.163 | 0.251 | 0.202 | - |
| a princess fell in the push | 0.014 | 0.050 | 0.031 | - |
| cards / push | 2.32 | 2.58 | 2.10 | - |
| bodies / push | 5.7 | 6.3 | 4.7 | - |
| both-lane (split) share | 0.25 | 0.31 | 0.22 | - |
| our elixir at push start | 4.62 | 4.64 | 4.53 | - |

- The counting fix closes ~90% of the elixir-per-push gap. E4 goes 13.5 -> 8.2 vs live 7.6.
- On the old rule the defence trade sat 5.4 elixir apart; now it is 0.3 apart.
- Opponent elixir played per match: E4 121.6, I u40 117.5, live 107.2 (all plays, spells included; public detector live).
  The SIM opponents spend ~10-13% more in total.

## 3. Per archetype and per phase (gate cells; SIM / live, PASS = within +-25%, trade within +-1 elixir)

Archetype = the opponent's revealed win condition (clx_ranked/anatomy WINCON order):
- hog = Hog Rider;
- bridge = MK / PEKKA / Royal Hogs / Ram Rider / Battle Ram / Boss Bandit;
- beatdown = Golem / Giant / E-Giant / GG / E-Golem / LavaLoon / RG / 3M / GS / Rune Giant / Goblinstein;
- bait = Goblin / Skeleton Barrel, Drill, Wall Breakers;
- control = Graveyard / Miner / siege / Sparky / Bowler / Executioner / Skeleton King / Goblin Machine.

Mix (SIM / live):
- beatdown 0.33 / 0.23
- bridge 0.30 / 0.32
- hog 0.10 / 0.15
- bait 0.14 / 0.16
- control 0.11 / 0.09

7 cells per row: pushes / match, elixir / push, HP lost / push, HP lost / push elixir, conversion, defence trade,
conversion at our elixir < 4 (= "conversion after our mistake").

| cells | E4 | I u40 |
|---|---|---|
| all | **0 of 7 fail**, two at the edge: HP / push elixir 0.76x, low-elixir conversion 0.77x; elixir / push 1.07x, HP / push 0.81x, conversion 0.81x | **3 of 7 fail**: elixir / push 1.27x, HP / push 1.30x, low-elixir conversion 1.31x; HP / push elixir 1.02x, conversion 1.24x |
| hog (live n 73) | 2 fail: conversion 0.70x, low-elixir conversion 0.69x (HP / elixir 0.75x) | 1 fail: conversion 1.28x |
| bridge (151) | 1 fail: HP / elixir 0.74x | 4 fail: elixir / push 1.29x, HP / push 1.39x, conversion 1.34x, low-elixir 1.44x |
| beatdown (108) | 3 fail: HP / elixir 0.75x, conversion 0.74x, low-elixir 0.75x | 1 fail: low-elixir 1.27x |
| bait (75) | 1 fail: low-elixir 0.72x | 3 fail: pushes / match 1.27x, elixir / push 1.27x, conversion 1.26x |
| control (42) | 3 fail: HP / push 0.75x, conversion 0.75x, low-elixir 0.62x | 0 fail |

- (Every cell with its SIM and live values: `report.out` "PUSH GATE".)
- Live n per archetype is 42-151 matches, so a single cell's +-25% is not a significance test. The direction is
  consistent across cells.
- **E4 is soft in every archetype, by about the same amount (a).** HP per push elixir is 0.74-0.79x everywhere, so no
  single archetype drives it.
- **I u40's excess is push SIZE, not efficiency (a).**
  - Elixir per push: bridge 1.29x, bait 1.27x, beatdown 1.24x.
  - Damage per push elixir: 0.95-1.08x everywhere.

**By phase (a):**

| phase | E4 HP / push (per elixir) | I u40 | live | E4 / I u40 / live elixir per push |
|---|---|---|---|---|
| 1x | 592 (85.5) | 1,123 (127.5) | 770 (112.6) | 6.9 / 8.8 / 6.8 |
| 2x | 467 (51.2) | 584 (53.7) | 503 (59.4) | 9.1 / 10.9 / 8.5 |
| OT (complete pushes) | 365 (40.1) | 363 (36.7) | 373 (45.4) | 9.1 / 9.9 / 8.2 |

- Both gaps live mostly in **1x**. E4's 1x pushes do 0.77x live damage at the same size. I u40's 1x pushes are 1.29x
  live's size and do 1.46x live damage.
- 2x and OT are within ~15% for both.

**Our elixir state when the push starts (a)** (columns: n, HP lost / push, conversion, our spend, push value):

| our elixir at push start | E4 | I u40 | live |
|---|---|---|---|
| < 4 | 634, 0.207, 7.2, 7.9 | 1,210, 0.353, 7.7, 9.8 | 842, 0.268, 7.1, 7.8 |
| 4-7 | 397, 0.134, 9.4, 8.5 | 458, 0.169, 9.7, 9.6 | 437, 0.150, 8.1, 7.6 |
| >= 7 | 376, 0.122, 10.2, 8.0 | 495, 0.188, 10.5, 9.5 | 396, 0.154, 8.5, 7.1 |
| our offensive spend >= 6 in the 10 s before | 436, 0.144 | 683, 0.224 | 559, 0.177 |

- Timing vs our elixir is live-like for both (a): 43% of pushes meet us under 4 elixir in the SIM and in live.
- The extra damage from being LOW (< 4 minus 4-7) per push:
  - E4: +237 HP / +0.07 conversion
  - live: +405 HP / +0.12
  - I u40: +752 HP / +0.18
- So training vs I u40 pays 1.9x live for keeping elixir. The E4 gate pays 0.6x.
- This is the measured version of EXPLOIT's (b) hoarding incentive (association, not a causal estimate).
- The 10-18 habit number "0.7% vs 6-7%" could not be traced to a definition. The conversion cells above replace it.

## 4. Cause (step 2)

| hypothesis | grade | evidence |
|---|---|---|
| H1 spawned-unit counting makes SIM pushes look bigger | **(a) confirmed, ~90% of the elixir gap** | ape_punish `sim_value` values each child as its whole card (engine names are owner cards: `Witch` mx 130 = a skeleton). One rule: 13.5 -> 8.2 vs 7.6 |
| H2 an engine damage / targeting law makes SIM pushes softer | **(c)** | Same engine + same CLX: I u40 = live per elixir (1.02x; archetypes 0.95-1.08x; value buckets 3-5 / 5-8 / 8-12 / 12+: 373 / 475 / 823 / 1,405 vs live 301 / 512 / 729 / 1,338). One-card pushes under E4 = live: Hog 359 vs 381, Barrel 612 vs 612, Valk 113 vs 88, Royal Hogs 470 vs 500 (live n 36-159) |
| H3 E4's policy is softer than humans | **(a) for E4 as a whole** | At matched value: 3-5 / 5-8 / 8-12 / 12+ = 263 / 393 / 625 / 921 vs live 301 / 512 / 729 / 1,338. At matched spend (value 5-8, spend 3-6 / 6-9): 400 / 361 vs 524 / 515. At matched answer time (<= 0 / 1-3 / > 3 s): 461 / 496 / 611 vs 558 / 628 / 761 |
| H3a ... pushes too spread / poor support | **(c)** | multi-card pushes: peak value on our half / total 0.65 vs 0.67, card spread 5.4 vs 5.4 s, value 9.7 vs 9.3. Same, yet 581 vs 760 HP |
| H3b ... wrong push timing | **(c)** | push start at our elixir < 4: 43% vs 44%; mean 4.62 vs 4.53 |
| H3c ... placement | **(b), small** | troop plays on our side 3.1% vs 5.6% (Miner-type), bridge 69.7% vs 63.3%, back 14.5% vs 16.5%. Not enough to explain 25%; untested causally |
| H3d ... wrong targets (into our X-Bow / Tesla) / spells on our defenders | **(b), untested** | E4 spell elixir around a push 2.5 vs live 2.1. Test: our building HP / tower HP split per push (needs a Tesla body in `hab`) |
| H4 OUR live execution makes live pushes hurt more | **(a) real, (c) as the main cause** | live CLX answers later (median +0.3 vs -0.2 s from the first crossing) and spends 0.9 less per push (7.7 vs 8.6). But inside each answer-time bucket E4 is still ~20% softer and I u40 is at or above live |
| H5 I u40 pushes are too big | **(a)** | 9.67 vs 7.61 elixir (2.58 vs 2.10 cards), uniformly at every elixir state of ours; 1x hardest (8.8 vs 6.8). Fits DIAG_12's tempo finding (troop elixir / min in 2x 38.3 vs 30.4) |

**Remainder:** what E4 does wrong inside a push of normal size, shape and timing is not identified. One-card pushes are
fine. Multi-card pushes lose 24% (581 vs 760 HP). The candidates are support quality (which unit tanks for which) and target
choice (H3d).

## 5. Measurement problems found on the way (a)

- **`ape_punish.sim_value` (H1).** `ape/ape_score.py` has the same function, and `exploit/tools/drift_check.py` imports
  ape_score. So it also feeds:
  - `hab_match`'s Log kill value (`scaled=False`): a Witch skeleton counts 5 elixir, so the SIM "Logs killing < 1 elixir"
    share is understated ((b): the size is not measured);
  - the threat metrics (lane value on our half >= 5);
  - the drift gate's defence-trade bar (-0.25, on a scale where the base sat at +5.5).
  - **What it does to EXPLOIT 1b and the drift gate (a)** (`push_cal/threat_check.py` -> `push_cal/threat_{clx_e4,u100_e4,clx_iu40}.out`;
    E4, 1,920 each):

    | metric | CLX old rule -> one rule | CLXII (u100) old -> one | CLXII - CLX old / one | live CLX |
    |---|---|---|---|---|
    | threats / match | 3.43 -> 2.90 | 3.44 -> 2.92 | +0.01 / +0.02 | 3.15 |
    | threat ignored share | 0.256 -> 0.240 | 0.269 -> 0.255 | +0.013 / +0.015 | 0.219 |
    | idle >= 4 s share | 0.185 -> 0.184 | 0.208 -> 0.204 | +0.023 / **+0.020** | 0.169 |
    | defence trade / push | +5.54 -> -0.45 | +4.99 -> -0.38 | -0.55 / **+0.07** | -0.12 |

    - The threat / idle gate metrics survive the fix: the CLXII effect +0.023 becomes +0.020.
    - The defence-trade drift does NOT survive (c). EXPLOIT 1b's "same direction as live on defence trade" (-0.55 SIM vs
      -0.55 live) came from CLXII meeting fewer child-inflated pushes (13.54 -> 12.80 elixir / push on the old rule).
    - On one rule CLXII trades the same as CLX in the SIM: +0.07; the per-set CIs [-0.57, -0.34] and [-0.50, -0.27]
      overlap.
    - The drift gate's "defence trade -0.25" bar should be re-based or dropped until the fix lands.
  - Proposed fix (not applied: another worker's tool, and the drift test on 33572 uses it):
    1. value SIM bodies with `push_cal.card_val` (= `body_value` on `engine_key(name)`, `top` = the card's max max HP
       in the match);
    2. drop max HP < 20.
  - The live side is unchanged by this fix.
- **The SIM board recording stops before the deciding tower falls.**
  - E4 blocks 741200 + 742000: 200 OT losses, 0 with the deciding fall in the last sample; same for 3-crown ends.
  - So "a princess fell" is 0.000 for every SIM OT push.
  - Proposed: `search_s0 --record-board` appends one final sample at the end tick (code, not config).
  - push_cal drops pushes whose window reaches the decided end, on both sides.
- **The live end tick lags the deciding fall by 1.5-3 s.** push_cal uses our deciding fall instead (an OT tower or the king).

## 6. Step 3: proposal, gate run, and why nothing was trained

**Gate runs on 32525** (`push_cal/gate_eval.sh` = exploit/ev.sh + per-line flags; CLX D3, all16, --record-board; seeds
741200 + 742000, 960 games each, paired with the existing rows):

| arm | knob (eval-time, config only) | pushes / match | elixir / push | HP lost / push | HP / elixir | conversion | conv. at our elixir < 4 | CLX win | push cells failed (all + 5 archetypes) |
|---|---|---|---|---|---|---|---|---|---|
| I u40 (base) | - | 6.86 | 9.67 | 786 | 81.4 | 0.251 | 0.353 | 477 / 960 | 12 of 42 |
| I u40 tau .55 | `--opp-tau 0.55` (W18 P-B) | 6.31 | 9.64 | 794 | 82.3 | 0.256 | 0.374 | 479 / 960 | 16 of 42: worse |
| E4 (base, the same 2 blocks) | - | 6.32 | 8.22 | 502 | 61.1 | 0.164 | 0.206 | 681 / 960 | 8 of 42 |
| E4 T .03 | `--opp-T 0.03` (10-14 calibration arm) | 6.38 | 8.12 | 478 | 58.9 | 0.157 | 0.205 | 707 / 960 | 10 of 42: no better, and weaker (CLX +2.7 pp) |
| I u40 decide 60 | `--opp-decide-every 60` | 6.38 | 9.94 | 861 | 86.7 | 0.275 | 0.416 | 514 / 960 | 22 of 42: much worse |
| live | | 6.52 | 7.61 | 607 | 79.7 | 0.202 | 0.268 | | |

- **None of the three eval-time knobs is a push-size knob (a).**
  - tau .55 removes pushes (6.86 -> 6.31) and leaves their size and damage unchanged. The low-elixir conversion even
    rises (0.353 -> 0.374).
  - decide 60 makes the opponent weaker overall (CLX +3.9 pp) but its pushes BIGGER and harder (9.94 elixir, 861 HP,
    low-elixir conversion 1.55x). A slower or more patient opponent banks elixir and commits more per push.
  - E4 at T .03 changes nothing on pushes and is weaker (CLX +2.7 pp).
  - So the push size has to be trained, not decoded.
- The CLX live-tap handicap (`--tap-loss`, DIAG_12 G2) could not be applied on 32525: its tree's `pipeline.e1_eval` has
  no `parse_tap_loss`. The gate runs above are without it. At 1.5-2% of taps it is small next to a 25% gap (b).

**Proposals (owner / lead decisions; none applied):**
1. **Fix the metric first (a, cheap).** Patch ape_punish's SIM valuation (section 5). Re-score drift_check's
   defence-trade bar and EXPLOIT section 2 cause 2 on it. EXPLOIT's "SIM opponents over-commit into cheap-to-defend
   pushes" is (c) on the fixed metric.
2. **Training opponent (I u40): calibrate push SIZE down ~20%, keep the efficiency.**
   - The matching knob already exists and is running: W18 R3 `play_cost` (cfg/oppW18R3_playcost_s74.yaml, 33401).
   - Score its snapshots on this push gate as well as O4: add `--record-board` to W18's gate evals, then run
     `push_cal.py sim` + `report`.
   - Not duplicated on 32525.
3. **Gate opponent (E4): it is 0.76x live on damage per push elixir and 0.77x on punishing our low elixir.**
   - A successor that leaks chip damage live is under-penalised on the E4 gate.
   - E4 at T .03 does not help (section 6 table).
   - Options: gate on a mix with I u40 / W7 R6 u20 (their errors have opposite signs), or replace E4 with a trained
     successor that passes this gate. This is a gate-definition change.
4. **Add the push gate to the promotion SIM checks.** All cells within +-25% per archetype, live = the 473 CLX matches
   or the most recent Ranked window. Rebuild live rows with `push_cal.py live`.
5. **Record the deciding fall in --record-board (code).**

**Why no opponent training was launched (the brief's condition):**
- The only config-level opponent-training change that targets the measured gap (R3 play_cost) is already W18's running
  round. Re-launching it on 32525 would duplicate W18.
- The three eval knobs do not move push size.
- The rest is metric fixes and gate-definition decisions.
- (b) Whether play_cost shrinks pushes or just removes plays the way tau did is untested. The decide-60 result says a
  less active opponent can bank and push BIGGER, so R3 needs this gate, not only ppm / style.

## 7. Files and reproduce

- `opp_model/push_cal/push_cal.py`:
  - `sim OUT SRC DIR...` (pod; reads DIR/*/D3/matches.jsonl with `hab`);
  - `live OUT` (laptop; clx_live.txt + habits cache + cache_extra; ~10 s);
  - `report ROWS...` (~30 s);
  - `selftest` (the one rule's asserts: a Witch skeleton = 1/3 elixir, not 5; passes on the laptop and the pod).
- Do NOT stage `push_cal/cache_extra/` (12 MB of live-log pickles). `push_cal/data/` (27 MB) is already gitignored.
- `push_cal/build_extra.py`: habits-format pickles for the 61 CLX matches newer than habits/cache (idle priority).
- `push_cal/threat_check.py DIR...` (pod): ape_punish's threat metrics on the old vs the one rule -> `threat_*.out`.
- `push_cal/gate_eval.sh`, `gate_q2.txt` (tau .55), `gate_q3.txt` (E4 T .03, I u40 decide 60).
  - Usage: `gate_eval.sh /abs/queue.txt` on 32525; it takes /workspace/cpu.lock.
  - A first queue with `--tap-loss` failed at startup (no `parse_tap_loss` in that tree) and was deleted.
  - Pod copy: `/workspace/pushcal/` (mirror repo `repo/` with symlinks into cb_stepd; nothing in cb_stepd, ckev or exploit
    was written).
  - Outputs: `/workspace/pushcal/ev/`, `/workspace/pushcal/out/*.jsonl`.
- Rows: `push_cal/data/*.jsonl` (per match: archetype, win, per-push records).
  - e4 (1,920), e4_2blk (its 741200 + 742000 half), iu40, iu40_t55, iu40_d60, e4_T03;
  - u100_e4 (CLXII, 1,920);
  - live, live_step6.
- Reports: `push_cal/report.out` (e4, iu40, iu40_t55, live) and `push_cal/report_gate.out` (the gate arms).
- Reproduce the gate table:
  `python push_cal.py report data/e4_2blk.jsonl data/e4_T03.jsonl data/iu40.jsonl data/iu40_t55.jsonl data/iu40_d60.jsonl data/live.jsonl`.
