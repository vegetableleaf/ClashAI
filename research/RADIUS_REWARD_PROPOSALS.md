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
credit   = w_time * band(t_resp; lo = t_cross + 0.5, hi = t_hit - 0.5, w = 1.5 s)
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
tower    = the enemy princess tower the bow will lock (nearest by d)
credit   = w_bow * band(d(b, tower); lo = r_atk(tower) + 0.5, hi = siege_sight (11.5), w = 1.0)
           * (1 - band(d(b, enemy building), lo = 0, hi = r_atk(building), w = 0.5))   # not under a Cannon/Tesla
```

- Reach check against the engine's own measurement (engine.py ~2567): an X-Bow reaches an enemy
  princess only from y <= ~0.56 (tile ~17.9; 11.18 tiles to the tower's edge vs 11.50 reach); at y 0.60
  it is 12.34 and cannot hit. So the pros' modal lane bow (2, 19.5) does NOT reach the tower -- it is a
  DEFENSIVE placement (§5ag already classed those 48% as "neither"), graded by P1/P2, not here. And the
  policy's corner bow (1.5, 18.5 = y 0.578) does not reach it either: L56's hypothesis (b)(1) "the X-Bow
  at 234 is rewarded because it reaches the left tower" is CONTRADICTED by the engine's number; the
  corner cell is not an offensive bow. P6 pays only bows placed to lock: the 17% "tower-reaching" pro
  bows sit within ~1.5 tiles of the bank, and the graded edge at 11.5 teaches the half-tile that
  separates a firing bow from a bow that "aims and never fires" (the sim-view symptom quoted in the
  engine comment).
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
2. P5's window uses the FIRST tower hit as the late edge; pros sometimes take one hit deliberately.
   Accept `t_hit - 0.5`, or widen to `t_hit + 1.0`?
3. Arm plan in §2 (G / G+E / E, two at a time) -- or G+E only, accepting the attribution loss?
4. Live: log-only for the first run (my default), or live-trained from the start?
