# LIVECAL

Status: implemented and tested without SIM. No best pool has been measured yet.
Everything is confined to this directory; pipeline and live scripts are unchanged.

## What the experiment measures

Each of the 10 available checkpoint/fast combinations plays 480 games per pool
(120 with `--quick`), split equally between the EVO and ladder censuses. Games
are paired **across checkpoints** by census and seed; K counts games, not pairs
of side-swapped games. Consecutive seeds balance learner sides. Starting seed
740000 separates this experiment from the weekend gates.

The decision bundle is the requested S2/CAL bundle from
`C:/Users/benpe/cb_weekend/scratchpad/gauntlet/L74/weekend/run_wk.sh`: tau .35,
phase thresholds .35/.45/.55, class-sampled X-Bow floor .3, Rocket-area and
Log-barrel aim, hazard decoder at 9 elixir or a recently threatened tower,
lethal Rocket/Log, dead-lane/dead-target blocks, threatened tau .2, own effects,
deck forms, and hero abilities v2. Grafted heads are already in the listed
checkpoint files. Fast arms add `pipeline_decisions`, delta 0.

**This is a standardized S2/CAL calibration, not an exact replay of every live
era.** The logs contain additional settings that the existing eval does not
fully reproduce: later Rocket/Tornado follow-ups, Log-air, card levels, input
timing, identity handling, and earlier anti-leak/decision bundles. In particular,
the current SIM cannot combine planned follow-ups with pipelined decisions.
`manifest.json -> groups -> eras` preserves the recorded settings and differences;
all runs use the S2/CAL bundle, the existing 26-tick action delay/extrapolation,
and **no forced-spend/anti-stall rule on either side**. Treat a successful pool
ordering as calibration evidence for that specified surrogate, not proof of
live execution parity. The standardization was raised explicitly during the task.

| Pool | Opponent |
|---|---|
| P1 | rdef_e4 graft, sample T=.1, CAL set c |
| P2 | gen_v1_s0, sample T=.3 |
| P3 | gen_v1_s0, sample T=1.0 |
| P4 | ADAPT final `latest` main + three final `latest` exploiters, uniform per game, T=.3 |
| P5 | Exactly 50% P2 + 50% P1; randomized assignment balanced by census and side |

P4 uses the raw training league members, not `adaptive_final_grafted.pt`. It is
available in this snapshot. If none are present at preparation, P4 is explicitly
omitted; a partial main/exploiter pool is an error. T=.3 is fixed for P4 because
the ticket did not prescribe its temperature.

The two checked-in `census_*.json` files apply the weekend archetype weighting
algorithm: boost Royal Giant (+/- Monk), Lava Hound, Golem, PEKKA bridge and
hyperbait toward `min(.6, max(3 * natural_share, .5))`, using alpha .5/floor .5.
Both full censuses reach 60% before the existing eval's Icebow exclusion and
unsupported-deck redraws. The runner reuses `search_s0.opp_deck_for/setup_job`.
P1/P2 therefore retain the named policies/temperatures, with the ticket's
archetype-weighted deck distribution rather than an exact replay of the older
unweighted gate. Sampled deck, side and opponent SHA must agree across arms.

Only `search_s0`'s **plain** policy is allowed: no search, forks, or hidden-state
rollouts. `e1_eval` supplies the policy observation and public opponent counter;
each policy receives its own hand/deck, not the opponent's. The worker explicitly
sets `stall_elixir=None` for both sides. No new gameplay rule is implemented.

## Frozen live evidence

`live_truth.py` calls the current `phase_stats.read_live` and tower helpers. It
keeps the `{4424, 7032}` main-account tower signature, X-Bow own-hand requirement,
end-event requirement, monotone clock and early-terminal defeat correction.
Results are the same tower-position crown proxy; an unknown `card_id=-1` body
away from a tower cannot affect the outcome. It is not an official battle-log
result. Draws remain in the denominator as non-wins.

`truth.json` contains **1,042 accepted logs**, their content hashes, exclusion
counts, and 32 checkpoint/SHA/fast/era groups. Every referenced checkpoint still
exists and matches its recorded SHA. Older logs without public decisions cannot
pass this rule: they are reported as excluded, not reconstructed with another
scorecard. Missing `pipeline_decisions` means off, matching phase_stats; the
number of explicitly recorded flags is retained.

`truth.txt` lists every era with n>=30 and both small adaptive arms. For review,
these are the descriptive checkpoint/fast totals (mixed eras):

| Checkpoint | Fast | n | W/L/D | Win rate, Wilson 95% CI |
|---|---|---:|---|---|
| R1e31 u0155 | off | 305 | 149/155/1 | 48.9% [43.3,54.4] |
| tower_spatial_v7 candidate | off | 15 | 5/10/0 | 33.3% [15.2,58.3] |
| R2l u0120 | off | 6 | 3/3/0 | 50.0% [18.8,81.2] |
| R3c barrel2k cellref | off | 99 | 54/44/1 | 54.5% [44.8,64.0] |
| Old towerref_w2 | off | 400 | 218/181/1 | 54.5% [49.6,59.3] |
| E4 graft | off | 38 | 16/22/0 | 42.1% [27.9,57.8] |
| Old towerref_w2 | on | 98 | 46/52/0 | 46.9% [37.4,56.7] |
| adapt_fixed | on | 46 | 20/26/0 | 43.5% [30.2,57.8] |
| adapt_alone | on | 24 | 10/14/0 | 41.7% [24.5,61.2] |
| adapt_alone | off | 11 | 7/4/0 | 63.6% [35.4,84.8] |

E4's era counts are 9, 2 and 27; none separately meets n>=30. Its aggregate
still supports the requested descriptive comparison. These counts differ from
the ticket's earlier 52/379 samples; the frozen receipts and the exact requested
account/selection rule are authoritative for this experiment. Exclusions:
694 no public decisions, 487 other-account tower signatures, 3 no X-Bow in own
hand, 3 no end event. New live matches do not silently change a prepared run.

## Scoring

One calibration observation per checkpoint/SHA/fast combination with n>=30,
equally weighted. Eras are pooled by live match counts, so a checkpoint with
many configuration edits does not receive extra votes. All 10 arms are evaluated,
including smaller earlier checkpoints and adapt_alone; those with n<30 do not
enter rank/MAE selection. The two primary sign comparisons are old off > E4 off
and old off > old on. Adaptive comparisons use the same fast flag as old and are
report-only, regardless of n. These are observational mixed-era comparisons.

Spearman uses average ranks for ties; a constant vector has undefined correlation.
The per-pool offset is `median(live - SIM)`, minimizing unweighted absolute error;
offset MAE is the resulting error, with no clipping. A tied SIM difference does
not reproduce a strict live ordering. Winner selection is lexicographic: number
of primary signs reproduced, Spearman, then lower offset MAE (pool ID breaks an
exact tie). The first line is `pool X reproduces K of M live orderings`.

2,000 deterministic bootstrap replicates resample SIM seeds jointly across all
checkpoints within each census and live wins independently within each group.
The offset is refitted each replicate. Reported 95% percentile intervals cover
rank correlation, offset, MAE, sign count, and each live/SIM pairwise delta;
pairwise bootstrap agreement is also reported. Undefined rank replicates are
counted. This assumes independent live matches, not session clusters, and does
not remove in-sample selection optimism. Future checkpoints should validate the
selected pool. No best pool is named before complete SIM results exist.

## Files and launch

`NEEDED_FILES.txt` is the exact source-to-pod-path list, with sizes and SHA256.
There are **13 checkpoint files totaling 247,479,569 bytes (236.0 MiB)**. The
ADAPT sources are outside this repo under the backup directory. Copy those to
the listed `icebow/data/...` destinations, along with the other checkpoints.
Copy this directory into the pod's full ClashBot checkout. The pinned eval
sources and ability-policy Python/JSON are also listed and hash-checked. Keep
the existing repository data/config files and installed Royale runtime/venv.
The driver installs/downloads nothing. Raw live logs are not needed on the pod.

Assuming the prepared checkout is `/workspace/ClashBot` and its existing Python
is `/workspace/venv/bin/python`, the exact full launch is:

```bash
cd /workspace/ClashBot
PY=/workspace/venv/bin/python bash scratchpad/gauntlet/L74/livecal/run_livecal.sh
```

This holds `flock /workspace/cpu.lock` through the entire run and launches at
most **28 single-threaded eval processes**. The Python controller uses threads
to supervise them. Default outputs are `/workspace/results/LIVECAL/SUMMARY.txt`,
`DONE` (with exit code), `plan.json`, `matches.jsonl`, `score.json`, and per-chunk
receipts/logs. Ordinary preflight/eval/scoring failures write a failure summary
and DONE too. Failed or completed output directories cannot be reused.

For the first pass, use a separate output so the full run retains its default:

```bash
cd /workspace/ClashBot
LIVECAL_OUT=/workspace/results/LIVECAL_QUICK PY=/workspace/venv/bin/python \
  bash scratchpad/gauntlet/L74/livecal/run_livecal.sh --quick
```

At 47 games/minute with 28 workers: full **24,000 games = 8 h 31 min**; quick
**6,000 games = 2 h 08 min**, plus lock wait, startup and scoring. P4 unavailable
would reduce these to 19,200/4,800 games. `--workers N` accepts 1..28; `--k K`
accepts multiples of four. Use `LIVECAL_OUT`, not `--out`, with the shell driver.

### Optional two-pod split and offline merge

Both features are opt-in; omitting `--pools` still runs all available pools.
`--pools P1,P3` selects just those pools. Selection filters the full schedule
without renumbering checkpoint/fast groups, changing seeds, or redrawing opponent
assignments (including P4 and P5). Requested IDs must be distinct and available
in the frozen manifest. Every part must use the same copied manifest/censuses,
code, and K; do not independently regenerate preparation between parts.

Pod A (28 workers, P1/P2/P3):

```bash
cd /workspace/ClashBot
PART=A PY=/workspace/venv/bin/python bash scratchpad/gauntlet/L74/livecal/run_livecal.sh --pools P1,P2,P3 --workers 28
```

Pod C (25 workers, P4/P5):

```bash
cd /workspace/ClashBot
PART=C PY=/workspace/venv/bin/python bash scratchpad/gauntlet/L74/livecal/run_livecal.sh --pools P4,P5 --workers 25
```

`PART=A` names `/workspace/results/LIVECAL_A`; `PART=C` names
`/workspace/results/LIVECAL_C`. PART permits letters, digits, `_` and `-` only.
An explicit `LIVECAL_OUT` overrides PART. With neither set, the original
`/workspace/results/LIVECAL` default remains. All arguments, including `--pools`,
pass through to Python. Each pod holds its own `/workspace/cpu.lock`.

Each pool has 10 x 480 = 4,800 games in the frozen manifest:

| Part | Games | Workers | Estimated games/min | ETA |
|---|---:|---:|---:|---|
| A: P1/P2/P3 | 14,400 | 28 | 47.00 | 5 h 06 min |
| C: P4/P5 | 9,600 | 25 | 41.96 | 3 h 49 min |

Rates assume linear worker scaling from 47 games/min per 28 workers. Simultaneous
completion is about 5 h 06 min, plus lock wait, startup and scoring; actual pool
speeds can differ. Optional `--quick` on **both** commands reduces the parts to
3,600/2,400 games, about 1 h 17 min / 57 min respectively. Part summaries rank
only their selected pools and say `PART ONLY`; merge to choose across all pools.

After copying the complete A and C result directories back to
`C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/livecal/results/LIVECAL_A` and
`.../results/LIVECAL_C`, run this on the laptop (PowerShell):

```powershell
Set-Location C:\Users\benpe\ClashBot
icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/livecal/livecal.py --merge scratchpad/gauntlet/L74/livecal/results/LIVECAL_A scratchpad/gauntlet/L74/livecal/results/LIVECAL_C --out scratchpad/gauntlet/L74/livecal/results/LIVECAL_MERGED
```

Merge reads each saved `plan.json` and `matches.jsonl`; it needs no checkpoint
files, original live logs, network, SIM runtime, or local manifest. It writes
`plan.json`, the union `matches.jsonl`, `score.json`, `SUMMARY.txt` and `DONE` to a
fresh output directory. Complete coverage uses exactly the full-run scorer,
including deterministic bootstrap intervals, summary format and `exit_code=0`.
Use the same `--bootstrap` as a reference run when comparing scores.

An arm is a checkpoint/fast group x pool, complete only after all K expected
census/seed observations are present. Missing or partial arms are listed by
pool/group with observed/expected counts in `score.json` and `SUMMARY.txt`;
merge returns 1 and writes `DONE` with `exit_code=1`. No outcomes are imputed.
Complete pools are still scored; finished arms in incomplete pools have
descriptive rates, but those pools are excluded from ranking and no overall
winner is named. A failed/interrupted part can contribute its flushed matches;
unaggregated chunk files are not recovered automatically. A missing matches file
counts as zero observations, including a plan-only directory.

Identical overlapping results are deduplicated. Conflicting results, changed
plans/truth/checkpoint identities, invalid outcomes, and mismatched pairing or
opponent receipts fail closed. Original unsplit result directories are also
accepted. Merge never changes input directories and refuses a reused output.

Optional offline regeneration on the laptop (refreshes the frozen sample):

```powershell
python scratchpad/gauntlet/L74/livecal/live_truth.py
python scratchpad/gauntlet/L74/livecal/livecal.py --prepare
```

A no-SIM plan check and the tests:

```powershell
python scratchpad/gauntlet/L74/livecal/livecal.py --quick --plan-only --out scratchpad/gauntlet/L74/livecal/new_plan
icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/livecal -q -p no:cacheprovider
```

The implementation was verified with synthetic account/result/grouping tests,
scoring tests, paired scheduling, hash/receipt handling, fake-worker aggregation,
failure artifacts, optional P4, and a generated command accepted by the real
search_s0 argument parser (`--help`, zero games). All 13 checkpoint files also
loaded through `e1_eval.load_policy` on CPU with the same `lattice` grid; the
receipt is `POLICY_LOAD_CHECK.json`. The original 24 pytest cases and new
split/merge coverage pass without SIM; current counts are in `SPLIT_VERIFICATION.json`.
Linux shell execution and actual
SIM games remain pod-side validation; this Windows sandbox could not start Git
Bash (CreateFileMapping access denied). No network or live actions were taken.
