
### §5cs.18 -- hogeq brought to parity with icebow (2026-09-04, L48d; owner order) + the "cheap cards" observation measured: it is the GATE, not the card head

**Owner order (verbatim):** "while we wait, can you update hogeq again with the relevant changes again so that it's up to
date with icebow? i've noticed that the hogeq model tends to play cheaper cards more often which is a similar failure
mode to icebow." Second parity pass after §5bc (2f9cd8e, 2026-09-02). Everything icebow landed between 2f9cd8e and
6cca0a0 was triaged into: byte-copy (shared files), hand-port (declared-different files), or icebow-only (not ported,
reason given). c2r kept running throughout (hogeq edits touch nothing c2r imports; 17 python processes before/after).

**Byte-copied (12 shared files, `parity_check.py --strict` from BOTH decks: 72 identical / 15 declared different /
0 unexpected, PARITY OK):** `clock.py, controller.py, detect_obs.py, interactions.py, replay_bc.py, reward.py,
sim/drill_env.py, sim/engine.py` (incl. the 6cca0a0 crown fix -- hogeq's crowns() now reads real CR too),
`sim/scenarios.py, sim/view.py` + new `sim/aggro_drills.py, sim/aggro_oracle.py`.

**Hand-ported into the declared-different files (each verified by import + the suite below):**
- `sim/env.py`: `observation.lock_aware_targets` (default false), `enemy_troop_min_age()`, the `_interaction_state()`
  helper feeding `interaction_vector(hints=)` / `predictive_channels(hints=)`.
- `sim/opponents.py`: `ScriptedBot(attack_floor=)` + `sim.bot_attack_floor` (training bots only, via `adaptive`).
- `sim/remote_pool.py`: `"eage"` in the worker payload.
- `train_sim_ppo.py`: schema-2 gate prior (`sim.ppo_gate_prior_pressure_s`, 3-D table, PRESSURE print, `eage` roll
  column). The lines added since 2f9cd8e are byte-identical to icebow's (checked by diffing the two added-line sets).
- `env.py` (live): `_SIM_TOWERS_BOARD` anchors + `canonical_render(anchors=, alive=)`, `env.spell_cast_delay_s`,
  `_impact_time(is_log=)`, lead-before-judge in `_wheels_spell_aim`, `env.opp_mem_slot5` switch, stop_requested guard
  on the play-again tap.
- `train_rl.py`: `train.rl_gate_tau` greedy rule (WAIT iff sigmoid(Q_play - Q_wait) <= tau) with the legacy rule when
  the key is absent.
- `play.py`: `opp_mem_slot5` switch, cast-delay lead for the rocket path, and a **NEW Log corridor assist block**
  (`log_corridor_cell` on tracks led by the cast delay, flyers excluded via the KB) -- icebow's play.py has had it since
  5bc.3, hogeq's never did although the train-rl env had it. **This is a live-path behaviour change for hogeq** (the
  Log is hogeq's card, not icebow's); hogeq has no live history, so it is (b) untested on a real screen. Same flag as
  §5bc.3: the owner should know before a hogeq live session.
- `config/config.yaml`: `observation.lock_aware_targets: false`, `train.rl_gate_tau: 0.25`, `env.opp_mem_slot5:
  opp_estimate`, `env.spell_cast_delay_s: 1.0`, `sim.bot_attack_floor: 0.0`, `sim.aggro_drills: false` -- icebow's
  VALUES, read back through `Config.load()`. `ppo_gate_prior_pressure_s` is NOT in icebow's config.yaml either (only
  `c2r_run.yaml:2102`), so hogeq inherits the code default 0.0 exactly as icebow does.
- tools: `gate_prior.py` (schema 2), `gate_prior_probe.py`, `latency_stage_timer.py`, `ppo_watchdog.py` (the `_Drift`
  detector + per-label floor; hogeq's copy had NO drift detector at all -- it was behind at 5bc already, tools are
  informational in the parity check), `real_run_gates.py` (`--run <tag>`). `replay_priors.py` was already identical.
- tests copied and green on hogeq: `test_aggro_oracle, test_bot_attack_floor, test_lock_aware_targets, test_gate_prior`.

**NOT ported, and why:** `nado_retarget_reach_fix` / `_tower_in_reach` (hogeq has no `_register_nado`), xbow
`_defensive_w` overtime ramp + alive-princess bow credit + `env.xbow_defense_ramp_s` (no bow), the icebow-only tests
`test_defensive_ramp, test_nado_retarget_reach, test_aggro_drills` (copied speculatively, 8 failures all of the form
"knight_guards_the_bow not in the hogeq pool" / ImportError on the ramp -- removed; not regressions), `config/
gate_prior_p6.json` (icebow's table is icebow's corpus; see next).

**hogeq's OWN schema-2 pressure table fitted (a):** `tools/gate_prior.py --pressure-s 6 --out config/gate_prior_p6.json`
on hogeq's crawl (595 replays, 30,258 plays, dt 0.6, reconstruction-under-cost 2.8%). Blend byte-identical to the
schema-1 `gate_prior.json`. Single elixir at 5/6/7 elixir: QUIET 4.6/4.3/5.5% vs PRESSURE 8.8/8.8/9.7% (62%/38% of
windows). Icebow's pros (5bx): quiet 2.4/3.0/2.9 vs pressure 8.6/6.8/6.6. Hog pros play ~1.7x more often when quiet
than bow pros -- expected for a 2.9 deck -- and the same under pressure. `sim.ppo_gate_prior_coef` stays 0.0 in hogeq's
config (off); the table is there for the run that turns it on.

**hogeq suite:** `python -m unittest discover` 1,330 tests, 310 s: 1,322 OK / 64 skipped / the 8 icebow-only failures
above (files then removed). Baseline at 5bc was 1,288 OK / 64 skipped; the +34 are the copied deck-neutral tests.

**The "cheap cards" observation, measured (a) -- `tools/gate_prior_probe.py data/policy_sim_ppo_best.pt` (hogeq's
best, m=2000, 2026-08-17; the watchdog's SAMPLED-gate instrument, 6 envs x 400 steps, seeds 0/1/2):**

| seed | elixir mean | >=6 share | P(play) on affordable rows | plays/row | mean cost of a play | plays at <3 elixir |
|---|---|---|---|---|---|---|
| 0 | 1.82 | 0.17% | 0.488 | 13.3% | 2.05 | 181 of 318 (57%) |
| 1 | 1.88 | 0.25% | 0.415 | 12.8% | 2.05 | 178 of 306 (58%) |
| 2 | 1.83 | 0.17% | 0.445 | 13.1% | 2.02 | 175 of 315 (56%) |

Pro reference from the SAME corpus (28,858 blue in-deck plays, `scratchpad/gauntlet/L48/_pro_costs.py`): mean cost
**2.61**; shares ice_spirit 15.9 / skeletons 15.4 / firecracker 14.6 / mighty_miner 13.1 / log 11.9 / hog 11.9 /
tesla 10.4 / earthquake 6.9%; <=2-cost 43.1%, 4-cost 35.3%. So pros ALSO play the 1-costs most (a cycle deck rotates),
and the owner's observation is still (a) confirmed: the policy's mean play cost is 2.02-2.05 vs 2.61, its plays at <3
elixir are skeletons/ice_spirit/log at cost 1.3, and **hog_rider is in the top-4 of NO elixir bucket on any seed**
(pros 11.9%). Bucket rows: only 2% of rows are at >=4 elixir; P(play) at 1/2/3 elixir 0.56/0.54/0.49 vs pros
0.048/0.059/0.075 (7-11x).

**Mechanism -- the card head is NOT the cause (a, `--force-bank 4`, seed 0):** suppress every play below 4 elixir and
let the SAME checkpoint act: elixir mean 1.82 -> 2.99, and the card head picks **mighty_miner 36 / hog_rider 31 /
tesla 30 / ice_spirit 26** on the 211 plays at 3-5 elixir; mean play cost **2.96** (ABOVE the pros' 2.61). Given the
elixir, the card head reaches for the 4-costs at once. What is broken is the gate: it opens on ~60% of rows at 1-3
elixir, so the bank never reaches 4 and the only affordable cards are the 1-2-costs. "Plays cheaper cards" is the
SYMPTOM of "never waits" -- the identical failure to icebow's 18k run (§5bf: >=6 share 2% -> 0.02%; here 0.2% at
m=2000). One seed for the counterfactual, but the move (hog 0 -> 31 of 211, cost 2.05 -> 2.96) is far outside the
3-seed spread of the unforced read (2.02-2.05).

**Does NOT establish:** what a GREEDY hogeq policy does (this is the sampled instrument; at tau 0.25 a gate at
p 0.5-0.6 opens even more, so greedy is not better); which hogeq checkpoint the owner watched (best is m=2000 from
2026-08-17; `policy_sim_ppo.pt` 08-20 and `policy_rl*.pt` exist -- (b) re-run the probe on whichever one the owner
means); that the gate prior fixes it on hogeq (b -- icebow's c2r is the first test of that on any deck; a hogeq
run with `ppo_gate_prior_coef > 0` + `gate_prior_p6.json` + `ppo_gate_prior_pressure_s 6.0` is the mirror arm, after
c2r's m30k verdict says whether the mechanism holds); the live Log assist on a real screen (b).

**Traps found:** (1) copying icebow's tests wholesale into hogeq costs a 310-s suite run to discover the bow-specific
ones -- grep the test for `x_bow|_register_nado|xbow_defense` first. (2) The probe's elixir-bucket "affordable" column
is misleading on a drained policy: 29.5% affordable rows is not "nothing to play" but "already spent it". (3) The
gate_prior_probe reports top-4 cards per bucket only; hog's absence from every top-4 is the finding, the exact share
needs the `--json` picks (not dumped per card -- add if needed).

Files: hogeq/{config/config.yaml, config/gate_prior_p6.json, src/clashrl/..., tests/..., tools/...} as listed;
`scratchpad/gauntlet/L48/{_port_trainer.py, _port_liveenv.py, _port_play.py, _port_config.py, _pro_costs.py,
hogeq_probe_best.txt, hogeq_probe_best_s{0,1,2}.json, hogeq_probe_best_fb4.txt, hogeq_probe_best_fb4_s0.json,
hogeq_suite.txt}`.
