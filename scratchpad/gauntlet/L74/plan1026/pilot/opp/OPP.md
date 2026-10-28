# LOOP-OPP: the frozen opponent pool in the fast loop (2026-10-28)

Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS
- DONE: pool manifest `POOL.json` (built on pod 32657 by `pool_manifest.py` from succ48_x_s101 + E4 as a 6th
  league_external; every file sha256 + bytes + in_git); `pipeline/loop_opp.py` (opponent cfg, RNG, schedule, decode);
  decision identity harness `oppcheck/` (hooks rl_royale's actors; production code untouched).
- RUNNING: `oppcheck1` on pod 32657 (tree /workspace/loopopp/cb = HEAD code overlaid on a symlink copy of
  /workspace/cb_stepd; lib /workspace/loopopp/lib_cfclone = 33308's d2t2/lib_cfclone, core 3e86169b), 12 actors,
  CPUs 100-115, max_updates 1, with D2-T2's Java obs check chained (OBSCHECK=1). Log /workspace/loopopp/logs/oppcheck1.log,
  per-actor JSON /workspace/loopopp/oppcheck1/, obs check /workspace/loopopp/oppcheck1_obs/.
- Restart: `cd /workspace/loopopp && OBSCHECK=1 nohup cb/scratchpad/gauntlet/L74/plan1026/pilot/opp/oppcheck/run.sh
  /workspace/loopopp/cb oppcheckN 100-115 12 max_updates=1 'league_external=[... 6 paths as in POOL.json ...]' &`
- NEXT: `python oppcheck/summ.py /workspace/loopopp/oppcheck1 > results/oppcheck1_sum.json` (+ obscheck_sum.py on
  the _obs dir); fill the measured table below; send row shares to LOOP-SRV, the inputs list to LOOP-INT.

## 1. Pool (POOL.json; (a) sha256 equal on every copy on pods 33308 / 30408 / 32657 / 33920)
| id | sha256 | arch | selection (succ48_x_s101) | decode before style |
|---|---|---|---|---|
| w14opp_I (`icebow/data/pipeline/o2/w14opp_I.pt`) | 4ff9fe93b02d | GenPolicy fv5, d128x4, no cue / memory / refine | league_exploiters share 0.3, decks `L74/mix/decks_live_train.json` | T 0.1, tau 0.2, decide_every 20 |
| wk_adapt_exp1/2/3 u0015 | 3e019ae92802 / efe5e3f6ebfd / ead818a8322e | fv6, no cue / memory / refine | PFSP (1-p)^2 + 0.05 over init + snapshots + externals, census decks `icebow/data/rltest/decks_rl.json` (not in git) | T 0.5, tau 0.35, decide_every 10 |
| newsim_base_exp1/2 u0015 | d0ef0ea32e05 / 24cbbe3fcdb7 | as above | as above | as above |
| E4 (`rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt`) | 430faaee52d9 | fv6 + cell_refine + tower_refine | NOT in succ48_x_s101 (pilot addition; here a 6th external) | as externals |

All: card vocab equal to the learner's (124 cards), grid lattice, action delay 26, extrapolate 26, opp_elixir counter,
noise off, T_gate = T, no SAMPLE_RULES, no posture / ability head (the opponent's ability presses are the ENV's v2
rule + live IW rule: D2-T2 item 3, not this ticket). init / snapshots are the learner's own weights (memory + cue),
also styled opponents. Every opponent is styled (opp_style 'on'): per match (seed, k) tau - aggression [-.08, .08],
T x [0.8, 1.2], cell lane bias [-.7, .7] x T, WAIT while my elixir < bank [0, 4] with no enemy body on my half, spell
plays + [0, 4] ticks.

## 2. What a fast-loop opponent seat needs (pipeline/loop_opp.py)
- inputs: `E.gen_row_keys(model)` = the 19 non-cue GenModel keys for every frozen model (fv5 and fv6 build the same
  rows: nothing in the observation branches on 6); D2-T2 ccdetC (a): all 20 keys identical Java vs production on
  564,737 actor seat-rows incl. these opponents, 0 rows skipped for vocab / fv. Per seat: one gid table (all equal),
  grid lattice, extrap 26, the seat's OWN decision cadence (the public counter / observer update at its decisions).
- per row besides the model inputs: allowed, stalled (Match.pre), my_elixir (float), enemy_my_half (bool) -> bank.
- per match: `opp_match_cfg(cfg, spec["opp"], grid, seed, k, update, fv)`, `behave_rng(tag, k, update)`,
  `deck_ids(opp_deck)`.
- schedule `after_decision(tick, d, cfg, eng)`: crforge eng 20 -> match delay 6 (+ style spell delay); after a play
  the next decision is tick + de * ((delay + eng) // de + 1) (+30 / +40 at de 10, +40 at de 20), else tick + de.
- decode `decide(...)`: production's own styled_decisions / sample_decide_batch on stand-in sides; cell logits from
  the server (`cell_fn(rows, slots)`), the lane bias added in the producer.

## 3. Findings
- (a, code) spell delay applies only to opponents whose deck is the icebow card set: other decks get placeholder slot
  ids (dataset_gen.side_deck), so vocab.is_spell is False. Kept as production does it.
- (a, code) `league_opp_T` never reaches the actors (actor_base does not copy it): opponents sample at the run's T.
- E4 has no rl_royale training role in succ48_x_s101; the lead decides its share (here: PFSP like an external).

## 4. Measured (oppcheck1) -- pending
