# THE SPELL EXPERIMENTS — measurement ledger

HANDOFF §6-PRIORITY (owner's standing request), rescoped by `rollout_search.md` §5.1 / §6.2 / §7a.
Harness `scratchpad/spell_arms.py` (derived verbatim from `scratchpad/rollout_search.py`; not
imported by any source file, not shipped). Probes `scratchpad/live_grid_probe2.py`,
`scratchpad/live_assist_probe.py`, `scratchpad/king_mask_probe.py`.

---

## 0. PRE-COMMITMENT (written before any n=300 arm was run)

### 0.1 Why these are DECISION-TIME arms and not training arms
§6-PRIORITY's design ("matched control, same init, same episode count") costs **~2 h per arm**
(measured: `ARM_control4` 1 h 50 m, `ARM_fix23b` 1 h 52 m, `ARM_clipfix` 1 h 53 m at 2600 episodes),
and §4n's own post-mortem is that *"a 1.5 h training arm was spent on a question the instrument
could never answer — compute the detectable effect size BEFORE running the arm"*.

Both spell questions have a **prerequisite** that a decision-time arm answers in 8 minutes at far
higher power: *if the rule is FORCED at decision time, does it help at all?* If forcing a restraint
rule with ENGINE GROUND TRUTH does not move the primary metric, then training a policy to
approximate that rule from a degraded observation cannot either, and a training arm would be spent
on a dead question. So every arm here is an **upper bound** on what the corresponding training
change could deliver, and each is labelled as one.

This is the same instrument, the same seeds and the same statistics as `rollout_search.md`, so the
results sit on one scale with the search numbers.

### 0.2 Fixed protocol
* **Reference policy** — `scratchpad/_rs_policy.pt`, VERIFIED md5 `9dd42804fdf6709d5387ec61f188cb83`
  identical to `icebow/data/policy_BEST_m18000_20260826.pt`. No trainer running (§4s trap).
* **n = 300 matches per arm**, seeds `5_000_000 … 5_000_299`, identical across every arm → PAIRED.
* **GREEDY selection in every arm** (`rollout_search.md` §7a: `play.epsilon: 0.0`, eval and live both
  take argmax; a spell A/B graded on the SAMPLED dump rate grades behaviour that never ships).
* **Primary outcome: TOWER DELTA**, the same continuous metric the search experiment used.
  **Secondary: winrate, crown delta, dump rate, casts/match.**
* **THE BAR: |paired mean difference| / sem >= 2.0, or NO MEASUREMENT.** sem reported regardless.
* `PYTHONHASHSEED=0`, `torch.set_num_threads(1)`, `domain_rand` off, ladder opponent pool.
* **Multiplicity, declared up front:** Experiment A is a MONOTONE FAMILY (K = 1, 2, 3) plus one
  independent criterion (elixir trade). One arm at 2σ with the rest flat is NOT a result; a trend
  across K is. Experiment B is a single pre-named arm.

### 0.3 ⚠ THE BASELINE HAD TO BE RE-MEASURED. `rs_base.json` IS NO LONGER REPRODUCIBLE.
`scratchpad/spell_arms.py` with every arm OFF is byte-identical to `scratchpad/rollout_search.py`
on this tree (12 matches, full records incl. `cast_rows`: IDENTICAL). Both now disagree with
`rs_base.json`, which was produced before commit **d9b20d6** *("ruling 29: price all 20 spawned
bodies")* landed at 14:14:51. Seed 5000000 goes 371 steps / 49 plays (ledger) → 215 / 17 (today).

Ruling 29 changed `spec.elixir` for 20 spawned bodies, which feeds `threat_value` → the threat
vector → the observation → the policy's action stream. **This is §4q's "arms hours apart differ by
every commit between them" trap, and it bites EVAL arms too.** Every number below is measured on
the current tree against its own baseline, and no arm here is compared to a `rollout_search.md`
number without saying so.

### 0.4 The arms
```
EXPERIMENT A — RESTRAINT (state-conditioned, NOT a scalar).
  A spell card is REFUSED when THIS board offers it no legal cell that would connect. The gate,
  the cell head and every other card are untouched; the only variable is "may this spell be chosen
  at all, on this board". A scalar gate threshold cannot express it (rollout_search.md §6.2 swept
  tau 0.02->0.60; 0.25 is optimal and worse in BOTH directions).
  Geometry MIRRORS THE ENGINE (§4v's retraction): a rolling spell is a CORRIDOR
  (|dx|*18 <= spell_radius half-width, -1.0 <= dy_forward*32 <= roll_len, ground only), the tornado
  is a pull DISC of pull_radius, a blast is a disc of spell_radius.
    k1     : refuse unless the best legal cell catches >= 1 enemy body
    k2     : ... >= 2 bodies
    k3     : ... >= 3 bodies
    trade  : refuse unless the ENEMY ELIXIR caught (each body = its card's elixir / bodies dealt)
             is >= the spell's own elixir. The deck's own elixir-trade currency, not an invented
             value function.
    ctl    : CONTROL — ban the same NUMBER of playable cards per decision, chosen UNIFORMLY AT
             RANDOM, at the winning arm's measured rate. Holds "the arm plays less / plays a
             different card" constant so only the TARGETING criterion differs.

EXPERIMENT B — PLACEMENT CEILING.
    aim    : keep the policy's CARD, move the CELL to the engine-true best-hitting legal cell
             (ties broken by the policy's own cell logit). This is the CEILING of a perfect spell
             placement head — strictly above any doctrine prior or entropy floor — so a null here
             closes the placement question with a BOUND rather than with one prior's failure.
             rollout_search.md §5.2 independently bounds cell search at +3.3pp / +0.216 tower.
```

### 0.5 What these arms CANNOT establish (stated before the numbers)
* They use **engine ground truth** for the geometry. The policy sees a degraded detector
  observation (`sim_detector_recall 0.82`). Every arm is therefore an **upper bound**, not an
  estimate of what a trained policy would achieve.
* A win here licenses a training arm; it does not substitute for one.
* Nothing here touches the §4t eval decay.

---

## 1. THE HARNESS, and the check it had to pass

`scratchpad/spell_arms.py`, a verbatim copy of `scratchpad/rollout_search.py` with the arms added
behind flags that all default OFF. Same process shape: `torch.set_num_threads(1)`,
`PYTHONHASHSEED=0`, one `SimMatchEnv` reused with `env.rng.seed(seed)` before every `reset()`,
`domain_rand` OFF, ladder opponent pool.

```
CHECK: spell_arms.py with every arm OFF vs rollout_search.py, separate processes, 12 matches
       full records including per-cast geometry rows          IDENTICAL
```

The arms live in `greedy_action()`, which is byte-identical to `train_sim_ppo.choose_greedy` for one
env. Nothing else in the harness is touched.

### The geometry MIRRORS THE ENGINE (§4v's retracted finding is the reason this is spelled out)
```
roll  (the_log)  engine._tick_roll     -1.0 <= (uy-cy)*fdir*32 <= roll_len (9.6)
                                       AND |ux-cx|*18 <= spell_radius (1.95 HALF-width)
                                       ground bodies only; _LOG_BACK_SLOP = 1.0
pull  (tornado)  engine._tick_vortex   hypot((ux-cx)*18,(uy-cy)*32) <= pull_radius (5.5)
blast (rocket)   engine._resolve_spell hypot(...) <= spell_radius (2.0); ground_only skips flyers
```
A rolling spell is a CORRIDOR, never a disc. `spell_radius` is its HALF-WIDTH.

---

## 2. BASELINE on this tree, 300 matches

```
n=300   winrate 43.0%   tower delta -0.841   crown delta -0.373
        plays/match 32.4   casts/match 7.87   dump 36.7%
        mean elixir 3.35   steps at >=6 elixir 13.6%   mean match length 175.4 s   1.93 s/match
```
Per-card GREEDY dump rate (zero enemies inside the spell's own radius at the instant of the cast):
```
the_log   1671 casts   46.2% dumped
tornado    561 casts   15.0% dumped
rocket     128 casts    8.6% dumped
```
Consistent with `rollout_search.md` §7a's independent greedy read (the_log 52.7%, tornado 14.2%)
and NOT with §4r's sampled 73% / 58%. **The mode is the explanation, as §7a said.**

⚠ This baseline is 43.0% / -0.841 where `rollout_search.md` reads 37.0% / -0.928 on the same seeds
and the same checkpoint. The difference is commit **d9b20d6**, not noise — see §0.3.

---

## 3. ⚠⚠ THE LIVE PATH — FOUR DEFECTS, THREE OF THEM SHIPPED-CODE UNITS ERRORS

The owner's original report was about LIVE play: *"the model dumps spells all over the place, almost
never on an enemy target."* `rollout_search.md` §7a showed greedy dumps the Tornado at only ~10-15%
in sim, so the sim policy does not explain what he saw and the live path was the first suspect.
It is not clean. All four were found by reading + offline probes; no live session was run.

### 3.1 ✅ CLEAN: the grid round trip
`cell_center -> coords_to_grid -> cell` is exact on **0 of 432 cells wrong** in the live
`ActionSpace`. §4.2's 22/24-row error is fixed and has stayed fixed.

### 3.2 ⚠ SHIPPED, FIXED HERE: the enemy-KING keep-out was comparing FRAME coords to a BOARD anchor
`ActionSpace.no_king_mask` builds `king_xy` from `sim.board.king_tile` — **board-space,
unconditionally** — and compares it against `cell_center`, which in the LIVE space returns FRAME
coordinates. That is conflicts.md **RS-4's trap in shipped code**, not in a probe.
```
                                 live blocked   sim blocked
before                                12            22
```
The ten extra cells sit **1.54 - 2.69 TRUE tiles** from the enemy king — inside the 2.6-tile
clearance the mask exists to enforce — and four of them (gy=2 gx=7/10, gy=3 gx=8/9, at 1.54-1.74
tiles) are inside a Rocket's own **2.0-tile blast**. So live could select a rocket cell that lands
on the enemy king and wakes it: precisely the self-inflicted penalty the mask was written to make
impossible (*"a rocket landed on the king within minutes of raising epsilon. A reward cannot stop a
random choice; only a mask can."* — user, 2026-08-16).
**FIXED**: convert through `warp.frame_to_board` before the distance test. In the sim the warp is
the identity so this is a no-op there. Both decks, `test_king_mask_units.py`.
⚠ It is only **10 of 432 cells (2.3%)**, so it is a real defect and it is NOT the explanation of the
owner's report. Reported as what it is.

### 3.3 ⚠ SHIPPED, FIXED HERE: the TORNADO was being snapped onto Crown Towers
`play.py` redirects a cast to the weaker enemy princess via `reward.weaker_princess_cell` whenever
the card is in `anywhere_ids` — the comment says *"a rocket / offensive miner at a princess"* but
the SET is every anywhere-spell, and for icebow that is **{rocket, TORNADO}**. A Tornado centred on
a Crown Tower pulls nothing (`engine._tick_vortex` refuses to drag a building) and chips it for a
rounding error, so the assist converts a chosen cast into a guaranteed whiff.
```
MEASURED: 80 of 432 cells = 18.5% of the board lie inside the +/- spell_tower_aim_radius (0.12)
box of an enemy princess, spanning board tile-y 0.7 .. 10.0 in BOTH lanes.
```
So roughly **one tornado cast in five** was being redirected onto a building it cannot affect —
a live-only dumping mechanism the sim never sees, on top of the policy's own placement.
The rule already existed and simply never reached live — `sim/env.py::spell_target_mask`:
*"a live enemy princess is a valid chip target for a DAMAGE spell (never for a pull)"*.
**FIXED**: gate the snap on the card DB's `pull` flag. Both decks,
`test_pull_spell_no_tower_snap.py`. hogeq's current deck has no pull spell, so the code lands in
both and the behaviour changes only in icebow.

### 3.4 ⚠ MEASURED, NOT FIXED (deliberately): the live whiff verdict mixes FRAME coords with TILE radii
`reward.spell_whiffed` takes a radius **in TILES** and scales the two axes by 18 and 32 — correct
in BOARD space. Every live caller feeds it FRAME coordinates: `play.py`'s spell mask and
`env.py`'s live reward both pass `actions.cell_center(...)` and `TeamTracker` tracks, which are
screen-normalised. The frame->board slope is **not 1 and not constant** (the perspective warp runs
2.67 board-units-per-frame-unit at the enemy end and 1.04 at ours), so a radius meant to be 4.5
tiles actually spans:
```
board row (tile-y)     0.7   3.3   8.7  13.9  19.3  24.0  30.0
vertical reach (tiles) 12.03 12.03  5.63  7.74  7.74  4.69 10.04     (intended 4.50)
horizontal             5.53 at every depth                           (intended 4.50)
```
i.e. **1.0x to 2.7x too generous, varying with depth** — the live reward systematically
UNDER-charges whiffs, worst at the enemy end where a rocket most needs the verdict. It is the exact
bug `spell_whiffed`'s own docstring records fixing once (*"silently stretched every blast
vertically"*), reintroduced by the caller rather than by the function.
**NOT SHIPPED HERE.** It touches ~10 call sites across `env.py` and `play.py` in two decks and it
moves the LIVE REWARD, so it is its own change with its own verification (§4q: one change at a
time). ⚠ Note `play.spell_target_mask: false` today, so the mask half is currently inert; the
`env.py` reward half is not.
Same family, same call sites, not separately re-measured: `nado_king_cell`, `spell_intercept_cell`,
`pump_rocket_cell` and `weaker_princess_cell` all compare RAW normalised distances against a single
radius, where the two axes have different tile scales (`reward.py` lines 224, 231, 244, 275, 314).

### 3.5 The live OBSERVATION is clean
`play.py` / `detect_obs.py` / `env.py` all convert detections and tower anchors through
`warp.frame_to_board` before painting the canvas or building the threat vector. The perception the
policy is shown is board-space in both live and sim. **The asymmetry is action-side only.**

### 3.6 ⚠⚠ AND THE BIGGEST ONE IS NOT IN LIVE AT ALL — the SIM'S action space is clamped by SCREEN constants
Found while chasing 3.2. `sim/env.py::_board_action_space` rebuilds `ActionSpace` with board-true
overrides (`arena_box`, `deploy_top`, tower anchors, board edges) but does **not** override three
config values that `cell_center` applies to whatever space it is in:
```
label.arena_top / label.arena_bottom   keep a TAP off the card tray
buttons.chat_avoid_box                 keeps a TAP off the emote icon
```
Applied to BOARD coordinates they clamp the sim's own action space. MEASURED, **identical in both
decks**, 18x24 = 432 cells over an 18x32-tile arena:
```
96 of 432 cells (22.2%) deploy somewhere OTHER than their own board centre, worst 6.37 tiles
only 372 DISTINCT deploy points exist -> 60 cells are EXACT DUPLICATES of another cell
   e.g. grid (0,19) (0,20) (0,21) (0,22) (0,23) ALL deploy at board tile (0.50, 24.96)
board tile-y outside 3.20 .. 27.52 is UNREACHABLE (the arena is 0 .. 32)
attribution: arena_top 36 cells | arena_bottom 54 cells | the EMOTE-ICON box 15 cells
```
Three consequences that connect to numbers already in this project's ledgers:
1. **`never_rocket_their_king` scores 0-17%** (§4t/§4r). All 36 cells of grid rows 0 and 1 clamp to
   board tile-y **3.20**, and the enemy king sits at tile-y **3.0** — so 8.3% of the action space
   lands on the king, and the trainer masks **none** of it: `train_sim_ppo.py:199` sets
   `allcells_mask = torch.ones(n_cells)`, so `no_king_mask` is never applied in training at all.
   The policy is not choosing to rocket their king so much as being unable to avoid it.
2. **60 duplicate actions.** The cell head is being asked to distinguish actions that are literally
   the same action. That is a STRUCTURAL contributor to §4r's near-uniform cell head, independent of
   any learning failure, and no entropy floor or doctrine prior can fix it.
3. **Cross-check.** After fixing 3.2, live and sim still disagreed on exactly 6 cells — and in every
   one of them LIVE is right and the SIM is wrong, because the sim clamps grid row 0 from its true
   tile-y 0.67 up to 3.20. An independent second sighting of the same bug.

**And the clamps were inert where they belong**: in the LIVE `ActionSpace` all three fire on
**0 of 432 cells**, because the warped grid already lands inside them. So they were doing nothing
in live and mangling a fifth of the action space in the sim. This is the mirror image of the §4.2 /
detector-audit trap — not an offline tool reading live coordinates, but a **live-screen constant
applied to the board**.
**FIXED** in both decks (`test_sim_board_cells.py`). ⚠⚠ **THIS CHANGES THE SIM'S ACTION SEMANTICS
AND REQUIRES A RETRAIN.** 96 cells move, and every placement the reference checkpoint learned,
every doctrine cell and every drill reference line was calibrated against the clamped mapping.

---

## 4. EXPERIMENT A -- RESTRAINT. MEASURED, AND THE MECHANISM IS MOSTLY *VOLUME*, NOT AIM.

All arms n=300, same seeds, paired against section 2's baseline, GREEDY.

```
arm       rule                                    win%  towerd  casts/m  dump%  len(s)
base      --                                      43.0  -0.841    7.87    36.7  175.4
k1        spell needs >=1 body at its best cell   41.7  -0.866    7.47    32.9  176.2
k2        ... >=2                                 37.7  -0.818    6.12    23.5  180.7
k3        ... >=3                                 47.7  -0.607    4.32    18.5  183.5
k4        ... >=4                                 50.0  -0.508    2.64    17.3  180.3
k5        ... >=5                                 49.7  -0.444    1.56    11.3  181.6
k7        ... >=7                                 52.0  -0.458    0.53     9.4  181.0
knever    NEVER cast a spell                      50.0  -0.534    0.00     0.0  179.4
tr1       enemy elixir caught >= the spell cost   42.0  -0.824    7.01    32.5  176.4
ctlany    CONTROL: ban random cards               36.7  -0.875    8.46    33.4  178.2
ctlS3     CONTROL: random SPELL bans, k3 volume   41.3  -0.815    4.41    40.1  173.8
ctlS5     CONTROL: random SPELL bans, k5 volume   50.3  -0.452    1.52    45.1  177.5
```
```
PAIRED vs base          towerd delta    sem   sigma      crownd sig    win pp    sig
k1                          -0.025    0.036   -0.69         -1.07       -1.3   -0.73   NO MEAS.
k2                          +0.023    0.060   +0.38         -0.81       -5.3   -1.95   NO MEAS.
k3                          +0.233    0.065   +3.58         +2.74       +4.7   +1.65   SIG
k4                          +0.332    0.065   +5.12         +3.71       +7.0   +2.55   SIG
k5                          +0.397    0.063   +6.31         +3.89       +6.7   +2.45   SIG
k7                          +0.383    0.066   +5.82         +4.48       +9.0   +3.26   SIG
knever                      +0.306    0.071   +4.33         +3.60       +7.0   +2.44   SIG
tr1                         +0.017    0.044   +0.38         -0.31       -1.0   -0.48   NO MEAS.
ctlany                      -0.035    0.062   -0.57         -2.13       -6.3   -2.37   NO MEAS.
```
**The pre-committed bar wanted a TREND across K, not one lucky arm. It is monotone** on tower
delta (-0.025, +0.023, +0.233, +0.332, +0.397), on crown delta, and on the dump rate
(36.7 -> 32.9 -> 23.5 -> 18.5 -> 11.3 -> 9.4%), and it plateaus at K >= 5. It is not a
multiplicity artefact.

### 4.1 THE CONTROLS SAY MOST OF IT IS VOLUME. Read this before quoting any number above.
Arm-against-arm, paired on the same 300 seeds:
```
ctlS3 -> k3      same 4.3 casts/m, criterion vs RANDOM spell bans   +0.207  2.98 sigma  SIG
ctlS5 -> k5      same 1.5 casts/m, criterion vs RANDOM spell bans   +0.009  0.16 sigma  NO MEAS.
base  -> knever  cast NO spells at all, ever                        +0.306  4.33 sigma  SIG
knever -> k7     0.53 SELECTIVE casts per match vs none at all      +0.077  2.24 sigma  SIG
k3    -> k5      same criterion, fewer casts                        +0.164  3.16 sigma  SIG
```
Three statements, in order of size:
1. **The single largest effect is that this policy should barely cast its spells at all.** Deleting
   all three from its action set -- three of eight cards, a Log, a Tornado and the deck's only
   Rocket -- is worth **+0.306 tower fractions and +7.0pp of winrate at 4.33 sigma**. Nothing about
   aim, nothing about restraint criteria: just not casting.
2. **A targeting criterion is worth something, but only while volume is still high.** At 4.3
   casts/match the engine-true clump test beats a volume-matched RANDOM spell ban by **+0.207
   (2.98 sigma)**. By 1.5 casts/match it adds **nothing** (+0.009, 0.16 sigma) -- once volume is cut
   that far, which casts you keep stops mattering. The two arms do genuinely behave differently: at
   matched volume the criterion arm dumps 18.5% of its casts and the random arm dumps **40.1%**.
3. **Spells are not worthless -- they are worth about half a cast per match.** k7 (0.53 casts/match
   through a 7-body clump test) beats casting none at all by +0.077 (2.24 sigma), and is the best
   arm on winrate (+9.0pp, 3.26 sigma).

### 4.2 The elixir-trade criterion is a NULL, and the reason is its FIRE RATE
`tr1` (the best legal cell must catch enemy elixir at least equal to the spell's own cost) is
+0.017, 0.38 sigma. It fires on only **3.7% of decisions** against k3's 14.4%: valuing each caught
body at its card's full elixir share over-values what a spell merely clips, so the criterion almost
never bites. The idea is not refuted; **this implementation of it is under-powered and should not be
re-run as written.**

### 4.3 "Play less" only helps when it is SPELLS. `ctlany` is the control that says so.
Banning playable cards at random (0.209 per play-decision, so it lands on troops too) costs
**-6.3pp of winrate (-2.37 sigma)** and moves tower delta the wrong way. Together with
`rollout_search.md` section 6.2 -- where the scalar gate threshold was swept 0.02 -> 0.60 and the
shipped 0.25 was optimal in BOTH directions -- the refined statement is:
**global "play less" is harmful; SPELL-SPECIFIC "play less" is worth 7 points of winrate.**
That is exactly why a scalar gate could not express it: the gate is card-agnostic (it fires before
the card argmax), so it cannot be spell-specific by construction.

---

## 5. EXPERIMENT B -- PLACEMENT. THE PRE-REGISTERED ARM IS A NULL, WITH A DEMONSTRATED INSTRUMENT.

`aim`: keep the policy's CARD, move the CELL to the engine-true best-hitting legal cell, ties broken
by the policy's own cell logit. **This is the CEILING of a perfect spell placement head** -- above
any doctrine prior or entropy floor, because it is the argmax of the thing those priors approximate.
```
base -> aim     tower delta  +0.004   sem 0.051   +0.07 sigma   NO MEASUREMENT
                winrate      -3.3pp                -1.31 sigma
```
**The instrument was not asleep.** The arm moved the cell on **856 casts** (36.5% of all casts),
gained **1290 enemy bodies hit**, and **413** of those moves started from a cell that would have hit
nothing. It shows in the geometry:
```
per-card dump rate      base       aim
tornado                 15.0%  ->   4.4%
rocket                   8.6%  ->   2.5%
the_log                 46.2%  ->  45.3%
```
So placement CAN be near-perfected for the Tornado and the Rocket, and it buys **+0.004 +/- 0.051**
tower fractions. The 2 sigma upper bound on a perfect spell placement head is **+0.106**, against
`rollout_search.md` section 5.2's +0.216 for searching cells over ALL cards -- consistent, and it
locates that gain outside the spells.

### 5.1 AND THE LOG'S DUMPS ARE NOT A PLACEMENT FAILURE AT ALL
Perfect aim moves the Log's dump rate 46.2% -> 45.3%; the restraint arm moves it 46.2% -> 27.8%.
The Log is `own_half_only` (ruling 20), so when the enemy is on THEIR side there is no legal cell
that connects -- the cast is unsavable by aiming and should not have happened. **Section 4r's
two-failure split is now decided PER CARD: the Tornado's and the Rocket's dumps are a placement
failure that placement can fix and that is worth nothing; the Log's are a RESTRAINT failure.**

### 5.2 EXPLORATORY, NOT PRE-REGISTERED: aim pays only once restraint is applied
```
base -> aim        perfect spell aim alone                +0.004   +0.07 sigma   NO MEASUREMENT
k3   -> k3aim      perfect spell aim ON TOP of restraint  +0.103   +2.49 sigma   SIG
```
Mechanistically sensible -- the baseline casts mostly at boards with nothing worth hitting, so a
better cell has nothing to find; restrict casting to boards that DO hold a clump and aiming at it
pays. This was **NOT pre-registered and must not be reported as Experiment B's verdict.** It lands
at +0.103 against the pre-registered arm's own 2 sigma upper bound of +0.106, so the two readings
are consistent rather than contradictory. It is a hypothesis for the next experiment, not a result.

---

## 6. WHICH SPELL IS THE PROBLEM? NONE OF THEM. IT IS SPELL CASTING AS A CLASS.

One card removed from the action set at a time, n=300 paired:
```
arm      removed        win%  towerd  casts/m  |  towerd delta   sem    sigma   verdict
base     --             43.0  -0.841    7.87   |       --         --      --
nolog    the_log        41.3  -0.774    4.82   |     +0.066     0.065   +1.01   NO MEASUREMENT
nonado   tornado        45.0  -0.759    5.75   |     +0.082     0.048   +1.72   NO MEASUREMENT
norock   rocket         43.7  -0.793    7.47   |     +0.048     0.018   +2.62   SIG
knever   ALL THREE      50.0  -0.534    0.00   |     +0.306     0.071   +4.33   SIG
```
**No single spell carries it.** The three singles sum to +0.196 and the joint arm is +0.306, i.e.
SUPER-additive; and only the Rocket clears 2 sigma, on the smallest effect of the three (it is
significant because it is a low-variance change -- the Rocket is cast 128 times in 300 matches,
against the Log's 1671).

The practical consequence is a DO-NOT: **do not nerf, reprice or delete one spell.** Removing the
Log alone is +1.01 sigma and its winrate goes DOWN 1.7pp. Whatever is wrong is a property of how
this policy casts spells in general, not of one card's stats or one card's cell head.

`k7log` (the >=7-body clump rule applied to the LOG ONLY) is +0.090, 1.36 sigma -- also
NO MEASUREMENT. The rule has to apply to every spell to reach the bar.

---

## 7. WHAT THIS MEANS -- and what it does NOT

### 7.1 The one-line result
**This policy's spells are net-negative at the volume it casts them, and the fix is a
state-conditioned CARD-level veto, not a better cell head and not a scalar gate.**
```
delete all three spells                       +0.306 tower fractions   +7.0pp win   4.33 sigma
cast only into a >=7-body clump (0.53/match)  +0.383 tower fractions   +9.0pp win   5.82 sigma
perfect spell PLACEMENT, volume unchanged     +0.004 tower fractions   -3.3pp win   0.07 sigma
```

### 7.2 It resolves section 4r's two-failure split, per card
Section 4r said placement and restraint were two separate failures and might need different levers.
They are, and they do -- but the split runs by CARD, not by lever:
* **the_log** -- a RESTRAINT failure. Perfect aim moves its dump rate 46.2% -> 45.3% (nothing);
  restraint moves it to 27.8%. It is `own_half_only`, so when the enemy is on their side of the
  river no legal cell connects and no amount of aiming saves the cast.
* **tornado / rocket** -- a PLACEMENT failure that placement genuinely fixes (15.0% -> 4.4% and
  8.6% -> 2.5% dumped) and that is worth **nothing** in outcome.

### 7.3 It explains why a scalar gate could never do this (`rollout_search.md` section 6.2)
The gate fires BEFORE the card argmax, so it is card-agnostic by construction. Section 6.2 measured
that moving it in either direction is harmful, and `ctlany` here measures that banning cards at
random costs 6.3pp of winrate. **Global "play less" is harmful; spell-specific "play less" is worth
7-9 points.** The restraint the search found at N=1 is expressible -- but only at the card level.

### 7.4 ⚠ WHAT THESE ARMS CANNOT ESTABLISH (restating section 0.5 against the results)
* **Every arm uses ENGINE GROUND TRUTH to count bodies.** In the SIM that is free -- the existing
  `env.spell_target_mask` already reads the engine directly, so a trained rule can be exact. LIVE it
  would run on the detector: at `sim_detector_recall 0.82`, a genuine 3-body clump is seen in full
  only 0.82^3 = **55%** of the time, so the live port would veto roughly half the casts it should
  allow. **The live port is a separate question and must not be assumed from these numbers.**
* **These are DECISION-TIME arms.** They bound what a trained policy could achieve; they do not show
  it can learn it.
* **One checkpoint, one opponent pool** (`policy_BEST_m18000_20260826`, the frozen ladder). A
  different policy might not have net-negative spells.
* Nothing here touches the section 4t eval decay.

### 7.5 RECOMMENDATION FOR THE NEXT TRAINING RUN -- one change, and four DO-NOTs

**THE ONE CHANGE.** Promote the spell mask from a CELL mask to a CARD veto, on the ENGINE's own
geometry, at a clump threshold -- and apply it in sampling, in `choose_greedy`, and in eval.
```
new    sim.ppo_spell_min_bodies: 3     a spell is UNPLAYABLE unless some legal cell would catch
                                       at least this many enemy bodies under the engine's own hit
                                       test (corridor for a roll, pull disc, blast disc)
hold   sim.ppo_spell_mask_anneal / _end unchanged, so only one thing moves
```
Why K=3 and not K=5 or K=7, when 5 and 7 score higher: **K=3 is the largest threshold at which the
CRITERION is doing the work rather than the volume cut.** At K=3 it beats its volume-matched random
control by +0.207 (2.98 sigma); at K=5 it beats it by +0.009 (0.16 sigma). Above K=3 you are simply
buying "cast fewer spells", which a training run cannot be expected to generalise from and which
`knever` already shows you could get by deleting the cards. Measured value of the K=3 rule at eval:
**+0.233 tower fractions, 3.58 sigma.**
⚠ Machinery already exists: `sim/env.py::spell_target_mask` computes per-cell validity from engine
truth, and `train_sim_ppo.py:458-497` already plumbs it into sampling. What is missing is (a) the
ENGINE geometry instead of the flat `spell_waste_tiles` disc, (b) the >= K test, (c) promotion from
cells to the CARD, and (d) `choose_greedy` applying it (it does not today, so eval and live have
always run unmasked while sampling ran masked).

**DO NOT 1 -- do not spend an arm on the cell head.** No doctrine cell prior, no spell cell-entropy
floor. The CEILING of a perfect spell placement head is +0.106 tower fractions (the pre-registered
arm's 2 sigma upper bound) and the point estimate is +0.004. Section 5.2's +3.3pp for all-card cell
search is real and is somewhere other than the spells.

**DO NOT 2 -- do not ship "tighten `sim.spell_waste_tiles` 4.5 -> 2.0" as the fix.** Section
6-PRIORITY named it arm 1 and section 4r had already measured it as explaining only 17-25% of dumps.
Here the card-level version of the same idea (k1: refuse only when NOTHING anywhere would be hit) is
**-0.025, -0.69 sigma**. The binding variable is HOW MANY bodies are required, not the tolerance
radius.

**DO NOT 3 -- do not retune `sim.ppo_gate_threshold`.** Closed by `rollout_search.md` section 6.2
and re-confirmed by `ctlany` here.

**DO NOT 4 -- do not nerf, reprice or remove a single spell.** Section 6: no single removal clears
the bar and the Log's removal makes winrate worse.

**AND, BEFORE ANY OF IT: the sim action-space fix (section 3.6) must land first and the run must
start after it.** It moves 96 of 432 cells and removes 60 duplicate actions, so every placement the
current checkpoint learned, every doctrine cell and every drill reference line predates it. Starting
a spell experiment on the old mapping would measure a spell rule against a broken action space.
The `bx` arm says the fix is SAFE to apply to the current checkpoint (+0.006, 0.24 sigma, winrate
identical) -- it costs nothing now and can only help a retrain.

### 7.6 UNTESTED HYPOTHESIS worth exactly one arm after that (do not bundle)
`knever` removes the HITS as well as the whiffs and still wins by 4.33 sigma, and `k7` shows the
marginal value of every cast past the best ~0.5 per match is negative. So the problem is not only
that whiffs are under-charged -- **it is that a cast which hits one or two bodies is being paid for
at all.** `rewards.spell_waste: -0.3` fires only when nothing is within 4.5 tiles; there is no term
anywhere that prices "a 2-elixir Log clipped one Skeleton" as the losing trade it is. Candidate:
credit a cast by the enemy elixir it actually destroys minus its own cost, instead of charging a
flat penalty for the total whiff. **NOT TESTED. Stated so it is not mistaken for a result.**

---

## 8. THE VALUE-FORM SWEEP (2026-08-27, post-§7.5; the shipped rule). OWNER REJECTED THE COUNT FORM.

§7.5 recommended the card veto at K=3 BODIES. **The owner rejected the body-count form**: this
deck's highest-value casts are routinely SINGLE-body (`nado_king_activation` pulls exactly one Hog,
`nado_the_sneaky_lock` one Knight, `rocket_the_two_for_one` one Witch, `rocket_the_pump_on_sight`
one building), and K=3 refuses every one of them. The shipped criterion is a VALUE threshold in
TOWER FRACTIONS (`threat_value.catch_value_frac`, a new function -- `bodies_ignore_frac` reads
`inf` for kamikaze/spirit bodies and would wave those casts through) plus an exemption set for
casts whose payoff is not the bodies. Full enumeration with per-entry sources:
**decisions.md ruling 30.** Harness `scratchpad/spell_arms_valueform.py` (spell_arms.py + a
`--veto value` arm that calls `env.spell_card_ok` -- the arm grades SOURCE code, not a copy).

### 8.1 ⚠ Baseline re-measured AGAIN (tree 1143af2 + this change): 43.0% / -0.835
`vbase` reproduces `sx_bx.json` -- §3.6's board-exact arm -- on **300 of 300 matches**: today's
tree IS the action-space-fixed baseline. §2's -0.841 (pre-51f34fb) is close but not identical
(255/300); nothing here is compared across that boundary.
⚠ Commit **b4be2b7** (ruling 31a, Electro Giant reflection) landed at 17:55 the same day, DURING
the drill gates but AFTER every §8 arm below was launched (last launch 17:23; the decisive pairs
all launched <= 16:47). Drift RE-MEASURED on the post-31a/31b tree: 12-match repro vs `vbase` =
**11/12 byte-identical**, the one difference 0.004 tower fractions on seed 5000007 -- two orders
below the 0.05-0.07 sems here, so no §8 comparison is re-run. §4q's rule is the reason this
paragraph exists.

### 8.2 The sweep. n=300, seeds 5_000_000..299, paired, GREEDY, same bar
⚠ **RUN UNDER THE ROOT `.venv` (torch 2.13.0+cpu), NOT THE DECK'S (2.11.0+cu128).** Every wave
script in this ledger launches the harness as bare `python`. Isolated 2026-08-27 on the same
seeds, same checkpoint and same tree: **43.0% / -0.8303 root venv vs 37.0% / -0.9348 deck venv**,
-6.0pp winrate (2.62σ). Within-block comparisons below are unaffected; the arm-vs-control lines
are re-measured in §8.5 and two of §8.3's findings do not survive it.
```
arm                          win%  towerd  casts/m  dump%  | vs base   sigma
vbase                        43.0  -0.835    7.83    36.5  |    --       --
k3    (count form, re-run)   48.7  -0.583    4.25    18.4  |  +0.252   +3.80  SIG
value 0.45  NO exemptions    48.7  -0.596    4.33    21.4  |  +0.239   +3.91  SIG
value 0.65  NO exemptions    46.7  -0.618    3.35    21.5  |  +0.217   +3.30  SIG
value 0.90  NO exemptions    47.3  -0.600    2.48    18.1  |  +0.235   +3.40  SIG
value 0.10  NO exemptions    41.3  -0.853    7.04    31.4  |  -0.018   -0.42  NO MEAS.
value 0.20  NO exemptions    39.3  -0.876    6.25    28.2  |  -0.041   -0.78  NO MEAS.
value 0.45  WITH exemptions  45.3  -0.799    5.83    25.9  |  +0.036   +0.65  NO MEAS.
value 0.65  WITH exemptions  45.7  -0.764    5.51    26.6  |  +0.071   +1.26  NO MEAS.
```
Controls (random spell bans at matched rate, §0.4's `ctl` design):
```
ctl(0.83) -> value0.45 no-exempt   4.36 -> 4.33 casts/m   +0.149   2.14σ   SIG
ctl(0.83) -> k3                    4.36 -> 4.25 casts/m   +0.162   2.31σ   SIG
k3        -> value0.45 no-exempt   4.25 -> 4.33 casts/m   -0.013   0.22σ   NO MEAS. (equal)
ctl(0.30) -> value0.45 exempt      7.03 -> 5.83 casts/m   +0.068   1.16σ   NO MEAS.
ctl(0.50) -> value0.65 exempt      6.49 -> 5.51 casts/m   +0.002   0.03σ   NO MEAS.
```
### 8.3 The three findings
1. **The value criterion equals the count criterion** at matched volume (-0.013, 0.22σ) and beats
   its volume-matched control at **2.14σ**. The owner's re-formulation costs nothing in aggregate.
2. **⚠ The enumerated exemption set costs +0.203 (3.82σ) at 0.45** and the exempted compound rule
   does NOT clear 2σ against base or its controls. Two exemption bugs were measured out during
   calibration (an ungated tower-chip exempted the Rocket on 300/300 steps; an ungated lock-break
   fired on 21% of evaluations) -- the shipped gates are `_rocket_value`'s and `_nado_catch`'s own.
   What remains is the honest price of protecting the single-target plays.
3. **No threshold resolves the trade-off**: the single-target reference lines sit at 0.070-0.340,
   below any bar that moves the metric (>=0.45). The exemptions are the bridge; ruling 30 records
   the drill-by-drill acceptance table (`scratchpad/ref_line_probe.py`) -- every owner-named
   single-target line survives at every threshold, and 0.45 is the highest bar that keeps all but
   two low-value LOG drills.

### 8.5 RE-MEASURED UNDER THE DECK'S OWN VENV, TWO SEED BLOCKS, 600 PAIRED MATCHES

Full tables in decisions.md 30.6. The three lines that matter:
```
value 0.45 no-exempt vs ctl(0.83)   +0.047   0.98σ   NO MEASUREMENT   (§8.2 read +0.149, 2.14σ)
count K=3           vs ctl(0.83)   +0.174   3.64σ   SIG
value 0.45 no-exempt vs count K=3   -0.127  -2.99σ   SIG              (§8.2 read -0.013, 0.22σ)
```
* **§8.3 finding 1 is CONTRADICTED**: the value form is not equal to the count form, it is worse
  at matched volume.
* **§8.3's "beats its volume-matched control at 2.14σ" is NOT SUPPORTED**: 0.98σ pooled. The
  control's own effect against base swung **+0.301 (4.54σ) to +0.051 (0.76σ)** between blocks,
  because `ctl(r)` is ONE DRAW of a ban pattern -- which is the methodological lesson here, and it
  applies to every `ctl` line in §§4-7 of this ledger.
* **§8.3 finding 2 (the exemptions cost what the criterion buys) REPRODUCES.**
* What survives: the owner's objection to the count form (quantified in 30.7), the exemption set
  doing its job on every owner-named reference line, and the choose_greedy asymmetry being fixed.

### 8.4 What shipped (default OFF -- an 8k run was live in this tree; §3n's config seam)
`sim.ppo_spell_min_value` (0.0 = off; **0.45 is the drill-safe threshold IF it is ever enabled --
§8.5 withdrew the recommendation to enable it**), applied in
`choose_sample`, **`choose_greedy` (which applied NO spell mask before -- §7.5's asymmetry, now
fixed: eval/live and training see the same rule)**, and the drill report's `--spell-min-value`.
Tests `test_spell_card_veto.py`, byte-identical in both decks; hogeq's exemption set derives from
its own spec flags (earthquake gets `building`/`tower_*`/`hits_hidden`; no pull spell, so no
king-activation branch fires).

---

*Harness `scratchpad/spell_arms.py`; analysis `scratchpad/sx_analyze.py`, `scratchpad/sx_pair.py`;
live probes `scratchpad/live_grid_probe2.py`, `scratchpad/live_assist_probe.py`,
`scratchpad/king_mask_probe.py`, `scratchpad/cellcenter_probe.py`. None is in the repo tree. Raw
per-match records in `scratchpad/sx_<arm>.json`. Reference policy
`scratchpad/_rs_policy.pt`, md5 `9dd42804fdf6709d5387ec61f188cb83` =
`icebow/data/policy_BEST_m18000_20260826.pt`. Every arm ran on tree `d9b20d6` plus the two
live-only fixes of sections 3.2/3.3, which were verified sim-neutral (12-match baseline byte-identical
before and after).*
