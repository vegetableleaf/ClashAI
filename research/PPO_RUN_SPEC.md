# PPO run spec — band-geometry test + continuation corpus (awaiting owner approval)

**Drafted:** 2026-08-31, gauntlet L8. **Status:** NOT LAUNCHED — posted with --questions.

## The ONE change this run tests
The §5aj geometry ruling as a unit: widened defensive band (`central` 0.278→0.389), the two
lane-bow doctrine spots (0.11/0.89, 0.64), and the bank-start lane-softening window — all from
one owner ruling, treated as one coherent change (the same way §5y was).

## Design — paired against controls that already exist
```
arms      3 scratch seeds (41/42/43) under CURRENT config (5aj geometry)
controls  stack1_s41/s42/s43 — already on disk, identical config except the 5aj ruling
          (they trained under the 5y narrow band; same scratch start, same seeds, same
          1500 matches, same canvas_stack 1, same search-interval 4, workers 0)
matches   1500/arm, sequential (3 × ~1.3h ≈ 4h box time), envs 96
also ON   train.continuation_log — instrumentation, not treatment: this run generates the
          first continuation corpus (~15-20k rows est.) for the P4 hazard-head A/B that follows
```

## Instruments (all paired, all existing)
* `xbow_probe` 24 matches — primary: defensive-bow rate and in-band % under the NEW definition.
  /!\ The def-edge default changed (4.0→2.0), so the stack1 controls get RE-PROBED under the
  same definition — old probe numbers are not comparable.
* `regret_corpus eval` both views — decision quality unchanged or better (guardrail).
* `continuation_report` 32 matches — after-bow follow-ups and L1-to-pro (32, not 16: after-bow
  n was 5-16 at 16 matches).
* Winrate recorded, never interpreted (±12pp at n=16).

## Pre-committed reads and stopping
* Fixed 1500 matches — matched to the controls; no early stop, no extension.
* Verdict rule: defensive-bow in-band % rises at ≥2 of 3 seeds under the paired probe → the
  lane spots teach; flat at all 3 → geometry alone doesn't move placement and the warm-start
  question (§5ah) becomes the next experiment instead.
* All claims at n=3 seeds; per-seed tables in HANDOFF; no single-seed conclusions.

## What this run is NOT
* Not a hazard-head run — that A/B needs the corpus this run produces.
* Not a warm-start run — §5ah measured warm-start blocking placement learning; scratch isolates
  the geometry effect. The warm-start-with-cell-head-reset question stays parked.
* Not a winrate experiment.

## Approval question for the owner
Approve as specced? Options: (a) approve — launches immediately, ~4h, report per wave;
(b) modify (different seeds/length/arms — say the word); (c) reject in favor of something else.
