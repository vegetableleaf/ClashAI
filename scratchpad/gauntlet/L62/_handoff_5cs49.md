
### §5cs.49 -- L62j (2026-09-05 20:1x-20:4x UTC): **engB m250 -- THE GATE PRIOR HELD THE GATE ALIVE IN BOTH ARMS, THE KL ARM'S CELL HEADS ARE AT THE INIT'S LEVEL, THE CONTROL'S HAVE COLLAPSED FASTER THAN engA's -- AND UNDER THE DEPLOY RULE (`sigmoid > 0.25`) BOTH ARMS STILL PLAY ALMOST NOTHING, BECAUSE A PRO-CALIBRATED GATE CANNOT BE GREEDY-THRESHOLDED AT 0.25.** Plus a RETRACTION of the lead's own alarm criterion from §5cs.47 ("frac_gt_tau < 0.02 = falsified"): a gate that matches the pro rate NEVER crosses 0.25 in single elixir, so that criterion would have flagged success as failure. The diagnostic is `p_gate` vs `gp_target` and the p50/p90/max spread, not the tau crossing.

Instruments this loop (all by the lead): `L61/read_ckpt.py` (cell agreement, conditional on a play, deterministic);
`L62/gate_probe.py` (sim, greedy tau 0.25, 3 matches, records p(play) every decision); `clashrl.cli policy-stats`
(sim, greedy tau 0.25, 16 matches, seed 4242, `--size 432`); the engB train logs' GATE readout (engine boards, SAMPLED
policy). Raw outputs `scratchpad/gauntlet/L62/grade_engB_m250/`. Checkpoints `icebow/data/bench/engB_{ctrl,kl}_m250.pt`
(written 20:18-20:19 UTC). (a) unless marked.

**A. Cell-head grade (read_ckpt; conditional on a play -- says nothing about play rate, per §5cs.46 B).**

| checkpoint | v1 top1/top5 (n 1004) | v2 top1/top5 (n 1333) | rails frac>8 / p99 |
| --- | --- | --- | --- |
| init `bc_bias_native_s0` (carried from §5cs.44) | 15.44 / 46.61 | 15.00 / 43.51 | -- / 6.3 |
| engA control m250 (carried, §5cs.45; NO gate prior) | 11.25 / 32.97 | 10.95 / 33.53 | 0.026 / 9.6 |
| engA KL m253 (carried, §5cs.45; NO gate prior) | 16.73 / 44.02 | 16.28 / 42.69 | 0.015 / 8.9 |
| **engB control m250** (kl 0, gate prior 2.0) | **7.47 / 26.79** | **6.83 / 26.86** | 0.027 / 9.8 |
| **engB KL m250** (kl 0.3, gate prior 2.0) | **16.33 / 44.02** | **14.25 / 42.76** | 0.019 / 9.8 |

Arm gap at m250: **+8.86 top-1 / +17.23 top-5** (v1), +7.42 / +15.90 (v2) -- larger than engA's +5.5 / +11.1, and
entirely because the CONTROL fell further (7.47 vs 11.25), not because the KL arm rose. Reading (b): with the gate
prior holding play rate up, the control's policy gradient gets ~4x more play rows per rollout than engA's control did
(p_play 0.05-0.08 vs 0.03-0.06 and falling), so the unshaped-reward drift of the cell heads runs faster -- kl_cell at
m290 is 0.56-0.75 nats (engA control reached ~1.2 by m422). The KL arm sits within noise of the init on top-1
(+0.89 v1 / -0.75 v2) and slightly under on top-5 (-2.59 / -0.75): the per-board KL at 0.3 is doing what it is for --
holding the cell heads at the pro prior (kl_cell 0.04-0.05 nats at m290) -- and NOT (yet) improving on it.
Per-card, the control's losses are again the low-frequency cards (skeletons 1.7, the_log 0.7, knight 0.0 top-1 on v1
vs the KL arm's 9.4 / 23.1 / 11.1). One seed, one coefficient; m500 (~21:15 UTC) is the next point.

**B. The gate is ALIVE in both arms (the thing engB was launched to test) -- but the deploy rule still hides it.**

Engine boards, sampled, from the train logs at m=284-290 (one rollout each, n 875-997 unmasked rows):

| arm | p_gate mean | p90 | frac_gt_tau | gp_target (pro rate on the same rows) | gp_ce | p_play (sampled) |
| --- | --- | --- | --- | --- | --- | --- |
| engB control | 0.058-0.080 | 0.098-0.150 | 0.000-0.012 | 0.090-0.111 | 0.30-0.35 | 0.049-0.067 |
| engB KL | 0.075-0.085 | 0.128-0.157 | 0.000-0.009 | 0.103-0.113 | 0.33-0.35 | 0.068-0.082 |

Sim boards, greedy tau 0.25, `gate_probe.py` (the deploy rule sim-view uses):

| checkpoint | decisions | plays | p(play) mean / p50 / p90 / max | frac > 0.25 | affordable cards |
| --- | --- | --- | --- | --- | --- |
| engA KL m253 (carried, §5cs.46) | 710 | 0 | 0.155 / -- / **0.2325 / 0.2326** | 0.000 | 3.98 |
| engB control m250 | 710 | **0** | 0.161 / 0.152 / 0.201 / 0.245 | 0.000 | 3.98 |
| engB KL m250 | 1089 | **63** | 0.191 / 0.194 / 0.241 / 0.318 | 0.058 | 3.72 |

Two readings. (1) **Not collapsed:** engA's KL arm emitted a constant (p90 = max to four decimals); engB's arms have a
p50->max spread of 0.09 (control) and 0.12 (KL) -- the gate still depends on the board. On the engine, p_gate tracks
gp_target at ~65-80% of the pro rate with gp_ce stable at 0.30-0.35 since update ~6 (a); the prior is holding it
where it was fitted to hold it. (2) **Still catatonic under the rule:** greedy tau 0.25 gives the control 0 plays in
710 decisions and `policy-stats` reads **0.1 plays/match** (control) and **1.5 plays/match** (KL) over 16 matches --
while `gate_probe` reads 21 plays/match for the SAME KL checkpoint under the SAME rule on 3 other matches. That
20x swing between two seed sets of one instrument is the finding, not noise to average: tau 0.25 sits at the gate's
~p92-p95, so the play count is decided by which boards happen to nudge over the line, i.e. by the threshold, not by
the policy. (Do not compare the sim-probe means 0.16-0.19 with the engine-log means 0.06-0.08: different boards,
different opponent, different elixir profile -- two instruments.)

**C. Why this is the deploy rule's bug and not the gate's (c against the §5cs.47 alarm; a on every number).**
`config/gate_prior.json` (519 replays, 23,620 plays, dt 0.6): pro mean P(play) per window **0.111**; the LARGEST
single-elixir entry is 0.203 (9 elixir); double-elixir at 9 is 0.446; only **8.14%** of 212,265 pro windows exceed
0.25. A gate trained to that table is BELOW 0.25 on essentially every single-elixir board by construction -- so
`sigmoid(g1-g0) > 0.25`, which sim-view, policy-stats, gate_probe and the sim trainer's greedy bench all apply, renders
any calibrated policy as "never plays". The BC init only looked active (36.2 plays/match, §5cs.46) because its gate was
MIScalibrated high -- the live-view agent's shadow run of the BC init on engine boards measured p(play) mean **0.47**
with **87%** of decisions above 0.25 (`ext/engine_view/live_selftest_full.json`, 527 decisions) -- four times the pro
rate. So: the owner's sim-view observation ("extremely inactive") is real for engB too, and it is now the viewer's
rule that is wrong, not the policy. **RETRACTION:** the §5cs.47 relaunch note set "frac_gt_tau below 0.02 = the prior
failed". Wrong criterion -- a working prior produces exactly that number. Diagnostic from now on: `p_gate` within ~0.7-
1.3x of `gp_target`, p50/p90/max NOT coincident, gp_ce flat. engB passes all three at m290.

**D. What the rule should be (owner-facing; NOT changed this loop -- doctrine, and sim-view/policy-stats/gate_probe/
live_view/play.py all read it).** Options, each with the number it implies: (1) **sample the gate** (what training
does): expected 0.05-0.08 plays per 0.5-s decision on the engine = ~20-30 plays/match, pro ghosts 45.1 (§5cs.41 D,
a different instrument); (2) **lower tau to the calibrated level** (~0.10, near the pro mean): greedy, deterministic,
but converts a probability into a step function -- at 9 elixir single (p 0.20) it plays every decision it can, at 3
elixir (p 0.06) never, which is not the pro behaviour either (b); (3) keep 0.25 -> catatonic. The lead's
recommendation is (1) for viewing/grading with a fixed seed, and the greedy-cell metric kept for the cell heads only.
`live_view.py` already defaults to `--rule sample` with `--rule threshold --gate_tau` as the option, so the new viewer
does not inherit the bug; `sim_view._policy_agent`, `policy-stats` (cli.py:336-380) and `gate_probe.py` do.

**Not established.** Whether the KL arm's cell heads move ABOVE the init by m2000 (m250 says "held", not "improved");
the across-seed band of any number in A (one seed); the true play rate of these checkpoints under sampling on the
ENGINE with a fresh seed (the train-log p_play is the on-policy rollout, which is the same policy but not a clean
measurement); whether the control's faster cell drift is caused by the higher play rate (b -- the natural test is the
engA/engB control pair at equal play counts, not available). Trap: **any instrument that applies
`ppo_gate_threshold` must print the play rate next to the agreement number** -- policy-stats does (0.1 / 1.5); the
§5cs.45 grade did not, and that is how a catatonic checkpoint was called "better".
