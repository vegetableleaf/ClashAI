L74: learned fast-follow card choice (never deploy)

Scope
  Explicit entry points only. No runtime/default changes, RL, gate training,
  forced-spend rules or network. Uncommitted for the lead to review.

Dataset
  pipeline.pending_states reads an existing, unshifted dataset_gen NPZ.
  Valid own-past ages 0..24 ticks (inclusive; 20 ticks/second), PLAY rows only.
  Card and cell labels are the pro's actual labels. Padding and WAIT labels
  are excluded. Recent-play WAIT states are also excluded from ordinary KL.
  The output is an index dataset: exact source row IDs, card/cell/xy labels,
  replay split, ordinary indexes, source SHA256 and row/mix report. Observations
  are read from that immutable source; the job refuses a source hash mismatch.
  No corpus rebuild or simulator is needed for this step.

Measured locally on gen_dataset_v32_fv5.npz (unshifted public corpus)
  Source SHA256: 29ecefa9d3025a51d7d4e4cbf67ad15a6fe79a9fd7b222b394dd391e0bc76530
  3,517,863 source rows; 71,708 fast-follow PLAY rows across all decks.
  Icebow: 5,469 fast-follow rows = 4,809 train + 660 held-out validation.
  Second-card mix: Skeletons 28.195%, Log 17.462%, Knight 13.622%,
  Ice Wizard 13.147%, Tornado 11.903%, Tesla 10.459%, Rocket 2.907%, X-Bow 2.304%.
  Full counts, vocabulary and all-deck mix: local_pending.json.
  local_pending.npz is ignored; the pod builds its own source-bound indexes.

Training
  Default trainable parameters: card_q.weight, card_q.bias, card_b.weight.
  Verified on the real live checkpoint: 8,380 trainable parameters, feature
  version 6; corpus version 5 is its supported input schema. Grid/vocab match.
  Frozen trunk, shared embeddings, gate, value, wait, memory and refinement
  modules stay in eval mode and are checked bitwise after every epoch.
  Optional --train-cell additionally trains query, cell_key, cell_bias only.
  CE uses only pending pro labels. KL(base || learner) uses a fixed 100,000-row
  ordinary training sample, traversed every epoch. KL weight 100, LR 1e-4,
  five epochs, batch 256, no weight decay. All are CLI settings in train_pending.
  A separate replay-held-out ordinary sample (up to 30,000 rows) measures raw
  top-card identity changes among valid hand slots, on PLAY and WAIT states.
  Log counts and drift every epoch; save the lowest held-out pending CE only
  if it improves on the start and ordinary drift is strictly below 1%.
  No qualifying epoch => nonzero exit, metrics retained, no model saved.
  Samples are persisted. Full corpus arrays stay on CPU, batches move to GPU.
  Memory-mapped caches are retained in the result folder (allow disk space for
  the uncompressed source NPZ). The training result is not a deployment claim.

SIM plan (pod only)
  Reuses search_s0/e1_eval and adaptive/run_wk CAL/S2 live flags.
  Per learner checkpoint: 480 evo census + 480 ladder census = 960 games,
  seeds 30000:30480 and 30480:30960, identical for baseline/fixed.
  Opponents: rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt, sampled T=0.1;
             gen_v1_s0/gen_s0.pt, sampled T=0.3.
  Each opponent gets live/fixed with pipeline ON at tau delta 0, and live/fixed
  with pipeline OFF. Total: 7,680 games for the mandatory Icebow experiment.
  No changed gate threshold or restraint. Pipelining is learner-side only,
  matching the existing diagnostic. Opponent settings stay paired.
  Record-plays supplies accepted landing ticks, actual card and raw observed
  own elixir at decision. Report both fast pairs/all plays and fast pairs/all
  consecutive gaps, full second-card mixes and mean elixir. The elixir field
  is the existing observation-time metric, not reconstructed landing elixir.
  Wins are strict wins (draws counted separately), 95% percentile bootstrap
  CIs (10,000 replicates), with paired resampling of win differences.
  Duplicate/missing/skipped/truncated games, missing telemetry, checkpoint
  mismatches and mismatched seeds/sides/opponent decks cannot pass reporting.
  candidate requires, separately against BOTH opponents:
    pipeline-ON Tornado second-card share <= 2 * 0.119 (pinned pro baseline),
    pipeline-ON paired win CI lower bound > -3 percentage points,
    pipeline-OFF paired win CI lower bound > -3 percentage points.
  Zero fast-follow observations cannot satisfy the Tornado criterion.
  Dataset-derived pro mix is reported alongside the pinned baseline.

Bait applicability
  The existing S8 bait deck has no Tornado. The default job explicitly reports
  this. Optional --bait-init PATH repeats extraction, head training and all
  four comparisons on that deck from the supplied generalist base; Tornado is
  inapplicable, but both ordinary and pipeline win gates still apply. It uses
  the existing logbait_s0.py wrapper and exact base-card deck filter. No rows
  or missing held-out split => fail, never substitute Icebow labels. The
  overall verdict then also requires bait non-inferiority. Budget doubles.

Exact pod commands (checkout located at /workspace/wt_tornado)
  cd /workspace/wt_tornado
  bash -n scratchpad/gauntlet/L74/tornado/run_tornado_fix.sh
  /workspace/venv/bin/python -m pytest -q -p no:cacheprovider pipeline/tests/test_pending.py pipeline/tests/test_tornado_driver.py pipeline/tests/test_e1_pipeline_decisions.py pipeline/tests/test_e1_action_delay.py
  WAIT_FOR=/workspace/results/wk/CHAIN_DONE bash scratchpad/gauntlet/L74/tornado/run_tornado_fix.sh

  The WAIT_FOR path is the predecessor marker: use the lead's actual marker
  if it differs from CHAIN_DONE. Waiting happens before shared gpu/cpu locks.
  Default OUT=/workspace/results/wk/TORNADO must not already exist. It writes
  SUMMARY.txt and DONE on normal success, failure or handled interruption;
  DONE means ended, never accepted. Check the verdict and process exit code.
  Input/checkpoint/source hashes, stage logs, metrics and report.json persist.
  Do not reuse an old OUT: choose a fresh path for a second experiment.

  Optional additional bait experiment (instead of the default launch):
  WAIT_FOR=/workspace/results/wk/CHAIN_DONE bash scratchpad/gauntlet/L74/tornado/run_tornado_fix.sh --bait-init icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel.pt

  Separate entry points, if needed:
  /workspace/venv/bin/python -m pipeline.pending_states --data icebow/data/pipeline/gen_dataset_v32_fv5.npz --out /workspace/results/wk/TORNADO_manual_pending.npz --deck ice-wizard knight the-log rocket skeletons tesla tornado x-bow
  /workspace/venv/bin/python -m pipeline.train_pending --data icebow/data/pipeline/gen_dataset_v32_fv5.npz --pending /workspace/results/wk/TORNADO_manual_pending.npz --init icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt --out /workspace/results/wk/TORNADO_manual_fixed.pt --device cuda

Local verification limitations
  No SIM, GPU training, network, deployment or Git commit was performed.
  Git Bash cannot start in this Windows sandbox (CreateFileMapping, Win32 5).
  The shell wrapper was reviewed and statically tested; run bash -n above on
  the pod before launch. Corpus_v6 source replay fixtures are absent here;
  extraction was instead measured directly on the real dataset_gen NPZ.
