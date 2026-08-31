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

---
# ADDENDUM 2026-08-31: THE REAL RUN (gauntlet terminal condition, owner directive)

**Launches IMMEDIATELY when the last gate is green** — owner rule: failed experiments get
modified and rerun first; otherwise no waiting. The gauntlet ends AT this launch.

## Gates (in order, each with its pass condition)
1. **Parity chain** (running): per-seed-pair corpus deltas small + sign-mixed → workers 12;
   one-sided gap → workers 0 (launch anyway, slower path).
2. **Geometry redo** (seeds 54-56, fixed constants): pre-committed rule from 5am. Pass → current
   config stands; fail cleanly (no implementation flaw) → REVERT lane spots to centre-only band
   (5aj minus lane spots), then launch. A third implementation flaw → fix + one more redo.
3. **Hazard A/B** (2 arms × 3 seeds, sized from measured pace tomorrow): mechanism win on
   realized-wait regret (paired corpora) → real run carries the hazard head; null → launches
   without it. Mechanical failure → fix + rerun per owner rule.

## The run itself
* config: `data/bench/real_run.yaml` (checkpoint ISOLATED at data/policy_real_20260901.pt --
  never touches policy_sim_ppo.pt; continuation_log ON to data/continuations_real.jsonl)
* horizon: --matches 40000; workers per gate 1; seed 41; --search-interval 4; scratch vs
  warm-start DECIDED BY THE REDO (5ah: warm-start blocks placement learning -- if geometry
  passes at 3 seeds scratch, the real run goes scratch; this is the standing intent, owner can
  override at launch notification)
* §4d anti-plateau gate: paired instrument reads at m=5k/10k/20k (probe + corpora + continuation
  report); keep-best stays on; a sustained regression across TWO consecutive reads posts a
  --questions alert rather than silently training on.
* watchdog armed on the real checkpoint path; Discord report at every instrument gate.
