# Review of LIVE_POLICY_PERFORMANCE_BRAINSTORM.md — accept / modify / reject

**Reviewer:** gauntlet loop L1, 2026-08-30
**Verdict basis:** every judgement below cites a measurement; where none exists the verdict says so.
**Critical context the document does not have:** it was written 2026-08-29. On 2026-08-30 the
3-seed confirmation (HANDOFF §5ab) REFUTED the bank_hold results it cites in §14.1, and measured
control's seed spread at **2.2% vs 20.3% >=6-elixir at identical config** — a 9x range that
re-frames the document's own measurement priorities.

## Verdict table

| § | Proposal | Verdict | One-line reason |
|---|---|---|---|
| 1 | Central diagnosis: temporal coherence, not capacity/perception | **ACCEPT** | Best available synthesis of §4x (37→85.7%), the card-distillation null, and §5j |
| 4 | Response-regret benchmark | **ACCEPT, promote to #1** | Paired design also solves §5ab's power problem (below) |
| 5 | Joint candidate scorer Q(s, cand) vs WAIT | **ACCEPT w/ mods** | Seam is real (§5h/§5j); reuse `Searcher.candidates()`/`_rollout()`, don't build new |
| 6 | canvas_stack 1→2 | **ACCEPT** | Cheap, code exists, directly tests the missing-motion hypothesis |
| 6 | GRU + R2D2 sequence replay | **DEFER** | Right idea, big rewrite; gate on canvas_stack + benchmark results first |
| 7 | Teach continuations (teacher plans, DAgger) | **ACCEPT w/ mods** | Restraint-veto evidence (95% precision, still harmful) is real; start with the cheap plan-record |
| 8 | Two-speed reactive/strategic policy + router | **REJECT for now** | No measurement says regime imbalance is the failure; benchmark buckets will produce that evidence or not |
| 9 | Event-balanced sequence replay for live DDQN | **DEFER** | Sound, but live DDQN is not the active training loop; revisit when it is |
| 10 | Opponent belief aux heads | **DEFER** | Plausible-untested; needs the benchmark to even score it |
| 11 | Sim-to-live practices | **ACCEPT** | Restates already-proven project practice |
| 12 | Learned world model | **AGREE with its own caveat** | Last, not first — the doc says so itself |
| 13 | Ensembles/uncertainty | **DEFER** | Doc's own condition (benchmark first) not yet met |
| 14.1 | Finish 3-seed bank_hold confirmation | **DONE — and the premise is REFUTED** | §5ab: control beats both bank arms at both fresh seeds |
| 14.2 | canvas_stack screen | **ACCEPT** | Now the leading architecture screen |
| 14.3 | Worker-search parity/throughput | **DONE** | 1.83x measured; parity unresolved-but-training (§5aa) |
| 15 | All nine deprioritisations | **ACCEPT** | Each matches a recorded measurement or failure |
| 16 | Phase order A→E | **ACCEPT w/ one insertion** | Phase A gains "measure control seed-variance"; A.1 is done (negatively) |
| 17 | Experimental discipline list | **ACCEPT** | Already house style; adopt the standard report format |

## The two modifications that matter

### 1. The response-regret benchmark is ALSO the answer to §5ab, and the doc doesn't know it
§5ab measured a 9x seed spread on the >=6-elixir endpoint — the 4-arm A/B was underpowered ~10x,
and run-level comparisons of ANY future change inherit that. The benchmark's design kills most of
this variance structurally: every candidate (WAIT, policy pick, counter-table, doctrine) is scored
on the SAME cloned state with common random numbers, so comparisons are within-state and the
match-level variance that swamped the A/B never enters. **Response regret is a paired-design
instrument.** That makes it not merely the doc's Priority 1 but the prerequisite for measuring
anything else this project wants to change.

### 2. Don't build the harness the doc describes — wrap the one that exists
§4's proposed harness (clone state, enumerate WAIT + top cells per card + counter-table +
doctrine, roll 12s, score outcome) is `Searcher.act` minus the argmax: `candidates()` already
enumerates WAIT-first, `_rollout()` already scores each candidate through the measured 12s horizon
with the outcome-grounded `Scorer` (princess-tower fractions), `reseed_opp` already provides the
oracle/belief split, and `eng.last_deploy[1]` timestamps enemy plays for event detection. The
benchmark is ~200 lines of instrumentation, not a project.

## What the document misses entirely (fresh evidence, all 2026-08-29/30)
* **The x-bow placement hole (§5aa):** zero defensive x-bows in any trained arm (1/178 overall),
  24–37% of bows in the dead zone, doctrine prior sampling 0.6 tiles behind our bank against the
  owner's 3.0-tile band (§5y). This is a concrete, owner-approved, measured gap in exactly the
  focus areas (x-bow use, defending the bow) — and it needs no new architecture.
* **The human anchors (§5w):** pro play rate 11.3% of decision steps, inter-play gap median 3.6s,
  3.55 bows/match — external calibration the benchmark's buckets should adopt.
* **Reward-side evidence:** the doc is architecture-centric, but §5p/§5ab together say reward
  patches (restraint_hold, bank_hold at two doses) keep failing to move the collapse — which
  *supports* the doc's thesis that the failure is temporal/structural, not reward-tunable. Worth
  stating as convergent evidence rather than leaving implicit.

## Bottom line
Adopt the document's spine — benchmark first, joint scorer second, temporal memory third, world
model last — with the §5ab power argument welded on, the harness built as a Searcher wrapper, and
the x-bow band retune (already approved) executed immediately since it is measured, cheap, and in
the goal's focus areas. Reject the two-speed router until the benchmark's buckets earn it.
