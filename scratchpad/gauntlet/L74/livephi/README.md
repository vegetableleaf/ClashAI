# LIVEPHI reproduction

All commands run from the repository root with the existing CPU PyTorch environment:
`research/ext/Royale/.venv/Scripts/python.exe`. No downloads, simulator runs,
policy training, live-loop changes, or deployment are performed.

1. `build.py --seconds 240` (repeat until every frozen source-manifest file has a receipt).
2. `fit.py` (assemble chronological dataset; fit a 1,185-parameter predictor in at most 540 seconds plus calibration).
3. `baselines.py --seconds 240` (repeat until `BASELINES COMPLETE`).
4. `pro.py --prepare` (load exact L73 row IDs from local fv5 pro dataset).
5. `pro.py --seconds 240` (repeat until `PRO DATASET COMPLETE`).
6. `evaluate.py`, then `report.py`.
7. `verify.py dataset`, `verify.py evaluation`, and the tests below.

Scripts are paths under `scratchpad/gauntlet/L74/livephi/`.
Baseline inference and pro inference are resumable in short, below-normal-priority jobs with at most four threads.
`run_inference.py` runs these jobs sequentially to completion; each child exits
after approximately four minutes, finishing its current match or 1,024-row shard.
The one-thread benchmark was 0.747 s / 32 rows; two threads took 0.464 s and four
took 0.369 s on this 16-logical-CPU laptop. Scoring used 1/2/4 threads as the
bounded jobs were tuned; all computations stayed float32. Training and feature
extraction remain single-threaded. A separate attention-kernel benchmark was
slower and was not adopted (`attention_benchmark.json`).
During this run, an audit found the earlier Windows priority call had silently
left jobs at normal priority. The final pro jobs used the corrected HANDLE
binding and verified below-normal priority. Earlier jobs were still bounded by
the thread cap and four-minute chunk limit. Current code fails if setting or
verifying the requested priority fails.
Run jobs sequentially on the shared laptop. Training is CPU-only and has a hard
540-second deadline inside its minibatch loop. All learned weights belong only
to the win predictor; the old policy remains frozen. The archived source-manifest
is intentionally not refreshed on reruns.

Tests (PowerShell):

```powershell
$env:ROYALE_RUNTIME='20261006'
research/ext/Royale/.venv/Scripts/python.exe -m pytest pipeline/tests/test_live_phi.py pipeline/tests/test_reward_shaping.py pipeline/tests/test_value_phi.py::TestMath scratchpad/gauntlet/L74/livephi/test_data.py -q -p no:cacheprovider
```

Optional learner config, **not activated**:

```yaml
advantage: gae
shaping: live_phi
critic_warmup_updates: 1
shaping_critic_scale: 1.5
shaping_w_value: 0.5
shaping_phi_window_s: 10.0
shaping_phi_ckpt: scratchpad/gauntlet/L74/livephi/phi_live.pt
```

The source labels deliberately match `phase_stats.py`'s scorecard proxy. Exact
model-time board inputs are rebuilt from audit fields using the shared encoder.
The full value-head baseline needs additional partially reconstructed history;
see `REPORT.md` before interpreting its live comparison. Pro baseline inference
uses the exact source dataset inputs, not the earlier L73 model's saved logits.

The projection ignores action/history fields, even though the frozen baseline
requires them. Opponent hidden hand, next card, true elixir, readiness and deck
are never retained by extraction or used as features.

Reconstruction correction is recorded in `baseline_input_repair.json`: public
frame history and live Hero deduplication are used for all final baseline inputs.
The predictor's board features stayed bit-identical. Revision 1/2 predictions
are never accepted by the final baseline loader. On a clean rebuild this logic
is already in `build.py`; the one-off `repair_baseline_inputs.py` is unnecessary.

Artifacts remain local and uncommitted. Check `REPORT.md` for the verdict before
considering any separate future policy experiment.
