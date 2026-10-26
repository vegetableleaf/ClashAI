# cf_credit (counterfactual credit from SIM forks) -- plan for the remaining work

## State when plan mode started (edits ALREADY made, uncommitted)
1. `pipeline/e1_eval.py`
   - `run_selfplay_batch`: the per-round decide is moved out unchanged into `selfplay_decide(due) -> [(side, p, d)]`
     (same grouping, same order, same calls). After the decide, `cf.hook(live, todo)` runs only when `cfg["cf"]` is set;
     with no `cfg["cf"]` the loop is the old one.
   - `SelfPlayMatch.result`: adds `r["cf"] = cf_credit.match_record(self.cf_state)` only when the match has a cf_state.
2. `pipeline/search_s0.py`: `fork_into(m, env2, blob, fresh=())`. The new optional argument lists side attributes a fork
   starts empty (cf uses `("traj",)`); the default is the old behaviour.
3. `pipeline/cf_credit.py` (new): `DEFAULTS`/`KEYS`, `cf_cfg` (validation + refusals), `canonical` (for the hash),
   alternatives (`rocket_clump`, `rocket_princess`, `siege_<card>`), `alt_logprobs` (the sampler's own float64 tempered
   gate x card x cell), `siege_target` (enemy building locked on our tower via `target_uid`, or an X-Bow / Mortar within
   XBOW_REACH_TILES), `Runner.hook` / `Runner.rollouts` (baseline fork + one fork per alternative, lockstep through
   `selfplay_decide`, stop at the learner's first decision >= root + H and read V = v_scale x value_scalar(value_head), or
   the terminal reward), `batch_stats`.

How forking works: `search_s0.fork_into` gives each fork its own engine via `env.core.save_state()` / `load_state(blob)` into
pooled `RoyaleSelfPlayEnv`s. The env's python fields and both sides' python state are deep-copied, including every RNG
(rng_behave, rng_obs, rng_ability, tap-loss RNGs) and the engine Rng inside the blob. Models / cfg / deck are shared.
Because RNG state is copied rather than reseeded, the baseline fork should replay the real continuation draw for draw;
a test will check this.

## Remaining steps
### A. `pipeline/rl_royale.py`
- `from pipeline import cf_credit as CF`.
- `load_config`: accept `CF.KEYS` as overrides; call `CF.cf_cfg(cfg)` (SystemExit on a bad value).
- `config_sha`: `cfg = CF.canonical(cfg)` before hashing, so off / absent gives the historical hash.
- `actor_base`: when on, `base["cf"] = {**cf, "v_scale": s}`, where s = `shaping_critic_scale` if spell / crown / habit terms
  are on (residual critic, Phi = 0) and 1.0 otherwise.
- `actor_cfg`: `kind == "rollout"` and `base.get("cf")` -> `cfg["cf"]`. In `actor_main.mk_cfg`, the ability label-mode
  branch (the B6 warm start) does `c.pop("cf", None)`, so no forks are spent on warm-start rollouts.
- `collate(..., cf=None)`: when on, compute `st` on the real rows first. Then APPEND the alternative rows at the END of every
  row-aligned key (everything except `mem_tab_*`):
  - The decision's inputs are copied from `traj[k][smp["row"]]`.
  - Overrides: played=True; slot / cell / lp_* from the alternative; lp_old = their sum;
    A = cf_w x clip(dq, -cf_clip, cf_clip); w = that match's row weight; match = j; mem_row_tab = use.index(j);
    mem_row_t = mem_t[row]; ab_sampled / ab_press False; ab_lp 0; w_ab 0; r_step 0; gamma_row 1; phi 0.
  - Add `B["cf"]` (False for real rows, True for alternative rows) and `st["cf"] = CF.batch_stats(...)`.
  - Raise if a row-aligned key has no rule, so a future key cannot be dropped silently.
- `gae_batch`: when `"cf" in B`, compute on the real-row slice `[:n]` only. Then A = cat(normalised real A, the
  alternatives' preset A), ret = cat(target, zeros), v_old = full. Monitors use real rows only. With no cf, the slice is
  `slice(None)`, so the arithmetic is unchanged.
- `minibatch_loss`: when `"cf" in B`, real = ~cf[idx]:
  - value-loss weight = w x real;
  - KL gate / card / cell and the entropy monitors use the real rows only (`t["cell_lp"][real[pl]]`);
  - L_pg and the ratio / lp_maxdiff monitors include the alternative rows. This means the update-0 on-policy assert also
    checks the alternatives' old log-probs.
  - The absent path keeps the original expressions.
- `ref_terms`: the `R["ent"]` masks exclude cf rows when present.
- `one_update`: pass `cf=CF.cf_cfg(cfg)` to collate. `rec["cf"]` arrives through `**bst`. Log segment:
  `| cf trig {..} alts n dq mean / +share [kind n dq] fork s/m, share of match wall`.

### B. `pipeline/tests/test_cf_credit.py`
Pure tests, run in the laptop's icebow venv with `torch.set_num_threads(1)`:
- Absent is the pre-change trainer. PRE = 98edb8e (git show), compared against:
  - config_sha of rl_royale.yaml and stepd_l16_s74.yaml for absent / null / false (and on must differ);
  - collate bytes;
  - two whole gae updates' records, weights, beta, rng and checkpoint keys (the `_learner` / `_strip` helpers from
    test_rl_gae).
- collate with cf: real rows are byte-identical to cf off; alternative rows carry the decision's inputs, the alternative's
  action / log-probs, A = w x clip(dq), and no value / GAE contribution. gae_batch's real-row A / ret equal the cf-off ones.
- Old log-probs: `alt_logprobs` on a tiny S1 model's synthetic row equals `policy_terms`' recompute on the collated
  alternative row (< 1e-6). Covers tau_phase gate_tau and T_gate.
- Gradient sign: one alternative row with synthetic dq > 0 (all real A = 0) raises log pi(alt) after one PPO step, and
  dq < 0 lowers it. Alternative rows put no gradient on value_head.
- Validation: refusals (no gae / league, branch_gate, posture_head, critic_ctx, shaping, potential, stray keys).

Engine tests (RoyaleSim; laptop `ROYALE_RUNTIME=20261006 research/ext/Royale/.venv` for a few seconds each, else on the pod),
using test_search_s0's tiny models on icebow vs hogeq, `in_flight=1`:
- Fork determinism: two baseline-only fork sets from one state end with an equal engine state_hash and an equal V.
- Baseline reproduces the real continuation: a spy on `Runner.rollouts` captures the baseline fork's learner plays and
  engine hash at its end tick. The real match, continued, must show the same plays and hash at that tick. With batch size
  1 in both, forwards should be bit-identical. In production the real forward is batched with the other in-flight matches,
  so a float difference at ~1e-7 can flip a draw that lands on a threshold. The report will say this.
- An end-to-end match with cf on (triggers forced by p=1 / budgets) produces samples, and `collate` + `policy_terms` on its
  alternative rows reproduce lp_* within 1e-5.

### C. Checks before the pod
pyflakes on the changed files. The test suites test_cf_credit, test_rl_gae, test_reward_terms_1020 TestAbsentIsPre,
test_league and test_search_s0, kept short (shared laptop).

### D. Pod smoke (ssh -p 32657 root@157.157.221.29, tree /workspace/cb_arm, venv /workspace/venvf15)
- The pod's rl_royale.py, e1_eval.py and search_s0.py hash-match local HEAD. Its decision_options.py is older but has every
  helper cf uses (checked). Copy cf_credit.py, rl_royale.py, e1_eval.py, search_s0.py and the test with scp to `*.tmp`, then
  `mv` (atomic, so a restarting actor of the live run never imports a half-written file). Absent-key behaviour is unchanged,
  so the running brT10 job is unaffected. Do not stop it.
- Config: copy of scratchpad/gauntlet/L74/stepd/cfg/brT10_s107.yaml (pod-only file) + `cf_credit: true` ->
  `.../cfg/brT10_s107_cf.yaml`.
- `ROYALE_RUNTIME=fin15-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 /workspace/venvf15/bin/python -m pipeline.rl_royale
  --config scratchpad/gauntlet/L74/stepd/cfg/brT10_s107_cf.yaml --run smoke_cf --smoke`. Use 1 local actor, no
  remote_actors and no flock. Run the engine tests there too.
- Note: smoke = 2 updates, all inside the critic warm-up (critic_warmup_updates 5), so no policy step uses the rows. The
  DeltaQ stats, the update-0 on-policy assert (which covers the alternative rows) and SMOKE PASS are what it shows.
- Report:
  - triggers / alternatives per match, DeltaQ mean / share positive per kind;
  - fork wall time per match vs the measured 14.6 s/match of the live brT10 run (`actor_s_per_match`).

## Open decisions to put to the owner (not blockers)
1. Scale: real-row A is batch-normalised (std 1), but the raw GAE advantage std in brT10 is ~0.18 (u44-47 log). So
   cf_w = 1 with dq in value units makes the alternative rows ~5x weaker than real rows; cf_w ~5 would match them. Default
   left at 1.0 per the spec.
2. When the policy actually Rockets, the spec's alternatives are only other Rocket placements, so the played Rocket itself
   gets no "vs not rocketing" credit. A `hold` alternative (gate closed) would add that.
3. Cost: once the baseline fork is shown to reproduce the real continuation, it could be dropped and V_base read from the
   real match's row (saves 1 / (1 + n_alt) of the fork time).
4. One continuation per branch, so DeltaQ carries 15 s of sampling noise. With k > 1 the cost grows linearly.
5. Ceilings marked ponytail in code:
   - no pocket territory for siege answers;
   - the Tornado is the only no-building-damage spell;
   - no discounting inside the horizon;
   - crown / habit shaping rewards accrued inside the horizon are not added to DeltaQ (V predicts them after the horizon,
     not within).
