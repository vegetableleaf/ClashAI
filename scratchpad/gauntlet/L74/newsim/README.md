# NEWSIM

Build for two separate arms in pinned RoyaleSim 0.1.33 / RoyaleGym 0.1.23 with
Hero Ice Wizard. No pod was launched, and nothing deploys automatically.
The code is uncommitted: linked-worktree Git metadata is outside the writable
workspace. `merge_receipt.json` identifies both branch tips and the conflict.
See `VERIFICATION.json` for actual local checks and blockers.

Local result: **132 passed, 1 deselected** across NEWSIM (36 tests), adaptive,
league and RL regressions. The deselected process-exit test requires Windows
named-pipe access unavailable here. A broader focused run including Hero IW
had 149 passes and one missing-catalog failure. Full pipeline collection had
12 errors; running the other modules produced 783 passes, 512 failures and
48 skips. Missing runtime, public catalogs, ignored fixtures and host-specific
checks prevent full acceptance. These are not claimed to be 512 regressions,
nor has an asset-complete baseline comparison been run. Bash could not start
(`CreateFileMapping`, Win32 error 5), so shell syntax was source-reviewed only.
Completion ledger: 3 gates met, 2 abandoned for explicit handoff (full suite
and formal merge metadata). Agent-created empty `tmp1rdriaac/` remains after
automatic approval review rejected its cleanup as blocked by policy.

From an isolated pod source checkout, after provisioning [NEEDED_FILES.txt](NEEDED_FILES.txt):

```bash
ARM=base WORKERS=24 bash scratchpad/gauntlet/L74/newsim/run_newsim.sh
ARM=fast WORKERS=24 bash scratchpad/gauntlet/L74/newsim/run_newsim.sh
```

One command runs one arm. WORKERS accepts 1..24, leaving four process slots for
the shell, driver, trainer/evaluator and spawn resource tracker. GPU then CPU
descriptor locks serialize stages. Each output directory is claimed atomically
before traps can write it; used output/run names are refused. Installation is
offline (`--no-index`), using HEROIW's isolated venv and dependency-link helper.
An existing venv must pass version, file hash and compiled-provenance checks.
The eight-game HEROIW smoke runs before any training. Install/gate/train/eval
failures produce a verdict-first SUMMARY and a DONE with a nonzero exit code.

ETA: roughly **12–16 hours per arm** on the 27–30-vCPU L40 pod after locks clear.
The owner's ADAPT2 measurement of 55 min/20 updates gives about 4.8 h for 105
updates; screens, startup and 7,680 eval games add the rest. New-runtime speed
has not been measured. At smaller WORKERS, revise from first-cycle timing.

Training uses ADAPT's final main weights plus frozen exp1–3. It starts a fresh
optimizer, KL anchor, PFSP ratings and update counter on the new runtime; it
does not relabel old engine state as resumable. Three cycles train main to
20/40/60 and a fresh exploiter for 15 updates each. Main is icebow; exploiters
draw human/census decks and face a frozen main. PFSP and opponent styles use the
ADAPT code. Hero abilities use existing v2, including the inherited Hero IW
fallback. No new play rules, forced spending or reward shaping were added.

`learner_pipeline_frac` defaults to zero, which adds no match keys, consumes no
RNG and preserves config hashes. Positive fractions use an independent hash of
training seed, match tag, rollout index and update: a Bernoulli selection per
rollout (approximately 30%, not a per-worker quota). Enabled learner rollouts
use existing pending-state observations and `pipeline_tau_delta=0`. Frozen
opponents and held-out training screens are unchanged. Both main and exploiter
learners use their arm's fraction. Before NEWSIM, `rl_royale` had no supported
`pipeline_decisions` override: CLI rejected it; a YAML key was retained but
never forwarded by `actor_cfg`. The SIM Match/SelfPlaySide implementation
already supported it (a stale ghost-only comment was corrected).

The CSV was absent, so `rebuild_csv.py` regenerated it from the saved public
raw2/bait pages and checked counts against PRO2's tracked receipt. Historical
training-corpus dedupe was not repeated because that corpus is absent; PRO2
reported zero overlaps. No original pages are copied into the repo. CSV has
1,064 unique battles, 2,128 sides and 406 distinct unordered decks. Using names
in the existing loadable censuses, 209 sides containing unknown `minion-giant`
are dropped, leaving 1,919 sides and 370 decks. No card alias or replacement is
invented, and a rejected card drops its whole eight-card deck. Unknown forms
remain unspecified/base; they are not claimed to be observed base forms.

Offline retained counts (new-runtime and policy-vocabulary rejection checks
are still performed on the pod; see `census_offline.json`):

| Archetype | Unique decks | Deck sides |
|---|---:|---:|
| Hyperbait | 30 | 347 |
| PEKKA bridge | 18 | 113 |
| Lava | 12 | 30 |
| Royal Giant | 6 | 48 |
| Royal Giant + Monk | 3 | 4 |
| Golem | 25 | 124 |
| Weak other | 130 | 542 |
| Other | 146 | 711 |

The pod checks actual runtime deck resets and the shared policy vocabulary,
merges both census sources plus human decks for RL, and adds humans to each
eval census. Exact unordered decks retain summed frequencies; forms remain
distinct. Each consumer removes icebow opponents and assigns 60% probability
to the six owner-named categories, retaining within-group frequencies. The
sampler uses alpha=1/floor=0 after weighting so it does not temper the weights
a second time. Raw counts, blocked card occurrences, runtime rejection reasons
and achieved probability are saved before training.

The exact ADAPT graft helper copies CellRefine, TowerRefine and
projectile_target_* from the old live checkpoint; equality is verified and the
grafted checkpoint is saved **inside results**. Training stdout, JSONL logs and
configs are copied there too, including after a training/eval failure.

Evaluation is 960 matched old/new pairs per pool and pipeline condition:
480 EVO + 480 ladder; CAL-c rdef_e4 T=.1, P2 gen_v1_s0 T=.3. Both evaluated
models use the same S2/CAL live flags and the same OFF/ON setting. The fixed
sampled opponent keeps its policy across comparisons, following LIVECAL.
This means 4 comparisons, 3,840 pairs, **7,680 actual games per arm**. Pairing
checks reject missing/duplicate/skipped/truncated records and differing decks,
seeds or seats. Summary includes model delta and each model's ON-minus-OFF
cost, paired normal 95% intervals (ADAPT's method), and archetype tables.
Improvement is shown only if the lower interval bound exceeds zero in both
OFF pools; no non-inferiority margin is invented.

Per-game phase records measure own minus opponent total tower HP at phase end,
and its change during that phase. Boundaries are ticks 0/2400/4800/6000; no
tiebreak drain. Tank/Tesla diagnostics adapt `phase_stats/video_metrics.py`:
observed river crossings, same-lane or central Tesla, lane quiet for 3 s ends
the episode. Saved events include the previous/crossing tick, existing Tesla,
response delay, missing response and censored episode. These use public frames
already held by BehaviourTelemetry; they never reach the policy or reward.
Old matches.jsonl files with only final HP cannot recover these metrics.

Offline checks:

```bash
python scratchpad/gauntlet/L74/newsim/driver.py --arm fast --workers 24 --out /tmp/newsim_plan --plan-only
python -m pytest scratchpad/gauntlet/L74/newsim/test_newsim.py pipeline/tests/test_adaptive_opponents.py pipeline/tests/test_league.py pipeline/tests/test_rl_royale.py pipeline/tests/test_heroiw.py -q
```

Managed Windows can use `verify_offline.py`, which gives temporary test files
inherited workspace ACLs. Pytest dependencies were copied from the existing
local uv cache into ignored `.test_deps`; no packages were downloaded.
