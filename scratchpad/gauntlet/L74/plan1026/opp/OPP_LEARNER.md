# OPP-LEARN-B: the P2 opponent model as the rl_royale LEARNER (strength calibration, REPORT_opponents 3 step 4.3)

Goal: RL the human-like opponent (timing-head GenModel, plan1026/opp checkpoints) for STRENGTH while it stays human-like:
a FIXED pull toward its own imitation init, timing + ability heads FROZEN, win-only reward, partners = the bot pool on our
deck + the human model vs itself on census deck pairs. Part A (fast-loop timing seats) = OPP-LEARN-A; part C (routing this
through the fast loop) comes after both.

## What was built (all opt-in; a gate model / absent key = byte-identical)
| piece | where | how it is switched on |
|---|---|---|
| (1) learner-seat recording | e1_eval `th_record` (called by `timing_decide_batch` under cfg record), `timing_cfg` (record allowed only with `th_learner`), `_record` / `_traj_arrays` (deck_gid / ctx_* ids = `opp_row_keys`, labels th_j / th_ab) | rl_royale `actor_cfg` sets `th_learner` on rollout cfgs when the init is a timing-head model |
| rows | every slot-start / drawn-tick decision is a traj row; lp_card / lp_cell on play rows (mask = the seat's real allowed slots after held plays / Mirror cost, float64 of the float32 heads at T); lp_gate 0, gate_sampled False everywhere; th_j = tick-in-slot drawn at a slot start (-1 none, -2 = the play row at a drawn tick, -3 game over); th_ab = tick an ability press was queued (-1 none); p_gate = sigmoid(hazard) | - |
| (2) `freeze_heads: [timing, ability]` | rl_royale `freeze_heads` (FREEZE_HEADS = timing_head.* / ability_head.*): requires_grad False -> no gradient, Adam never steps them; the smoke checks them bit-identical | config key; absent / null = nothing (hash unchanged) |
| (3) card / cell-only PPO + KL | `policy_terms`: a gate-less model gets x = 0 (never gate-sampled), so lp_gate = 0, KL_gate = 0, gate entropy None; the loss is card / cell PPO + KL on play rows. No new term: the existing loss on these rows IS card / cell only | automatic for a timing-head init |
| (4) fixed pull to the init | NO new key: `beta0 = beta_min = beta_max = lambda` (adapt_beta clamps to lambda every update) with `kl_ref_refresh_every` absent (ref = the frozen init forever). Note: Guards' "beta at clamp" KL stop is then always armed = a plain KL_cell > kl_cell_stop for stop_consecutive updates stop | config |
| (5) opponent-architecture learner | Learner: `self.th` (init has opp.timing) -> `_load_net` via model_gen.load_model (timing / ability heads, deck encoder, ctx tokens, memory); saves + league snapshots carry opp / opp_sim / memory (`opp_learner_meta`); actors rebuild it (`base["opp_init"]`) with GenPolicy(opp_sim); `policy_terms` builds GenPolicy without opp_sim (heads_t only; rows carry the ids); startup / loop skip pro agreement + the ghost screen (both decode a gate model) | automatic; refuses: league off, decide_every != 10, no opp_sim, posture / ability_head / tau_phase / branch / kl_ref_gate / kl_ref_card / pipelining / cf_credit |
| partners | config only: `league_mix {init: 0.4, s1: 0.6}` + `league_specialist: CLXIII` (the s1 slot always plays icebow = the bot on our deck), `league_learner_icebow_share 0` (learner decks = census). A multi-bot pool on our decks needs a decks file the league can read: league_decks drops icebow by design, so `league_exploiters` cannot carry icebow today (b: use the s1 slot, or a follow-up key) | `learner/opp_learner_smoke.yaml` |

Advantage: `advantage: match_loo` (win-only, per-match LOO within the matchup's G repeats; no critic: the opponent's value
head is untrained). T = 1.0 (the imitation temperature; timing_decide_batch and policy_terms both read cfg T).

Known ceiling (ponytail, b, untested): the shared trunk trains, so the frozen heads' OUTPUTS (hazard, tick, ability
hazard) can drift with it even though their weights do not. Measure: the hazard on fixed recorded rows, u0 vs uN.

## Tests (laptop, a)
`icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_opp_learner.py` -> 6 passed:
recorded rows + labels + ctx ids on the fake self-play env; policy_terms recompute of lp_card / lp_cell < 1e-5 (lp_gate 0);
frozen heads grad None + bit-identical after 3 Adam steps while card_q trains (KL_card + KL_cell > 0, KL_gate 0);
adapt_beta fixed at lambda; freeze_heads absent / refusals; config_sha(absent) == config_sha(null); actor_cfg / timing_cfg
unchanged without the opp init. Existing: test_timing_head_decode + test_league 42 passed, 1 skipped, 2 failed -- the same
2 (TestSelfPlayCounters, x_bow vs x-bow names) fail on the unchanged tree too (a: pre-existing).

## STATUS (OPP-LEARN-B, 2026-10-28)
- Code: private worktree, rebased onto 4dd9911 (LEARNER-SCALE MemRowCache landed; one conflict in policy_terms resolved: my GenPolicy line + their gen_rows), committed as hunks only; the merged tree re-smoked (opplearn_opp3: SMOKE PASS, W16 shas = opp2's). Others'
  uncommitted MemRowCache hunks in the shared rl_royale.py are not mine and stay uncommitted).
- Pod smoke (33903 CPUs 200-203, lead OK; crforge fe364ceb + tables 16.635.3 copied from 32657; trees /workspace/opplearn/cb_base
  + cb; script learner/pod_smoke.sh TREE RUN CONFIG; logs /workspace/opplearn/logs/RUN.log): see the Smoke section below.
- Pod smoke RESULTS (a, 33903 CPUs 200-203, fe364ceb + 16.635.3, laptop copies .foreman/scratch/a2/opplearn/logs/):
  | run | tree | config | config sha | W16 u0000 batch / weights | W16 u0001 batch / weights | result |
  |---|---|---|---|---|---|---|
  | opplearn_base2 | 17d006b | succ48_x_s101 | b5e2a2bbafef | b43dd869 / 3e07cff4 | 70b4b263 / d9fd3a96 | SMOKE PASS |
  | opplearn_new2 | 17d006b + this change | succ48_x_s101 | b5e2a2bbafef | b43dd869 / 3e07cff4 | 70b4b263 / d9fd3a96 | SMOKE PASS |
  | opplearn_opp2 | + this change | learner/opp_learner_smoke.yaml (init v0 opp_m10_s0_sim.pt) | dc28331e27cc | f5b6bd67 / b3eaf2ad | 6ecc1abc / 7ac7ec43 | SMOKE PASS |
  base vs new: w16_batch / w16_matches u0000-u0001 files byte-identical (cmp); config sha = the historical b5e2a2bbafef.
  opp learner: freeze_heads 4 tensors (7,062 params) bit-identical + not trainable after 2 updates; beta 0.1 -> 0.1 both
  updates; update-0 on-policy check passed (KL g/c/x 0 / 1e-4 / 1e-4); u0000 213 play rows, 8 matches, ppm 8.08; u0001 KL
  card / cell 1e-4 / 3e-4; u0000 reload state_dict identical; resume check all True. Pod tests: 17 passed (test_opp_learner
  + test_timing_head_decode). pyflakes: only the 2 pre-existing e1_eval warnings (same on the base tree).
  Finding (a; n = 8, so the rate is noise): the s1 partner (CLXIII) won 2 of 8 vs v0 because league opponents sample at
  league_opp_T, unset = the LEARNER's T = 1.0, so CLXIII played at T 1. One league_opp_T covers BOTH partner kinds (the frozen
  human init must stay at T 1). Needed before any strength number is read (b): a per-partner decode (the s1 slot's own T, or
  league_exploiters with an icebow deck pool -- league_decks drops icebow by design).
  Smoke fixes found on the way (in this commit): train_gen --opp checkpoints carry "step", not "epoch" (Learner init_meta);
  policy_terms built GenPolicy(model, ()) which refuses an opponent model without opp_sim.
- Codex: OPPLEARNB_1 (medium): trees + overlay + symlinks done, BLOCKED at the tables copy (ssh -A to 32657: publickey
  denied); I relayed the tables through the laptop (28 files, combined sha256 45b357f8 equal on both pods) and ran pyflakes /
  tests / smokes myself (/workspace/opplearn/chain.sh). (c) Codex reported every copy verified but pod_smoke.sh was missing.
- Restart: `ssh -p 33903 ... 'cd /workspace/opplearn && (setsid nohup bash chain.sh < /dev/null > chain.out 2>&1 &)'` (rename the
  RUN names in chain.sh first: rl_royale refuses an existing run dir).
- Next: (0) a per-partner decode for the bot slot (finding above); (1) the v1 checkpoint as the init once level A/B pass (attach_sim first); (2) the trunk-drift monitor above;
  (3) part C (fast loop) after OPP-LEARN-A; (4) a real calibration run: E 64, G 4, lambda sweep {0.03, 0.1, 0.3} on a GPU learner.
