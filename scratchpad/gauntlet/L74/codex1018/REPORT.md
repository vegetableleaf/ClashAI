# Codex worker report - 2026-10-18

Pod observation cut: 2026-10-18 14:11:53 Eastern Daylight Time (2026-10-18T18:11:53.200132+00:00); replacement local workers were checked separately at the time shown below.

No completed candidate clears the required positive lower paired CI on both standard and fresh seeds.
The first next action is for the still-running executor to repair its D1 smoke failure: `TypeError: drive() got an unexpected keyword argument on_frame`. D1 started after the completed cue evaluation released CPU capacity and exited 1 at 18:11:11 UTC. Continue the existing Stage 2, C3 ability and FIN13 jobs, then qualify the pro-imitation step-d comparisons on the final runtime. Keep the reward optional and evidence-gated. Report candidates to the owner before any live decision. Codex did not deploy, switch the live checkpoint, or start a live run.

The reference is **ICEBOW Mark CLIII: LEVELS**, grafted checkpoint `edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952`. The dated HEAD handover reported **+4.4 pp SIM but 47.8% live over 46 matches**. That SIM gain has not transferred to live. Every new performance number below is SIM.

## Job status

The original step-d executor (PID 10448), round-7 closer (26708), and combo relay (41080) are **failed**, not done. The first two failed on an API workspace-scoping error; the launcher wrote exit 0 despite failure. Claude fixed the header in dc5363e and relaunched them at 12:14 EDT. Codex did not restart either worker. The relay was absent and its last log, 08:14 EDT, described an older failed attempt; Codex replaced its collection function for this ticket. PID reuse is not treated as recovery.

| Replacement local worker | Status at inventory | Evidence |
|---|---|---|
| round-7 closer | alive; root PID 58888 | 14 processes in its current tree; checked 2026-10-18T18:12:22.5837258Z |
| step-d executor | alive; root PID 54792 | 11 processes in its current tree; checked 2026-10-18T18:12:22.5837258Z |

The executor ticket now specifies a **very loose, card-choice-only KL leash anchored to the pro-imitation IL-cue policy**, with the CLIII-anchor twin optional. The correction is logged in stepd/STATUS.md. For this leash correction, Codex changed ticket text and status only; the recovered executor independently implemented and committed its trainer in 3f72766 after real pod PPO-update smokes.

The executor reports the two D2a weighted no-cue imitation models copied with SHA verification to `C:/Users/benpe/pod_backup_weekend/stepd/d2/`. Codex independently observed D2A_DONE and the 17:39:04 UTC completion log. Those imitation validation scores are not candidate win-rate measurements or a controlled estimate of the weighting effect. D1/arm/reference waiters belong to the executor and use completion/claim checks; their current presence is recorded below and in job_snapshot.json.

| Pod | Job status at cut | Disposition |
|---|---|---|
| 15617 (216.81.151.5) | Completed round-7 results copied; no tracked parity compute at cut; closer capacity retained | KEEP (owner) |
| 19899 (64.247.206.76) | Completed round-7 results copied; RUNNING: v7_r7b_hr, FIN13 | KEEP (owner) |
| 13396 (64.247.206.76) | Stage 2 ALIVE: training; update 85/130; 0 evaluation rows; step-d arm waiter present | KEEP (owner) |
| 14009 (64.247.206.76) | cue_ab2 and CLIII reference DONE and copied; c3_ab training done; evaluation running; max_updates 65 reached; 310 evaluation rows; executor step-d waiter staged | KEEP (owner) |
| 30988 (64.247.206.80) | CLIII/cue paired evaluation DONE and copied (5,760 games); D2a DONE; D1 smoke FAILED at 18:11:11 UTC (on_frame API mismatch); executor recovery pending | Retain: executor repair, D1/D2 and subsequent step-d work |
| 19834 (64.247.206.120) | Stage 2 ALIVE: training; update 92/130; 0 evaluation rows; step-d arm waiter present | Retain: active Stage 2 and queued step-d |
| 10757 (64.247.206.79) | c3_ctl DONE: 1,920 games and checkpoints copied; executor work active: stepd_smoke.sh | Retain; released capacity handed to executor |
| 19400 (64.247.206.79) | combo_ctl_c3 original DONE and copied; added paired follow-ups DONE and copied | Retain for remaining delegable step-d/final-runtime work |
| 34210 (216.81.245.71) | combo_rew_c3 original DONE and copied; added paired follow-ups DONE and copied; executor stepd_ctrl_nos2 waiter now staged | Retain for remaining delegable step-d/final-runtime work |
| 38758 (216.81.245.71) | SSH refused; stopped in the dated HEAD handover, not independently API-confirmed | No lifecycle action |
| 23363 (81.27.69.177) | SSH refused; stopped in the dated HEAD handover, not independently API-confirmed | No lifecycle action |
| 29286 (216.81.245.71) | SSH refused; stopped in the dated HEAD handover, not independently API-confirmed | No lifecycle action |
| 23408 (81.27.69.177) | SSH refused; stopped in the dated HEAD handover, not independently API-confirmed | No lifecycle action |

All nine reachable pods have KEEP. No pod was stopped and no stop timer was armed. The four owner keep ports are 15617, 19899, 13396 and 14009. Temporary pods remain available while step-d and final-runtime work remain delegable. Before later shutdown, finish and verify copying, confirm the remaining queue, and use only L74/deploy/stop_pod.sh. Do not stop a shared worker by process name.

## Verified collection

The private backup root is `C:/Users/benpe/pod_backup_weekend/codex1018/`: **48 verified archives, 20,274 unique pod/path files**. The linked [backup index](backup_index.json) lists every receipt and source root. Each copy verifies the archive SHA-256, safely extracts only manifest members, and verifies every file SHA-256 and byte count. Git-Bash `hash *path` and Linux `hash  path` normalize before comparison. Repeated snapshots are counted once in the unique-file total.

Full finished cue/reference, C3 control, combo control/reward and round-7 outputs include their available checkpoints and logs. Stage 2 smoke results are copied; unfinished Stage 2 final models and C3 ability evaluations are explicitly pending. Incomplete old parity scratch attempts are not reported as completed results. The first failed parity extraction has no COPY_VERIFIED receipt and is excluded. Raw rows, checkpoint binaries and archives remain in the private backup directory.

## Candidate results

All complete results, original archived rates, CLIII reference rates and behavior intervals are in [CANDIDATE_RESULTS.md](CANDIDATE_RESULTS.md) and [candidate_scores.json](candidate_scores.json). The compact table below gives candidate minus CLIII in percentage points with 95% paired CIs.

| Context | Candidate | Standard: delta pp [95% CI] | Fresh: delta pp [95% CI] | Two-set gate |
|---|---|---|---|---|
| cue_same_code | cue_ab2_sample | +5.21 [+1.67, +8.85] | +1.25 [-2.19, +4.69] | FAIL |
| cue_same_code | cue_ab2 | +4.69 [+1.15, +8.23] | +2.08 [-1.36, +5.52] | FAIL |
| c3_same_code | c3_ab | pending; no complete paired result | pending; no complete paired result | pending |
| c3_same_code | c3_ctl | +1.15 [-2.40, +4.69] | +1.67 [-1.77, +5.00] | FAIL |
| combo_off | combo_ctl_c3 | -1.88 [-5.52, +1.67] | -0.73 [-4.06, +2.60] | FAIL |
| combo_off | combo_rew_c3 | -0.52 [-4.06, +2.92] | -1.35 [-4.79, +2.08] | FAIL |
| combo_offc | combo_ctl_c3 | -1.88 [-5.52, +1.67] | -0.83 [-4.27, +2.50] | FAIL |
| combo_offc | combo_rew_c3 | -0.73 [-4.27, +2.71] | -1.46 [-4.90, +2.08] | FAIL |

Standard seeds are 741200+742000; fresh seeds are 743000+744000, with 960 paired games per set. The completed Codex follow-ups add 13,440 SIM games across the cue and combo pods. Existing gap.py runs all games on pods. Existing live_cmp.py / paired_drift uses 10,000 paired bootstrap draws within census and learner side; draws count as non-wins. Win-rate intervals use Wilson; behavior deltas use 2,000 paired draws. Intervals are nominal, without a multiple-comparison correction. Pooled results are descriptive and cannot override a failed individual seed-set gate.

The original cue archive and C3 reference used different evaluation source. Codex therefore re-ran CLIII, sampled cue and greedy cue under one frozen C3 source on 30988. That isolated environment uses PyTorch 2.8.0; original C3/combo environments use 2.11.0. Original and rerun rows are kept separate. Combo offc preserves the existing combo-rule evaluation setting; off is the historical promotion protocol. No live rule was introduced.

The 21-path public evaluation-source check (including matching absent optional paths) agrees within each paired source group and remained unchanged on all five pods at 2026-10-18T18:10:14.233685+00:00. This is a bounded allowlist check, not a claim that every source file or software version is identical across all experiments.

Sampled cue illustrates the gating issue: standard +5.21 pp [1.67, 8.85], fresh +1.25 pp [-2.19, 4.69], pooled +3.23 pp [0.73, 5.68]. It fails the fresh gate despite a positive pooled interval. Standard accepted ability presses fall from 1.718 to 0.930 per game, delta -0.787 [-0.903, -0.682]; presses with a recorded freeze fall from 1.172 to 0.698, delta -0.474 [-0.564, -0.385]. The candidate still uses the ability, but less often. Its training lineage also differs from the CLIII-initialized C3 experiment.

C3 control lowers Rocket usage on both sets: -0.105 per game [-0.171, -0.041] standard and -0.085 [-0.147, -0.025] fresh. Counts of spells, presses and frozen catalogue elixir are behavior observations, not causal quality measures. Original combo output lacks the counterfactual telemetry needed to establish that each Tornado was necessary.

The supplementary paired [reward-versus-control table](COMBO_CONTROL_RESULTS.md) separates reward attribution from the CLIII gate. A standard-seed gain over control alone would not establish a standard-and-fresh gain over CLIII.

## Round 7

[ROUND7_RESULTS.md](ROUND7_RESULTS.md) contains **27 paired arm readouts and 51 original result-directory tables**, with their CIs. Paired intervals resample whole matches (2,000 draws), splicing complete affected-match results over FIN12 using the existing strict-fight/card-agreement definitions. Different fight denominators are retained and documented. Correlated alternatives must not have their gains added together.

The recovered closer independently reproduced H-VOLLEY + H-CUBE-DATE v2, H-SNAP-BACK, S-PULSE-TWICE, S-EK-HITTICK and S-HOLD-REACH. Harness fixes landed in e15b284; the fork changes landed in the coordinator-owned clashbot36 tree and passed its 1,960-test gate with 3 ignored. These are the closer's changes, not changes made by this report ticket. Redundant H-FIXED-AIM v2 and H-IW-PRESS-DATE alternatives were not separately landed.

The volley/cube joint improves upgraded raw agreement from 0.92503 to 0.92677, **+0.174 pp [0.015, 0.342]**, with 32 fights up and 12 down. Its raw 95% interval is **[0.91921, 0.93407]**. H-SNAP-BACK is **+0.100 pp [0.001, 0.199]**; S-EK-HITTICK is **+0.045 pp [-0.023, 0.117]**; S-HOLD-REACH is **+0.037 pp [-0.017, 0.103]**. A mechanistic land verdict is separate from a statistically clear aggregate gain.

The required overall lower CI of 0.975 is still unmet. The combined FIN13 qualification remains running at this observation cut; no complete combined score is inferred from its individual patch results. The older orphan hold-reach verification may also still be running; current process/result evidence is in the pod snapshot.

## Handoff and verification

Have the alive executor repair the D1 on_frame API mismatch and pass its smoke before resuming the full drive. Codex recorded the exact error in stepd/STATUS.md without restarting the worker or editing its implementation. Continue the existing Stage 2 A/B and C3 ability chains without restarting them, and let the closer finish FIN13. Preserve the corrected pro-imitation card-only leash. Apply the same standard-and-fresh CLIII gate on the final runtime before treating an optional feature as an improvement. Keep reward off unless its required evidence clears the agreed bar.

Codex verified inventory coverage, corrected ticket wording, backup receipts, paired-score completeness for completed candidates, public source identities, and unchanged live-control/stale-handoff hashes. The new HANDOFF section is built from git show HEAD:HANDOFF.md and staged as a blob through hash-object/update-index; the stale working file is preserved. Publication uses explicit paths, a staged-count check, and both a quiet rg secret scan and independent pattern checks. The concise Discord summary is sent only after the report commit is confirmed on main.

Upstream was fetched without changing an experiment runtime. Existing RoyaleSim/RoyaleGym/RoyaleLearn/RoyaleViser checkouts were 68/252/93/27 commits behind their tracked upstream branches. Those are checkout gaps, not a claim that all commits arrived today.
