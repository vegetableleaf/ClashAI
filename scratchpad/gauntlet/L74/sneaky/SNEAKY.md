# W20: the SNEAKY LOCK (owner 10-22) -- is it attempted, does it work, is it worth it?

Owner question: our X-Bow is placed, and ONE enemy blocker holds its attention (the X-Bow targets it, or is about to,
instead of the enemy tower). A Tornado pulls the blocker out of the X-Bow's range so the X-Bow locks the tower. Does the
model try this, does it work, and when is it worth it? Forcing it (rules, per-event rewards) hurt overall play before.

Labels: **(a)** measured (number given), **(b)** plausible but untested (the test is named), **(c)** contradicted
(evidence given). CIs are 95%: Wilson for plain rates, bootstrap over MATCHES for anything with several rows per match.

## Bottom line

1. **The opportunity is common. (a)** Live (CLX + CLXI): **2.89 per match [2.62, 3.15]**, 0.62 per X-Bow placed, in 338
   of 439 matches. Our X-Bow spends 42% of its alive time (245 of 582 min) shooting an enemy troop, not a tower.
2. **The model almost never attempts it, and the attempts do not lock. (a)** Live: **8 of 1,268 = 0.6% [0.3, 1.2]**
   (CLX 0.5%, CLXI 2/98). **Success: 0 of 8 [0, 32]**. In 6 of the 8 the blocker stayed in range. These were defensive
   Tornados that happened to touch the blocker, not lock pulls. SIM (CLX on fin15): 2.0% [1.8, 2.3] Tornado-in-window,
   lock within 3 s 14.9% [11.3, 19.4], below the 21.0% natural lock rate without a Tornado.
3. **Pros rarely do it either, but when they do it tends to work. (a, with a re-drive caveat)** Pros: 1.9% [1.5, 2.5] of
   1,629 matches' opportunities (0.036 per match). Lock 36% [25, 49] vs 18% natural. +0.045 [+0.010, +0.083] princess of
   X-Bow damage in 10 s vs matched no-Tornado moments. The pro board is a level-11 native RE-DRIVE (replayed engine
   board), so the outcome is a counterfactual estimate. The decisions are real.
4. **The model SEES the X-Bow's target. (a)** Two cue bits sit on our X-Bow's own unit token: "has a target" and "target
   is a crown tower". The X-Bow's bolts in flight also show their aim points. It does not see WHICH body is the target.
   With one troop in range, the two bits are enough to identify it. So the gap is the decision, not the input. Details
   in section 5.
5. **Forcing it has been measured to lose. (a, older setup)** The 10-10 fork-harness run (MECH=sneaky; model r3c vs
   the gen_v1 opponent at T .3, the SIM of that week; 582 forks, 480 matches): forcing the Tornado raised the lock rate **+16.3 pp** and tower damage **+112 hp at +10 s**. But it lost
   **-428 hp of tower difference by the end** and **-9.8 pp of win rate [-14.5, -5.1]**. The 10-09 rule test agrees:
   SIM -5.6 pp [-11.3, 0.0]. The lock works mechanically: 148/148 vs an idle opponent, 57.9% vs a playing one. It costs
   more than it gains.
6. **Why (b, rough arithmetic):** a held blocker usually holds the X-Bow only briefly (lone-blocker episode median
   1.7 s, p90 4.7 s). The X-Bow kills most blockers itself; 29% are gone within 3 s. A locked X-Bow does about **0.050
   princess per second** (242 hp/s, measured live). So a perfect pull buys roughly 0.09-0.24 princess. At the SIM rule's
   58% success, the expected gain is ~0.05-0.14 princess. The price is 3 elixir (~0.12-0.14 princess at the 10-15
   A3' exchange rate of 22-25 elixir per princess), plus losing the Tornado for defence. That is break-even at best,
   only in long blocks.

**Recommendation:** no rule and no per-event reward (both measured to lose). Do not add a training lever yet. First run
the per-opportunity fork counterfactual on CLX / fin15 (section 7, ~1.7-2.4 pod-hours; not run, the owner's 2-pod rule
applies). It looks for a stratum where Tornado-on-blocker beats the model's own choice on WIN, with CI low > 0 on a
held-out half. If no stratum passes, close the line as "measured, not worth it". If one passes, use the memory plan's
step 3: 5-10% scenario starts from real states of that stratum, win reward only.

## 1. Definitions

**Opportunity** (one per X-Bow + blocker pair; a gap > 1 s starts a new episode), from public board state in engine
units:
- our X-Bow alive on the board (deploying or active);
- an enemy PRINCESS in X-Bow range;
- exactly ONE enemy ground troop in range, and no enemy building in range (a Tornado cannot move a building);
- attention, one of two kinds:
  - **held**: the active X-Bow currently targets that troop;
  - **about**: the X-Bow is still deploying, and the troop is closer than the nearest in-range princess. The targeting
    rule picks the closest target when the X-Bow activates. 51% of these episodes do turn into held;
- Tornado in our hand (the last decision's hand) and own elixir >= 3. The opportunity tick t0 is the first frame of the
  episode where both hold.
- Lone-blocker episodes without Tornado-in-hand + 3 elixir: 592 of 1,860.

**Range rule** (SIM card table 160402017): in range = centre distance - 0.6 (X-Bow radius) - target radius <= 11.5 tiles
(princess radius 1.0, so a princess centre within 13.1 t). The X-Bow is GROUND ONLY (attacks_air false), so an air unit
can never hold it. **Air blockers: (c)** by the card data, and by the reader: 0.15% of X-Bow target frames are tagged
air, all skeleton_barrel / balloon card ids, i.e. ground bodies sharing an air card's id.

**The X-Bow's current target**:
- live: the reader's phase-3 attack row (`target_gen`) through `pipeline/live_unit_state.LiveCues.units`. This is the
  same function, with the same far-target drop, that builds the model's cue input. Validated against the X-Bow's own
  bolts in flight (projectile source -> target): **same body on 98.4%** of 145,785 bolt frames (a);
- SIM: the engine's X-Bow `target_uid` from W14's opt-in trace (`o3_trace`);
- pros: no target field. The targeting rule is applied to the re-drive board: keep the target while it lives and stays
  in range, else take the closest in-range ground target. On live frames this rule matches the reader's target class
  **88.9%** of the time (troop 95.8%, tower 79.0%; n 1,699 frames at the pro 1-s cadence; `rulecheck.out`).

**Attempt**: our own Tornado decided from 0.5 s before to 2 s after t0, landing within 5.5 tiles (+ the blocker's radius)
of the blocker. **Any Tornado** = any own Tornado in that window.

**Success (lock)**: the X-Bow targets an enemy crown tower within 3 s after the Tornado lands. **Natural lock** = the same
within 5 s of t0 (the 2-s window + 3 s), used for opportunities with no attempt.

**Value**: enemy-tower HP lost while the X-Bow targets that tower over the next 10 / 15 s (pocket.py's rule), in princess
units. **Matched** = attempt minus the mean of no-attempt opportunities in the same (kind, phase, X-Bow hp band, own elixir
band) stratum.

## 2. Live (a)

Data: every non-dry main-account log since 10-19 14:02 whose checkpoint is CLX or CLXI (registry sha). That is 507 logs:
439 analysed (414 CLX, 25 CLXI); 48 classic-challenge logs at level-11 towers (3052), 19 without frames and 1 without
the deck were skipped. Result = the CLX Ranked index when present, else the end event.

| | all | CLX | CLXI |
|---|---|---|---|
| matches / X-Bows | 439 / 2,039 | 414 / 1,895 | 25 / 144 |
| opportunities per match | **2.89 [2.62, 3.15]** | 2.83 [2.56, 3.10] | 3.92 [2.64, 5.32] |
| held / about | 604 / 664 | 560 / 610 | 44 / 54 |
| **attempt** | **8/1,268 = 0.6% [0.3, 1.2]** | 6/1,170 = 0.5% [0.2, 1.1] | 2/98 = 2.0% [0.6, 7.1] |
| any Tornado in the window | 15 = 1.2% [0.7, 1.9] | 12 = 1.0% | 3 = 3.1% |
| **success** | **0/8 [0, 32.4]** | 0/6 | 0/2 |
| natural lock <= 5 s (no attempt) | 21.6% [19.4, 23.9] (held 32.3, about 11.8) | 22.1% | 15.6% |
| blocker gone <= 3 s | 29.4% | 29.6% | 27.6% |
| X-Bow dmg 10 s / 15 s, no attempt | 0.058 / 0.093 | 0.061 / 0.096 | 0.033 / 0.055 |
| X-Bow dmg 15 s, attempt minus matched | -0.076 [-0.103, -0.044] (n 8) | -0.074 | -0.055 |

- **Blockers**: Valkyrie 159, Knight 111, Mega Knight 75, Firecracker 56, E-Wizard 44, PEKKA 40, Hog 39, Executioner 36,
  Witch 35, Dart Goblin 33. Phase: 1x 269, 2x 504, OT 495. Elixir at t0 is 3.98 on average.
- **The 8 attempts**: Giant Skeleton, Valkyrie, Knight, Bowler, Magic Archer, Mini PEKKA, Hog, Dart Goblin.
  - All decided by the model (`forced` false).
  - The blocker left range or died in 2 of 8.
  - No lock in any of them.
  - 1 of the 8 matches won.
  - The damage difference is confounded: these Tornados were defensive pulls.
- **Every own Tornado cast while our X-Bow lived** (167, 0.38 per match). The X-Bow's target at that moment:
  - troop: 93; the tower was locked within 3 s of the landing in 4/93 = 4.3% [1.7, 10.5];
  - tower: 36;
  - none: 35.
- **Superset** (the SIM-comparable definition: the active X-Bow targets ANY enemy troop, any number in range):
  - 5.41 per match;
  - Tornado in the window 1.5% [1.1, 2.1];
  - lock 4/36 = 11.1% [4.4, 25.3] vs 16.7% natural.
  - With 2+ troops in range: attempt 1.8%, lock 15.4%. With 1 troop: attempt 1.1%, lock 0/10.

## 3. SIM (a, superset only)

CLX (5d212358) on fin15 at all16, seed block 741200, with W14's pos telemetry. That is 10 opponent configurations
(W14 B u20 / E u40 / I u40, E4, R6 u20, W18 I u40 at tau .35-.75), 4,800 games. The trace has no body positions, so
"lone blocker" cannot be checked: the SIM opportunity is the superset (X-Bow held by any non-tower target, enemy princess
in reach). Episodes are dropped when an enemy building was deployed within reach (the target might be that building).
Our hand comes from the play order (a card returns after 4 more plays), and elixir is estimated from the logged
elixir-at-play plus regen.

| | value |
|---|---|
| opportunities per match | 3.02 [2.89, 3.15] (per opponent 2.21-4.46) |
| Tornado in the window | **295/14,512 = 2.0% [1.8, 2.3]** (per opponent 1.2-2.5%) |
| lock <= 3 s after it | **44/295 = 14.9% [11.3, 19.4]** |
| natural lock <= 5 s, no Tornado | 21.0% [20.4, 21.7] |
| X-Bow dmg 10 s / 15 s, Tornado minus matched | -0.011 [-0.023, +0.002] / -0.016 [-0.032, +0.001] |
| every own Tornado while the X-Bow targets a unit | 1,192; lock <= 3 s 10.3% [8.7, 12.2] |

The live superset Tornado rate (1.5%) is near the SIM's (2.0%): the habit transfers. Its lock rate after a Tornado, 11%,
is also close to the SIM's 15%.

## 4. Pros (a for the decisions; the outcomes are a re-drive estimate)

The icebow8 Path of Legend sides (`invlib.pro_matches`): 1,629 matches. Decisions and hands are real. The board is the
native re-drive at level 11 with 1-s frames, and the target is inferred by the rule (section 1).

| | held | about | both |
|---|---|---|---|
| opportunities | 1,984 | 1,012 | 2,996 = **1.84 per match [1.74, 1.94]** |
| attempt | 1.6% [1.1, 2.2] | 2.7% [1.8, 3.9] | **1.9% [1.5, 2.5]** (0.036 per match) |
| any Tornado in the window | 8.8% | 7.7% | 8.4% |
| success | 12/31 = 38.7% | 9/27 = 33.3% | **21/58 = 36.2% [25.1, 49.1]** |
| natural lock <= 5 s | 22.1% | 10.4% | 18.1% |
| X-Bow dmg 10 s, attempt minus matched | +0.037 [-0.013, +0.097] | +0.053 [+0.009, +0.106] | **+0.045 [+0.010, +0.083]** |
| match win with / without attempt | 0.45 / 0.55 | 0.44 / 0.49 | 0.45 / 0.53 (confounded) |

- Pros use Tornado near a blocked X-Bow 7x as often as CLX (8.4% vs 1.2%), but the deliberate pull is still rare.
- When pros do it, the blocker leaves range in 33 of 58 cases (live CLX: 2 of 8).
- Their lower win rate in those matches is association only. Pros pull when the X-Bow is in trouble.

## 5. Does the policy see the X-Bow's target? YES, as two bits (a)

- Cue input (step c), one row per unit token. `pipeline/model_gen.py:45-51` `cue_vector`:
  [known, state x7, charging, hidden, **has_target, target_is_tower**, attack phase x3, progress, status x5, slow_frac].
  It is added to each unit token's embedding by `cue_in` (`pipeline/model_gen.py:206-209`).
- CLX has a TRAINED cue layer. The checkpoint holds `cue_in.weight` 128 x 22 (column norm: target_is_tower 0.096,
  has_target 0.047, comparable to the other columns).
- Live source: `pipeline/live_unit_state.py:151-161` (phase-3 `target_gen`, far-target drop), `:197`
  (`target_is_tower`), `:211` (-> `cue_vector`). `pipeline/live_gen.py:354-359` feeds the cue and refuses to play a
  cue model without it. SIM twin: `pipeline/e1_eval.py:697-726` (the engine's attack target).
- In the live logs, every decision with our X-Bow on the board had an X-Bow unit token (301/301 in the 10-19 14:02
  log) and a logged cue block. 3.4% of the X-Bow frames (12,106 of 358,444) are degraded, and those read "cue unknown".
- Projectile tokens: `pipeline/projectile_observation.py:19` (PROJECTILE_COLS includes target_x / target_y) and `:168`.
  feature_version 6 target patches: `pipeline/model_gen.py:145-167`. CLX is feature_version 6 with
  `projectile_target_in` weights, so the bolts' aim points are visible too.
- NOT encoded: the target's identity (no pointer from the X-Bow to the body it shoots); `pipeline/obs_contract.py` has
  no target field. With exactly one troop in range, "has_target and not tower" identifies it.
- **"The model cannot see it" is (c).**

## 6. Mechanism checks (`dropcheck.out`, 80 live logs)

- Acquisition edge distance: median 5.26 tiles, p90 10.08, all <= 11.5 (n 191). This matches the 11.5 range. (a)
- Drops while the old target is still alive: n 30, median 3.74 tiles. Only **1** was beyond 11.5. A troop leaving range
  and the X-Bow then retargeting essentially never happens live, so the SIM's keep distance (drop at ~11.85 tiles edge;
  Knight acquired at 12.6 / dropped at ~12.95 centre, from the 10-09 rule) is **untested live (b)**. It needs a
  classic-challenge parity scenario (our X-Bow on a Knight, Tornado it out) before trusting the SIM's B branch.
- A locked X-Bow costs the tower **242 hp/s = 0.050 princess/s** (all sources on that tower; 1,176 s of lock). (a)

## 7. Fork-harness counterfactual: design (NOT run)

**Tool:** `L74/mechanic_fork/mech_fork.py`, the forked same-moment harness. It is a measurement tool; drills are closed.
It forks the full engine plus both sides' Python state with `search_s0.fork_into`. On 10-10 its A-replay was
hash-identical at +10 s, +20 s and the end in 56/56 checks.

**New trigger `MECH=sneaky2`, from engine state** (no probe decision needed):
- the section-1 opportunity, computed from `sim_unit_state.extract` (positions + attack targets, the cue's own source);
- held or about; Tornado in hand; elixir >= 3;
- fork at the first decision of each episode.

**Branches:**
- **A**: the original match (the model's own choice). If A itself casts Tornado on the blocker within 2 s (expected
  ~1-2%), the "best non-Tornado action" is the model re-decoded with Tornado masked. Otherwise A already is it.
- **B**: Tornado now, at the cell that pushes the blocker furthest past the X-Bow's keep distance. This is the
  `sneaky_lock_plan` forward model in `L74/drills/sneaky_rule.py` (a copy of the 10-09 rule). Fallback: 5.5 tiles beyond
  the blocker on the X-Bow -> blocker ray. Then the model plays as usual.
- **B2** (optional): Tornado at the model's own Tornado cell (cell head conditioned on Tornado). It asks whether the
  model's placement would work if it chose to cast.

**Recorded per branch:**
- lock within 3 s;
- X-Bow tower damage at 10 / 15 s;
- tower difference at +10 / +20 s / end;
- elixir; win.

**Strata (all public):** kind; blocker card / elixir / hp; the blocker's distance to the range edge; X-Bow age and hp;
enemy princess hp; our elixir after the Tornado; crown state; phase; enemy troops on our half (threat); Tornado's cycle
position.

**Decision rule (pre-registered):**
- paired B - A on WIN, bootstrap over matches, overall and per stratum;
- fit a small tree on seed blocks 1-3, evaluate on blocks 4-6;
- "worth it" = a stratum whose held-out win gain has CI low > 0. None -> close the line.

**Setup:** CLX (and the current successor) vs W14 I u40 (calibrated) and E4, fin15, all16, `--crown-log` + O3_POS.
6 seed blocks = 2,880 matches.

**Size:**
- ~3 forks per match -> ~8,600 forks: win CI about +-1.2 pp overall, about +-3.5 pp per 1,000-fork stratum. The 10-10
  run had +-4.7 pp at 582 forks.
- Cost per match ~ 1 + 3 x 0.5 = 2.5 game-equivalents: each fork re-plays about half a match.
- Base SIM eval speed: 480 games in 5.6 min on a 54-core 4090 pod (w14c_Iu40_pos run.log).
- 2,880 x 2.5 = 7,200 game-equivalents ~ **1.4 pod-hours**; B2 adds ~0.7; dev pass (96 matches) + faithfulness checks
  ~0.3.
- **Total ~1.7-2.4 pod-hours** of CPU, no GPU.

**Code needed (~1 worker day):**
- `sneaky2` in mech_fork.py (trigger + B cell + per-fork strata);
- a stratified summary on top of `mech_summary.py`;
- a fin15 / Hero-IW dry run: forks cannot snapshot during a live Bowler-hero buff; those rounds are skipped and counted,
  as on 10-10.

**Caveat:** B's value rests on SIM Tornado pull parity (W1: Tornado 0.82, light units 0.59-0.66) and the untested live
keep distance (section 6). Run the parity scenario first, or report B with that caveat.

## Files (`scratchpad/gauntlet/L74/sneaky/`)

| file | what |
|---|---|
| `sneaky.py` | `live` / `sim` / `pro` extractors, `report`, `rulecheck` (rule vs reader), `dropcheck` (keep / drop distance, lock dps), `selftest` |
| `report.out` | all tables (live, live superset, SIM per opponent, pros, rule check) |
| `live_matches.jsonl`, `live_opps.jsonl`, `livesup_opps.jsonl` | live per-match / per-opportunity rows (~25 min to rebuild) |
| `dropcheck.out`, `rulecheck.out`, `rule_check.json` | mechanism checks |
| `sim_*.jsonl`, `pro_*.jsonl` | not committed (10 MB; `sneaky.py sim` / `pro` rebuild them in about 1 min each) |

Run (icebow venv, idle priority, single thread): `python -B sneaky.py live --fresh` (~25 min for 507 logs), `sim`, `pro`,
`report > report.out`. Public information only: the opponent's hand, deck and elixir (and the frame's opp_elixir_est) are
never read.
