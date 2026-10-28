# P6 macro prefixes as fork alternatives -- design note (not code), P3-FORK, 2026-10-28

Labels: (a) measured, (b) plausible / untested, (c) contradicted. Nothing below is built; section 7 lists what is.

## 1. What P6 needs from cf_credit (PLAN P6 mechanisms 2 and 3)
A macro is a multi-play plan (up to ~20 s) credited ONLY as a fork alternative: at a decision where its start condition
holds, one extra candidate plays the macro's scripted prefix, the learned policy continues, and the composite-return
difference against the other candidates becomes the advantage on EVERY action of the prefix. Deployment runs the learned
policy alone; a macro is never a rule or a reward. cf_credit already has the pieces for a ONE-step alternative (candidate
records, K = 2 paired continuations, Q in the trainer's return, per-trigger shrink, horizon, audit). What is missing is
(i) a candidate that carries several plays, (ii) a row for every play of the prefix, (iii) a per-macro horizon and budget.

## 2. Macro record (what the library, mined from the 252k HF replays + pro corpus + live logs by a later ticket, must hand over)
```
{"id": "sneaky_lock", "doc": "...", "owner_named": true,
 "start": {...},            # predicate over the decision's state, a dict of named conditions (section 3)
 "prefix": [step, ...],     # 1..4 steps
 "horizon_ticks": 400,      # the window over which the macro's human win lift is measured (PLAN P6 mechanism 3)
 "gap_ticks": 100,          # min ticks between two samples of this macro in one match
 "alt_of": ["wait", "chosen"]}   # which plain alternatives it is compared with (the baseline set); chosen is always in
step = {"card": "tornado" | {"role": "answer_to_tank"},   # card name or a role the executor resolves from the hand
        "where": {"ref": "enemy_defender_nearest_xbow_lock_line", "dx": 0.0, "dy": 1.5} | {"cell_set": "xbow_lock_tile"},
        "wait_ticks": 0,    # ticks after the PREVIOUS step's decision before this step is due (0 = same decision: follow_ups)
        "require": {"elixir_by_due": 4.0, "in_hand": true},     # preconditions at the due tick
        "on_fail": "abort"}  # abort | skip
```
`where` is a geometric spec resolved on the live board at the step's due tick (a reference to units / towers / tiles plus
an offset), never a fixed cell: the sneaky lock's X-Bow tile depends on where the Tornado left the defender. A set of
resolvers (named, unit-tested, one per reference kind) lives in cf_credit next to siege_cells / front_cells / pull_centre.
The owner-named macros of PLAN P6 are always in the library; mining only refines `start` and `prefix`.

## 3. Start conditions
Reuse the trigger machinery: a macro is a trigger named `macro:<id>` with `cond`, `cf_p["macro:<id>"]`, the gap rule, the
cond_ticks record for the budget model, and the same "first firing trigger with an alternative" order. `start` is the AND
of named conditions that already exist as helpers (siege_target, redirect_target, combo_hit, xbow_failed window, bait_seen,
hand / elixir tests); a new condition = one function + one planted-state test. The pilot's trigger set therefore stays the
building blocks, and a macro is a trigger with a longer alternative.

## 4. Executing a prefix in a fork (two mechanisms, both already in e1_eval)
1. Same-moment plays (the Rocket + Tornado combo is the built instance): step 2 is a `follow_ups` play of the first
   (e1_eval.follow_up_spec: due `after_ticks` later, afford check, expiry). No new engine code. Limit: the cell is fixed at the
   root, so it cannot react to the board.
2. Reactive plays (sneaky lock, defensive X-Bow then counter-lock, counter-push behind survivors): a `Prefix` object attached to
   the fork's learner side. At each of that side's decisions after the root, if a step is due (`wait_ticks` elapsed), the
   decide result is REPLACED by the step's resolved action (card from the hand, cell from the resolver on the live board) with
   `why = "cf_prefix"`; the sampled decision is discarded. A failed `require` aborts (or skips) the rest and is counted.
   After the last step the side is the plain learned policy again. The action delay (26 ticks) and the SIM's pending lock
   apply as for any play, so steps are >= one decision apart (decide_every 10) -- the same constraint a human-speed player
   has; sub-decision pairs use mechanism 1.
   Candidate 0 (the policy's own decision) and plain alternatives never carry a prefix, and the prefix runs only on the K
   continuations of its own candidate: the CRN pairing is unchanged.
A failed attempt is a real outcome of trying the macro, so it keeps its Q (it is not dropped); the per-macro
`abort_rate` and `well_executed` (all steps played) are reported next to the advantage so that the owner's "well-executed vs
failed attempts" diagnosis is read from data. (b) Aborts bias the macro's advantage down; the report splits both.

## 5. Rows: one per prefix play, advantage on every one
- Step 0 is the root decision: the existing alternative row (the real decision's inputs, the step's action, behaviour log-probs
  from `alt_logprobs` on the real forward).
- Step j >= 1 is a decision of the FORK's learner side (mechanism 2), so the fork already holds its row: the fork side's
  `traj` starts empty (FORK_FRESH) and `_record` appends one row per decision with the full inputs. After the fork ends, take
  those rows (`f.learner._traj_arrays()` row indices recorded when each prefix step is applied) and ship them in the sample as
  `cands[i]["prefix_rows"] = [{"step": j, "tick", "inputs": traj slice of that row, "play", "slot", "cell", "lp_gate",
  "lp_card", "lp_cell"}]`. The log-probs of a forced action come from the same sampler on that row's own forward
  (`alt_logprobs`), as for the root alternative.
- Learner side (rl_royale.cf_append): an alternative candidate with `prefix_rows` appends 1 + len(prefix_rows) rows, all with the
  candidate's A_i (PLAN: "the composite-return difference vs the base branch becomes the advantage on EVERY action of the
  prefix"). The cf_append rule "every row-aligned key of B has a rule" holds: the prefix row's keys come from its own traj
  slice (not the real match's `t[k][di]`), and `mem_row_tab` / memory-table keys need the fork's memory rows -- see 7(c).
- Size (b): a traj row is ~10-100 kB; 1 macro sample x 3 steps x ~0.3 samples/match x 512 matches = ~150 rows/update; fine over
  the actor result pipe. If rows must stay out of the pipe, store the fork seed + prefix and re-run the fork on the learner
  host (re-playing is deterministic, `test_forks` proves it); not needed at this volume.
- The combo built now (candidates with `follow_ups`) is the 1-row case: its Tornado has no row, so the policy learns the
  Rocket cell but not the second card (see "Combo caveat" in section 6). Mechanism 2 gives the second card its row.

## 6. Horizon, budget, noise (PLAN P6 mechanism 3, P3 noise controls)
- `horizon_ticks` per macro: Q is read at the first learner decision >= root + horizon (Runner.rollouts takes `stop` per
  candidate instead of per call; today it is one `cf_horizon_ticks`). A macro whose payoff is the match end (Rocket cycling in
  2x / OT) sets horizon = run to the end (the existing `to_end` path).
- Cost: fork ticks = K x (1 + alts) x horizon per sample; `cf_cap_ticks` and the pilot_report budget model (cond_ticks -> samples per
  match at any p -> water-filling over triggers incl. macros) keep the total <= 1x match ticks. A macro with SNR < 0.5 gets more
  continuations (`k_for_snr_0.5` in the report), a horizon matched to its payoff, or a control variate (the plain-alternative
  baseline's own Q, subtracted per continuation: the CRN pairing already does most of this).
- The 10% terminal audit covers every macro: the slope of the terminal return on the horizon Q per macro, band [0.7, 1.3].
- Combo caveat (a, by construction): the built combo credits the Rocket row only; the learned policy can raise
  "Rocket at the pull centre" but cannot learn "Tornado 8-14 ticks later" until a macro-style row exists for the second card
  (this section 5) or the learner decides with `pipeline_decisions` (two plays outstanding, e1_eval FOLLOW_MAX_OUT).

## 7. Build order (each a separately committed, separately tested step; none is built yet)
a. `Prefix` executor in the fork + resolvers + planted-state tests (a prefix plays exactly as scripted; abort accounting; a
   scripted prefix leaves candidate 0 and the plain alternatives bit-identical; determinism over two fork sets).
b. Per-candidate `stop`/horizon; macro record loader (JSON schema above, validated like cf_cfg: unknown refs, steps > 4, bad
   horizons refuse); `macro:<id>` triggers in `triggers()` / `candidates()`; cond_ticks for the budget model.
c. Prefix rows through the actor record -> `cf_append` (memory-table keys: the fork's memory rows exist only if the fork side
   runs the memory encoder -- it does with `memory` on, in the same process; the row's `mem_t` comes from its own traj slice).
d. Toy with a known answer: a planted macro whose prefix wins in the SIM gets a positive A on every prefix row and its sign
   flips when the engine outcome is flipped; a macro that loses gets the negative sign.
e. Owner-named macros one by one with a measured sign against the human lift (P4 audit): sneaky lock first (it needs the
   Tornado-pull + X-Bow-targeting fidelity items), then Rocket cycling, Rocket + Tornado, Tornado redirect, defensive X-Bow +
   counter-lock. A wrong sign starts the PLAN P4 iteration (fidelity / opponent punishment / horizon / critic bias / spec).

## 8. Not decided here (owner / lead)
- Whether a prefix step may be a learned-policy sample restricted to a card (a "constrained rollout") instead of a scripted
  cell: more general, noisier. Default here is scripted cells from named resolvers.
- Macro-start probabilities `cf_p["macro:<id>"]` and the budget share per macro: set from pilot_report's budget model once the
  library exists (the same procedure as the current triggers).
