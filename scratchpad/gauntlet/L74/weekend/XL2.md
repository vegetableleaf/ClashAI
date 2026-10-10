# XL2 pod handoff

Use a **separate checkout of `l74-drills-xl2`**, suggested path `/workspace/wk_xl2`.
Do not update the checkout currently running S9XL/S10XL. Nothing here deploys a
checkpoint or writes `icebow/data/`. Candidate weights live in
`/workspace/results/wk/S10XL2/candidate.pt`.

## Data and preflight

The checkout needs the pod's existing read access to the checkpoint/census assets
and `research/ext/Royale/RoyaleSim/data/derived/cards.json` (including the existing
unit-value/catalogue dependencies used by `build_live.py`). Use the existing pod
Python environment; no new package or network installation is needed.

The pro input is the **icebow pro re-drive corpus**, normally
`/workspace/clashbot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json`.
Set `PRO_CORPUS` to its actual pod location if different. `build_pros.py` produces
`scratchpad/gauntlet/L74/drills/data/pros.pkl.gz`. Fit on that normalized file,
not on the previously harvested `moments_pros.jsonl.gz`: the latter lacks the
complete public state history needed by the feature extractor.

```bash
cd /workspace/wk_xl2
export CB_MAIN="$PWD/"
export PRO_CORPUS='/workspace/clashbot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json'
/workspace/venv/bin/python scratchpad/gauntlet/L74/drills/build_pros.py
/workspace/venv/bin/python scratchpad/gauntlet/L74/drills/pro_when.py \
  --pros scratchpad/gauntlet/L74/drills/data/pros.pkl.gz \
  --table scratchpad/gauntlet/L74/drills/data/pro_when.jsonl.gz \
  --out scratchpad/gauntlet/L74/drills/data/pro_when.json
/workspace/venv/bin/python -m pytest scratchpad/gauntlet/L74/weekend/tests -q -p no:cacheprovider
/workspace/venv/bin/python scratchpad/gauntlet/L74/weekend/tests/check_xl2.py --shell
```

`pro_when.json` contains D1–D9 coefficients, feature order, train-only scaling,
regularization, held-out match IDs, held-out AUC and sample counts. Both pro sides
of a replay stay in the same partition. A single-class held-out sample has AUC
`null`; an unfittable drill is explicitly reported and makes the fit command fail.
No coefficients or AUCs have been fabricated locally. D10 retains its existing
S9XL label/mechanic; it has no `drills.py` selector and is not a WHEN fit here.

The opponent-elixir feature is a **public visible-body estimate**, starting at 5,
regenerating with time and subtracting newly observed body value. It is imperfect
for spells, obscured deployments and spawned children. The same estimator runs
on pro and SIM rows, using increases in value per visible class rather than pro
entity IDs. Lane values cover the full visible board; own-half value is separate.
It never reads `opp_deck`, `opx`, opponent hand/next, or exact
engine elixir. Tower HP is normalized using public tower maxima (SIM dump HP is
already fractional). No future own play enters the seconds-since-play feature.

## Start the chain

Confirm `XL2_CKPT` is the current live checkpoint. The value below is the same E4
graft identified as current live by the existing weekend driver. It is hashed at
S9XL2 start and must remain unchanged through training. Start exactly:

```bash
cd /workspace/wk_xl2
export XL2_REPO="$PWD"
export XL2_CKPT='icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt'
export PRO_WHEN="$PWD/scratchpad/gauntlet/L74/drills/data/pro_when.json"
mkdir -p /workspace/results/wk
nohup bash scratchpad/gauntlet/L74/weekend/run_xl2.sh > /workspace/results/wk/xl2.out 2>&1 &
```

The launcher polls `S10XL/DONE` every 30 seconds without holding CPU/GPU locks.
It then runs S9XL2 with `cpu.lock`, and S10XL2 with **gpu.lock first, cpu.lock
second**. Each stage writes `SUMMARY.txt` and `DONE`, including failures. `SUCCESS`
is separate from `DONE`; failed S9XL2 cannot feed training. The launcher finally
touches `/workspace/results/wk/ICEBOW_DONE`, including failure paths, to release
the waiting Log Bait job. Concurrent launch and reuse of completed output are
rejected. Do not clear prior output to choose another winner on the same TEST set.

## Definitions and evidence

| Work | Evo seeds | Ladder seeds | Target |
|---|---|---|---|
| Fixed D1/D4/D9 | 8000:10000 | 10000:12000 | up to 1250 opportunities per drill per census |
| Variant DEV | 12000:14000 | 14000:16000 | up to 1250 per drill per census |
| Selected variant TEST | 16000:18000 | 18000:20000 | up to 1250 per drill per census |
| Candidate vs current live | 20000:20480 | 20000:20480 | 960 paired games |

Ranges are half-open, disjoint from earlier stages through S10XL's 7200:7800.
Fixed selectors/arms retain S9 definitions. The approximately 2500 target is a
moment cap, not a fabricated count: rare opportunities and no-arm skips are
reported, with a shortfall flag below 2250 scored fixed moments. Every run uses
the S9 archetype-weighting code and deployed `run_wk.sh` flags. Dumps are retained
for audit; plan disk space for the dump, fork and ordinary-row files.

D5 selects the highest-value Log corridor that actually contains at least three
small ground bodies or a visible Goblin/Skeleton Barrel. D6 reuses deployed
`rocket_value_choice` / `rocket_value_cell`, with a 10-elixir impact threshold,
edge hitboxes and catalog **drift lead** through Rocket flight time. D7 calls the
verbatim shared tower-Rocket helper; D8 uses the existing drill suite's copied
sneaky-lock rule. Their direct HOLD arms retain the spell at the root; as with
the existing fork mechanics, the model then resumes.

Search tries `DO`, `DO_when_0.3`, `DO_when_0.5`, `DO_when_0.7`; D4 also tries
`DO_best_air` (including Rocket, model-selected card and unrestricted best cell).
The pro gate copies the model's **entire own decision** when below q, including
follow-ups; these zero-effect moments stay in the score. All variants share the
plain arm's eligibility, and the DEV opportunity population hash must match.
The highest DEV win B−A wins, ties use declared variant order. The choice is
written before any TEST evaluation. Exactly that choice is tested, once.

S9XL2 searches D5–D8 plus D4. D4's required fixed measurement remains descriptive;
its training label comes exclusively from the separately selected TEST variant,
with no fallback to the fixed result. The generic search CLI also supports any
of D1–D9. It never pools DEV with TEST or retries TEST selection.

XL2 labels use binary match-end **win(B) − win(model A)**, CR1 95% CI clustered
by match. Positive CI labels DO; negative CI labels **own A**, not an untested
forced HOLD. Existing S9XL labels keep their original DO/HOLD meaning. Search
JSON lists every comparison, mean, CI half-width, sample size, skips, seed range,
selected variant and TEST result. Incomplete matches, moment replay mismatch or
A-replay hash mismatch fail the stage rather than silently reducing the sample.

S10XL2 builds an auditable training input containing all labelled S9XL drills and
all final labelled XL2 drills. Selected variants contribute **TEST rows only**;
DEV rows cannot enter training. It reconstructs own-A alternative targets where
required (including D10) and namespaces old match tags to avoid collisions.
`train_drills.py` is unchanged: current-live start, KL weight 50 on ordinary rows,
three epochs / 60-minute cap and its existing drift guard. Ordinary rows shared
across drill runs are deduplicated. Evaluation reuses the same weighted census
and live flags, requires all 960 matched games and reports opponent archetypes.
Only a strictly positive paired 95% lower bound earns
`candidate: ask owner to deploy`; otherwise the verdict is `no gain`.

## Local verification limits

Synthetic pytest tests and Python import/syntax/legacy-preservation checks run
without SIM. The Windows sandbox cannot launch Git Bash or Dash
(`CreateFileMapping ... Win32 error 5`), so run the `--shell` preflight above on
the pod. No local SIM runs, pro fits, real AUC estimates, candidate training or
performance claims are part of this code ticket's validation.

The local commit is also blocked by the sandbox: this worktree's Git metadata is
`C:/Users/benpe/ClashBot/.git/worktrees/cb_drills2`, outside its writable root;
`git add` failed to create `index.lock`. No commit was created. From an unrestricted
host shell in `C:/Users/benpe/cb_drills2`, stage the ticket files listed by
`git status --short` (exclude any temporary pytest cache directories), then:

```text
git commit -m "Add XL2 public-conditioned drill forks and held-out variant search"
```

Only after that commit should the pod deployer transfer this branch to the
separate XL2 checkout. The existing running stages require no changes.
