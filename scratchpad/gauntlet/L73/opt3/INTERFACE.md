# Option 3 (counterfactual branching for the play/wait gate) -- lead interface contract, 2026-10-07

Branch `opt3-branching`, worktree `.claude/worktrees/opt3`. Three tickets, disjoint write sets, this contract binds them.

## T1 pipeline/branching.py (fork + paired rollouts)
- Reuse `pipeline.search_s0`: `fork_into`, the pooled-engine + lockstep batched rollout pattern (`Runner.rollout_scores`),
  `SHARED_SIDE`. Do NOT edit search_s0.py.
- `@dataclass BranchSpec`: hold_s (float), hold_tau (float, default 0.55), horizon_s (float or None = play to the end),
  k (int continuations per branch), seed (int).
- `class BranchRunner(make_env, learner, opps, learner_cfg, *, device)`:
  `pair(m, ds, spec) -> BranchResult`. At decision ds of SelfPlayMatch m (our side about to PLAY under the live rule):
  * PLAY branch = the live rule's action now (gate tau from learner_cfg, argmax card/cell).
  * HOLD branch = for hold_s seconds our side may play only if P(play) > hold_tau (stricter gate; anti-stall unchanged);
    afterwards the live rule resumes.
  * Both branches then run our live rule and the opponent's own policy/cfg (the real opponent of m, not a self-model).
  * COMMON RANDOM NUMBERS: continuation j of PLAY and of HOLD use identical RNG seeds for every stochastic component
    (opponent sampling, our sampling if any, engine RNG if exposed). k continuations per branch.
  * Stops at the end of the match or horizon_s; returns the end states.
- `@dataclass BranchResult`: tick, phase, p_play, elixir, play_end: list[state snapshot], hold_end: list[...],
  play_outcome / hold_outcome: list[int|None] (+1 win, -1 loss, 0 draw, None = horizon reached), wall_s.
- Determinism test: fork + identical actions -> identical engine state hash and identical python-side state.

## T2 pipeline/branch_score.py (scoring + validation gate)
- `score(end_snapshot, outcome, *, kind)` for kind in {"outcome", "phi", "towers"}: outcome when the match ended
  (+1/-1/0); "phi" = a FROZEN gen model's value head P(win)-P(loss) at the horizon state (public inputs only; model path
  from config); "towers" = tower-HP fraction difference (reference only). NEVER charge spent elixir (S0's scorer did:
  it chose WAIT on 78% of decisions and did not win more).
- `branch_label(result, kind) -> (delta, weight)`: delta = mean score(PLAY) - mean score(HOLD) over the k pairs.
- Validation harness `scratchpad/gauntlet/L73/opt3/validate.py`: N decision points from sim matches; horizon-H
  scores vs FULL-MATCH outcome deltas (k continuations to the end); report Spearman / sign agreement with CIs per H.
  This is the scorer gate for R3.

## T3 pipeline/rl_royale.py integration (opt-in, default off = byte-identical)
- Config keys: branch_gate (bool, default false), branch_actors (int, default 1: one actor process runs branch jobs
  instead of PPO rollouts), branch_points_per_match (default 4), branch_band [0.2, 0.65] (p_play range at tau .35;
  stratify more points in 2x/OT), branch_hold_s [2, 4, 8], branch_hold_tau 0.55, branch_horizon_s, branch_k,
  branch_score ("phi"|"outcome"), branch_phi_ckpt, branch_coef (gate-loss weight), branch_min_abs_delta.
- Branch actor: plays its own matches with the CURRENT learner weights (synced like PPO actors), greedy live rule
  (tau .35, argmax) on the main trajectory; at selected points calls BranchRunner.pair, emits samples
  (decision row in the learner's row format + delta + weight).
- Learner: extra loss on branch samples only: BCE(gate_prob(row), target) * weight * branch_coef, target = 1 if
  delta > 0 else 0 (|delta| < branch_min_abs_delta -> dropped), gate_prob uses the same parameterisation as the live
  gate (P(play) vs tau). PPO + KL leash unchanged. Log per update: n samples, share HOLD-better, mean delta, by phase.
