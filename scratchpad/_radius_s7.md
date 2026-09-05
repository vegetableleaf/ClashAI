
## 7. Owner additions and corrections (2026-09-04) -- each one checked against the code first

### 7.1 "The model sees none of the radii but should derive them from enemy positions / crown towers"

**What the model actually sees today (measured from the code, not assumed):**
- The image: 6 semantic channels (`detect_obs.CHANNELS`: enemy ground / enemy air / enemy building /
  my ground / my building / spell) + 3 predictive (`enemy_predicted`, `my_predicted`, `enemy_urgency`)
  + 2 HP channels. Each unit is drawn as a blob whose SIZE is its collision radius (`spec.radius`,
  `view.py:167`). **No card name is in the image.** A Hog and a PEKKA are both "enemy ground" blobs;
  the only cue separating them is blob size and speed across frames.
- The vector: a 10-dim identity block (`card_threat.IDENTITY_DIM`) = KB ROLE bits of the deepest
  RECOGNISED enemy on our half: present / tank / swarm / air / building / win-condition /
  building-targeting / depth / velocity / predicted depth. It "prioritises, does not blend": one threat
  at a time, and only for cards on the `observation.detector_cards` whitelist (Hog, Giant, PEKKA,
  Mini PEKKA, Balloon, Royal Hogs, Miner, Mega Knight ... ~30 cards listed in `config.yaml:427-470`) and only past
  the identity watch line. Plus a 6-dim tower block (HP fraction of L/R/king, mine then theirs).

**So: can it derive the radii?** Partly, and the part it cannot derive matters less than it sounds.
- The reward's LOW edge (P1 `lo = r_atk(t) + 1.0`, "not on top of a melee threat") is almost the same
  number for every melee threat (r_atk 0.8-1.6 tiles -> lo 1.8-2.6). Role bits + blob size give this
  to within a tile. Derivable.
- The HIGH edge (P1 `hi = r_sight(t)`) varies INSIDE a role: wincon role covers Hog 9.5 / Giant 7.5 /
  Ram 5.5 / Balloon 5.5; tank role covers PEKKA 5.0 / Golem 7.0. Spread ~4 tiles, wider than the 2-tile
  ramp. The model can learn the ROLE-average band, not the per-card band. For Icebow's real
  threats this costs something only where a Hog is on the board (its 9.5 sight makes a centre Tesla
  legal where a Giant's 7.5 would not -- and the centre tile (9,21) is inside BOTH, so the pros' modal
  tile is credited either way).
- Whether the model can read a card from blob size + speed is **(b) untested**. Measurement: train a
  linear probe on the trunk features of `c2r_best` to predict `base_card` of the deepest enemy; if
  accuracy over the whitelist is ~role-level (~40%) the identity is not there.

**Two ways to give it what it needs, neither of which feeds a radius:**
- **(i) Zero obs change (my recommendation for run 1).** The reward uses true per-card radii; the
  model sees role + position and learns the role-average band. Resume-safe from `c2r_best`, no trunk
  change, attributable to the reward alone (one change per experiment). The residual per-card error
  is measured by the §3 gate: score the pros' Tesla tiles with per-card radii AND with role-average
  radii; if the rank of the pros' modal tile is the same, the model does not need the card name.
- **(ii) Identity channel (if the gate says the card matters).** Add ONE extra image channel per
  whitelisted card group (or a per-unit card-id embedding painted into the blob), fed from ground truth
  in the sim and from the YOLO detector live -- exactly the information the identity block already
  carries, but per unit instead of "deepest only". This is card IDENTITY, not radius: the model still
  has to learn what a Hog's aggro band is from reward. Cost: obs schema change -> cannot resume the
  trunk from `c2r_best` (fresh trunk or a widened first conv with zero-init on the new channels), and
  the live side is only as good as detector recall (0.4-0.6 for the "moderate" tier, Hog included).
  This is a second experiment, not a bundle.

### 7.2 "The sim debugger must show the radii"

The debugger is `run.py sim-view` (`src/clashrl/sim_view.py`, OpenCV, `render_frame` at line 117;
`--out FILE --no-window` writes an mp4). It already draws: unit blobs at collision radius, shield
rings, spell AOE ellipses on impact (`:200`), splash flashes (`:210`), the Tornado vortex (`:187`),
tower footprints with HP, and a dead tower as a crossed-out box (`:219-223`). It draws **no attack
range and no sight/aggro ring** today.

Deliverable (implementation step 0, before any reward code): a `--radii` flag for `render_frame` that
draws, per alive unit/building/tower, `r_atk` (solid ring, team colour) and `r_sight` (dotted ring,
dimmer), and for a placement just made, the P1 band it was scored against (shaded annulus between
`lo` and `hi`) with the term's value printed next to the unit. Both rings are read from the same
`geometry_reward` helpers the reward uses (`radii_of(spec)`), so what you see IS what is scored -- a
separate drawing table would be a second source of truth and the thing you are trying to verify.
Verification you can do by eye: pause on a pro-replayed frame (§3 gate) and check the pros' Tesla
sits inside the shaded band.

### 7.3 Tornado: pull distance and direction, vs the pros

Added to P4 (replaces the "units pulled / units in push" fraction alone):

```
for each enemy unit u within r_pull of the vortex centre c:
    d_u      = d(u, c)                                # pull distance
    dir_u    = unit vector (u -> c)
    goal_u   = unit vector (u -> our nearest ALIVE tower u would otherwise reach)
    away     = 0.5 * (1 - dot(dir_u, goal_u))         # 1 = pulled straight AWAY from its goal, 0 = toward it
    weight_u = value(u) * clip(1 - d_u / r_pull, 0, 1)   # pull strength falls with distance (engine's _Vortex)
tornado  = w_nado * ( sum_u weight_u * away ) / value(push)
         + w_king * king_activation     # 1 if the pull ends inside the KING's r_atk while the king is
                                        #   asleep and >= 1 enemy unit is dragged into it; 0 otherwise
```
- `king_activation` is the mechanic the owner named: pros' modal Tornado tile (8-9, 24) (§5cs.27,
  n=979) is the pull that drops a push under the sleeping king. The term pays once per match per king.
- *Pro test (§3 gate):* replay the 979 pro Tornados through the engine and record `(d_u, away,
  king_activation)` per pull; the term must rank the pros' modal tile above the policy's, and the
  distribution of pro `d_u` (I expect most mass at 2-4 tiles from the target, the vortex radius being
  5.5) becomes the reference the debugger overlays.
- The engine's `_Vortex` already moves units by distance-scaled pull; the sim reward reads it, the
  live path has no vortex object -- live scores `d_u`/`away` from the tracked positions at cast and
  1.0 s later (log-only in run 1 anyway).

### 7.4 Bridge-blocking: cases to engrain; never penalise an early block

I could not watch the video (the fetch returns only the title: **"When Should you Bridge Block?" --
Abdod**). The cases below are the standard doctrine as I know it; **please strike or add** -- this is
the one part of §7 that is not checked against anything measured.

A bridge block = a body placed ON the bridge tile (or just behind it) so a crossing troop is stopped
at the river instead of on our side. It is correct when at least one of:

| # | Case | Why the tower-support rule (P5) is wrong here |
|---|------|-----------------------------------------------|
| B1 | Fast building-targeter (Hog, Royal Hogs, Ram, Battle Ram, Wall Breakers) with our tower already low | it reaches the tower before any counter engages; a Knight/Ice Golem body on the bridge makes it stop where BOTH princesses + the Tesla reach |
| B2 | Dashing/charging units (Bandit, Prince, Ram) | the charge is broken at the bridge; letting them cross gives the charge |
| B3 | Splash setup: the enemy stacks support behind a tank at the bridge | holding the tank at the river bunches the push for Tornado/Log/Rocket (Icebow's whole plan) |
| B4 | Opposite-lane pressure: our X-Bow is locked on the other side | a block buys the bow its lock time; letting the push cross costs the bow |
| B5 | Double-elixir defence of a single-elixir push already on our side | (not a block; listed to say P5's late edge still applies there) |

Not a block (P5 applies unchanged): a lone tank without support (let it walk to the tower), a swarm
(bridge body dies to it), air (nothing to block).

Reward treatment:
- Detect a block geometrically, not by card: placement within 1.5 tiles of a bridge tile
  (`x in {3.5, 14.5}`, `y in [15, 17.5]`) while an enemy ground unit is in that lane within
  `r_sight(unit) + 3` tiles of the bridge and moving toward it.
- If detected: **P5 timing credit = full**, no early penalty (`t_resp < t_cross` is exactly the point),
  and P1/P3 are scored with the bridge tile as the intercept point.
- Credit only if the block HOLDS: the unit's `d_march` to our tower has not decreased for >= 1.5 s
  after `T_deploy`, or it retargets the blocker. A body that gets walked past is scored as an ordinary
  early play (P5's early ramp), which is the "don't pre-place blindly" guard the 08-20 ruling wants.
- The owner's constraint: **an early block is never negative**. The worst a block can score is 0.

### 7.5 A taken princess tower is removed from the match

Checked -- the sim already does this in every place I could find, and the live bug the owner
describes was real and is the reason the tower block exists:
- Engine: dead towers are excluded from targeting (`engine.py:2460, 2546, 2592, 2618, 2661, 3121`,
  all gated on `t.alive`) and from collision ("alive crown towers", `:2371`). An X-Bow cannot lock a
  dead tower.
- Observation: the pixel canvas skips a dead tower (`view.py:95`, `if not tw.alive: continue`); the
  identity/threat items carry `alive` per tower (`view.py:296`); the tower block reports HP 0.
- Live: `env.py:170-178` (comment) records exactly the owner's fear -- "after taking a princess the
  policy kept placing X-Bows at the spot that used to reach it" -- as the observed live bug that the
  6-dim tower block was added to fix (HP read from the HUD, 0 when taken).
- Debugger: a dead tower is drawn crossed out (`sim_view.py:219`).

What is NOT yet true and becomes a deliverable: the NEW terms must use alive towers only. P6 now says
"nearest ALIVE enemy princess; if both are dead, the king" and P2's `cover` sums over own ALIVE towers
(it did already). Test: a unit test that kills the left princess and asserts P6 scores the old
left-reaching tile as 0 and the king-reaching tile as in-band. The live side reads `alive` from the
tower block (HP == 0), the same signal the policy sees.

### 7.6 Q1 answered: keep the replaced weights vs scale the graded family up

Plain terms. Today the building term pays **1.0 or nothing**: a Tesla anywhere in the depth window
against a correct-role threat gets 1.0, corner and centre alike. Under P1 the same term pays
`w * band(...)`: 1.0 at the pros' tile, a fraction at the policy's corner tile (the §3 gate will
measure it; my guess ~0.4-0.5 because the corner is 6-8 tiles from a lane-centre threat's path).

- **Keep `w = 1.0` (replaced weight).** The MAXIMUM credit is unchanged; the AVERAGE credit the
  current policy earns drops (it is at the corner, so ~0.45 instead of 1.0 per Tesla). Effect on the
  gradient: two signals at once -- "move toward the band" (the slope, what we want) and "defending
  pays less than it did" (a level drop). The level drop pushes the balance toward the outcome terms
  (tower damage, crowns), which is the direction of "play buildings less". Risk: the policy plays
  fewer Teslas rather than better-placed ones. That is the failure mode of every wait-side change in
  this project (§5cs.x action-tax entries).
- **Scale up (`w = 1 / mean band score of the current policy`, capped at 2.0).** The AVERAGE credit
  stays at today's 1.0, so the total shaping share of the reward is unchanged on day 1 and only the
  slope is new. Risk: the MAXIMUM is now ~2.0, so a policy that finds the band earns more shaping than
  today -- more shaping share means more pressure to farm it (the per-threat budget and ledger in §0
  are the guard). And the calibration constant is measured on `c2r_best`, so it is specific to this
  start point.

Recommendation: **scale up, calibrated by the §3 gate**, because the thing we are trying to teach is
the slope and the level drop is a confound we already know how the policy responds to (it stops
playing). Read the reward_stats ledger at m5k: if the per-Tesla mean credit has risen while the count
of Teslas per match has not fallen, the slope is doing the work; if the count fell, the level was the
lever and the answer is wrong. Both arms (G and G+E) use the same `w`.

### 7.7 Rulings folded in
- Q2: late edge `t_hit + 1.0` (P5 updated).
- Q3: all three arms G / G+E / E, two at a time (§2 unchanged; E is the control that isolates the
  exploration change).
- Q4: live path log-only in run 1 -- `geometry_reward.score_placement` runs on the live tracks, its
  per-term values go to reward_stats and the session log, and NOTHING is added to the live reward.
