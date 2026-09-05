
### §5cs.44 -- L62e (2026-09-05 17:4x-18:0x UTC, owner order "start the engine training"): FIRST PPO ON THE REAL ENGINE IS RUNNING -- pair launched 17:49:44 UTC from `bc_bias_native_s0.pt` (sha a1273d5d, asserted read-only), control (`--kl_coef 0`, worker PID 31628, direct port 38031) vs KL-to-frozen-init (`--kl_coef 0.3`, PID 54320, port 38032), same seed 41, same ghost-tag sequence, one VM (qemu 54304). **Finding before any policy gradient: the bcA-style critic warm-up (60 critic-only minibatches on the SHARED trunk) moved BOTH arms ~1.15 nats of per-board cell-KL away from the pro init** (control kl_cell 0.95-1.20 at m=48 with raw-logit p99 13.6 vs the init's 6.3; the KL arm recovers to 0.08 within 3 updates once the term enters at update 8). ~12 s/match per arm on an 83-90%-loaded box -> 2,000 matches lands ~00:30-01:30 UTC Sep 6 (not the 2.2 h §5cs.42 extrapolated from the greedy bench). VM left running under the pair.

Source: `scratchpad/gauntlet/L62/engine_ppo.md` (agent, STATUS complete); code `L62/engine_ppo.py` (the file the pair runs is
frozen as `L62/engine_ppo_launched_20260905.py`), launcher `L62/engA_launch.ps1`, PIDs `L62/engA_pids.json`, logs
`L62/engA_{ctrl,kl}_20260905.log`; checkpoints `icebow/data/bench/engA_{ctrl,kl}_m{N}.pt` every 250 + `_latest.pt`
(outside git). (a) unless marked.

**A. What the driver is.** PPONet (PolicyNet + gate + value + value_d; hazard head omitted) loaded exactly as bcA's
`--init` path (`PolicyNet.load_compat`, 0 dropped tensors, gate loaded, VALUE HEAD FRESH -- the init carries c2r's SIM
critic, discarded as bcA did). Rollout 1,024 decisions from ONE `EngineMatchEnv`, episodes span rollouts, tail-caps are
truncations in GAE. Sampling = `masked_logits` semantics, pure policy: no explore floors, no gate prior, no spell
mask/veto, no drills, no distill, no search. Update = GAE(0.994, 0.95), clip 0.2, lr 2.5e-4, ent 0.02 (gate+card),
cell-ent 0.05 -> 0.008 over 3,000 episodes, 4 epochs x 512 minibatch, vf 0.5, grad-norm 0.5, head-norm cap 2.0x,
value warm-up 60 minibatches -- every value read from `bcA_run.yaml`, not `cfg.get` defaults (table in engine_ppo.md
§2.1). KL term = kl_coef x mean over PLAY rows of KL(pi(cell | board, chosen card) || pi_ref), both renormalised over
the card's deployable mask; pi_ref = frozen deep copy of the init, evaluated once per update batched. Rail metric =
pre-tanh cell logits of the sampled card, p99 over the rollout (same quantity `read_ckpt.py` prints). Checkpoint layout
= `train_sim_ppo.save()` + an `engine_ppo` dict; `read_ckpt.py` on `_m0.pt` reproduces the init EXACTLY (v1 15.44/46.61,
v2 15.00/43.51) -- the grading instrument reads these files. Smoke: coef 0 and 0.1, 5 matches each, no NaN.
kl_coef 0.3 chosen from the smoke (|KL term|/|policy loss| 0.025 at update 1, 0.16 at update 2 at coef 0.1) -- (b) a
guess at "about half the policy loss", not a tuned value.

**B. The warm-up drift (the finding).** During the 60 critic-only minibatches the shared trunk is trained on the value
target with no policy loss; the policy heads see a moved trunk. Both arms' kl_cell rose to ~1.15 nats by update 7
before ANY policy gradient. Consequence: the control's starting point for PPO is ~1 nat from the pro prior (bcA had
the same warm-up and ended at 6.47/21.12 -- how much of that fall was warm-up is untested); the KL arm pulls back to
0.08-0.09 within 3 updates of the term entering (kl_term +0.024-0.028 vs pl +0.008-0.014). `engine_ppo.py` now has
`--kl_in_warmup` (default 1); the running pair is `--kl_in_warmup 0` (the agent's kill/relaunch was refused by its
tool sandbox; the lead chose to keep the pair rather than restart: both arms share the drift, kl_coef stays the only
difference, and the drifted control is precisely the bcA-like baseline). Parked arm: trunk-frozen warm-up.

**C. Throughput and box (a, contended -- NOT a benchmark).** Per arm: rollout 27-28 s per 1,024 decisions (policy
4.7 s of it) + update 12 s -> 10-17 s/match (3-4 matches per rollout). Direct transport 38031/38032 (~2 ms/RPC) vs the
adb forward 37031/37032 (~20 ms). RAM: 5.3-5.7 GB free after the VM, **2.2-2.5 GB free after both trainers** (~2 GB WS,
~3 GB private each, not climbing over 10 min) -- below the brief's 6 GB line; recorded, accepted because nothing else
heavy is to be launched (the RE agent is capped at 1 GB). No `--resume`: a stopped arm restarts from m0. Stop runbook
engine_ppo.md §6 (taskkill the 4 PIDs incl. launcher shims 51956/32284, then `worker stop --workers 2 --stop-vm`).

**D. Early state at m=45-48 (descriptive only).** control cum 7W/41L, KL 7W/38L (sampled policy, not greedy; winrate is
not a discriminator); p_play 0.03-0.06 per 0.5-s decision (~17 plays/match, matches the greedy bench's 15.9); pl
+0.008-0.026, vl 0.44-0.68, clip 0.03-0.05; cell_ent control 3.07-3.29 vs KL 3.74; raw_p99 control 13.0-13.6 vs KL
10.5-11.0. Grading at m250/m500 with `L61/read_ckpt.py` (both val sets + rails) is the instrument; expected m250
~18:40 UTC, m500 ~19:30 UTC.

**Not established:** whether the unshaped engine reward is learnable at this cadence (nothing at m=48 says either
way); whether coef 0.3 is the right strength (one value, one seed -- a screen); how much of bcA's fall was warm-up.
Traps: (1) a critic warm-up on a shared trunk IS a policy change -- log KL through warm-up on every future run; (2)
`s/match` under a 2-trainer + crawler + agent load is not comparable with §5cs.42's 1.95 s greedy bench; (3) the agent's
tool sandbox cannot kill processes -- process control stays with the lead (PowerShell `taskkill /PID <pid> /T /F`).
