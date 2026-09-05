# Radius-graded reward: proposals for owner review

Owner's idea (2026-09-04, verbatim in spirit): stop grading placements black-and-white. Every unit,
building and crown tower carries two circles -- its **attack range** and its **aggro (sight) radius** --
and most interactions are decided by those two numbers. Grade a placement by *how far* it sits from the
right band around the right circle, and grade the *timing* of a response by where it falls in a window
derived from the threat's approach. The model is told none of this; it is reward-side only.

This document is the review draft. Nothing here is implemented. Each proposal states what it grades,
which radii it uses, the curve, what it replaces in `icebow/src/clashrl/sim/env.py`, the way it can be
gamed, and the test that says whether it measures the right thing *before* a training run is spent on it.

---

## 0. Assessment first: is the premise right?

**Yes, and it is measured, not assumed.** The current building credit is exactly black-and-white and
blind to *where* on the x axis:

- `env.py::_threat_response` (line ~1050): a defensive building earns the full `w_threat_response` (+1.0)
  iff it is the KB-correct role, `0.50 <= ny <= 0.80`, the threat is inside the depth window
  (`threat_min_depth 0.12` .. `threat_max_depth 0.65`) and the per-threat budget is unspent. No x term at
  all. A Tesla at the left riverside corner (cell 234, tile (1.5, 18.5)) and one at centre (tile (9, 21))
  earn the identical +1.0 against the same hog. The comment in the code says *where* is "settled by what
  follows -- the chip/crown terms bill the damage it failed to prevent."
- L56/L57 measured that "what follows" does **not** separate them in the sim: per-Tesla damage corner
  1040 vs centre 1157 (CIs overlap, both seeds), still flat with the `hidden_pull` mechanic (935 vs 1029).
  The scripted bots never make a corner turret pay.
- Pros do separate them: Tesla at x=9 in 48% of 1,705 placements, x 6-11 in 81%; the policy's tile
  holds 2.0% of pro Teslas (L57).

So the reward currently delegates "where" to an outcome the opponent model cannot produce. A graded
geometric term is the right kind of fix: it injects the real game's geometry where the sim's opponent
cannot. Same logic as the pro-prior KL I proposed in L57, but conditional on the board instead of a
static tile histogram -- strictly more general when the rules are right, strictly worse when they are
wrong, which is why every proposal below carries a pro-corpus test.

**Four things the idea does not cover on its own -- all measured in this project, not opinions:**

1. **A gradient the policy never samples is no gradient.** PPO turns a reward slope into a policy
   change only through the actions it actually takes. The cell head is saturated (raw logit |81| at the
   c2r resume, RAIL GUARD rescale), entropy is 0.06 and each card sits on one cell (L55). A Tesla that is
   *always* placed at cell 234 sees the graded reward at cell 234 and nowhere else; the slope toward the
   centre is never observed. The graded term makes *local* exploration productive (a neighbouring cell
   now scores differently, which a binary band cannot do), but it needs the exploration to exist. The
   training arm must ship with a cell-head temperature / entropy floor, and that is a second change --
   §2 below says how to keep the experiment attributable.
2. **A penalty that can only subtract is an action tax.** Measured twice here: the "premature defender"
   penalty fired 257 times with zero bonuses over 40 matches and the policy learned "play less" (plays
   per match 50.1 -> 30.9, winrate 4.4% -> 0.0% while episode reward *improved*). The owner's
   "punishment scaling with distance outside the aggro radius" is one-sided. Every curve below is
   therefore a **credit that peaks in the band and decays to zero** -- not below zero -- outside it, and
   the only negative parts are the geometric mistakes that lose material in the real game (a building
   dropped inside a melee wincon's attack reach; a splash-fragile troop dropped inside a splash radius).
3. **Additive shaping gets farmed.** The wincon bank failed twice and its replacement was 98% inert; the
   eight offensive bow windows shipped and "are not the lever". A per-placement credit is farmed by
   placing more (the policy already plays 5-7 Teslas per match, L56). Every term keeps the existing
   per-threat-episode budget (`threat_credit_budget`) and a per-match cap, and is logged with fire
   counts and sign balance the way the premature penalty should have been.
4. **Timing was measured as a second-order deficit.** §5ae's regret corpus found the gap is
   CONTINUATIONS (what happens after the first response), not event responses. The timing gradient
   (P5) is still worth building because the current window is binary and the gate is the one head that
   still learns (L55), but it should not be expected to move the crowns-match on its own.

**Recommendation:** build P1, P2, P5 and P6 first (they replace existing binary terms one-for-one),
validate on the pro corpus (§3) before any training, then one training arm with the controls in §2.

---

## 1. Definitions (all distances in TILES; the board is 18 x 32 and the axes are not isotropic --
use the engine's `_dist`/`_gap`, never a normalised hypot)

| symbol | meaning | source |
|---|---|---|
| `r_atk(u)` | attack range of unit/building/tower `u` | `CardSpec.reach`; tower reach constants in `engine.py` |
| `r_sight(u)` | aggro / sight radius | `cards.py::sight_range_tiles` (cr-api `sight_range`, curated overrides in `config/cards.yaml`): most troops 5.5, PEKKA / Giant Skeleton 5.0, building-targeting tanks 7.0-7.7, Hog / Royal Hogs 8.5-9.5, Firecracker 8.0, X-Bow `siege_sight` 11.5 |
| `d_march(t, b)` | lane-aware travel distance from threat `t` to building `b` | `engine._march_gap` (through the bridge when the river is between) |
| `d(a, b)` | straight distance | `engine._gap` |
| `T_deploy` | 1.0 s before a placed unit acts | `CardSpec.deploy_time` |
| `v(t)` | threat speed, tiles/s | `CardSpec.speed` x 32 |
| `value(t)` | threat value from the existing triage | `threat_value` (IGNORE_FRAC gate stays) |
| `band(x; lo, hi, w)` | 1 for lo <= x <= hi, linear to 0 over `w` tiles on each side, 0 beyond | the one curve shape used everywhere |

"Significant threat" everywhere below = the existing triage's `value(t) >= IGNORE_FRAC` **and** the
threat is a wincon / tank / building-targeter or a push whose summed value clears the same bar. A lone
skeleton or goblin never qualifies -- the owner's condition, and the triage already computes it.

---

## 2. How to run it without losing attributability

The one-change-per-experiment rule and caveat 0.1 pull against each other. Resolution: **three arms
from `c2r_best`, two at a time on the box** (4 arms measured 9.14 GB / 16 cores saturated; c2r alone was
17 procs):

| arm | change | what it isolates |
|---|---|---|
| G | graded terms (P1/P2/P5/P6 replacing their binary counterparts) | the reward alone -- expected near-null (caveat 0.1) |
| G+E | graded terms + cell-head temperature floor | the owner's proposal as it must ship |
| E | temperature floor alone (the L55 exploration arm) | whether exploration alone does it (control) |

Reads at m5k and m10k, never winrate: `place_probe` (distinct cells per card, tesla@234 share,
**pro-mass-within-1.5-tiles per card** from L57), `gate_prior_probe` (spend/hold side effects), the
per-term ledger (fire counts, sign balance, credit per match). Three seeds before any claim.

---

## 3. Validation gate (runs BEFORE training; ~1-2 h, no box contention)

Each term is a function `score(board, placement)`. Compute it on two populations:

- **Pros:** the 268 converted replays' 20 Hz timelines replayed through the sim engine give enemy
  positions at every blue placement (the L51 driver already does this), so every pro Tesla / X-Bow /
  troop placement gets a score under each proposal.
- **Policy:** `c2r_best`'s greedy placements in the sim (L55/L56 probes already record them).

A proposal survives only if pro placements score clearly higher than the policy's (report the two
distributions and the gap; a proposal that scores the pros' modal Tesla tile (9,21) below the policy's
corner is wrong and is dropped, not tuned). This is the check the three failed placement priors never
had. It also calibrates `w`, `lo`, `hi` from data instead of by hand.

---

## 4. Proposals

### P1 -- Building pull band (Tesla / Cannon / X-Bow-as-defence vs a building-targeter)

*Replaces:* the building branch of `_threat_response` (`0.50 <= ny <= 0.80`, x-blind).

*Grades:* where the building sits relative to the threat's aggro circle **and** whether it will actually
be pulled to. A building pulls a building-targeter only when it is the nearest building by march
distance -- if the princess tower is nearer, the building is decoration (engine `_acquire`, and the real
engine agrees: L52 hog turned to a Tesla 6.2 / 7.1 tiles away).

```
pull_ok  = d_march(t, b) < d_march(t, nearest own tower)          # it will be the target
x        = d_march(t, b)
credit   = w_pull * band(x; lo = r_atk(t) + 1.0, hi = r_sight(t), w = 2.0) * pull_ok
penalty  = -w_pull * clip((r_atk(t) + 1.0 - x) / (r_atk(t) + 1.0), 0, 1)   # dropped on top of a melee wincon
```

- Hog (sight 8.5-9.5, melee): band 1.8 .. 9.0 tiles from the hog along its path, full credit; the
  corner Tesla vs a right-lane hog has `d_march` ~ 14 and `pull_ok` false -> 0. A centre Tesla at
  (9, 21) vs a hog at the bridge (3.5, 16): ~7.4 tiles, inside 9.0, nearest building -> full credit.
- Giant / Golem (sight 7.0-7.7): narrower band; a placement 9 tiles away decays to 0 by 9.7.
- The penalty is the only negative part: inside `r_atk + 1` of a melee wincon the building is hit
  before it shoots. Capped at `-w_pull`, once per threat episode.
- *Hack:* farming the credit by placing buildings every hog. Kept under `threat_credit_budget`
  (1-2 credits per threat episode) and the elixir terms.
- *Pro test:* pro Tesla tiles vs hog / giant positions at placement -> expected mostly inside band;
  policy corner -> mostly `pull_ok` false.
- *Live:* needs the threat's identity (detector card class) and position (track) -- both exist in
  the live env (`env.py` tracks carry `sight`); `d_march` needs only lane side and y. Log-only first.

### P2 -- Tower-support geometry (the reason pros use the centre)

*Replaces:* nothing (new); modulates P1 and P3.

*Grades:* whether the fight the placement creates happens under our princess tower(s). For a building:
its own position. For a troop: the intercept point (where the threat's path meets the counter's sight
circle).

```
p        = engagement point
cover    = sum over own alive princess towers of band(d(p, tower); lo = 0, hi = r_atk(tower), w = 1.5)
credit   = w_cover * min(cover, 2) / 2                                 # 0 .. 1; both towers = 1
```

- Centre Tesla (9, 21): inside both princess reaches (towers at x 3.5 / 14.5, y ~25.5, reach 7.5;
  d ~ 7.1 each) -> cover ~2 -> credit 1.0. Corner Tesla (1.5, 18.5): left tower d ~ 7.3 (edge), right
  tower 14.8 -> cover ~0.9 -> credit ~0.45. Lane Tesla (4.5, 20.5): left only, ~1 -> 0.5.
- This is the term that makes x matter for buildings with no hand-picked band. A defensive building
  placed so that BOTH towers shoot the pulled wincon is the textbook rule; the number says so.
- Multiplied into P1 (`credit_P1 * (0.5 + 0.5 * credit_P2)`) so a pulled-but-uncovered building still
  earns half, never zero.
- *Pro test:* pro Tesla x-distribution (48% at x=9) is precisely the two-tower overlap; if the
  computed cover peaks anywhere else, the tower reach constants are wrong.

### P3 -- Troop intercept, graded (replaces the binary lane test)

*Replaces:* `intercept = abs(nx - tx) <= intercept_lane (0.15) and ny >= 0.5`.

```
path     = threat's march line to its target (bridge -> tower for troops; its locked target if any)
x        = distance from the counter's landing tile to that path
r_c      = r_sight(counter)                                          # the counter must SEE it
credit   = w_int * band(x; lo = 0, hi = r_c, w = 2.0) * ahead(counter, t)
ahead    = 1 if the counter lands between the threat and its target (a body in the path), 0.5 if beside, 0 behind
kite     = for kiteable threats (r_sight(t) <= 5.0, e.g. PEKKA / Mini PEKKA / Giant Skeleton):
           extra band(d(counter, t); lo = r_sight(t) - 1.0, hi = r_sight(t), w = 0.5) when the counter is
           inside a princess tower's reach -- the pull-to-the-tower kite that pros use
```

- Melee counters (Knight) need to be near the path; ranged (Ice Wizard, sight 5.5, reach 5.5) score
  from further out -- that is what using the counter's own radius buys over a flat 0.15 lane tolerance.
- The Skeletons-in-front-of-the-king cell (9.3, 24.1) vs a bridge hog at (3.5, 16): 7.6 tiles from the
  path, behind everything -> 0 credit where the binary term gives 0 too, but a Skeletons at (3, 17)
  (the pros' modal tile) gives 1.0 and (5, 19) gives ~0.6 instead of 0.
- *Pro test:* pro Knight / Skeletons / Ice Wizard tiles vs threat positions.

### P4 -- Splash / spell radius overlap (graded spell credit)

*Replaces:* the binary `spell_waste` and the fixed blast-window attribution for damage spells; adds a
geometric grade for the Tornado.

```
frac     = (value of enemy units inside the blast radius at impact) / (value of the push)
credit   = w_spell * frac        (0 .. 1), 0 counted as a miss under the existing spell_waste rule
tornado  = w_nado * (units pulled into the pull radius) / (units in the push), plus the P2 cover of the
           pull centre (a tornado that drags the push under the king tower scores the king's reach)
```

- The engine has `splash` / blast radii per spell and the `_Vortex` pull radius already.
- *Pro test:* pro Log / Tornado tiles (Log modal (14,17)/(3,17) at the bank, Tornado (8-9, 24) = the
  king-activation pull) should score high under `frac` and `cover`.
- Lower priority than P1/P2/P5/P6 (the spell terms were audited in §5cs.8-12 already).

### P5 -- Timing gradient (the owner's second ask)

*Replaces:* the binary depth window `threat_min_depth 0.12 <= dpt <= threat_max_depth 0.65`.

*Grades:* when the response lands relative to a window derived from the threat's own motion, not from a
fixed depth.

```
t_cross  = time until the threat crosses the river (from y, v(t)); 0 if already across
t_tower  = time until it enters the reach of our nearest princess tower (path length / v(t))
t_hit    = time until it reaches r_atk(t) of that tower (first tower damage)
t_resp   = time the counter is effective = now + T_deploy + (travel of the counter to the intercept, 0 for buildings)
window   = [t_cross, t_hit]         # after crossing (tower support), before the first hit
credit   = w_time * band(t_resp; lo = t_cross + 0.5, hi = t_hit + 1.0, w = 1.5 s)   # late edge: owner's ruling 2026-09-04 (Q2)
           # EXCEPTION (owner, 2026-09-04): a BRIDGE-BLOCK play is never penalised for being early -- see §7.4.
```

- Too early (counter effective before the threat has crossed): decays to 0 over 1.5 s -- the pros'
  "let it cross" rule, no negative. Too late (effective after the first tower hit): 0, and the chip term
  bills the damage as it does today; no second charge.
- For a building the counter's travel is 0, so its window is the widest -- consistent with the pro
  Tesla being placed early and centrally.
- Elixir is not in this term (the existing spend/hold terms own it).
- *Pro test:* pro response times vs `window` for the threat present -- the §5ag continuation anchors
  (after-bow next play median 5.5 s, inter-play gap median 3.85 s) are the sanity bound.
- *Live:* speed and position from tracks; `t_cross` is well-defined from y alone.

### P6 -- Offensive siege geometry (X-Bow)

*Replaces:* the `central = abs(nx - 0.5) <= 0.390` / `xbow_front..xbow_back` in-band credit and the
`xbow_lane_frac` softening.

```
tower    = the nearest ALIVE enemy princess tower (dead towers do not exist to this term -- §7.5);
           if both princesses are dead, the king tower
credit   = w_bow * band(d(b, tower); lo = r_atk(tower) + 0.5, hi = siege_sight (11.5), w = 1.0)
           * (1 - band(d(b, enemy building), lo = 0, hi = r_atk(building), w = 0.5))   # not under a Cannon/Tesla
```

- **RETRACTION (2026-09-04, L58 step 0).** Rev 1-3 of this note said the corner bow (1.5, 18.5) and the
  pros' lane bow do NOT reach the enemy princess, quoting the engine comment at `engine.py:2567`
  (11.18 tiles at y 0.56). That comment is STALE: the running engine's `_gap` from (1.5, 18.5) to the
  enemy princess's hitbox edge is **10.67 tiles < 11.5 reach** (box-edge geometry: dx 3.0-1.5, dy
  12.0-1.5 -> hypot 10.6), and a deployed X-Bow there locks and damages the princess (4858 -> 4568 HP
  in 6 s, measured by the step-0 build in `scratchpad/gauntlet/L58/impl_geometry.md`). So the
  policy's corner cell IS an offensive bow, L56's hypothesis (b)(1) "the X-Bow at 234 is rewarded
  because it reaches the left tower" is back to (b) untested (not contradicted), and the 17% / 48%
  "tower-reaching" / "neither" split in §5ag needs re-deriving with `_gap`, not centre distance. P6 as
  written scores the corner tile 1.0 -- the formula stands; the example was wrong.
- Centre bow (8.5, 22): both towers ~16 away -> 0 offensive credit (it is a defensive placement, graded
  by P1/P2 instead). This removes the hand-picked band entirely.
- *Pro test:* 1,038 pro bows: the offensive-scored fraction should match the §5ag split (17% tower-
  reaching, 35% in-band, 48% neither) up to the corner-vs-centre tile convention.

### P7 -- Unnecessary closeness / fragility (the only other negative term)

```
penalty  = -w_frag * band(d(counter, t); lo = 0, hi = r_atk(t), w = 0.5)   for splash / melee threats vs
           low-HP counters (Ice Wizard, Skeletons vs Valkyrie / Wizard / Baby Dragon / PEKKA)
```

- Capped once per placement; never fires on a building (P1 owns that case).
- Kept small (`w_frag <= 0.3`): the trade ledger already bills the lost unit.

---

## 5. Implementation shape (for after the review)

- One pure module `src/clashrl/sim/geometry_reward.py`: `score_placement(board, placement) -> {term: value}`
  with `board` a plain record (units with team/pos/spec radii/speed/path target, towers, elixir). The
  sim env builds it from the engine (ground truth); the live env builds it from tracks (`env.py`
  `_track_pump` already carries per-track sight). The model sees nothing from it.
- Every term writes to the existing `reward_stats` ledger with fire count, sum, sign balance per match
  (the audit the premature penalty lacked).
- Weights start equal to the terms they replace (`w_pull = w_threat_response = 1.0`, etc.) so the
  first run changes the SHAPE and not the SCALE of the reward -- the one-change rule applied inside the
  reward.
- Config keys under `env.geometry.*`; the binary terms stay selectable for the control arm.
- Sim-parity note: the radii come from the KB (real game), not from what the sim's units do. Where the
  sim's targeting is known to differ (hidden Tesla pull, L52), the reward follows the real rule; that
  is the point of the term.

## 6. Open questions for the owner

1. Weights: keep the replaced terms' weights (my default) or scale the graded family up?
   -> answered in §7.6; RULED 2026-09-04: scale up, calibrated by the §3 gate.
2. P5's window uses the FIRST tower hit as the late edge; pros sometimes take one hit deliberately.
   Accept `t_hit - 0.5`, or widen to `t_hit + 1.0`?  -> RULED 2026-09-04: `t_hit + 1.0` (folded into P5).
3. Arm plan in §2 (G / G+E / E, two at a time) -- or G+E only, accepting the attribution loss?
   -> RULED 2026-09-04: all three arms, two at a time.
4. Live: log-only for the first run (my default), or live-trained from the start?
   -> RULED 2026-09-04: log-only for the first run.

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

**Source (rev 3):** the owner's download `clashbot/bridgeblock.mp4` ("When Should you Bridge Block?",
Abdod, 9:03). I cannot watch video; I read 136 frames (1 per 4 s, `scratchpad/bb/sheet*.png`) and ran
the built-in Windows recogniser on the audio (`scratchpad/bb/transcript.txt`, `stt.ps1`; no packages
installed). The transcript is rough ("hog rider" comes out as "hall light") -- every case below is
decoded from the transcript AND checked against the frames; where I am not sure I say so.

**The video's headline rule, which changes the reward treatment:** *by default do NOT bridge block --
letting the troop cross so your towers help is the advantage; block only with a specific reason, because
a block at the wrong time gets punished.* This is the SAME principle P5 already encodes (respond after
the crossing so the princess tower helps). So a bridge block is not an exception to P5's idea, it is a
short list of situations where the crossing itself is what you cannot afford. The three block types the
video names: a **win condition** (hard -- needs a well-placed building or a body exactly on the bridge),
a **mini-tank** (easy -- any ground card), and a **support troop** you want separated from the push.

| # | Case (video) | Block it because | Icebow relevance |
|---|--------------|------------------|------------------|
| B1 | **Hog Rider in X-Bow / two-building decks** (frames 2:40-3:08: Tesla/X-Bow vs Hog) | the video says X-Bow decks specifically *want* the hog blocked: an offensive X-Bow or a Tesla at the bridge stops the hog where the tower still targets it; "the more universal technique, any deck: block when you cannot afford the chip damage" (tower low) | **primary case** -- this is our deck |
| B2 | **Lumberjack + Balloon** (frames 0:56-1:32: Balloon, Lumberjack, Minions vs Tesla) | you want the Balloon killed first; a body/building that holds the Lumberjack at the bridge keeps its rage from reaching the Balloon ("the rage drops behind the balloon and gets wasted") | Tesla + Ice Wizard |
| B3 | **Mighty Miner (mini-tank) + Hog** (frame 2:44) | block the Mighty Miner with Skeletons at the bridge; then Tornado pulls the push to the king -- the king-activation play of §7.3 | Skeletons + Tornado |
| B4 | **Balloon alone** | only if the tower is so low it cannot take a single hit; otherwise let it cross -- tower help is worth more (transcript: "the only time I'd consider blocking a balloon... if your tower is very low") | rarely |
| B5 | **Giant / Goblin Giant / tank + escort** (frames 3:28-3:52: Elixir Golem + Battle Healer, Ice Spirit + Guards; Royal Giant 2:04) | hold the tank BEHIND the bridge so the support arrives on our side without it ("fully loaded on your side is a squishy support... guards start eating"); a building on the bridge works for a Giant followed by a Rocket; **Elixir Golem + Healer "is a must to block"** because letting them close lets the healer heal under tower | Knight / Tesla-on-bridge |
| B6 | **Graveyard tank** (Knight / Barbarians escort) | "bridge blocking is a graveyard player's worst nightmare": block the escort at the bridge so the graveyard is cast without a tank in front | Knight at the bridge |
| B7 | **Wall Breakers** | depends on the counter: a splash card (Dark Prince) -- do NOT block, let the tower + splash handle it; a single-target slow card (Knight) -- block so the tower helps finish | Knight -> block; Log -> no block |
| B8 | **Princess at the bridge** | "Tesla is great at bridge blocking Princess; X-Bow players keep [a cheap card] to make sure they never get caught by a surprise princess at the bridge, where tower damage matters" | Tesla / Skeletons |
| B9 | **Magic Archer / Firecracker** (transcript: skeleton-blocking them "on paper seems good, in practice sucks -- it helps them line up on the tower") | NOT a block case: a body at the bridge lines the archer up on the tower; take them out instead | do NOT credit a bridge body vs these |
| B10 | **Cards to keep away from the tower** (transcript names "Royal Ghost / [wall breakers?] / Mega Knight" -- uncertain) | play safe: blocking them before they reach tower range denies the chain | uncertain -- owner to confirm |

Anti-cases the video is explicit about (a bridge body earns NO credit here, and the ordinary P5 early
ramp applies): (1) **a lot of support behind the tank** -- "any form of blocking can be an issue if they
have so much stuff behind it: you lose the unit and the push comes fully deployed"; (2) a **building on
the bridge vs a tank with splash behind it** ("a bad idea"; most buildings are locked for the deploy
time -- Goblin Cage is the exception); (3) B9 above.

Reward treatment (unchanged in shape, now driven by the table):
- Detect a block geometrically, not by card: placement within 1.5 tiles of a bridge tile
  (`x in {3.5, 14.5}`, `y in [15, 17.5]`) while an enemy ground unit is in that lane within
  `r_sight(unit) + 3` tiles of the bridge and moving toward it.
- `block_case` = 1 if any of B1-B8 holds (recognisable from KB roles + our deck + tower HP: hog-role
  wincon and we hold a building; balloon-role with a ground escort; mini-tank; tank with escort; escort
  ahead of a graveyard-role spell; wall-breakers with a single-target counter; princess-role ranged at
  the bridge), 0 otherwise. Support-count anti-case (1) zeroes it when >= 3 enemy troops trail the tank.
- If detected and `block_case`: **P5 timing credit = full** (`t_resp < t_cross` is the point), P1/P3
  scored with the bridge tile as the intercept point.
- Credit only if the block HOLDS: the unit's `d_march` to our tower has not decreased for >= 1.5 s after
  `T_deploy`, or it retargets the blocker. A body walked past scores as an ordinary early play.
- If detected and NOT `block_case`: no P5 credit, no P5 penalty (owner: an early block is never
  negative). The worst a bridge play can score is 0. The video's "default: don't" is expressed as
  absence of credit, not as a penalty -- the 08-20 ruling against wait-side terms stands.
- Ledger: `bridge_block_detected`, `bridge_block_case`, `bridge_block_held` counts per match, so the
  first read shows whether the policy ever finds these plays at all.

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

### 7.8 Decisions taken for run 1 (2026-09-04, rev 3)

- **Q1 -> scale up** (owner ruling): `w_geom = 1 / mean(band score of c2r_best's own placements)`,
  measured by the §3 gate, capped at 2.0; same `w` in G and G+E.
- **Obs change in run 1 -> NO** (owner left it to me). Reasons, in order of weight: (1) attributability
  -- run 1 is the reward change alone, resumable from `c2r_best` (36k episodes of trunk we would
  otherwise discard; a new first-conv cannot resume); (2) the pros' modal Tesla tile (9,21) is inside
  the band for every wincon in the whitelist, so the role-average band the model CAN derive credits the
  right tile -- the per-card difference is at the band EDGES, not at the optimum; (3) live, an identity
  channel is bounded by detector recall 0.4-0.6 for Hog/Giant/PEKKA, so half the time it would be empty
  anyway. What would flip this: the §3 gate showing the pros' tile ranks differently under role-average
  radii (then identity matters at the optimum, not just the edges), or the cheap linear probe on
  `c2r_best` features showing card identity is absent AND the G arm moving the Tesla toward the band
  edge rather than the centre. Both measurements are in the gate step, so the decision is revisited
  with numbers before arm 2 launches.
- **Bridge-block table** rebuilt from the owner's video (§7.4); B10 stays marked uncertain.
