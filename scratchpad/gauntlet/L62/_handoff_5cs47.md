
### §5cs.47 -- L62h (2026-09-05 19:2x-19:5x UTC): **engB PAIR RELAUNCHED WITH THE PRO GATE PRIOR IN BOTH ARMS AND THE GATE IS ALIVE** -- control (kl 0, worker PID 71976, port 38031) vs KL-to-frozen-init 0.3 (PID 46364, 38032), `--gate_prior_coef 2.0` in BOTH so `--kl_coef` is still the only between-arm variable; at update 1 both arms report **p_gate 0.2157, p90 0.3815, frac_gt_tau 0.3208, gp_ce 0.5050, gp_target 0.0784** -- byte-identical between arms, which is the determinism check passing (same init, seed 41, ghost sequence; they can only diverge through kl_coef). Against the killed engA KL arm's frac_gt_tau **0.0000**. Three launch failures fixed on the way, all mine or the launcher's, none the engine's.

Source: `scratchpad/gauntlet/L62/engine_ppo_v2.md` (agent, STATUS complete) for the patch and its offline checks; the
launch, the recovery and the readouts measured by the lead. Logs `L62/engB_{ctrl,kl}_20260905.log`, launcher
`engB_launch.ps1`, preflight `engB_preflight.py`, checkpoints `icebow/data/bench/engB_{ctrl,kl}_m{N}.pt` (outside git).
(a) unless marked.

**A. The patch (agent, 17 exact-string edits to `engine_ppo.py`, 521 -> 627 lines).** `loss += coef *
mean(-(p*log pi_play + (1-p)*log pi_wait))` over rows where the PLAY logit is unmasked (the sim's exact exclusion
`gq_m[:,1] > _NEG*0.5`), target `p = gate_prior.json[phase][elixir bucket]` read BEFORE `env.step()` (which advances
tick and elixir); card and cell heads untouched -- verified by gradient check: `gate.weight |grad| 33.93` with
`card_head.grad None` and `cell_conv[-1].grad None`. Phase from tick: double from 120 s, triple from 240 s (b -- the
4.5 s pre-battle countdown may offset this; identical in both arms). Unit check of the lookup 27/27 PASS
(single/3 0.062606, single/9 0.203290, double/9 0.446343; bucket edges at 2.999 -> 2, 2.9999995 -> 3).
`--gate_prior_coef 0.0` proven byte-for-byte equal to the pre-patch file (18/18 shared log fields identical, all 33
parameter tensors `torch.equal` after 2 updates at kl 0.3). New monitoring on every update line, existing field names
unchanged: `p_gate` mean/p90, `frac_gt_tau`, `gp_ce`, `gp_target`, `gp_rows`. `_m0` reproduces the init EXACTLY
(v1 15.44/46.61, v2 15.00/43.51; all 27 model + all gate tensors `torch.equal` to `bc_bias_native_s0.pt`).

**B. Calibration the brief did not have (agent, (a) from the table itself).** A gate that MATCHES the prior does NOT
sit above tau: over gate_prior.json's own 212,265 windows the mean target is 0.1109 and only **8.14%** exceed
tau = 0.25 -- the largest single-elixir entry in the whole table is 0.2033, below tau. So a healthy `frac_gt_tau`
should FALL from the launch value and settle near **0.05-0.10**, not the BC init's sim-measured 0.22; the alarm line
stays "heading for <= 0.02". What the prior actually restores is STATE DEPENDENCE -- targets span 0.010-0.459, so a
gate that fits them cannot be the constant engA collapsed to. Second finding, deliberately UNFIXED (one change per
experiment): the table is fitted at **dt 0.6 s** while engine_ppo decides every **0.5 s** (`decision_ticks 10`), i.e.
~20% more plays/second than pros; identical in both arms, so it does not confound the contrast. Proposal
`--decision_ticks 12` parked.

**C. The three launch failures (all fixable, none the engine's fault; recorded because each is a trap).**
1. **My `taskkill /T` on the engA trainers killed the two IN-GUEST WORKER SERVICES with them** (`worker status` ->
   `services [false, false]` with `vm_ready true`). The agent could not recover -- its one `worker start` attempt was
   refused by its tool sandbox -- so it correctly stopped and reported instead of guessing. Recovered by the lead with
   the existing `L62/_boot.ps1`; both slots `ready: true` at 19:30 UTC, VM never restarted.
   **TRAP: tree-killing a trainer takes the engine service down; restart it before the next launch.**
2. The launcher's preflight passed a multi-line here-string to `python -c`; Windows argument passing mangled it into a
   syntax error. Moved to `engB_preflight.py`.
3. The preflight then reported "SLOTS DOWN: IndexError" -- it called `NativeRoyaleEnv.observe()` with NO BATTLE
   CONSTRUCTED. The service was healthy the whole time. Rewritten to do what the trainer does (`EngineMatchEnv(port)`
   + `reset(index=0)`); both slots return `obs (96,64,12) tick 90`. **TRAP: a liveness probe that does not exercise
   the caller's own path can report a false death.**

**D. State at launch.** Both arms `--matches 2000 --seed 41 --rollout 1024 --save_every 250 --value_warmup 60
--kl_in_warmup 0 --gate_prior_coef 2.0`; banner confirms the table (519 replays, 23,620 plays, dt 0.6). RSS ~2.0 GB
each, free RAM 3.7 GB, guarded processes verified alive after launch (crawler 29444 + 53824, owner's uvicorn 63608,
qemu 54304). At update 1: pl +0.0370, vl 0.6677, ent 0.272, cell_ent 3.704, kl_cell 0.1195, raw_p99 6.33,
p_play 0.099, s/match 6.76 (uncontended by a second trainer only for that first rollout).

**Not established.** Whether the prior HOLDS the gate open past m=50 (that is the whole point of the run -- the first
real check is frac_gt_tau at m30-50, then m250); whether the collapse would also be prevented at a lower coef; the
tick -> phase mapping; the 0.6 s / 0.5 s dt mismatch's effect on learned play rate; anything about pro agreement
(no engB checkpoint beyond m0 exists yet). engA's checkpoints are retained as the counterfactual.
