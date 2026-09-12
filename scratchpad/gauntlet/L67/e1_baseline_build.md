# E1 option B -- baseline tooling build log (L67, 2026-09-12)

Owner ruling 2026-09-12 "go with B": measure `icebow/data/pipeline/s1_icebow_v6lat_s0.pt` against HELD-OUT ghosts
in the engine under the LIVE deploy rule. No training code. Design: `e1_engine_rl_design.md` (same dir).
Labels: (a) verified/measured; (b) untested. Code + offline tests only; engine NOT booted in this build.

## Log
- Started. Build log created; design read (sections 0-7).
- (a) `pipeline/` is the repo top-level package (engine_play.py, obs_contract.py, dataset.py, tests/). New files go there.
- (a) Python for everything: `icebow/.venv/Scripts/python.exe` (imports torch 2.11.0+cu128, native_core.env and
  replay_drive without connecting -- checked by import only).
- (a) Corpus v6 sources: 1,638 tags are in `icebow/data/royaleapi/crawl2/battles.csv`, 603 in
  `scratchpad/gauntlet/ext/crawl_hf_icebow/battles.csv`, 0 in both, 0 in neither.
- (a) crawl2: OUR deck is always the `team_deck` column (1,635 rows team-only + 3 mirrors, 0 opponent-only), so
  `opponent_tags` IS the ghost's tag. HF battles.csv: `opponent_tags` empty in all rows (as the design says).
  One crawl2 tag has 2 identical rows (L9YPLCC9G vs JP0G2Q2P8) -- same opponent, harmless.
- (a) Live rule constants: HANDOFF l.2747 "gate tau 0.27, anti-stall 9 elixir / 12 s" for v6lat_s0 run8/run9;
  play.py:181-185 reads `play.stall_elixir` (default 9.0) and `play.student_gate_tau`; neither key is in
  icebow/config/config.yaml (so 0.27 came from the owner's CLI/overrides -- taken from HANDOFF, not config).
- (a) Live deck forms: `icebow/config/cards.yaml` deck = tesla `evolved: true`, knight `evolved: true`, rest base;
  `pipeline/decks/icebow.yaml` = tesla_evo / knight_evo. So our-side filter = {Knight@evolution, Tesla@evolution}.
- DECISION: RawEngineEnv is a `__new__` factory returning an instance of a closure class, so it cannot be
  subclassed directly. `PoolV1Env` repeats the same factory pattern over `EngineMatchEnv` with RawEngineEnv's two
  overrides (`_render` raw, `final_decks`) plus pool-v1 `_resolve_decks`. Deviation in form only.
- DECISION: pool v1 deck items are stored IN THE CORPUS FINAL ORDER (so `_resolve_decks` is a lookup, no probe
  reset); items are rebuilt with `replay_drive.deck_for_side` on the source battles.csv row and permuted to match
  `final_decks` names exactly (assert).
- Wrote `pipeline/e1_view.py` (live_view) and `pipeline/e1_pool.py` (builder + verify + PoolV1Mixin/PoolV1Env).
- (a) FULL BUILD into session scratch (not data) 2026-09-12 ~16:00, 25.1 s, 2,241 corpus files streamed one by one:
  **1,810 candidates -> held-out 293 / train 1,505 / dropped 12** -- identical to the design's counts.
  Refused: 428 our forms != live deck, 3 not exactly one side. S1 split check against the stored split in
  `s1_dataset_v6.npz`: 1,810/1,810 candidates in the dataset, crc rule agrees on 1,810/1,810.
- Wrote `pipeline/e1_eval.py` (live / none / random policies, eval + parity modes, sharding, resume).
- (a) TAIL TRAP found and fixed: the first build refused the ghost-script tail on ~half the rows ("crawl differs from
  log") because crawl2 `plays_ext.csv` lacks positions for many plays and has no rows for ~40% of tags -- the corpus
  was driven from `plays_ext_i1.csv` (replay_batch `--plays-file`, L64h re-fetch). The builder now tries
  `plays_ext_i1.csv` then `plays_ext.csv` per tag and keeps the first whose rows reproduce every logged play
  (tick, side, card, x, y). Second scratch build: tail source matched **1,810/1,810**; 442 corpus logs carried a
  terminal skip (plays after the engine episode ended -> no position in the log). Held-out rows with a tail: 74.
- DEVIATION (design 2.2 does not mention it): ghost commands = corpus log + that crawl tail, so a ghost keeps playing
  its real script if S1's match outlives the pro's engine replay. `ghost_plays_corpus` keeps the log-only count;
  `last_ghost_tick` includes the tail. Reason: without it 74 held-out ghosts would fall silent EARLY by construction,
  inflating the "outlived the script" exploit channel (design 4.1) for a reason unrelated to the policy.
- (a) Second scratch build stats: held-out 293 (190 with an opponent tag, 103 HF; ghost plays median 43 with tail,
  min 1, 3 with <= 5; real pro won 161; corpus engine replay won 158); train 1,505 (1 row with 0 ghost plays --
  kept, counted); dropped 12. 1,751 distinct groups, 50 with > 1 member. Corpus rows with elixir-delay retries:
  **0** in every split -> replay_drive's serial 1050-retry and the env's parallel retry cannot differ on this
  corpus. Corpus rows with some refused play: 85 held-out / 423 train (code-13 refusals not retried by
  replay_drive), hence parity mode defaults to replay_drive's retry set `(1050,)` (`--parity-retry corpus`).
- Design count "13 of 1,798 with <= 5 ghost plays" vs ours 3 + 11 = 14 of 1,798 (tail adds plays) -- consistent.
- Added `e1_pool screen` (the fixed 60 lowest-crc32 held-out tags), `e1_eval --mode liveness` (reset entry 0 + 10
  ticks on one door, the caller's own path) and `suggested_p_random` in the scorer (attempted plays per decision
  that had an allowed slot) for the rate-matched random control.

## Final state (2026-09-12 ~16:15)

### Data written (the only data writes; all NEW, created with exclusive-create mode)
- `icebow/data/ghost_pool/pool_env_v1.jsonl` 42,700,406 B, sha256 `c37cb7bd7fe3d1fd1985c789ae610502f0d0b35687e6000e794f82a407badc80`
- `icebow/data/ghost_pool/pool_env_v1_split.json` sha256 `83323b38a99515e196f0af4dcbe8003be849d86ac38692681f6b137a5aa8ba5f`
- `icebow/data/ghost_pool/pool_env_v1_build.json` (built 16:09:56, 16.3 s)
- (a) byte-identical to the second scratch build (same pool and split sha); `e1_pool verify`: sha_ok, rule_mismatch 0,
  row_vs_frozen 0, counts 293 / 1,505 / 12, no group in both held-out and train. Git-ignored (`icebow/.gitignore:4`).
- Held-out (a): 293 entries, 190 crawl2 (all with an opponent tag) + 103 HF (own group), our side 1 in 243 / side 0 in
  50, 1 entry with <= 3 distinct ghost cards, 3 with <= 5 ghost plays, 74 with a crawl tail.
- Non-data: `scratchpad/gauntlet/L67/e1/screen60_heldout_tags.txt` (60 lowest-crc32 held-out tags).

### Code (new files only; `git status`: all `??`, nothing under pipeline/, icebow/src, L62, sandbox_tools modified)
- `pipeline/e1_view.py`, `pipeline/e1_pool.py`, `pipeline/e1_eval.py`, `pipeline/e1_score.py`,
  `pipeline/tests/test_e1_baseline.py`, runbook `scratchpad/gauntlet/L67/e1/baseline_runbook.md`.

### Tests (a) `icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_e1_baseline -v`: 23 tests, OK, 9.1 s
- live_view (5): hp_known 1 / hp 1.0 on every token, alive kings 1.0 (known 1), opp_known 0, floored elixir,
  source "degraded"; dead king stays 0/False; over 300 seeds no side -1 left on a class outside mine_classes, both
  branches exercised (resolved > 0, kept-unknown > 0), everything else identical to degrade() on the same seed; same
  seed -> identical tokens, 10/10 other seeds differ; eval seed = crc32("tag:eval:k").
- split (5): synthetic rule; crc rule == dataset._tag_split; forms deck yaml == final_decks names == live cards.yaml;
  FROZEN split: sha, counts 293/1505/12, rule re-derived, every held-out tag s1-val and its group has no member in
  train (s1-train members of held-out groups are dropped).
- live-rule parity (4): e1_eval.live_decide vs the REAL `clashrl.student_live.StudentPolicy.decide` (from_live patched
  to return the constructed state, same randomly initialised S1Model d32) on 216 states (6 elixir x 3 hands x 3 idle
  times x 4 tau): identical p, WAIT/PLAY, slot, cell and stall flag; all four branches hit (plays, waits, stall plays,
  no-affordable). Plus affordability mask, anti-stall 240-tick boundary, strict `p > tau`.
- PoolV1Mixin on a fake engine (3): retry set (13 retried at +1 tick vs refused under (1050,)), parity merge order
  (tick, play_index) with sides and final-order deck indices, final_decks assertion.
- eval guards (3): refuses a non-empty --out BEFORE touching the pool/ckpt; shards disjoint + complete; entries specs.
- scorer (3): W/D/L, duplicate handling, fixed-seed CI reproducible, clustered CI wider than the unclustered one on
  fully clustered data, per-seed/slot, before-script, buckets, pro-lost wins; paired 2x2 + exact McNemar (2*0.5^8);
  parity gate 19/20. CLI smoke (session scratch): md + json written, overwrite refused.

### Deviations from the design (all flagged (b) unless stated)
1. `PoolV1Env` = the RawEngineEnv factory pattern + `PoolV1Mixin` (RawEngineEnv's closure class cannot be
   subclassed); `_fire_ghosts_at` is a re-implementation of engine_env.py:366-393 with a per-command side, delivered
   card counts and a retry-code parameter -- equivalence to the base method tested only on a fake engine.
2. Ghost script = corpus log + crawl tail (see TAIL TRAP above). `last_ghost_tick` includes the tail.
3. Group key = the GHOST's tag column chosen by our side (`opponent_tags` if our side is 1 = team, `team_tags` if 0).
   (a) in crawl2 our deck is always the team side, so this equals the design's `opponent_tags` on every row.
4. Parity drives both sides through the env scheduler with replay_drive's retry set (1050,) by default
   (`--parity-retry env` for (13, 1050)); (a) 0 corpus rows had an elixir-delay retry, so serial vs parallel retry is
   inert on this corpus. Eval keeps EngineMatchEnv's (13, 1050) for the ghost.
5. Anti-stall clock origin = the first decision tick (engine tick 90, when deploys are first accepted), not tick 0.
   Live starts it at `reset_match()` wall time; the difference only affects the first possible stall (<= 4.5 s).
6. Random control is affordability-masked by default (the live rule never attempts an unaffordable card);
   `--random-hand-only` reproduces engine_play's §5cs.66 control. Rate matching via `suggested_p_random`.
7. "Continuity on the same 100 entries" read as held-out 0:100 of pool v1, paired against the live-rule baseline
   (pool v0's first 100 cannot run in the v1 env).
8. Additions not in the design: `--mode liveness`, `--resume`, `--max-matches`, `e1_pool screen`, `verify`.

### Not tested (b) -- nothing here touched the engine
- PoolV1Env construction/reset on a real door, the parity hash gate, wall s/match and RSS under the live rule
  (the runbook's 21 s/match is the §5cs.66 tau-0.5 number), liveness mode, errors/resume path on a real failure.
- Whether live_view matches the real detector's shift (it models degrade + three measured live fills only).

### Box time (b): core runbook ~1 h 20-25 min (parity gate + baseline 293 ~51 min + controls ~16 min); +~18 min
for the optional continuity run. Blocks: none for the build; the parity gate (>= 19/20) must pass before the baseline.

STATUS: complete
