# L59 brief: step 1 -- restrict the graded terms, path-based P1, wire into the sim reward (arm G)

Repo `C:\Users\benpe\ClashBot`; python `icebow/.venv/Scripts/python.exe` run from cwd `icebow` with
`C:/...` paths; `PYTHONHASHSEED=0`. No installs. No git commits (the lead commits). Never touch `data/`.
Do NOT edit `src/clashrl/env.py` (live path) in this brief -- the live log-only hook is a later step.
Do NOT change any existing `config/config.yaml` VALUE; you may ADD the `env.geometry:` block.
Progress file, written INCREMENTALLY as you go, ending `STATUS: complete`:
`C:\Users\benpe\ClashBot\scratchpad\gauntlet\L59\wire.md`. Numbers only from what you ran.

Read first: `research/RADIUS_REWARD_PROPOSALS.md` §1, §4 (P1/P2/P3/P5/P6), §7.4, §7.5;
`scratchpad/gauntlet/L58/impl_geometry.md` (the module's API + CHOICE list); `scratchpad/gauntlet/L58/gate.md`
§1a, §1c, §1d, §1e (WHY the restrictions below); HANDOFF.md §5cs.29 (grep for it).

## Part A -- `src/clashrl/geometry_reward.py` changes (the gate's verdicts, HANDOFF 5cs.29)

1. **P2_cover -> buildings only.** For placements of kind troop/spell `p2_cover` = 0.0. (Gate: on troops
   it ranks the pros' river-bank skeletons below the policy's behind-the-king cell 2%/23%; on spells the
   cast point on the enemy half has cover 0 by construction, rocket 1%/71%.)
2. **P7_fragility -> not for swarm cards.** If the placed card's KB role is swarm (skeletons, etc.;
   use the same role source `role_average_radii` uses) `p7_fragility` = 0.0. Keep it for ranged low-HP
   counters (ice wizard). (Gate: 0.1% for / 7.6% against the pros' surround placement.)
3. **Path-based P1** (replaces the current-position snapshot, impl_geometry deviation 4). For a
   building placement b against threat t:
   - `path(t)` = t's forward march path: current position -> its lane's bridge (if still on the enemy
     half of the river) -> the nearest own ALIVE tower it would target (`_march_gap` semantics; if t
     already has a locked target use that). Represent it as 1-2 straight segments in tiles.
   - `d_path` = min tile distance from b to the FORWARD part of the path (never the part behind t).
   - `pull_ok` = the march distance from t to b's hitbox is shorter than t's march distance to that
     own tower (b will be acquired first).
   - `p1_pull_band = band(d_path; lo = r_atk(t) + 1.0, hi = r_sight(t), w = 2.0) * pull_ok`;
     `p1_close_penalty` unchanged in form but measured on `d_path`.
   - Keep the old snapshot value available as `p1_snapshot` in the returned dict so the gate rerun can
     report both.
4. **Building P5** stays in the dict as `p5_timing` (it IS the timing term) -- no change to the
   formula; the wiring below treats it as a play-timing term, not a placement term.
5. **New helper** `placement_credit(terms: dict, kind: str) -> float` = the PLACEMENT part of the
   graded reward, per kind:
   - building: `p1_pull_band * (0.5 + 0.5 * p2_cover) + p1_close_penalty + p6_siege`
   - troop:    `p3_intercept`   (+ `p7_fragility` only if `cfg p7_enabled`, default off in run 1)
   - spell:    0.0  (P4 is LOGGED only in run 1; the spell ledger is untouched)
   and `timing_credit(terms) -> float` = `p5_timing` (bridge-block full credit is already inside P5
   per §7.4 -- check that `bridge_block_case` -> p5 = 1.0 is what the module does; if not, make it so).
6. Every term must be clipped so `placement_credit` is in [-0.3, 2.0] for a building (P1*(..)+P6 <= 2
   only if a placement is both a pull and an offensive bow -- if that can happen, cap at 1.0 total).

Tests to ADD to `tests/test_geometry_reward.py` (run `python -m unittest tests.test_geometry_reward`):
(a) pre-placed Tesla at (9,21) vs a Hog still at the ENEMY bridge approach (own-frame y ~ 12) --
snapshot P1 = 0 but path P1 > 0; (b) the same Tesla vs the Hog at (3.5,16) -- path P1 >= snapshot P1;
(c) P2 = 0 for a skeleton placement; (d) P7 = 0 for skeletons, unchanged for ice wizard; (e)
`placement_credit` bounds; (f) pull_ok false when the building is BEHIND the tower relative to the
threat's path (e.g. Tesla at (9,31) behind the king vs a Hog in the left lane).

**Gate rerun (required, ~2 min):** `scratchpad/gauntlet/L58/gate_replay.py` -> copy to
`scratchpad/gauntlet/L59/gate_replay.py`, run Part 1 for tesla and x-bow only, report: fraction of pro
Tesla plays with `p1_pull_band > 0` (was 40.9% with the snapshot, n=807), pro-tile-beats-locked on the
new `placement_credit` for tesla and x-bow, and the doc §3 gate rule (modal (9,21) vs corner on the
Hog/Giant/PEKKA boards) under path P1: median diff, modal>corner / <. If path P1 ranks (9,21) BELOW the
corner on the median board, STOP and report -- do not wire it.

## Part B -- wire into `src/clashrl/sim/env.py` (arm G)

Read `_threat_response` (line ~970) fully, and the X-Bow in-band credit at ~1588 (`central`,
`xbow_front..xbow_back`). Add a config block (defaults OFF so the current reward is byte-identical):

```yaml
env:
  geometry:
    enabled: false        # arm G sets true
    w_geom: 2.0           # HANDOFF 5cs.29: 1/mean restricted band score of c2r_best (0.430), cap 2.0
    w_time: 1.0           # replaces the binary deep_ok / threat_response credit scale
    pre_place_s: 3.0      # geometry credit still paid when t_resp is up to this early before t_cross
    p7_enabled: false
    log_all_terms: true   # every term into the ledger even when not paid
```

Read config VALUES via the project's `cfg.get("env", "geometry", ...)` idiom (check how nested keys are
read elsewhere in env.py; do not invent a new loader).

When `enabled`:
- In `_threat_response`, keep every NON-geometry gate exactly as is (quiet board -> 0; triage
  `bodies_ignore_frac`; `budget_ok`; `card_threat.counters`; the pull-spell and damage-spell early
  returns; the misread penalty). Replace ONLY the geometry/timing parts:
  - building branch: `deep_ok and 0.50 <= ny <= 0.80` -> compute `board = board_from_engine(self.eng, 0)`
    and `terms = score_placement(board, placement_from_spec(...))` (the threat the module picks must be
    the same as `_threat_pos()`'s -- if not, pass the env's threat explicitly; record which);
    `credit = w_time * timing_credit(terms) + w_geom * placement_credit(terms, "building") * gate`
    where `gate = 1.0` if `t_resp <= t_hit + 1.0` and `t_resp >= t_cross - pre_place_s`, else the
    band value of the same edges with w 1.5 s (a soft version; state your exact formula). Consume a
    threat credit (`self._threat_credits += 1`) only when `credit > 0`.
  - troop counter branch: `intercept and deep_ok` -> `credit = w_time * p5 + w_geom * p3` with the same
    gate; consume a credit only if `credit > 0`.
  - the misread penalty (`w_threat_miss if intercept`) keeps the BINARY `intercept` test (it is a role
    misread, not a geometry term).
- X-Bow (~1588): replace the `central`/`in_band` binary credit with `w_geom * p6_siege` (same
  `terms`); a defensive centre bow scores P6 = 0 there -- keep whatever the code pays for a DEFENSIVE
  bow through the other branches unchanged (read the surrounding code and say what it does).
- Ledger: `self.rw_stats.add(name, value)` for `geo_p1`, `geo_p2`, `geo_p3`, `geo_p5`, `geo_p6`,
  `geo_p1_close`, and log-only `geo_p4`, `geo_p4_nado`, `geo_p4_king`, `geo_p7`,
  `geo_bridge_detected`, `geo_bridge_case` (value 1 per fire so the count is readable). Check how
  `rw_stats.add` returns/accumulates (does it ADD the value to the episode reward, or only record?) --
  log-only terms must NOT change the reward; if `add` accumulates, use the ledger's record-only method
  or add one.
- `score_placement` is called at most once per accepted placement; cache `board_from_engine` per step.

Regression test (required): `tests/test_geometry_wiring.py` -- (1) with `enabled: false`, 2 sim
matches with a fixed seed and a fixed random action stream produce the SAME per-step reward sequence
as the current code (record the sequence BEFORE your edit into `scratchpad/gauntlet/L59/reward_ref.npy`
and compare after); (2) with `enabled: true`, the same stream runs without exceptions and the ledger
holds `geo_*` keys; print per-key fire count and sum per match. Also run the existing test suite
(`python -m unittest discover tests` -- note which tests already fail BEFORE your change, if any).

## Part C -- smoke of the training entry point (no launch)

Find how `train-sim-ppo` (or the entry used for c2r, grep HANDOFF for `c2r_best` launch command) reads
`env.geometry.enabled`; confirm a CLI/config path exists to turn it on for arm G without editing the
committed config value (e.g. an override yaml like `data/bench/live_obs.yaml` -- do not create anything
under data/; put an override at `scratchpad/gauntlet/L59/cfg_armG.yaml` if the loader supports one and
say how it is passed). Do NOT start training.

Report in wire.md: files + line ranges, test output verbatim, the gate rerun numbers with n, the exact
gate formula you used, the credit ranges, and anything you could not do as written.
