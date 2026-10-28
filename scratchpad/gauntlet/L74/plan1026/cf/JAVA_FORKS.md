# Counterfactual forks in the fast (Java) loop -- design note (not code), P3-FORK, 2026-10-28

Labels: (a) measured, (b) plausible / untested, (c) contradicted. The loop is plan1026/pilot/loop (LOOP-INT: CfTrain.java +
producer.py + fastloop.py; STATUS in LOOP_INT.md). cf_credit today runs only inside rl_royale's actor (Python forks of the SIM).

## 1. The interface LOOP-INT receives (unchanged by this note)
- Per match record: `SelfPlayMatch.result()["cf"]` = `cf_credit.match_record(state)`:
  `{"samples": [{row, tick, trigger, audit, to_end, cands: [{kind, play, slot, cell, lp_gate, lp_card, lp_cell, q:[K], end:[K],
  terminal:[K], q_end, follow_ups?}], fork_ticks, wall_s, target?}], triggers, fired, capped, cond, cond_ticks?, decisions,
  fork_ticks, wall_s, xbow_failed, k}`; `row` = index of the decision in the match's traj (`cands[0]` is that decision).
- The learner reads it in `rl_royale.cf_append` -> `cf_credit.batch_advantages` (A_i = Q_i - mean_j Q_j per candidate, shrunk by
  the trigger's reliability) and appends one row per alternative (the decision row's inputs, the alternative's action and
  behaviour log-probs). Nothing in the learner changes when forks run in Java: the producer only has to emit this record.
- Q is the trainer's own return: `gamma_tick^(t - root) (Phi(s_t) + v_scale v_net(s_t))` at the first learner decision >=
  root + horizon, or `gamma^(T - root) R_win` if the copy's match ended first; Phi = `tower_phat` from the same state record
  the rows use (reward_shaping.state_record / state_phi).

## 2. What a fork needs (the Python version, search_s0.fork_into + Runner.rollouts)
(1) the engine state (CfCore.save()/load(): crforge DeepCopy of the match + the facade's play log; a snapshot is never stepped,
so one snapshot feeds any number of forks); (2) a deep copy of both sides' Python state (RNG streams, accepted plays, pending
play, counters; `traj` starts empty); (3) CRN reseeding of the K >= 2 continuations (`cf_credit.reseed`); (4) the root
applied per candidate; (5) lockstep rounds of the plain decide over all copies until each learner side stops.

## 3. Proposed design: a fork is another match slot in the same CfTrain batch
- Reserve F extra slots per producer (`n = matches + F`); a free-slot list. Rows stay at the fixed positions `2 * slot + seat`,
  so a fork's seats are decided in the SAME batched forward as every real match (no new forward path).
- `CfTrain.forkInto(src, dst)`: `core[dst].load(core[src].save())`, then copy everything the loop keeps per match at index
  `src`: the schedule arrays (`next`, `pendLand`, `pendSlot`, `pendCell`, `pendX/Y`, `pendPX/PY`, `fresh`, `live`, job arrays
  `jDeck jForm jIds jLv jInv jSlotDeal jSeed jTl jDe jDelay`), `CfIdent`, `CfPubObj`, `CfCue.Seat`, the CfMem seats and their action
  `Log`, and the `CfOppElixir` counters. Each builder needs a `copyFrom(other)` (they are written re-runnable after a table
  miss, which suggests their state is plain arrays; (b), not read in full). Acceptance, per component: after the copy, `n` ticks
  of the same actions give rows bit-identical to the source's (the compare.py harness already does this kind of check).
- Python: the producer holds real `e1_eval.SelfPlaySide` objects per job on a capture-only env; a fork deep-copies the two sides
  (the `fork_into` Python half without the env) and applies `reseed` for k >= 1. A small per-fork state machine
  (root candidate applied, waiting for the stop tick, value read, result written into the sample) replaces `Runner.rollouts`'
  lockstep loop; the loop's own rounds step the forks with everything else.
- Q at the stop: the learner seat's forward at that decision already returns the value head (the same forward feeds the policy
  decide); Q = gamma^(t-root) (Phi + v_scale v) needs no extra forward. Phi needs the fork's tower HPs (CfCore state, cheap).
- Terminal: the match-end tally (`res[]`: endTick, winner, crowns) of the fork slot.
- CRN across candidates: the same `reseed(seed, k)` as today, so a fast-loop sample is comparable draw for draw with the Python
  Runner's (acceptance test below).

## 4. Alternatives need cell log-probs the producer does not hold in server mode
Restricted alternatives (rocket_clump, troop_on, front, xbow_defensive, tornado_king ...) take the policy's argmax cell inside a
cell set for a given card, and every alternative row needs `lp_gate / lp_card / lp_cell` under the sampler. That needs
`model.cell_logits(enc, slot)` for the alternative's card -- one extra pass through the cell head (cheap vs the trunk) at the
trigger decision only. With LOOP-SRV (the model lives in the GPU server) the interface has to grow one call:
`score(row_id, [(slot, cell_mask | cell), ...]) -> [(cell, lp_gate, lp_card, lp_cell)]`, run on the trunk output of that row
(keep `enc` of the last round's rows for one more round, or recompute that one row). (b) A few triggers per match, so the
extra load is far below 1% of the forward. In-process producers (no server) can call `cf_credit._Pol` unchanged.

## 5. Triggers in the loop
The fast loop does not build the raw `state["entities"]` dict each decision (rows are built in Java), and cf_credit's triggers
read it. Two classes:
- Board-free (need only the seat's own bookkeeping): `rocket` (Rocket affordable), `rocket_played`, `idle_full`, `log_bait`
  (accepted-plays list), `xbow` (the played cell), `random`. Port the condition checks as they are; the producer has the
  decided action, the allowed mask and the elixir.
- Board-reading: `wincon`, `siege`, `xbow_after_fail` (X-Bow watch), `tornado_redirect`, `rocket_tornado` (a clump). Evaluate
  them only at decisions where a cheap precondition holds (an enemy building on the board; our X-Bow alive; Tornado affordable;
  Rocket + Tornado in hand) and read the match's `CfCore.state()` through JPype then (one JSON per such decision); the SIM
  trigger code runs on the same entity arrays. A Java port of the geometry is the later optimisation.
- Today the loop raises `NotImplementedError` for follow_ups (CfTrain: "no follow-ups, no pipelined decisions"), so the combo
  candidate (a follow_ups Tornado, built in the Python Runner) needs either the port of `_apply_follow_ups` /
  `_follow_check` (the schedule arrays above already hold the pending play; a follow-up is a second pending entry with its
  own due / expiry / afford rule) or the macro-prefix executor of P6_DESIGN.md section 4 mechanism 2.

## 6. Cost (b: from the Python measurements and the loop benches, nothing here is measured in Java)
- Python forks today (a, pilots): fork ticks 4.4-7.4x the match ticks at the pilot probabilities, fork wall 55-125 s per match
  next to a 180 s match (cf/data/*). The tuned defaults (STATUS) target <= 1x ticks.
- The loop (a, LOOP_INT): 0.70 core-s/match all-in at 48.9k matches/h per 54-vCPU 4090 node. A fork is the same work per tick as a
  match (engine 0.25 + obs 0.04 + decide + forward), so cf at 1x ticks is ~+0.70 core-s/match and +1x rows through the server:
  matches/h about halves (~25k/h per node), still ~5x the Python rl_royale actor path (pilot LRN: 512 matches in 309 s with
  40 actors = 6k/h). With the 8x PRO 6000 box (LOOP_INT projection ~160k matches/h per inference GPU) cf-on lands near 80k/h per
  GPU: the 512-match update is seconds, so forks are not the bottleneck; the learner is (LRN.md).
- Memory: F reserved slots per producer; each slot is one match's buffers (rows 2 * slot) plus a CfCore: a few MB; F = 4 x the
  trigger samples in flight (K x C = 8 slots per sample at K = 2, 3 alternatives).

## 7. Acceptance and order of work (none built)
1. `forkInto` + builders' `copyFrom` with the bit-identity test above (engine + rows), no policy involved.
2. Producer fork state machine for plain-play alternatives; test: the same match, same trigger decision, same candidates ->
   `q` of every candidate / continuation equals `cf_credit.Runner.rollouts` to 1e-6 (the compare.py pattern: production vs
   producer, same process). K = 2 CRN draw for draw.
3. Board-free triggers, then board-reading ones; per-trigger fire-rate equality with the Python audit (trigger_audit.py).
4. `score` call for the server mode; follow_ups port (combo) or the prefix executor; macros (P6) on top.
5. Bench: matches/h with cf on at the tuned probabilities vs cf off (33553, same grid as LOOP_INT's table).
Owner of this later work: LOOP-INT; this note replaces nothing in LOOP_INT.md, it adds the fork requirements.
