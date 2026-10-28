# ONE_FORWARD: one policy pass per live decision (PLAN Pillar 4a latency gate), design for the ~10 M successor

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Design only: nothing here touches the live path.

## 0. Result

1. **(c) The premise "the live decision is 2 forwards" is stale.** `live_gen_v2.GenPilot.decide` has run ONE trunk pass per
   decision since 10-27 (`_policy_forward`: `encode_gen` -> `heads_gen`, then `cell_logits_gen` from that same encoding; ticket B,
   commit b8d4902). The laptop's own logged `decide_ms` shows the step (1.1). The 79 / 113 ms in PLAN 4a is the 10-26 state.
2. **(a) With one trunk pass the gate is already borderline at 1.76 M**: p99 97-99 ms on 10-27 / 10-28 (gate < 100 ms), p50 55 ms. A 10 M
   model therefore does not fail "because of a second forward"; it fails (b) because the trunk costs more launches (7 layers + the
   memory encoder) and the memory features cost CPU, and the budget has no slack.
3. **What is left to remove is launch / sync overhead, not a forward.** A decide is still 548 CUDA kernels in ~3 call groups (trunk,
   heads, cell head after a host sync). **(a) On the 4090, the SAME work as one CUDA-graph replay (trunk + heads + cell logits of all 4
   hand slots) takes p50 1.89 ms vs 9.52 ms eager, outputs bit-identical (max abs diff 0.0) for the 10 M base** (section 3.2). That is the
   design (section 4). Expected laptop effect on the 10 M model: p50 about 25-35 ms, p99 about 65-85 ms (b, section 6), vs about 67 /
   109 ms eager (b).
4. **(a) Closed-loop strength is a separate problem**: the 10 M icebow base (`base_ice`) scores 38.96% vs CLXIII 69.58% on the same 480
   crforge e4 games (paired -30.6 pp [-36.0, -25.2], P4_10M.md). Speed does not matter until the successor is competitive.

## 1. Measured state

### 1.1 Laptop live logs (RTX 5050, CLXIII, `decide_ms` of every `decision` event; every 6th log of the day; (a))
| day | decisions | p50 | p90 | p99 | code |
|---|---|---|---|---|---|
| 10-25 | 12,653 | 83 | 101 | 134 | two trunk passes |
| 10-26 | 20,105 | 78 | 93 | 126 | two trunk passes |
| 10-27 | 20,558 | 55 | 79 | 99 | one trunk pass from ~04:25-07:00 (per-file p50 79 at 02:09, 24 at 07:03) |
| 10-28 | 14,508 | 55 | 71 | 97 | one trunk pass |

Source: `scratchpad/gauntlet/L68/live_reader/live_play_2026102{5,6,7,8}_*.jsonl`, `grep -oh '"decide_ms": N'` + sort percentiles. Within a day
p50 drifts 24-61 ms (laptop load: MuMu, thermal), so a single figure carries about +-15 ms of state. The 10-26 -> 10-27 drop of 23 ms
at p50 is one forward on the laptop (the first S1 estimate was 45 ms, from an idle-GPU measurement; (c) for use as the live cost).

### 1.2 Where one HEAD decide spends its time (pod 30408, RTX 4090 quiet, fp32, the real `GenPilot` on 245 recorded live decisions of 4 logs)
Tool: `scale/v1/live_profile_v2.py` (this folder; raw `results/decide_profile/*.json`). "Staged" = a CUDA sync around each stage.

| model | decide p50 / p99 (staged) | row | encode_gen (trunk) | heads_gen | cell_logits_gen | rest (decode rules etc.) | batch shape signatures |
|---|---|---|---|---|---|---|---|
| CLXIII 1.76 M (fv6, cue, refine) | 10.28 / 12.46 | 1.16 | 6.87 | 0.85 | 0.56 | 0.83 | 1 |
| base_ice 11.1 M (fv6 + memory v2) | 12.71 / 15.07 | 2.45 | 8.55 | 0.46 | 0.36 | 0.87 | 1 |

- Trunk = 67% of the decide for both; going 1.76 -> 11.1 M adds 2.4 ms on the 4090 (+24%: 1.7 ms trunk + 1.3 ms memory row features, less the cheaper heads/cell).
- The cell head runs on 86% of decisions (it is also run for WAIT rows to log their xy), always from the SAME encoding.
- The un-staged pass has p99 51 / 41 ms from cold calls: the harness builds a new pilot per log (4 cold starts in 245 decisions). Warm p99
  is the staged one. (b: the live p99 tail of 30-40 ms spikes seen by S1 is `row`, not the model.)
- **One batch shape signature in 245 decisions** (all tensor keys): a static-shape graph needs exactly this.

### 1.3 Model-only latency from the held-out evals (pod 4090, batch 1, 300 reps, `scale_eval_v1.py`, (a))
| model | params | bs1 fp32 full forward p50 / p99 | bs1 bf16 p50 | decide path eager p50 / p99 | CUDA kernels / decide | one CUDA graph p50 / p99 |
|---|---|---|---|---|---|---|
| CLXIII | 1.76 M | 8.29 / n.a. | 9.55 | 8.56 / 10.95 | 497 | capture failed (below) |
| base_pre (= base_ice architecture) | 11.1 M | 9.33 / 11.79 | 12.24 | 9.52 / 15.77 | 548 | **1.89 / 2.02** |

- bf16 is SLOWER at batch 1 (12.2 vs 9.3 ms): precision is not a lever here.
- The kernel count is nearly the same for 1.76 M and 11.1 M (497 vs 548): batch-1 time is launch-bound, size barely matters (the S1
  finding, now also in the decide path).
- CLXIII's graph capture raised `Cannot copy between CPU and CUDA tensors during CUDA graph capture` (a constant tensor built inside
  its refine modules). The successor has no refine modules and captures; a refine model would need that constant registered as a
  buffer (b, small, not done).
- Graph vs eager outputs on the captured row: gate 0.0, card 0.0, cell 0.0 max abs difference, argmax equal (a, ONE real row; the
  N-decision identity test below is owed).
- More points (m2, m5, m20 at the same recipe) arrive with the curve-v1 evals (`results/`, `aggregate_v1.py` table 6).

## 2. What "one forward" means in the three decision paths (PLAN P1)
All three call the one `decision_options.decide(heads, p, allowed, stalled, cell_logits=...)`; they differ only in how `heads` and the
`cell_logits` callable are produced:

| path | trunk passes per decision | cell head | where |
|---|---|---|---|
| SIM eval / forks | 1 per batch row | lazily, per row that needs it, from the batch encoding | `e1_eval.GenPolicy.heads_t` (encode_gen + heads_gen), `decision_options.model_cell_logits` |
| rollouts (batched, policy server) | 1 per row | same, lazily (`lazy_refine` split) | `batched_rollout`, `policy_server.Client.decide` |
| live | 1 (since 10-27) | one call per decision, batch 1 | `live_gen_v2.GenPilot._policy_forward` |

So "training = SIM = live" already holds at the level that matters: the same model methods and the same decide. A graph replay would
be an execution strategy of the live callable pair (heads, cell), not a change of the decide.

## 3. Options for what is left (live gate, 10 M model), with evidence
| option | effect | status |
|---|---|---|
| A. one CUDA graph: trunk + heads + all-4-slot cell logits, one replay, one sync | pod 9.5 -> 1.9 ms; bit-identical on the captured row | (a) measured on the pod; laptop owed |
| B. skip the cell head on WAIT rows | saves 0.36-0.56 ms of 10 on the pod; changes the logged xy of 14%+ of rows; changes decision dicts | rejected: little gain, breaks the dict identity |
| C. bf16 / fp16 | slower at batch 1 (12.2 vs 9.3 ms) | (c) contradicted |
| D. CPU forward | 47 ms at 12 M (SPEED.md h) | rejected |
| E. fewer layers at equal params | fewer launches; not needed if A works | (b), curve shape unknown |
| F. torch.compile reduce-overhead | needs Triton; not on Windows torch | (b) unavailable |
| G. trim `row` / `rest` | row 1.2 -> 2.5 ms with memory (CPU), rest 0.8 ms; x5 on the laptop = 17 ms | (b); after A they are the whole decide |

## 4. Design for A: `GraphedPolicy` (replaces `GenPilot._policy_forward`'s body when `--policy-graph on`; default off)
- **Where**: a new `pipeline/policy_graph.py` (about 80 lines) used by `live_gen_v2.GenPilot._policy_forward`; `decision_options.decide`
  is not touched (P1 stays: one decide). SIM / rollouts do not use it (their batches vary in size).
- **Capture** (first decision, or when the batch signature is new): signature = sorted `(key, shape, dtype)` of all tensors in `b`; clone `b`
  into static buffers; 3 warm-up calls on a side stream; capture
  `enc = encode_gen(b); out = heads_gen(enc, b); cells = stack(cell_logits_gen(enc, hand_card[:, i], hand_form[:, i]) for i in 0..3)`;
  graph outputs = gate, card, value, wait, `g`, `cells` [1, 4, N_CELLS] and the `enc` tensors a fallback cell call needs.
- **Per decision**: `static[k].copy_(b[k])` for the keys, `graph.replay()`, then ONE host read (gate, card logits, and the cell logits of the hand
  position the rules ask for; the three tensors are copied back together). The decide's `cell_logits(ids, slots)` closure already
  holds the hand POSITION (`slots[0]`): the graph path returns `cells[:, pos]` instead of calling the model. A card not in hand (never
  asked by the rules today) falls back to an eager `cell_logits_gen` on the graph's `enc` outputs.
- **Fallbacks, never silent**: (1) signature changes -> eager `_policy_forward` for that decision, re-capture on the next, counted in the log;
  after 3 re-captures per match give up for the match; (2) capture error at start (as CLXIII's) -> eager for the run, written once in the start event;
  (3) a `--policy-graph check N` mode runs eager AND graph for the first N decisions and refuses to continue on any argmax difference.
- **Numbers kept the same**: fp32, same kernels as eager at batch 1. The cell logits are computed as a batch of 4 (the eager path calls batch 1);
  cuBLAS may pick another kernel for that shape, so cell logits are expected equal to ~1e-6, not bitwise (measured bitwise equal on the one row).
- **Memory**: graph + static buffers < 100 MB for the 10 M model (b, not measured on the laptop; the 4090 eval peak was 5.4 GB incl. the dataset).
- **10 M interplay**: the successor (fv6 + memory v2, no cue / refine modules) has ONE signature and captures (a). The memory features come from the
  CPU `row()` (2.45 ms on the pod), outside the graph. The IW-press / posture heads read `out['g']`: kept as a graph output.

## 5. Identity tests needed (all on recorded live decisions; none exists for the graph yet)
1. **Existing, must stay green with the flag off AND on**: `pipeline/tests/test_decide_identity.py` (live recorded decisions of 4 logs; live
   stress path; SIM rows; one live row through `decide_batch`). Measured today: new single-trunk path vs BASE a76f57e on CUDA, 1,718
   decisions, 229 taps, 0 tap and 0 decision-dict differences; stress 1,405 taps, 0 differences (SPEED.md k2, a).
2. **New T-graph**: the same 4 logs x (normal, stress) through the pilot with the graph vs eager, same checkpoint, same device: pass = 0 tap
   differences and 0 decision-dict differences except the documented float bits of `p_play`; any difference listed. Baseline noise to compare with:
   cpu vs cuda gave 0 action differences, `p_play` bits in 1,564 rows and one WAIT-row xy near-tie flip of 1,718 (SPEED.md k2).
3. **New T-shape**: over those logs the signature set has size 1 for the 10 M model (a: 1 over 245 decisions; extend to all 4 logs in full).
4. **New T-fallback**: force a new signature mid-match and a failing capture; the decisions equal eager and the counters/start event say so.
5. **New T-successor**: T-graph with the 10 M checkpoint (memory features from the pilot) against eager HEAD (no BASE exists for memory models).
6. **Laptop run (owed, needs live paused ~5 min)**: `live_profile_v2.py` (it works on the laptop: repo root as cwd, `icebow/.venv` python) for CLXIII
   plus T-graph on the RTX 5050 (Windows torch, sm_120): capture must succeed and match eager. Without this every laptop number below is (b).

## 6. Expected latency on the RTX 5050 laptop (b; no 5050 measurement exists for the successor)
Method: scale each pod stage by the observed laptop/pod ratio of the CURRENT decide (laptop 55 ms p50 vs pod staged 10.3 = 5.3x) and the laptop
p99 tail (+42 ms over p50, from 97 vs 55). The ratio is not uniform (launch-bound stages scale with the CPU, graph replay with the GPU), so ranges.

| scenario | p50 | p99 | basis |
|---|---|---|---|
| CLXIII, HEAD (a) | 55 | 97-99 | logged 10-27 / 10-28 |
| 10 M successor, eager | about 67 | about 109 | 12.7 ms x 5.3; same tail |
| 10 M successor, one graph replay | about 25-35 | about 65-85 | row 2.45 + rest 0.87 on the CPU x 5.3 = 17.6, + replay 2-6 ms on a 5050 + copies; same tail |
| S1's earlier estimate (SPEED.md a3) | 31-41 | - | one forward x 25-35 ms + 6 |

Reading: eager at 10 M fails the p99 < 100 ms gate by about 10 ms (b); the graph variant passes with about 15-35 ms of margin, and most of what
remains is CPU (`row` + `rest` + the 30-40 ms `row` spikes S1 saw), so the next lever after A is the memory feature builder, not the model.

## 7. Recommendation and what is owed
1. Do not shrink the model for latency; do not build a "one-forward" change (it exists). Build A (about 80 lines + tests 2-5) only when the
   successor is close to CLXIII in closed loop (today -30.6 pp); until then the gate is not the bottleneck.
2. Owed (cheap): the laptop run of `live_profile_v2.py` with live paused (section 5.6) to replace every (b) in section 6 by (a).
3. Owed: T-graph on the recorded logs (needs a worker with the pod tree `/workspace/p4/prof_tree`; the script harness is `decide_identity_cuda.py`).
4. Needs a lead / owner decision: adding `--policy-graph` is a live-path option (LIVE_OPTIONS-deployable like the others); not started.
