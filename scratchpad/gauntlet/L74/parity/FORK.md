# RoyaleSim fork and live parity foundation

Local branch `clashbot` was created from **cached** `origin/HEAD` = `origin/main`
at `cacb7005f0e441797c533e91ab4f44820f9919d4` (royalesim 0.1.33).
The previous local main remains `369fe33dc729b4a38dce831714724135fa7216ca`.
No network, GitHub repository, remote edits, commits or pushes were made. The
fork has zero local mechanics patches initially. Upstream is
`https://github.com/RoyaleGym/RoyaleSim`; its MIT license remains in the checkout.
Vendored game data has its own upstream licensing notes; MIT does not relicense it.

## Small patch queue

Keep `origin` pointing to upstream. Work only on the nested `clashbot` branch;
one independently reviewable mechanic per commit. The outer repository ignores
this checkout: an outer commit alone does not preserve the nested branch. For a
future authorized pod transfer, preserve the nested git history (a local git
bundle works), not just an archive with no provenance. This ticket does not
transfer anything.

After a separately authorized upstream fetch, with a clean worktree:

```bash
cd research/ext/Royale/RoyaleSim
git switch clashbot
git branch backup/clashbot-before-rebase
git rebase origin/HEAD
git log --oneline origin/HEAD..clashbot
```

Choose a fresh backup branch name for each rebase. Drop patches already fixed
upstream; retain upstream APIs and data generation. Rebuild a fresh isolated
runtime and rerun the **same hashed cohort** and parameters after every rebase.
Each future patch commit must name:

- mechanic and minimal reproduction;
- `Parity-Evidence:` path to per-match JSON, source SHA256, ticks and identities;
- upstream base, wheel SHA256, runtime manifest SHA256 and table stamp;
- paired before/after metric and coverage counts, including refusals and missing bodies;
- upstream tests run and any regression/uncertainty. A better average obtained
  by dropping hard matches is not a parity improvement.

The reports rank candidate investigations, not causal proof. A patch must improve
its fixed fixture and paired cohort without hiding availability regressions.
Do not claim a Tesla deploy, X-Bow target switch, Tornado pull or Log knockback
fix solely from an associated tower-HP change.

## Offline Linux wheel and runtime

`build_fork.sh` follows upstream `.github/workflows/wheels.yml` and README:
extract arena/cards/globals, select cards-15.535.json, stage wheel data, then
`maturin build --release --locked --offline --no-default-features`.
It requires a preinstalled Rust toolchain, cached Cargo crates, Python 3.10+,
maturin (the upstream pyproject requires >=1.15,<2), numpy/msgspec and a local
royalegym 0.1.23 wheel. No downloads or toolchain bootstrap are attempted.
This builds a wheel for the pod's Linux ABI, not a certified portable manylinux
release. Both launchers take `/workspace/cpu.lock`; builds use at most 24 jobs.

```bash
WHEELHOUSE=/workspace/wheels BUILD_PYTHON=/workspace/venv33/bin/python \
  bash scratchpad/gauntlet/L74/parity/build_fork.sh
```

Output: `research/ext/Royale-fork/{wheels,runtime,build_manifest.json}`.
Existing output is never overwritten. The manifest binds all installed files,
wheel SHA256, package versions and compiled clean git provenance. No source
patches are needed just to build. Dirty tracked build inputs fail closed.
`ROYALE_RUNTIME=fork` selects this directory in `pipeline/royale_runtime.py`;
unset and existing pins retain their paths and behavior. Missing/mutated files
or a previously imported engine fail. `fork` remains a distinct checkpoint stamp.
The parity driver explicitly uses the new client table for new/fork, and the old
table for old, just like their intended pinned configurations. This changes both
data and mechanics across old/new; it is not a one-mechanic ablation. The fork
selector alone does not activate the separate HEROIW policy helpers or live play.

## Public format chain and definitions

1. `phase_stats.read_live` applies the existing main-account tower signature
   `{4424,7032}`, observed Xbow hand, closed/non-dry-run, terminal/clock and file-stability filters.
2. Selection uses filename dates since 20261008, ascending order, first N eligible
   files (default 100), with explicit shortfall and exclusion receipts. Input hashes
   bind the cohort. Engine failures never cause replacement by easier matches.
3. `phase_stats.match_plays` supplies one-to-one confirmed own taps. Normalized
   coordinates use phase_stats's x correction and inverse seat rotation to raw
   millitiles. Confirmed spawn position is used when present; timing stays the tap
   tick, with confirmation tick saved as uncertainty evidence.
4. `phase_stats.video_metrics.bot` supplies the same first-sighting enemy placement
   proxies: omit opening bodies and >40-tick gaps, split identities after >60 ticks,
   group same-name bodies within 20 ticks/5 tiles. Spells without bodies are absent.
5. Deck candidates come only from own public hand and enemy public bodies/projectiles.
   Exactly eight distinct candidates per side are required; no unknown slot is filled.
   Observed evolution/hero forms are lower bounds. The reader's alias/cube exclusions
   are reused. Source reader addresses are hashed before any output.
6. The pro corpus was native-engine-driven (`replay_drive`), not SIM-driven. As in
   PRO2's adaptation, the harness translates to SIM, reusing the actual
   `replay_drive.infer_deals` public play-sequence solver. It reports the number of
   possible deals. No opponent hidden hand/elixir/deck from the live logs is read.
7. A direct `Battle` adapter uses the same RoyaleSim coordinate conversion as
   `pipeline.royale_env` (18 SIM units per native millitile). Unlike its level-11
   wrapper, `Battle.reset(levels=...,tower_levels=...)` accepts each requested level.
   Fields are decoded by the runtime's exported names; SIM IDs are mapped to native
   catalog/form IDs. No silent unsupported-card/form substitution is performed.
8. Both sides' commands are attempted at the recorded tick/position. SIM hand state
   is used only to execute that command. No delayed retry repairs the timeline.
   Rejections and resolved coordinates are saved. Same-tick commands precede the
   sampled state; command/observation order within a live tick is uncertain.
9. At every decision tick, match card ID + absolute side + spawn order. Within-engine
   identities preserve order through crossings; simultaneous births tie by x/y/key.
   Position error is Euclidean tiles; HP error is absolute HP; towers use side/slot.
   Missing bodies/towers are counted separately, not declared dead or zero HP.
10. Divergence is the first sampled tick with >0.5 tile, >=1 HP, missing identity,
    a newly refused command, or early SIM termination. Also report first refused
    command tick and time relative to first observation. Elixir error is measured
    only for the owner, separately; >0.1 elixir flags its group. Post-terminal SIM
    ticks are unavailable, not repeated frozen states.

Per-match JSON retains every compared identity/tick and command. `summary.json`
contains side-by-side metrics on the **intersection of successful matches**,
completed counts, missing/available observations and impact ranking. Group
frequency = mismatching sampled ticks / group-exposed ticks, not independent
trials. Body card groups and the last 100 ticks of plays define exposure. Mean
tower error is associated with that exposure and may appear in several groups.
For recent spell groups, unit errors are measured across the sampled board (a
temporal association), since a pull or knockback affects other cards' bodies.
Impact = mismatch fraction times `(4*tower HP MAE + unit HP MAE + 100*mean
unmatched + 100*position MAE + 100*own elixir MAE + 100*rejections/exposure)`.
This explicit prioritization score is not damage caused. Null means unavailable.

## Pod command and ETA

Pre-stage this checkout, nested fork history, live logs, public catalog/card stats,
the existing old `/workspace/venv` (0.1.17 + compatible gym), and new
`/workspace/venv33` (0.1.33 + gym 0.1.23), including their manifest dependencies.
Build the fork above. No installation occurs in the parity run.

```bash
# Explicit sensitivity scenario: logs do not establish card/tower levels.
ASSUME_LEVEL=15 WORKERS=24 MATCHES=100 \
  bash scratchpad/gauntlet/L74/parity/run_parity.sh
```

The default command without ASSUME_LEVEL still selects/audits 100 matches and
reports unavailable levels; it exits nonzero with no invented fidelity metrics.
Override `OLD_PY`, `NEW_PY`, `FORK_PY`, `SINCE` and fresh `OUT` as needed.
For a patch comparison use `COHORT=/workspace/results/PARITY/sources` and fresh
`OUT`, omitting `ASSUME_LEVEL` to preserve the frozen setup. Source JSON and
harness hashes are saved in selection.json. Python CLI equivalent: `--cohort`.
Individual arms: `python driver.py run --runtime old new fork --assume-level 15
--out <fresh-directory>`; the launcher sets interpreter paths and the lock.
Results are `/workspace/results/PARITY/SUMMARY.txt`, `summary.json`, selection,
sanitized sources, per-runtime match results/logs and `DONE`. DONE records exit
status on success **or failure**; read SUMMARY. No paired measurements exits 2.

Unbenchmarked planning ETA: **5-30 minutes** for 3 x 100 matches at 24 workers,
plus **5-20 minutes** for a cached release build, excluding cpu.lock wait.
The driver replaces this estimate with elapsed-throughput ETA after each batch.
No pod job, build or actual runtime parity result was run/claimed on this laptop.

## What these logs cannot support

- Exact per-card/tower levels: they contain HP/max HP but not explicit levels.
  Uniform level 15 is a requested sensitivity assumption, not recovered truth.
- Complete enemy decks or deals: token spawns/transforms may look like cards;
  unplayed cards stay hidden. Eight observed candidates does not certify a deck.
- Complete enemy spell/ability commands, precise deployment time/aim, command
  queue timing, or the unlogged opening. First sighting is an interval upper bound;
  units can move before sighting. Own confirmed spawn is also later than the tap.
- Hidden opponent hand/elixir, regen or queue truth. Own sampled elixir can be
  compared, but missing commands make an elixir mismatch ambiguous.
- Causal attack targets, HP damage sources, kill times, exact spawn pairing within
  swarms, visibility gaps, identity reuse, hero auxiliary bodies or future forms.
  Later comparisons can shift after an unmatched birth; matching isn't an oracle.
- True same-deck/same-level full-match mechanics parity or patch acceptance from
  these logs alone. This foundation measures reconstruction mismatch and exposes
  coverage. Public supplemental fixtures are needed to isolate mechanics.

## Offline verification

`icebow/.venv/Scripts/python.exe verify.py --tests` runs pytest without SIM;
`python verify.py --fork --selection --contract` checks branch/provenance,
100-match extraction and source/build contracts. See `verification.json` and
`GATES.md`. Linux execution remains an explicit handoff, not a passing gate.

Measured local selection: 100 eligible matches after 12 exclusions; 32,442
decision ticks; 3,594 confirmed own plays and 2,888 enemy placement proxies.
Only 34 matches have eight public candidates on both sides; 66 have incomplete
decks. All require explicit level assumptions for this log-only reconstruction.
Bash syntax attempts failed before parsing (`CreateFileMapping`, Win32 error 5).
No shell or real engine success is inferred from the offline Python checks.
