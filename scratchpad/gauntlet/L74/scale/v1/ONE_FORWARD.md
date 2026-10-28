# ONE_FORWARD: one policy pass per live decision (PLAN Pillar 4a latency gate), design for the ~10 M successor

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Design only: nothing here touches the live path.

## 0. Result

1. **(c) The premise "the live decision is 2 forwards" is stale.** `live_gen_v2.GenPilot.decide` has run ONE trunk pass per
   decision since 10-27 (`_policy_forward`: `encode_gen` -> `heads_gen`, then `cell_logits_gen` from that same encoding; ticket B,
   commit b8d4902). The laptop's own logged `decide_ms` shows the step (section 1.1).
2. **(a) With one trunk pass the gate is already borderline at 1.76 M**: p99 97-99 ms on 10-27 / 10-28 (gate: < 100 ms), p50 55 ms.
   So a 10 M model does not fail "because of a second forward"; it fails (b) because the trunk grows with depth (kernel launches)
   and the memory features cost CPU, with nothing left in the budget.
3. **What is left to remove** is launch/sync overhead, not a forward: the decide still makes 2 GPU call groups (trunk + heads, then
   the cell head after a host sync). Design: ONE CUDA-graph replay per decision (trunk + heads + cell logits of all 4 hand slots), see
   section 4. Expected effect on the 10 M model: section 6.

## 1. Measured state

### 1.1 Laptop live logs (RTX 5050, CLXIII, `decide_ms` of every `decision` event; every 6th log of the day; (a))
| day | decisions | p50 | p90 | p99 | code |
|---|---|---|---|---|---|
| 10-25 | 12,653 | 83 | 101 | 134 | two trunk passes |
| 10-26 | 20,105 | 78 | 93 | 126 | two trunk passes |
| 10-27 | 20,558 | 55 | 79 | 99 | one trunk pass from ~04:25-07:00 (per-file p50 79 at 02:09, 24 at 07:03) |
| 10-28 | 14,508 | 55 | 71 | 97 | one trunk pass |
Source: `scratchpad/gauntlet/L68/live_reader/live_play_2026102{5,6,7,8}_*.jsonl`, awk percentiles. Within a day p50 drifts 24-61 ms
(laptop load: MuMu, thermal), so single numbers carry about +-15 ms of state.

TBD_SECTION_1_2
