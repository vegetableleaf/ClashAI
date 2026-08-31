# P4 — Continuation teaching: design

**Created:** 2026-08-31, gauntlet L5. **Status:** design; nothing here is implemented.
**Why this is the frontier (all measured):** per-event response ranking is NOT where the reference
policy's match edge lives (§5ae: m18000 has the *worst* paired regret, ordering survives the
belief-view control); three repair families failed (restraint_hold §5j/§5ad, bank_hold §5ad,
placement-prior-alone §5ae); canvas_stack-2 is null-negative at a 4x cost (§5af). What has never
been taught is what the search teacher actually knows: **what happens after the action.**

## 1. The teacher plan record — CORRECTED 2026-08-31

/!\ THE ORIGINAL PREMISE HERE WAS WRONG. `_rollout` (rollout_search.py:308) IDLES OUR SIDE for
the whole horizon — "idle our side / run theirs". The teacher never simulates its own follow-up
plays, so there is no "winning branch continuation" to record. (Corollary worth its own line:
the searcher that lifted 37->85.7% scores every action followed by 12 s of DOING NOTHING — its
edge is pure single-action consequence, which makes the missing-continuation diagnosis sharper.)

Two replacement mechanisms:
(a) CHAINED SWEEPS — after picking the winner, re-search from the post-action state at +dt to
    synthesize a plan. Genuine teacher continuations; ~2x search cost; needs a cost probe before
    any training use.
(b) HINDSIGHT CONTINUATIONS — log what the policy+search actually EXECUTED next in the training
    stream. Free, on-policy, no behavior change. IMPLEMENTED as step 1 (continuation_log knob in
    train_sim_ppo; JSONL rows emitted from the finished horizon buffers).

The record (per searched play decision):

```
plan = {
  action_now: (gate, card, cell),
  next_play:  (dt_s, card, cell) | NONE-within-horizon,   # first subsequent deploy in the
                                                          # winning rollout branch
  second_play: same | NONE,
  plan_value: rollout score (already computed),
  intent: derived label — DEFEND (next play answers a live enemy body),
          BANK (no play >= 4s while elixir climbs), PUNISH (play crosses the river
          inside 5s), CYCLE (cheapest card, no threat context)
}
```

Cost: ~zero. The rollout engine already steps through these plays; recording them is bookkeeping
inside `_rollout`. One new structure per searched decision, serialized alongside the existing
imitation rows.

## 2. Losses (add ONE at a time — §one-change-per-experiment)

Ordered by expected information per unit risk:

1. **Time-to-next-play (hazard)**: discrete-time survival head over the next play's timing,
   trained on teacher plans. Directly attacks the measured failure — waits are wrong because
   nothing follows them. Grade with realized-wait regret, NOT accuracy (always-WAIT floor, §3n of
   the brainstorm).
2. **Next-action prediction** (card + coarse cell of `next_play`): auxiliary head; teaches the
   embedding that a wait is *pending action*, not absence.
3. **Plan-value regression**: calibrated value of the continuation; later the joint scorer's target.
4. **Intent classification**: 4-way auxiliary; cheapest, likely weakest; last.

## 3. Human anchors as evaluation (never as gradient — §5af owner ruling)

The measured pro targets the trained policy should approach (population, n=24, §5ag):

```
inter-play gap median 3.85s (p10 1.55, p90 10.15);  play rate 11.7/min
after X-BOW  -> next play median 5.5s: knight 20%, tesla 17%, skeletons 17%, log 16%, IW 16%
after TESLA  -> next play median 4.2s: skeletons 22%, knight 19%, log 18%, IW 17%
```

Add a `continuation_report.py` eval: given a checkpoint, measure ITS after-bow/after-tesla
follow-up distribution and timing on fixed seeds, report the L1 distance to the pro distribution.
This is a mechanism metric with an external anchor — the first eval in the project not derived
from the project's own earlier checkpoints.

## 4. Acceptance gates (pre-committed)

* Mechanism: hazard-head arm shows lower realized-wait regret on the frozen corpora (both views)
  than its control at matched m, 3 seeds, same instrument.
* Behavior: after-bow follow-up L1 distance to pro distribution shrinks vs control.
* Guardrail: tower delta / drills not worse.
* The 9x lesson (§5ab): plan comparisons on corpora (paired) wherever possible; any run-level
  claim needs 3 seeds.

## 5. What this design deliberately does NOT do

* No GRU/sequence replay yet (§5af: cheap temporal input was null-negative; recurrence waits for
  a positive hazard-head signal).
* No BC on human plays (§5af ruling: three distillation nulls; no reconstructable states).
* No band/doctrine edits (owner decision pending, §5ag).
* No two-speed router (§5ac: rejected pending bucket evidence).

## 6. Implementation order (next loops)

1. `_rollout` plan capture + serialization (no training change — pure logging). One loop.
2. `continuation_report.py` eval + baseline numbers for m18000/stack1/control arms. One loop.
3. Hazard head + its A/B (control vs +hazard), 3 seeds, corpora-graded. The first real P4 run.
