# L59 wire.md -- progress log (incremental)

STATUS: complete (s9 = lead rulings applied + Part C seam fix per the amendment; s9.8 = final suite)

## 0. Setup
- Created this file. Reading brief + required docs next.

## 1. Reading done (brief, doc s1/s4/s7.4-7.8, impl_geometry, gate.md 1a-1e, HANDOFF 5cs.29)
Findings that shape the work (before any edit):
- `RewardTerms.add` (icebow/src/clashrl/reward_stats.py:73) RECORDS and returns the value unchanged; the
  caller does `reward += add(...)`. So a log-only term is just `self.rw_stats.add(name, v)` with no `reward +=`.
  Zero values are not counted as fires (eps 1e-9) -> `geo_bridge_detected` etc. are logged as 1.0 per fire.
- step() (sim/env.py:3032) calls `eng.deploy` FIRST, then `_threat_response` and `_wincon_exec` for the same
  placement -> ONE `score_placement` per accepted placement, shared by both (cached on (t, card, cell)).
- `_threat_id_true` (env.py:624) comes from `view.identity_items` = enemy units past the identity watch line
  `identity_front_y = 0.44` (config:208). The quiet-board gate (`tid[0] < 0.5 -> 0`) is kept per the brief, so
  the geometry credit can only fire once the threat is within ~1.9 tiles of the river (local y >= 0.44).
  CONSEQUENCE: the pro "pre-place while the hog is at own-frame y ~ 12" case that path-P1 was built for is
  unreachable in the ENV under this gate (the gate rerun below measures it on the pro replays, where no such
  gate exists). Flagged in s6.
- `_threat_pos()` (env.py:922) = max (danger, y) among enemy troops with y >= 0.5 (our half); `pick_threat`
  (geometry_reward) = most urgent by march distance among value>=3/building_only enemies on EITHER half.
  They can differ -> I pass the env's threat explicitly (see Part B).
- Config nested read idiom: `cfg.get("env", "geometry", "enabled", default=False)` (Config.get is variadic).
- `--config` REPLACES config.yaml entirely (HANDOFF 5cr.1 trap) -> an arm-G override yaml must be a full copy.
- Module: the OLD `p1_pull_band` already carried the P2 factor (`raw * (0.5 + 0.5 * p2_cover)`, line 519).
  The brief's `placement_credit` multiplies by `(0.5 + 0.5 * p2_cover)` itself, so the NEW `p1_pull_band` is
  the RAW band x pull_ok (no P2 inside) and `p1_snapshot` is the raw snapshot band x pull_ok (same
  convention, so the two are comparable; the ">0" fractions are unaffected by the factor).

## 2. Pre-edit reference (Part B (1))
- `scratchpad/gauntlet/L59/reward_ref.py` + the driver in `tests/test_geometry_wiring.py`
  (`run_matches`, private `random.Random(1000+seed)` stream, hold p 0.2, seeds (7, 11), <= 400 steps).
- Recorded BEFORE any src edit: match 0 seed 7: 222 steps, reward sum -13.1924, 23 plays;
  match 1 seed 11: 290 steps, reward sum -13.2734, 35 plays. Saved `reward_ref.npy`.
- Re-run pre-edit `test_disabled_is_byte_identical`: OK (222/290 steps identical) -> the driver is deterministic.
- Full suite BEFORE the edit: running in the background -> `suite_before.txt` (reported in s5).

## 3. Part A -- `icebow/src/clashrl/geometry_reward.py` (DONE; 26/26 module tests pass)
Edits (line numbers after the edit):
- 62-64 `SWARM_ROLE = "swarm"`, `CREDIT_FLOOR = -0.3`, `CREDIT_CAP = 1.0`; 66-76 `TERM_KEYS` += `p1_snapshot`,
  `p1_close_snapshot`, `d_path`.
- 272-295 `placement_from_spec(..., db=None, roles=None)`: the placement now carries `roles` (explicit, or
  read from `db` through `card_threat.profile(db, base).roles()` -- the SAME source `role_average_radii`
  uses). No db and no roles -> `roles=()` -> P7 charged as before.
- 525-529 P2 = `_p2_cover(...)` only when `is_building`, else 0.0 (the intercept-point cover is still used
  internally for the P3 kite check); 640 spell branch P2 -> 0.0.
- 535-566 path-based P1: `d_path = max(0, _project(board, path, px, py).dist - r_body)` where `path` =
  `threat_path()` (pos -> lane bridge if the river is between -> nearest own ALIVE tower by march / locked
  target; `_project` clamps to the polyline so only the FORWARD part counts); falls back to the snapshot
  march gap when the path has < 2 points. `pull_ok` unchanged (snapshot march gap to b < march gap to the
  tower). `p1_pull_band = band(d_path; lo=r_atk+1, hi=r_sight, w=2) * pull_ok` (RAW, no P2 factor);
  `p1_snapshot = band(x_snapshot; same) * pull_ok`; `p1_close_penalty` = same form on `d_path`;
  `p1_close_snapshot` = the old form on the snapshot gap. Flying threats: `d_path` still uses the
  straight path (threat_path skips the bridge for flyers), snapshot uses the straight tile distance as before.
- 603-604 `t_cross`, `t_hit`, `t_resp` exported from the P5 block (env timing gate reads them; not TERM_KEYS).
- 606-614 P7 skipped when `"swarm" in placement["roles"]`.
- 659-677 `placement_credit(terms, kind, p7_enabled=False)`:
  building = `min(1.0, max(0, p1_pull_band*(0.5+0.5*p2_cover) + p6_siege)) + max(-0.3, p1_close_penalty)`;
  troop = `min(1.0, p3_intercept)` (+ `max(-0.3, p7_fragility)` if p7_enabled); spell = 0.0.
  RANGE: [-0.3, 1.0] for every kind. Capped at 1.0 (not 2.0) because a pull AND an offensive bow CAN
  coincide: an X-Bow on the bank vs a bridge hog scores P1 > 0 (pull) and P6 > 0 at once.
- 680-682 `timing_credit(terms) = clip01(p5_timing)`. CHECKED: the module already sets
  `p5_timing = 1.0 if bridge_block_case else 0.0` (score_placement P5 block, line ~577) before the
  timing band, so the bridge-block full credit is inside P5 as s7.4 says; nothing to change.
- 704-711 `nonzero_terms` skips `d_path` as well as `d_threat`.
FLAG (brief item 3, "close penalty unchanged in form but on d_path"): measured on d_path the penalty ALSO
fires for a building placed beside/in the lane while the threat is still far (d_path ~ 0 but the threat
never reaches it before deploy). Hand-board evidence: Tesla (5.5,23) vs PEKKA at (4.5,20) -- 2.66 tiles from
the PEKKA (snapshot penalty 0) but 1.02 tiles beside its march line -> path penalty -0.536; the doc's corner
Tesla (1.5,18.5) vs bridge hog: snapshot 0, path -0.167. Both twins are in the dict; the gate rerun (s4)
reports both firing rates on the pro Teslas so the lead can choose. I wired the brief's form (d_path).

Tests: `icebow/tests/test_geometry_reward.py` 1-414. Existing tests updated for the new convention:
`test_centre_beats_corner` (corner path P1 = 0.85 raw, snapshot 1.0; credits 1.0 vs 0.471),
`test_close_penalty_tesla_on_pekka` (`far` now pins the d_path penalty -0.536 and snapshot 0), `Bounds`
allows `d_path >= 0` and `p1_close_snapshot` in [-1, 0]. ADDED class `L59PathP1AndRestrictions` (277-358):
(a) `test_a_preplaced_tesla_vs_hog_at_enemy_bridge_approach` -- hog at own-frame y=11 (5 tiles short of the
    bridge): snapshot 0, path P1 1.0 (d_path 5.0); NOTE at y=12 exactly the snapshot march gap 10.9 is
    still on the band's outer ramp (0.28), so the test uses y=11 for the "snapshot = 0" claim and pins
    y=12 as snapshot < 0.3 / path 1.0;
(b) `test_b_...` hog at (3.5,16): path 1.0 >= snapshot 1.0;
(c) `test_c_...` P2 = 0 for skeletons and tornado, > 0 for a Tesla at the same tile;
(d) `test_d_...` P7 = 0 for skeletons with role swarm, -1.0 for role-less skeletons (adapter passes
    roles), -1.0 for ice wizard on top of a valkyrie / 0 at 6 tiles;
(e) `test_e_...` bounds: all-ones -> 1.0 (cap), all-worst -> -0.3, troop p7 off -> 0.0, spell 0, plus
    every tile x card on the hand board inside [-0.3, 1.0];
(f) `test_f_...` Tesla (9,31) behind the king vs left-lane hog: p1_pull_band 0 and p1_snapshot 0
    (d_path 7.28 is IN band; pull_ok = 0 zeroes it);
(+) `test_bridge_block_case_is_full_timing_credit`.
Output (`test_geometry_reward.txt`, verbatim tail):
```
Ran 26 tests in 1.078s

OK
```

## 4. Gate rerun (DONE; `gate_replay.py` copied from L58 + L59 additions, `gate_analyze.py`, outputs `p1/`, full table `gate_summary.txt`)
Run: `PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L59/gate_replay.py --out ../scratchpad/gauntlet/L59/p1`
-> 211 replays, 0 errors, 60 s; 1,453 scored building plays (blue tesla 807, blue x-bow 543, red tesla 63,
red x-bow 40); 350 gate-probe boards (hog 156, giant 126, pekka 68 -- the probe still runs at every
icebow-card play moment so n matches L58's 350). Changes vs L58's script: `SCORED = {tesla, x-bow}` for
the play rows, `db` passed to `placement_from_spec` (roles), GRADED += p1_snapshot / p1_close_snapshot /
d_path (reported, not summed), `placement_credit` / `timing_credit` columns (`*_pcred`, `*_tcred`),
locked tile for both buildings = corner (1.5,18.5) as in L58. "pc" = per-card radii, "ra" = role-average.
Sanity: `p1_snapshot > 0` on 0.409 of the 807 blue Teslas = L58's 40.9% exactly (same formula, same n).

(1) Fraction of pro (blue) Tesla plays with `p1_pull_band > 0` (path P1, pc): **0.533 (430/807)**, mean
    0.813 when it fires (snapshot: 0.409, 330/807, mean 0.770). Overlap: both fire 276, path-only 154,
    snapshot-only 54, neither 323. ra radii: path 0.570, snapshot 0.420.
    Per pro tile: (9,21) n=135 path P1 > 0 on 0.652 (snapshot 0.356); (9,19) n=71 0.634 (0.451);
    (9,22) n=68 0.721 (0.456); (9,18) river bank n=67 0.597 (0.418).
(2) Pro tile beats the locked corner on `placement_credit` (strict > / tie / <):
    - tesla blue n=807: pc **0.476 / 0.404 / 0.120** (mean pro 0.346 vs lock 0.101; median rank 2 of 27,
      rank-1 0.450); ra 0.523 / 0.362 / 0.115. (L58 summed-score was 0.633/0.180/0.187 -- the credit has
      more ties because P2 alone no longer counts and P5 is out of the placement part.)
    - x-bow blue n=543: pc **0.077 / 0.131 / 0.792** (mean pro 0.702 vs lock 0.947; median rank 9 of 27);
      ra 0.026 / 0.140 / 0.834. Driven by P6 as in L58 (p6 pro>lock 0.018 / < 0.895): the pros' bows are
      often defensive/centre (P6 = 0 by design) while the corner bow (1.5,18.5) is an offensive tile.
      P1 for a bow: path 0.162 > 0 vs snapshot 0.123. Unchanged verdict from L58 (not a stop condition).
    - red tesla n=63: pc 0.206 / 0.571 / 0.222; red x-bow n=40: 0.450 / 0.075 / 0.475 (small n).
    Credit ranges observed: tesla [-0.300, 1.000], x-bow [-0.300, 1.000]; `timing_credit` mean 0.615 on
    the pro Tesla (> 0 on 0.665), 0.119 on the pro bow (> 0 on 0.160).
(3) Doc s3 gate rule, modal (9,21) vs corner (1.5,18.5) Tesla on Hog/Giant/PEKKA boards, n=350, pc radii:
    - path `p1_pull_band`: **median diff +0.000, modal>corner 0.480, modal<corner 0.134** (L58 snapshot:
      0.000 / 0.414 / 0.114). ACTIVE boards (either tile non-zero) n=235 (L58: 196): median +0.441,
      > 0.715, < 0.200. Per threat: hog n=156 median 0 (> 0.256 / < 0.179), giant n=126 +0.496
      (0.690 / 0.087), pekka n=68 +0.329 (0.603 / 0.118).
    - `p1_snapshot` (same boards, this run): 0.000 / 0.286 / 0.134; ACTIVE n=196 median +0.070.
    - `placement_credit`: median diff **+0.148**, modal>corner **0.543**, < 0.143; ACTIVE n=242 median +0.579.
    - p2_cover +0.500 (0.817 / 0.000), p5_timing flat, SUM +0.500 (0.846 / 0.129).
    => path P1 does NOT rank (9,21) below the corner on the median board (median 0, i.e. level, with the
    modal ahead 3.6x as often as behind; on the credit the modal is strictly ahead on the median board).
    NOT a stop -> wired (Part B).
(4) Close-penalty forms on the PRO Tesla tile (blue, pc): d_path form fires 69/807 = 0.086 (mean -0.505),
    snapshot form 28/807 = 0.035 (mean -0.349); on the modal (9,21) the d_path form fires 1/135. On the
    gate boards the d_path form is active on 126/350 (modal mean -0.098 vs corner -0.074; > 0.524 / <
    0.476 on the active ones) vs 44/350 for the snapshot form. So the brief's d_path form charges the
    pros' Teslas ~2.5x as often as the snapshot form; it is bounded (floor -0.3 in the credit) and I wired
    the brief's form -- the lead can flip `p1_close_penalty` -> `p1_close_snapshot` in `placement_credit`
    (one line, geometry_reward.py 675) if the extra firing is unwanted.

## 5. Part B -- wiring into `icebow/src/clashrl/sim/env.py` (DONE; 2/2 wiring tests pass, disabled = byte-identical)

### 5.1 Config block (ADDED, no existing value changed)
`icebow/config/config.yaml` lines 1270-1276, at the end of the `env:` block (after `wc_release: 3`, before `play:`):
```
  geometry:
    enabled: false        # arm G sets true
    w_geom: 2.0
    w_time: 1.0
    pre_place_s: 3.0
    p7_enabled: false
    log_all_terms: true
```
Read in `SimMatchEnv.__init__` via `cfg.get("env", "geometry", <key>, default=...)` (`Config.get` is variadic;
a missing block falls to the same defaults, so a run yaml that predates the block behaves as `enabled: false`).
Verified: `Config.load().get('env','geometry')` -> `{'enabled': False, 'w_geom': 2.0, 'w_time': 1.0,
'pre_place_s': 3.0, 'p7_enabled': False, 'log_all_terms': True}`.

### 5.2 Edits to `src/clashrl/sim/env.py` (git diff: +124 lines, 0 deleted; `grep -n L59` finds every hunk)
- line 24: `from .. import geometry_reward as GR`.
- lines 433-446 (`__init__`, right after `xbow_lane_frac`): the six config reads -> `self.geo_enabled`,
  `geo_w_geom`, `geo_w_time`, `geo_pre_place_s`, `geo_p7_enabled`, `geo_log_all`; per-step caches
  `_geo_board` (engine.t, Board), `_geo_cache` ((card, nx, ny), terms), `_geo_used`.
- lines 988-1063, five new methods placed just before `_threat_response`:
  - `_geo_threat_obj(board)` 991-1001: the env's OWN assessed threat (the `_threat_pos()` unit = max
    (danger, y) enemy troop on our half) matched to a module `BoardObj` by exact engine coordinates; None
    when no enemy body is on our half -> the module's `pick_threat` is used and the ledger logs
    `geo_threat_module = 1` for that placement.
  - `_geo_terms(card_id, nx, ny)` 1003-1027: `board_from_engine(eng, 0)` at most ONCE per step (cached on
    `engine.t`), `score_placement` at most ONCE per accepted placement (cached on the (card, nx, ny) key --
    the building branch, the troop branch, the X-Bow branch and the ledger all read the same dict). The
    placement is scored at the ENGINE-SNAPPED landing tile read back from `eng.last_deploy[0]` (the
    engine quantises every tap to the tile it lands in; the deploy is still PENDING for `action_latency`
    0.25 s when the reward block runs, so the board is the pre-placement board -- the placement is not
    on it). `placement_from_spec(..., db=self.db)` so the KB roles reach P7's swarm rule.
  - `_geo_gate(terms)` 1029-1038 -- the EXACT gate formula used:
    `gate = 1.0 if t_cross - pre_place_s <= t_resp <= t_hit + 1.0 else band(t_resp, lo=t_cross - pre_place_s, hi=t_hit + 1.0, w=1.5)`
    i.e. `GR.band(t_resp, t_cross - 3.0, t_hit + 1.0, 1.5)` -- 1.0 inside the window, linear to 0 over
    1.5 s outside either edge (the module's `band` is exactly that shape; verified it accepts lo < 0).
    `t_resp` = the card's deploy time (+ travel to the intercept point for a troop), `t_cross` = the
    threat's time to the bridge (0 once it is over), `t_hit` = its time to the tower's reach. When the
    module computed no window (no `t_resp` key: bridge-block case, standing threat, no march path) the
    gate is 1.0 (placement part ungated).
  - `_geo_credit(terms, kind)` 1040-1047: `credit = w_time * timing_credit(terms) + w_geom * placement_credit(terms, kind, p7_enabled) * gate`
    -- only the PLACEMENT part is gated, as the brief says. Records `terms["credit"]`, sets `_geo_used`.
  - `_geo_ledger(terms)` 1049-1063: record-only `rw_stats.add` (RewardTerms.add only records; the episode
    reward is `reward += ...` at the call site and NONE of these are added there) of `geo_p1`, `geo_p2`,
    `geo_p3`, `geo_p5`, `geo_p6`, `geo_p1_close` and log-only `geo_p4`, `geo_p4_nado`, `geo_p4_king`,
    `geo_p7`, `geo_bridge_detected`, `geo_bridge_case` (1 per fire), plus diagnostics `geo_threat_module`,
    `geo_p1_snapshot`, `geo_gate`, `geo_credit`, `geo_paid_module_threat` (1 when a NONZERO credit was
    computed against the module-picked threat rather than the env's). Raw term values, so per-match sums
    read in [0, 1] units; zero values are not counted as fires by the ledger.
- lines 1148-1156 (building branch of `_threat_response`): when enabled,
  `if not (card_threat.counters(prof, tid) and budget_ok): return 0.0` (role + budget gates KEPT), then
  `credit = _geo_credit(_geo_terms(...), "building")`; `_threat_credits += 1` ONLY when `credit > 0`;
  returns the credit. The old line (`counters and 0.50 <= ny <= 0.80 and deep_ok and budget_ok` ->
  flat `w_threat_response`) is untouched and still runs when disabled. `deep_ok` (threat_min_depth 0.12 ..
  threat_max_depth 0.65 on the threat's identity depth) is NOT applied on the geometry path -- the
  brief's timing gate replaces it (see flag 6.2).
- lines 1171-1179 (troop counter branch): `intercept and deep_ok` -> `w_time * p5 + w_geom * p3 * gate`
  (`placement_credit(terms, "troop")` = P3, + P7 only when `p7_enabled`); budget gate kept; consume on
  `credit > 0`. The binary misread (`_threat_misread`) is above this and unchanged.
- lines 1743-1752 (`_wincon_exec`, X-Bow, branch `elif d <= self.xbow_range` = the OFFENSIVE bow, in
  tower range): `val = w_geom * p6_siege` replaces the flat `val = self.w_wincon` (3.0). The
  multipliers that follow (`bow_first_frac` before 30 s, the split-push `w_wincon * xbow_punish_mult`,
  the hostile-deck / `_ally_xbow_standing` zeroing) are unchanged. What the DEFENSIVE code does and why
  it is untouched: the branches around it credit a bow that is NOT in offensive range -- `_defensive`
  (a real threat on our half): `w_wincon * frac` where `frac` = the deep/lane fraction
  (`xbow_deep_frac`, `xbow_lane_frac`), or `w_wincon_mis` (-1.0) when the frac is 0; and the out-of-range
  fallback `w_wincon * 0.4 * frac` / mis. The brief calls the `in_band`/`frac` credit "central/in_band
  binary" -- it is the defensive credit, so per "keep the defensive-bow code unchanged" I left it and
  replaced only the offensive flat credit. P6 is 0 for a centre bow by design (doc s4 P6).
- line 3155 (`step()` top): caches reset. Lines 3182-3185: after the `wincon_exec` line the ledger is
  written when `geo_enabled and (log_all_terms or _geo_used)` -- with `log_all_terms: true` every
  ACCEPTED placement (troop, building, spell) is scored exactly once; a rejected/masked action is not.

### 5.3 Credit ranges (measured)
- `placement_credit` in [-0.3, 1.0] for every kind (test_e; gate rerun min/max on 807 pro Teslas + 543
  pro bows: -0.300 .. 1.000). `timing_credit` in [0, 1].
- Env credit = `w_time*P5 + w_geom*place*gate` in [-0.6, 3.0] at the config weights (1.0 + 2.0; the
  floor is 2.0 x -0.3). Observed in the env: building +0.000 .. +3.000 (s5.5 scenario, n=11 rows), troop
  +0.066 .. +3.000 (probe2, n=27 paid), spell 0 (P4 is log-only). The X-Bow offensive branch pays
  `w_geom*P6` in [0, 2.0] (x `bow_first_frac` before 30 s) where the old code paid a flat 3.0 (flag 6.5).
- Every geometry credit still passes through `self._bonus(...)` (the symmetric `correctness_cap` 20.0 per
  match), like the old `threat_response`; nothing about the cap was changed.

### 5.4 Regression test `icebow/tests/test_geometry_wiring.py` (99 lines) -- verbatim output
Driver: `run_matches(cfg, seeds=(7, 11))`, private `random.Random(1000+seed)` action stream, hold p 0.2,
<= 400 steps, config = `Config.load()` with `env.geometry.enabled` forced per test; reference sequence
`scratchpad/gauntlet/L59/reward_ref.npy` recorded BEFORE any src edit (s2).
`PYTHONHASHSEED=0 ./.venv/Scripts/python.exe -m unittest tests.test_geometry_wiring -v` (saved
`test_geometry_wiring.txt`; the env.py:1417 backslash-space SyntaxWarning lines are pre-existing, `git show HEAD`):
```
test_disabled_is_byte_identical (tests.test_geometry_wiring.GeometryWiring.test_disabled_is_byte_identical) ... ok
test_enabled_runs_and_logs_geo_terms (tests.test_geometry_wiring.GeometryWiring.test_enabled_runs_and_logs_geo_terms) ... ok

----------------------------------------------------------------------
Ran 2 tests in 2.842s

OK
[wiring] match 0 seed 7: 222 steps, reward sum -13.1924, identical to ref
[wiring] match 1 seed 11: 290 steps, reward sum -13.2734, identical to ref
[wiring] ENABLED match 0 seed 7: 222 steps, reward sum -11.9440, geo keys 5
    geo_credit           fires    1  sum   +0.9484  (+1 / -0)
    geo_gate             fires   17  sum  +16.9484  (+17 / -0)
    geo_p3               fires    1  sum   +1.0000  (+1 / -0)
    geo_p5               fires    3  sum   +2.9484  (+3 / -0)
    geo_threat_module    fires    8  sum   +8.0000  (+8 / -0)
[wiring] ENABLED match 1 seed 11: 290 steps, reward sum -8.2734, geo keys 8
    geo_credit           fires    3  sum   +7.0000  (+3 / -0)
    geo_gate             fires   24  sum  +23.3333  (+24 / -0)
    geo_p2               fires    1  sum   +1.0000  (+1 / -0)
    geo_p3               fires    7  sum   +4.4157  (+7 / -0)
    geo_p4               fires    1  sum   +0.3333  (+1 / -0)
    geo_p5               fires    7  sum   +6.3333  (+7 / -0)
    geo_paid_module_threat fires    2  sum   +2.0000  (+2 / -0)
    geo_threat_module    fires   11  sum  +11.0000  (+11 / -0)
```
Disabled: 512/512 steps identical to the pre-edit reference (222 + 290). Enabled: the reward sums move
(-13.19 -> -11.94, -13.27 -> -8.27) because the graded credits pay where the binary gate did not, and
the ledger carries the geo_* keys. `geo_p1`/`geo_p6`/`geo_p1_close` never fired in these two random-stream
matches (only 4 building placements in 512 steps, none paid) -- see s5.5 for a building measurement.

### 5.5 What the enabled path actually pays (probes; every number from a run)
- `geo_probe.py` -> `geo_probe.txt` (the two wiring matches): paid credits n=4, min +0.948, max +3.000:
  seed 7 step 131 ice_wizard vs lava_hound p3=0, p5=0.95 -> credit +0.948 (TIMING paid with NO placement
  term); seed 11 step 2 (t=1.8 s) skeletons vs giant, threat from the module, p3=0, p5=1.0 -> +1.000;
  steps 113/213 skeletons p3=1, p5=1 -> +3.000.
- `geo_probe2.py` -> `geo_probe2.txt`: seeds 20..31 (12 matches, ladder opponents), 366 scored
  placements: building scored 4 paid 0; troop scored 218 paid 27 (credit min +0.066, median +1.556,
  max +3.000; timing part > 0 on 27/27, placement part > 0 on 18/27, gate < 1 on 10/27, module-picked
  threat among the paid 2/27); spell scored 144 paid 0 (P4 nonzero on 17/144, logged only).
- `geo_scenario.py` -> `geo_scenario.txt` (n=11 enabled rows + 6 disabled): a scripted enemy Hog down the
  left lane (idle opponent, hog deployed at tile (3.5, 8) = 8 tiles short of the river), our Tesla at the
  pros' modal tile (9,21) dropped after `wait` steps of 0.6 s; every row is a fresh env (seed 3):
  ```
  hog tile y   8.5  8.7 11.1 12.3 13.5 | 14.7  15.9  17.1 | 18.3  20.7  23.1
  tid0 (env)     0    0    0    0    0 |    1     1     1 |    1     1     1
  P1 path     1.00 1.00 1.00 1.00 1.00 | 1.00  1.00  1.00 | 0.00  0.00  0.00
  P1 snapshot 0.00 0.00 0.00 0.36 0.95 | 1.00  1.00  1.00 | 0.00  0.00  0.00
  P5          0.00 0.00 0.00 0.07 0.46 | 0.85  1.00  1.00 | 1.00  1.00  1.00
  credit      0    0    0    0    0    | 2.848 3.000 3.000 | 1.000 1.000 1.000
  old binary  0    -    0    -    0    |   -   0      -    | 1.000 1.000  -
  ```
  Reading: (i) while the hog is on the enemy half the path P1 is already 1.0 but the env's quiet-board
  gate (`tid[0] = 0` until the hog passes `identity_front_y` 0.44 = tile 14.1) returns before any
  geometry runs -> the PRE-PLACE case is unreachable in the env as wired (flag 6.4); (ii) at hog y
  14.7-17.1 the graded credit pays 2.85-3.0 (P1 1.0 x P2 1.0 + P5) where the old binary paid 0 (the hog's
  depth was below `threat_min_depth`); (iii) once the hog is past y ~18 (locked on the left princess,
  whose 1.5-tile hitbox is now nearer by march than the Tesla: 5.73 vs 6.68 tiles) `pull_ok` = 0, P1 = 0
  and only the timing part pays (+1.0) -- the old binary paid its full +1.0 exactly there (hog y 18.3 /
  20.7), i.e. AFTER the pull was possible; (iv) at hog y 23.1 (t_hit 0.1 s) the graded credit still pays
  +1.0 (flag 6.2).

## 6. Flags -- things the brief's wording produces that the lead should rule on (none blocks the wiring)

6.1 **Timing credit is paid with NO placement term.** `credit = w_time*P5 + w_geom*place*gate` -- the
    first term pays whenever the right-role counter lands inside the P5 window, wherever it lands.
    Measured: ice_wizard vs lava_hound p3=0 -> +0.948 (probe, seed 7 step 131); skeletons at t=1.8 s
    p3=0 -> +1.000 (seed 11 step 2); probe2: 27 paid troop credits, 9 of them with placement part 0
    (timing part > 0 on 27/27, placement > 0 on 18/27). The old binary required `intercept` (same
    lane) for any credit. If the intent was "timing only counts with a placement", make it
    `place > 0 and ...` or multiply -- one line in `_geo_credit` (env.py 1043).

6.2 **The gate's late edge `t_hit + 1.0` (and P5's own `t_hit + P5_HI_PAD 1.0`) pays a LATE answer that
    the old `threat_max_depth 0.65` excluded.** Scenario: hog at tile 23.1, t_hit 0.1 s, Tesla dropped
    -> P5 1.0, gate 1.0, credit +1.000 (timing part). The old branch's `deep_ok` (identity depth <= 0.65)
    is not applied on the geometry path because the brief replaces it with the timing gate; the two
    disagree at the late end. Untested whether the policy exploits it (the correctness cap 20/match
    bounds it). Option: keep `deep_ok` as an extra binary gate on the geometry path (one `and`).

6.3 **d_path close penalty fires 2.5x more often than the snapshot form on the pros' Teslas**: 69/807 =
    0.086 (mean -0.505) vs 28/807 = 0.035 (s4). It is bounded (floor -0.3 inside `placement_credit`,
    -0.6 in the env credit) and it is the form the brief asked for; `p1_close_snapshot` sits beside it in
    the terms so the swap is one line (geometry_reward.py 675).

6.4 **The pre-place case is unreachable in the env.** `_threat_response` returns before any geometry
    when `tid[0] < 0.5` (quiet board), and identity only starts at `identity_front_y` 0.44 = tile 14.1
    (our frame). Scenario rows with the hog at tile 8.5-13.5: path P1 1.0, credit 0 (n=5). The gate's
    `t_cross - pre_place_s` edge therefore never bites for a building: by the time geometry runs
    `t_cross` is <= ~0.7 s. Reaching the pre-place case needs the quiet-board gate lifted for buildings
    (an env-doctrine change: HANDOFF says the quiet-board branch was retired deliberately) -- NOT done.
    Related: when the identity is set but no enemy body is on our half (`_threat_pos` finds none),
    `_geo_threat_obj` returns None and the module's `pick_threat` chooses (so the terms are still against
    a REAL body): `geo_threat_module` counts it (8 and 11 of the accepted placements in the two wiring
    matches), `geo_paid_module_threat` counts the paid ones (2 in match 1; probe2 2/27).

6.5 **Cap 1.0, not w_geom.** The brief: "cap at 1.0 if pull + offensive bow can coincide" -- they can (an
    X-Bow on the bank vs a bridge hog: P1 > 0 and P6 > 0), so `placement_credit` caps at 1.0 and the env
    credit tops out at w_time + w_geom = 3.0. The X-Bow offensive branch now pays w_geom*P6 <= 2.0
    where it paid a flat w_wincon 3.0 -- a scale drop for the main offensive credit of the deck, and P6
    is graded on the bow-to-tower gap (0 in the centre). Untested in training; it is the brief's spec.

6.6 **`_bonus` cap shared.** Geometry credits go through the same symmetric `correctness_cap` 20.0 per
    match as `threat_response` did. With credits up to 3.0 (vs 1.0 before) the cap is reached ~3x sooner
    on a busy defensive match. Not changed; noted.

6.7 **Full-suite artefact (not a regression):** in `unittest discover` the byte-identical test fails at
    ONE step (match 0 step 94: 0.0 vs ref -0.3, a `spell_waste`/`nado_bad` -0.3 that depends on
    cross-test process state) BEFORE and AFTER the edit; it passes standalone before and after (s5.4,
    s2). See s8 for the suite before/after diff.

## 7. Part C -- how `train-sim-ppo` reads `env.geometry.enabled` (NO training started)

7.1 **Parent process.** `run.py --config <yaml> train-sim-ppo ...`: `cli.py` 568 defines the GLOBAL
    `--config` (before the subcommand); `_cmd_train_sim_ppo` (cli.py 150-215) calls `_sized_config(args)`
    (cli.py 39-48) = `Config.load(args.config)` (+ the `--size` grid override), then wraps single keys
    with `_KeyOverride` (cli.py 217-231) for `--out`, `--drill-only` etc. There is NO CLI flag or
    environment variable for an arbitrary dotted key, and `Config.load` reads ONE file: `--config`
    REPLACES `config/config.yaml` entirely (HANDOFF 5cr.1 trap). So the override file must be a FULL copy.
    `train_sim_ppo` never reads `env.geometry` itself; the value is read by `SimMatchEnv.__init__`
    (env.py 438) from whatever `cfg` object the env is built with.

7.2 **Override file written:** `scratchpad/gauntlet/L59/cfg_armG.yaml` = byte copy of
    `icebow/config/config.yaml` (as of this brief, geometry block included) with ONE line changed
    (`diff` = line 1271 `enabled: false` -> `enabled: true`). Verified: `Config.load(cfg_armG)` ->
    `env.geometry = {'enabled': True, 'w_geom': 2.0, 'w_time': 1.0, 'pre_place_s': 3.0, 'p7_enabled':
    False, 'log_all_terms': True}`; every other key identical (`data` dicts equal after popping the
    block). The lead's launch line would be (same shape as `data/bench/c2r_run_launch.sh`):
    `PYTHONHASHSEED=0 .venv/Scripts/python.exe run.py --config C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/cfg_armG.yaml train-sim-ppo --out data/policy_armG.pt --seed 41 --size 432 --device cuda ... `
    (`--out` is required so it does not overwrite `train.sim_ppo_checkpoint`). NOTE the c2r arm did NOT
    run on `config/config.yaml` but on `data/bench/c2r_run.yaml`, which differs in more than the
    checkpoint keys (measured `diff` after stripping comments: `slots`, `lock_aware_targets` absent,
    `rl_epsilon_start/end` 0.60/0.10 vs 0.50/0.00, `rl_gate_tau` absent, `hazard_coef 0.5`,
    `opp_mem_slot5`/`spell_cast_delay_s` absent, plus the two c2r path keys). An arm G that is "c2r + geometry"
    must be derived from `data/bench/c2r_run.yaml` + the geometry block instead; I did not write that
    file (it would live under `data/`, which this brief must not touch) -- the lead can `cp` and append
    the 7-line block.

7.3 **BLOCKER for `--workers > 1` (the c2r shape uses `--workers 12`): the rollout workers do NOT see
    `--config`.** `src/clashrl/sim/remote_pool.py` `_worker` (line 52) does `cfg = Config.load()` with
    NO path (line 66) and builds its envs from that (`make_train_env(cfg, ...)` line 68) -- it re-reads
    `config/config.yaml` from disk in the spawned process, the exact seam HANDOFF already records for
    `--drill-frac` ("(c) `_worker` calls `Config.load()`") and the spell veto ("pass any threshold DOWN
    as a resolved float, never let the worker re-read the disk"). Reproduced the worker's code path in a
    fresh process: `Config.load()` + `make_train_env(cfg, seed=0, frac=0.0)` -> `geo_enabled = False`;
    the parent's `Config.load(cfg_armG)` -> `True`. So with `--config cfg_armG.yaml --workers 12` the
    learner's local twin env (`e0`, never stepped) would be geometry-ON and EVERY rollout env
    geometry-OFF -- the banner says on, the reward is off, no error. (The c2r run itself was not
    affected by this seam: `nado_retarget_reach_fix` is also true in `config/config.yaml` line 1170, and
    of the other keys where the two yamls differ the only env-side one is `observation.lock_aware_targets`
    -- absent in c2r_run.yaml, `false` in config.yaml, coded default `false` (env.py 165) -> same value both
    ways; `rl_epsilon_*`/`rl_gate_tau` are train_rl (live) keys, `hazard_coef` is read in the parent
    trainer, `opp_mem_slot5`/`spell_cast_delay_s`/`slots` are live-only.) Ways to actually run arm G,
    for the lead to pick:
    (a) `--workers 0` (in-process pool; the `cfg` object propagates) -- HANDOFF measures that at ~1/10-1/20
        the throughput of 12 workers;
    (b) the same fix shape as `drill_frac` / `spell_min_value`: ship the resolved `env.geometry` dict from
        the parent into `RemotePool(...)` -> `_worker(...)` and apply it in the worker as a
        `_KeyOverride`-style wrapper (or `cfg.data["env"]["geometry"] = geo` before `make_train_env`).
        ~10 lines in `remote_pool.py` + `train_sim_ppo.py` 156-161; NOT done here (outside the brief);
    (c) flip `enabled: true` in the committed `config/config.yaml` for the run's duration -- it would
        reach the workers, but it also flips every other sim consumer on the box and the brief forbids it.
    The eval pool (`train_sim_ppo.py` 1117, `SimMatchEnv(cfg, ...)` in-parent) reads the parent's cfg;
    with `--search-interval > 0` and workers, the searchers are built INSIDE the workers on the worker
    envs (`remote_pool.py` 267 `_RS.Searcher(e, ...)`), so the search inherits the worker's config too
    -- (b) fixes both at once, (a) makes everything in-parent.

## 8. Full suite before / after (`python -m unittest discover tests`, PYTHONHASHSEED=0)
- BEFORE any src edit (`suite_before.txt`): `Ran 1324 tests in 429.818s -- FAILED (failures=3, skipped=21)`:
  the two not-yet-wired `test_geometry_wiring` tests (expected: the enabled test could not pass before
  Part B; the disabled one failed at ONE step in discover mode only, s6.7) and
  `test_xbow_into_push.XbowIntoPushTests.test_the_clamped_frontmost_ROW_counts_as_forward`
  (`AssertionError: 0.5625 not greater than or equal to 0.625`) -- PRE-EXISTING, unrelated to this brief.
- AFTER all edits (`suite_after.txt`): `Ran 1331 tests in 419.338s -- FAILED (failures=1, skipped=21)`:
  only the same pre-existing `test_xbow_into_push` failure. +7 tests = the six new (a)-(f) module tests
  + `test_bridge_block_case_is_full_timing_credit`. Both wiring tests pass in discover mode this time
  (`[wiring] match 0 seed 7: 222 steps, reward sum -13.1924, identical to ref` / `match 1 seed 11: 290
  steps, -13.2734, identical to ref`). One discover-mode oddity to be honest about: the ENABLED match 0
  sum printed -12.2440 in the suite vs -11.9440 standalone (s5.4) -- a 0.3 difference of the same shape
  as the s6.7 artefact (a -0.3 spell term that depends on process state left by earlier tests); the
  disabled sequence was byte-identical in both runs, and the enabled test only asserts that geo_* keys
  are present, so this does not change any result here, but a future byte-level assertion on the
  ENABLED path should run the test standalone.
- No `data/` file touched; `src/clashrl/env.py` (live) untouched; no git commit made
  (`git status --short -- src tests config`: M config/config.yaml, M src/clashrl/geometry_reward.py,
  M src/clashrl/sim/env.py, M tests/test_geometry_reward.py, ?? tests/test_geometry_wiring.py).

## 9. Lead rulings on the s6 flags -- APPLIED (this section supersedes s5.2/5.3/5.5, s7.3 and the s8 suite line)

### 9.1 What changed (all `L59` hunks; `git diff --stat -- src tests config`: 6 files, +369/-21)
- **6.1** `src/clashrl/sim/env.py` 1040-1052 `_geo_credit`: `credit = (w_time*P5 + w_geom*place*gate) if place > 0 else 0.0`
  where `place = placement_credit(terms, kind, p7_enabled)`. A right-role card with no positive placement
  part (troop behind the king; a building once `pull_ok` = 0 and P6 = 0) earns nothing, timing included.
- **6.2** kept: the gate's late edge stays `t_hit + 1.0`; `deep_ok` NOT re-added on the geometry path.
- **6.3** `src/clashrl/geometry_reward.py` 662-680 `placement_credit(building)`: the close term is now
  `max(FLOOR, p1_close_snapshot)` (the gap to the threat's CURRENT position, i.e. dropping on top of it);
  `p1_close_penalty` (d_path form) is still computed and logged (`geo_p1_close`) but not charged.
  Tests updated: `test_centre_beats_corner` (corner credit 0.85*0.75 = 0.6375, the d_path penalty no longer
  charged), `test_e_placement_credit_bounds` (worst-case dict carries `p1_close_snapshot=-1`).
- **6.4** left as is; recorded (s5.5 scenario rows 1-5: P1 1.0, credit 0 while the hog is on the enemy half).
- **6.5** `src/clashrl/sim/env.py` 1749-1757 X-Bow offensive branch: `val = self.w_wincon * p6_siege`
  (w_wincon 3.0, the weight the flat credit had); `bow_first_frac` (< 30 s) and the split-push /
  hostile-deck factors below it unchanged. Range of the offensive credit is now [0, 3.0] (was flat 3.0).
- **6.6** left.
- **Part C** first done as (b) -- shipping only the resolved `env.geometry` dict -- then SUPERSEDED by the
  lead's amendment (general seam fix, s9.7): no `geometry` kwarg survives in `remote_pool.py` /
  `train_sim_ppo.py` (`grep -n "geometry=" src/clashrl/train_sim_ppo.py src/clashrl/sim/remote_pool.py`
  -> nothing). s9.2 below is the (b)-era test output, kept as the record of that step; s9.7 has the current one.

### 9.2 Test output (verbatim; `test_geometry_reward.txt`, `test_geometry_wiring.txt`)
`python -m unittest tests.test_geometry_reward`: `Ran 26 tests in 0.795s -- OK`.
`python -m unittest tests.test_geometry_wiring -v`:
```
test_override_reaches_the_worker_env (tests.test_geometry_wiring.GeometryReachesWorkers.test_override_reaches_the_worker_env) ... ok
test_disabled_is_byte_identical (tests.test_geometry_wiring.GeometryWiring.test_disabled_is_byte_identical) ... ok
test_enabled_runs_and_logs_geo_terms (tests.test_geometry_wiring.GeometryWiring.test_enabled_runs_and_logs_geo_terms) ... ok

----------------------------------------------------------------------
Ran 3 tests in 11.557s

OK
[wiring] worker probe with the shipped override: {'geo_enabled': True, 'geometry': {'enabled': True, 'w_geom': 2.0, 'w_time': 1.0, 'pre_place_s': 3.0, 'p7_enabled': False, 'log_all_terms': True}, 'cls': 'SimMatchEnv'}
[wiring] worker probe with nothing shipped: {'geo_enabled': False, 'geometry': {'enabled': False, 'w_geom': 2.0, 'w_time': 1.0, 'pre_place_s': 3.0, 'p7_enabled': False, 'log_all_terms': True}, 'cls': 'SimMatchEnv'}
[wiring] match 0 seed 7: 222 steps, non-trade reward sum -10.9461, identical to ref
[wiring] match 1 seed 11: 290 steps, non-trade reward sum -9.1382, identical to ref
[wiring] ENABLED match 0 seed 7: 222 steps, reward sum -10.9461, geo keys 4
    geo_gate             fires   17  sum  +16.9484  (+17 / -0)
    geo_p3               fires    1  sum   +1.0000  (+1 / -0)
    geo_p5               fires    3  sum   +2.9484  (+3 / -0)
    geo_threat_module    fires    8  sum   +8.0000  (+8 / -0)
[wiring] ENABLED match 1 seed 11: 290 steps, reward sum -5.1382, geo keys 8
    geo_credit           fires    2  sum   +6.0000  (+2 / -0)
    geo_gate             fires   24  sum  +23.3333  (+24 / -0)
    geo_p2               fires    1  sum   +1.0000  (+1 / -0)
    geo_p3               fires    7  sum   +4.4157  (+7 / -0)
    geo_p4               fires    1  sum   +0.3333  (+1 / -0)
    geo_p5               fires    7  sum   +6.3333  (+7 / -0)
    geo_paid_module_threat fires    1  sum   +1.0000  (+1 / -0)
    geo_threat_module    fires   11  sum  +11.0000  (+11 / -0)
```
The worker test builds a real 1-worker `RemotePool` (spawned process) with the parent's resolved block
(`enabled: True`) while `config/config.yaml` on disk says `false`: the worker reports `geo_enabled True`
and the shipped block; with nothing shipped it reports the disk value `False`. n = 1 worker x 1 env, each way.
The byte-identical regression was ALSO run standalone after every edit
(`python -m unittest tests.test_geometry_wiring.GeometryWiring.test_disabled_is_byte_identical`): OK,
222 + 290 steps identical to the reference. (The ENABLED sums are "reward sum" as before -- the enabled
test does not subtract the trade term -- match 0 now pays no geometry credit at all: its single paid
credit of s5.4 was the timing-only ice-wizard payment that 6.1 removes.)

### 9.3 A pre-existing nondeterminism found while doing that (NOT caused by this brief; not fixed -- the lead's call)
The first standalone rerun of the byte-identical test after adding the worker test FAILED at one step
(match 0 seed 7 step 94: 0.0 vs ref -0.3), the same step that flipped in discover mode (s6.7). Bisected in
fresh processes (`_seam.py`, n=5 modes): the sequence matches the reference in a bare process and after
`import torch`, but flips after ANY of `random.random()`, `Config.load()` twice, or `import
clashrl.sim.remote_pool` -- i.e. it depends on the process's memory layout, not on the RNG. The differing
term is `elixir_trade` (-0.3 on a skeletons drop at t=57.0 with 6 skeleton-army bodies on the board; same
board and action both ways, `_seam3.py`). `SimMatchEnv._trade_reward` (env.py 2134-2225) keys its
per-unit ledgers by `id(u)`; CPython reuses a dead object's address for the next allocation, so a new
unit can inherit a dead unit's ledger entry depending on allocation history. Consequence for training:
the trade term is ~1-in-500-steps noisy across processes (one step in 512 here) -- small, but it means no
per-step reward sequence is reproducible across processes until the ledger keys on a unit serial
instead of `id()`. Handling here: `run_matches` now records the per-step reward MINUS that step's
`elixir_trade` delta (nothing in this brief touches the trade ledger), the reference was RE-RECORDED
from the untouched HEAD tree (`git archive HEAD icebow/src/clashrl` unpacked to `L59/_head/`, imported
first by `reward_ref.py`, asserted `not hasattr(SimMatchEnv, "_geo_credit")`; old total-reward
reference kept as `reward_ref_total_v1.npy`), and the comparison uses `atol=1e-9` (the subtraction
leaves 5.6e-17 residue). Pre-edit non-trade sums: match 0 -10.9461, match 1 -9.1382; the post-edit
disabled path reproduces both to 1e-9 at every step.

### 9.4 Probes re-run under the rulings (every number from the run; `*_v2.txt`)
- `geo_probe_v2.txt` (the two wiring matches, enabled): paid credits n=2, both +3.000 (skeletons vs giant,
  p3 1.0, p5 1.0). The two timing-only payments of s5.5 (ice_wizard +0.948, skeletons at t=1.8 s +1.000)
  are gone, as 6.1 intends.
- `geo_probe2_v2.txt` (seeds 20..31, 12 ladder matches, 366 scored placements): building scored 4 paid 0;
  troop scored 218 paid 22 (was 27), credit min +0.114 median +2.000 max +3.000, placement part > 0 on
  22/22 (was 18/27), timing part > 0 on 22/22, gate < 1 on 9/22, module-picked threat among the paid 1/22;
  spell scored 144 paid 0 (P4 nonzero 17/144, log-only). P3 nonzero 61/218 (mean 0.533), P5 nonzero
  61/218 (mean 0.817) -- unchanged, they are logged terms.
- `geo_scenario_v2.txt` (Hog down the left lane vs Tesla at (9,21); n=11 enabled + 6 disabled rows):
  ```
  hog tile y   8.5  8.7 11.1 12.3 13.5 | 14.7  15.9  17.1 | 18.3  20.7  23.1
  tid0 (env)     0    0    0    0    0 |    1     1     1 |    1     1     1
  P1 path     1.00 1.00 1.00 1.00 1.00 | 1.00  1.00  1.00 | 0.00  0.00  0.00
  P5          0.00 0.00 0.00 0.07 0.46 | 0.85  1.00  1.00 | 1.00  1.00  1.00
  credit v1   0    0    0    0    0    | 2.848 3.000 3.000 | 1.000 1.000 1.000
  credit v2   0    0    0    0    0    | 2.848 3.000 3.000 | 0     0     0
  old binary  0    -    0    -    0    |   -   0      -    | 1.000 1.000  -
  ```
  After the ruling the Tesla is paid only while the pull is possible (hog tile 14.7-17.1: +2.85/+3.0/+3.0),
  nothing once the hog has locked on the tower (18.3+) and nothing at t_hit 0.1 s -- the late-answer
  payment of flag 6.2 was a timing-only payment and 6.1 removes it for buildings whose pull is gone
  (it remains for a troop counter placed with P3 > 0 late). The old binary's +1.0 at hog 18.3/20.7 is
  the credit the graded version stops paying.
- Credit ranges now: `placement_credit` in [-0.3, 1.0]; env credit for a building/troop is 0 or in
  (0, 3.0] (a positive placement part is required, so the -0.6 floor of s5.3 is unreachable: the snapshot
  close penalty can only reduce a positive P1 credit, and if it drives `place` to <= 0 nothing is paid);
  X-Bow offensive `w_wincon*P6` in [0, 3.0].

### 9.5 How arm G is launched (nothing under `data/` written by me) -- see s9.7 for the mechanism after the amendment
- Mechanism: `run.py --config <full run yaml> train-sim-ppo ...`. The yaml must be a FULL config (the
  flag REPLACES config.yaml) and must CONTAIN the `env.geometry` block with `enabled: true` -- the
  parent resolves it and ships it to every rollout worker; a yaml without the block ships `None` and the
  workers fall back to the disk `config/config.yaml` (`enabled: false`).
- Ready file: `C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/cfg_armG.yaml` = `icebow/config/config.yaml`
  with the single change `env.geometry.enabled: true` (verified by `Config.load`, s7.2). Launch line:
  `cd /c/Users/benpe/ClashBot/icebow && PYTHONHASHSEED=0 .venv/Scripts/python.exe run.py --config C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/cfg_armG.yaml train-sim-ppo --out data/policy_armG.pt --seed 41 --envs 96 --workers 12 --size 432 --device cuda --search-interval 4 --matches <N>`
  (`--out` so the default checkpoint is not overwritten; `--resume`/`--init` per the lead's choice of
  starting weights). If arm G is meant to be "c2r + geometry", the lead derives the yaml from
  `data/bench/c2r_run.yaml` + the 7-line block instead (s7.2 lists the measured differences).
- Proof the override reaches the workers: `tests/test_geometry_wiring.py::GeometryReachesWorkers` (s9.2).
  On a live launch the same check is `RemotePool.probe()`; the banner alone is not evidence (s7.3).
- NOT started. No commits. `data/` untouched. `src/clashrl/env.py` (live) untouched.

### 9.6 Full suite after the rulings (`suite_after_v2.txt`)
`python -m unittest discover -s tests -t .` with the s9.1 rulings applied (before the s9.7 amendment):
`Ran 1332 tests in 330.651s -- FAILED (failures=1, skipped=21)`; the one failure is the pre-existing
`test_xbow_into_push.XbowIntoPushTests.test_the_clamped_frontmost_ROW_counts_as_forward` (0.5625 < 0.625,
fails identically on the untouched HEAD tree, s8). 1332 = 1331 (s8) + the worker test. Nothing else changed.

### 9.7 Lead amendment to Part C -- the seam fixed generally (config PATH + parent overrides, not one dict)
**Does `Config` record its source?** No: `config.py` `Config` was `data` + `root` only; `load()` computed
`cfg_path` and dropped it. Added (additive, `src/clashrl/config.py` 16-20, 33):
`source: Optional[Path] = None`, set to `Path(cfg_path).resolve()` by `load()`. Default None keeps the
five `Config(data=..., root=...)` hand-constructors (sim_bench.py, 4 tests) working. The `_KeyOverride` /
`_DrillFracOverride` proxies forward unknown attributes (`__getattr__`), so `getattr(cfg, "source")` on
the wrapped cfg that `_cmd_train_sim_ppo` hands to `train_sim_ppo` resolves to the file `--config` named --
no threading of `args.config` through cli.py was needed, and cli.py is unchanged.

**What crosses the pipe now** (`src/clashrl/train_sim_ppo.py` 112-131 `worker_config_args(cfg)`, used at
185 `RemotePool(..., **worker_config_args(cfg))`):
- `config_path` = `cfg.source` (str) -- the worker does `Config.load(config_path)`; None (hand-built
  Config) -> `Config.load()`, the old behaviour (`remote_pool.py` 66-71).
- `overrides` = `[(key_tuple, value)]` for the parent's IN-MEMORY config changes that no file load can
  see: `("action","grid")` (`--size` mutates `cfg.data` in `_sized_config`) and `("sim","drill_only")`
  (`--drill-only` is a `_KeyOverride` proxy). Resolved values, never sentinels; a None value means
  "absent in the parent too" and is not shipped (setting it would turn a `get(..., default=X)` into None).
  Applied into `cfg.data` in the worker before `make_train_env` (`remote_pool.py` 72-79).
- `drill_frac` and `spell_min_value` keep their explicit arguments exactly as before (not regressed).
- `--out` (`train.sim_ppo_checkpoint`) is a parent-only key (the learner writes the checkpoint); it is
  not shipped and the test asserts the parent still resolves it.
`RemotePool.__init__` (311-317) takes `config_path=None, overrides=None`; spawn args 332-333; the
`("probe",)` reply (292-299) now also reports `config_source`, `grid`, `drill_only` from inside the worker.

**Pre-existing seam defects this closes (measured by the probe's "no --config" / "nothing shipped" rows):**
(1) EVERY env-side key of a `--config` run yaml stopped at the learner -- the parent and its local twin
env ran the yaml, every rollout env ran `config/config.yaml`. For the one run yaml I measured
(`data/bench/c2r_run.yaml`, s7.2) the only env-side key that differs is `observation.lock_aware_targets`,
absent there vs `false` on disk with coded default `false` -- the same value both ways, so THAT run's
rollout envs were not affected; the defect is structural (any env-side key that DOES differ, e.g.
`env.geometry.enabled` for arm G, would have been silently OFF in every worker). (2) `--drill-only <name>` never reached a worker: `drill_env.py` 1155 reads
`sim.drill_only` off the WORKER's cfg, which was the disk value (None) -- so under workers the flag
printed its banner and every drill still ran (the "nothing shipped" probe row shows `drill_only: None`,
which is what HEAD's workers saw). (3) `--size 576` with a 432 config.yaml would have built 576-cell
parent twins over 432-cell worker envs (not exercised; the grid override is shipped now).
Not claimed: whether any past run actually depended on (1)-(3) -- that is a log question for the lead.

**Proof, through the REAL CLI path** (`tests/test_geometry_wiring.py` 109-192 `GeometryReachesWorkers`):
the real argparse parser parses `--config <cfg_armG.yaml> train-sim-ppo --workers 1 --envs 1 --matches 1
--out C:/nonexistent/armG_probe.pt --drill-only tesla_pulls_the_wincon --size 432`; the real
`_cmd_train_sim_ppo` builds the cfg (with its `_KeyOverride` wrappers); `train_sim_ppo` is stubbed to
CAPTURE that cfg instead of training (no env built in the parent, nothing written); then a 1-worker
`RemotePool(1, 1, seed=5, drill_frac=0.0, spell_min_value=0.0, **worker_config_args(cfg))` is spawned
and probed. Output (`test_geometry_wiring_v3.txt`, verbatim, paths shortened):
```
[cli] --size 432 -> action.grid [18, 24]
[train-sim-ppo] checkpoint -> C:/nonexistent/armG_probe.pt
[train-sim-ppo] DRILL-ONLY: tesla_pulls_the_wincon
[wiring] --config cfg_armG.yaml --workers 1: shipped {'config_path': '...\\L59\\cfg_armG.yaml', 'overrides': [(('action', 'grid'), [18, 24]), (('sim', 'drill_only'), ['tesla_pulls_the_wincon'])]}
[wiring]   worker probe: {'geo_enabled': True, 'geometry': {'enabled': True, 'w_geom': 2.0, 'w_time': 1.0, 'pre_place_s': 3.0, 'p7_enabled': False, 'log_all_terms': True}, 'config_source': '...\\L59\\cfg_armG.yaml', 'grid': [18, 24], 'drill_only': ['tesla_pulls_the_wincon'], 'cls': 'SimMatchEnv'}
[wiring] no --config --workers 1: shipped {'config_path': '...\\icebow\\config\\config.yaml', 'overrides': [(('action', 'grid'), [18, 24]), (('sim', 'drill_only'), ['tesla_pulls_the_wincon'])]}
[wiring]   worker probe: {'geo_enabled': False, 'geometry': {'enabled': False, ...}, 'config_source': '...\\icebow\\config\\config.yaml', 'grid': [18, 24], 'drill_only': ['tesla_pulls_the_wincon'], 'cls': 'SimMatchEnv'}
[wiring] nothing shipped: {'geo_enabled': False, 'geometry': {'enabled': False, ...}, 'config_source': '...\\icebow\\config\\config.yaml', 'grid': [18, 24], 'drill_only': None, 'cls': 'SimMatchEnv'}
```
Asserted: with `--config cfg_armG.yaml` the worker's env has `geo_enabled True`, its `config_source`
IS cfg_armG.yaml, its geometry block equals the parent's, grid [18,24] and drill_only
['tesla_pulls_the_wincon'] arrived; with no `--config` the worker loads config.yaml and reports
`geo_enabled False`; with nothing shipped (hand-built Config) it falls back to `Config.load()`.
n = 1 worker x 1 env per row, 3 rows. `tests.test_geometry_wiring -v`: `Ran 3 tests in 14.351s -- OK`;
the byte-identical regression re-run standalone after ALL edits:
`tests.test_geometry_wiring.GeometryWiring.test_disabled_is_byte_identical` -> `Ran 1 test in 1.329s OK`,
match 0 seed 7 222 steps non-trade sum -10.9461 identical, match 1 seed 11 290 steps -9.1382 identical.
`tests.test_geometry_reward`: `Ran 26 tests in 0.816s -- OK`. Seam-adjacent modules re-run green:
test_spell_card_veto (its source-inspection tests of train_sim_ppo / remote_pool), test_wincon_bank,
test_aggro_drills, test_lock_aware_targets, test_nado_retarget_reach, test_bot_attack_floor
(the direct `Config(data=, root=)` constructors) -- `OK`.

**Arm G launch after the amendment** -- the s9.5 line is unchanged and is now the mechanism itself:
`cd /c/Users/benpe/ClashBot/icebow && PYTHONHASHSEED=0 .venv/Scripts/python.exe run.py --config C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/cfg_armG.yaml train-sim-ppo --out data/policy_armG.pt --seed 41 --envs 96 --workers 12 --size 432 --device cuda --search-interval 4 --matches <N>`
Every key of `cfg_armG.yaml` (a full config.yaml copy, only `env.geometry.enabled: true` differs) now
reaches all 12 workers because each loads that same file; no per-key shipping. The control arm is the
same line without `--config` (or with a full copy that keeps `enabled: false`). NOT started.
Footprint: `git diff --stat -- src tests config`: 7 files, +415/-23 (+ untracked
`tests/test_geometry_wiring.py`); no `data/` change; live `src/clashrl/env.py` untouched; no commits.

### 9.8 Full suite after the amendment (`suite_after_v3.txt`)
`python -m unittest discover -s tests -t .` after ALL edits (rulings + the s9.7 seam fix):
`Ran 1332 tests in 341.218s -- FAILED (failures=1, skipped=21)`; the one failure is the same pre-existing
`test_xbow_into_push.XbowIntoPushTests.test_the_clamped_frontmost_ROW_counts_as_forward` (0.5625 < 0.625,
fails identically on the untouched HEAD tree, s8). Identical pass/fail set to s9.6 (1332 tests, 1 fail,
21 skipped); the only difference is the wiring test's body. Suite time 341 s vs 331 s (v2), n=1 each.

## 10. File index (all under `C:/Users/benpe/ClashBot/`)
- Edited: `icebow/src/clashrl/geometry_reward.py`, `icebow/src/clashrl/sim/env.py`,
  `icebow/src/clashrl/config.py` (additive `source`), `icebow/src/clashrl/sim/remote_pool.py`,
  `icebow/src/clashrl/train_sim_ppo.py` (`worker_config_args` + the RemotePool call),
  `icebow/config/config.yaml` (block added only, 1270-1276), `icebow/tests/test_geometry_reward.py`;
  new `icebow/tests/test_geometry_wiring.py`. `cli.py` and the live `src/clashrl/env.py`: untouched.
- L59 scratch (`scratchpad/gauntlet/L59/`): `gate_replay.py`, `gate_analyze.py`, `gate_summary.txt`,
  `gate_run.log`, `p1/` (gate_plays.csv, gate_tesla_probe.csv, drive_summary.jsonl);
  test outputs `test_geometry_reward.txt`, `test_geometry_wiring.txt` (b-era), `test_geometry_wiring_v3.txt`
  (current); reference `reward_ref.py`, `reward_ref.npy` (non-trade, from the HEAD tree in `_head/`),
  `reward_ref_total_v1.npy` (old total-reward ref); suites `suite_before.txt`, `suite_after.txt`,
  `suite_after_v2.txt`, `suite_after_v3.txt` (final); probes `geo_probe.py/.txt/_v2.txt`,
  `geo_probe2.py/.txt/_v2.txt`, `geo_scenario.py/.txt/_v2.txt`; seam bisect `_seam.py`, `_seam2.py`,
  `_seam3.py`; `cfg_armG.yaml`; patch scripts `_patch_a.py`, `_patch_tests.py`, `_patch_env.py`,
  `_patch_rulings.py`; section drafts `_sec9.md`, `_sec9b.md`, `_sec9c.md`; `_head/` = `git archive HEAD
  icebow/src/clashrl` (read-only, for the reference recording). Pre-existing L59 files not mine:
  `armE_T3.txt`, `arm_gates.py`, `cell_sat_probe.*`, `make_armE_ckpt.py`.

STATUS: complete
