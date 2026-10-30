# OPP-PUSH: opponent model to the pilot bar (owner goal 2026-10-30; PLAN.md Pillar 2; no-discard)

Bar: CLXIII SIM win vs the opponent 30-50% on the D3 block (480 games, seed 741200, tables 16.635.3, crforge 5e8089a4, CLXIII on
its live stack); v6 B-live RMS <= 0.20; siege facts inside the v6 margins (lock .47 +- .05, zero-lock .12 +- .06,
P(lock|fail) .36 +- .07). Grades: (a) measured (number + source), (b) plausible untested, (c) contradicted.

## STATUS (2026-10-30 ~22:00 UTC, account 3) -- RESTART POINT
Pods: A = `ssh -i ~/.ssh/runpod_clashbot -p 40088 root@213.192.2.118` (3090, quota 31.1 CPUs, EPYC 7H12); B = `-p 40008
root@213.192.2.110` (3090, 31.1 CPUs, EPYC 7763). Both booted by boot_opp_pod.sh: BOOT OK (all 7 tree digests = 33903's), copy
293 / 298 s, keys removed from 33903 (grep count 0). Fast-loop tree on both: `/workspace/mfl/cbm` = origin/main 6ebf9ad
(pipeline + pilot/loop + obsid) over links to cb2 (mfl_tree.sh), facade build `jbuild_mfl` inside it.
- RUNNING (mine):
  - Pod A `oplc_ftR_l0003_live_s1f` = the live-partner recipe at seed 1 on the FAST LOOP (origin/main tree), CPUs 0-21, GPU 0.
    PIDs 5480 (bash) -> 5483 (timeout 48 h) -> 5484 (fastloop.py). Log `/workspace/oplm/logs/oplc_ftR_l0003_live_s1f.out`;
    ckpts `/workspace/mfl/cbm/icebow/data/bench/rl_royale/oplc_ftR_l0003_live_s1f/` (every 10, cap 400). Stop: `kill 5484`.
    Launch / resume (+ `--resume`): `HOST=213.192.2.118 TREE=/workspace/mfl/cbm JB=jbuild_mfl bash learner/launch_arm.sh 40088 oplc_ftR_l0003_live_s1f 0-21 /workspace/venvf16/bin/python scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml beta0=0.003 beta_min=0.003 beta_max=0.003 seed=1`
  - Laptop D3 loop for it: WMI bash PID 21612 running the copy `C:/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/5a62561c-4ecc-475a-8651-5d396102522c/scratchpad/arm_d3_s1f.sh`
    (= arm_d3_card.sh sha 53edd967) `HOST=213.192.2.118 ... oplc_ftR_l0003_live_s1f 40088 40088 22-30 8 0040 .. 0400`, log
    `.foreman/scratch/opp_push/d3_s1f.log` (D3 on pod A's spare CPUs, 8 workers, ~1.5-2.5 h per block). Stop: touch STOP_ARM_D3
    in that dir or Stop-Process 21612.
  - Pod B: style S0b = B-HF closed loop of ftR (both seats ftR, T 1, 3,761 HF test-split tier-A deck pairs, 5e8089a4 /
    16.635.3, 28 workers): `bhf_pod.sh ftR /workspace/oplm/opp_ft_s0_R_sim.pt 1.0`, PIDs 4782 (bash) -> 4825 (pairs.py), log
    `/workspace/style/bhf_ftR.out`, rows `/workspace/style/bhf_ftR/` (~2.6 h, done ~00:30 UTC). Resumable: rerun the same command.
    Jobs rebuilt by `mk_mvm_jobs.py` on 33903 (`/workspace/opppush/mvm_jobs4000.jsonl`, 3,761 rows, sha 6b799f6b; the original
    4,000-row file sha 1b0afd19 died with 32657). Score after: fetch rows to `.foreman/scratch/opp_push/rows/bhf_ftR`, then
    `card.py score --name ftR_bhf --sim <ftR D3 rows> --hf-sim .foreman/scratch/opp_push/rows/bhf_ftR --no-c --no-d`.
- E1 (a): pod B (EPYC 7763, Zen 3) replayed oplc_ftR_l0003_s1_u0040's D3 block: 390 / 480, sorted (end_tick, outcome) list
  IDENTICAL to 33903's (digest 9deb687d), 20 min at 28 workers. D3 blocks are game-identical across these pods' CPUs.
- Replicate u0 (a): W/L 41/215 (.160) at seed 1 vs seed 0's 28/228 (.109); GPU 14.3 GB of 24.
- LEAD 10-30 ~22:10 UTC: arm 2 goes on POD B's GPU (fast loop), started only AFTER the style B-HF run finishes (~00:30 UTC; never
  overlap them on pod B's 31 CPUs); its lever = the u40 read (gae + critic warm-up if training win is within ~3 pp of D3, else
  lever 4). Re-imitation plan REPLACED by the closed-loop diagnostic (calibration / sealed blocks stay untouched).
- RUN TYPES: oplc_ftR_l0003_live = PRODUCTION on cb2 (33903); oplc_ftR_l0003_live_s1f = FAST LOOP on origin/main (pod A).
- Exactness (a): E2 production on pod A, seed 0, u0: W/L 28/228 and w16_batch_u0000.json sha 32a2ae21 = 33903's live run
  (bit-identical; roll 649 s vs 855 s). E3 fast loop (origin/main tree) seed 0: u0 W/L 28/228, rows 6,555, KL / clip identical;
  per-field batch shas: 47 of 50 fields identical, only lp_card / lp_cell / lp_old differ (GPU vs CPU forward, ~1e-6 per
  FASTLOOP-FIX); so u1 diverges numerically (prod 30/226 rows 6,612 KL c/x .0090/.0145; fast 29/227 rows 6,651 .0091/.0154).
  Reading: fast = production in every decision at u0; past u0 they are different-but-equivalent samples (float noise grows
  into different draws), far below a seed's effect. Speed (a): fast u0 roll 201 s + upd 36 s, u1 170 + 34 s vs production on
  the same pod 649 + 36 s (~3x).
- Codex dispatches: none.
- LEAD DECISIONS (10-30 ~21:00 UTC): (1) pods = 2 single RTX 3090 pods (ports to come; 24 GB = one production arm per pod).
  (2) arm 2 at u40: lever 3 (`advantage: gae` + critic warm-up, win-only reward) APPROVED if transfer is fixed (training win
  within ~3 pp of D3), smoke first; else lever 4. tower_phat for opponents stays OFF (reward change = owner). (3) STYLE is
  OPP-PUSH's (no-discard): timing-head re-imitation on CLXIII-era human rows (v6 newest block held out) as its own track on the
  second 3090 pod + the our_half / pocket_share exploit check. Success marks reported vs BOTH G's best block (26.7%) and G's
  u80-u240 mean (23.3%).

## Bootstrap a new pod (laptop; ~10 GB pod to pod, never through the laptop)
1. `bash scratchpad/gauntlet/L74/plan1026/opp/learner/boot_opp_pod.sh NEWPORT` -> must end `BOOT OK` (digests of venvf16, cb2,
   cbe, icebow_data, crforge_main, tables, opp_ckpt equal on 33903 and the new pod). Prints CPUs / cgroup limits / GPUs / CPU
   model first; aborts under 30 GB free. The one-off key is removed from 33903 on exit (check: `grep -c opp-push-boot
   ~/.ssh/authorized_keys` on 33903 = 0). `boot_opp_pod.sh` also copies the s1 u40 checkpoint for check E1.
2. Exactness checks (both detached on the new pod; ~15-30 min):
   - E1 eval: `ssh ... -p NP root@157.157.221.29 'cd /workspace/oplm/d3 && LIB=/workspace/crforge_main/5e8089a4/plain CB=/workspace/oplm/cbe PY=/workspace/venvf16/bin/python CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 G2_ON=on OPP_T=1.0 WORKERS=30 CPUS=0-63 OPP_CKPT=/workspace/oplm/d3/ck/oplc_ftR_l0003_s1_u0040.pt setsid nohup bash /workspace/oplm/cbe/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh bootchk_s1u40 /workspace/oplm/d3/rows/bootchk_s1u40 741200 > /workspace/oplm/d3/bootchk_s1u40.out 2>&1 < /dev/null &'`
     Pass = CLXIII W 390 / 480 (33903, lead_d3.log 13:55) and the same sorted (end_tick, outcome) list as 33903's rows.
   - E2 train: `GPU=0 bash scratchpad/gauntlet/L74/plan1026/opp/learner/launch_arm_prod.sh NP bootchk_live_s0 CPUS 20 scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml beta0=0.003 beta_min=0.003 beta_max=0.003 max_updates=1`
     Pass = u0 W/L 28/228 and `w16_batch_u0000.json` sha = 33903's oplc_ftR_l0003_live one.
   (b) A different CPU model (33903 = AMD EPYC 7702, AVX2) can change torch CPU numerics and fail E1 / E2 with a perfect copy:
   then the new pod's D3 blocks are valid 480-game samples but not game-paired with 33903's; say so in every comparison.
3. Arms on the new pod: production `launch_arm_prod.sh NP RUN CPUS 20 CFG ...` (20 CPU actors ~ 22 CPUs; learner RESERVES 13 GB,
   peak 8.5 GB: one arm per 24 GB card, `GPU=1` for a second card, or two per card with `ALLOC=expandable_segments:True` (b));
   D3 per arm: a scratch COPY of `arm_d3_card.sh` (new name each) `RUN NP NP CPUS 30 0040 0080 ...`, started by WMI on the laptop.
   Fast loop (after FASTLOOP-FIX passes): copy FASTLOOP-FIX's loop tree too (not in boot_opp_pod.sh yet).

## Lever list (ranked by evidence; each = one change; how it keeps human-likeness)
Reference (a): G (beta .003) D3 opponent win u40-u240 16.2 / 23.8 / 23.1 / 26.7 / 21.9 (288 games) / 21.2%: u160 is its best of
six blocks (SE ~2 pp per block); mean u80-u240 23.3%. Seed 1 u40 18.7%. C (beta .01) u80-u320 18.3-25.6%.
Live-partner run, training win vs the live-stack partner (a, 33903 log): u0-9 .141, u10-19 .153, u20-23 .170 (sampled-partner
G family: .157 / .163 / .217 at u0-9 / 10-19 / 20-29).

| # | lever | evidence | expected effect | style |
|---|---|---|---|---|
| 1 | live-stack partner (RUNNING) + seed replicate (s1) | (a) D3 = .053 + .51 x training win, 24 ckpts, r .78; W7 R4 precedent | (b) D3 tracks training at slope ~1; opp win ~30-35% by u160 | pull unchanged |
| 2 | fast loop for the same recipe (FASTLOOP-FIX) | (b) 880 -> ~160-240 s/update (sampled-partner numbers) | time only: the bar is ~1,100 updates away at C's slowing rate (PLATEAU, b) = 11 days production, ~2.5 days fast | none |
| 3 | `advantage: gae` + critic warm-up (shaping none: reward stays win-only) | (b) update looks noise-dominated: no critic, mixed groups .44-.66, 3.3x lr does not speed training (PLATEAU); pilot critic EV .92 | faster training per update | pull unchanged; drift per update may grow -> quick card each D3 |
| 3b | then `shaping: tower_phat` (potential-based) | (b) as 3 | lower variance again | changes the training REWARD: lead / owner OK first |
| 4 | full live stack + D3 census decks for the partner (own_effects, afford_ticks 23, follow-up taps; decks_live_eval) | (b) the residual train / eval differences PLATEAU lists | only if the u40 / u80 transfer gap stays > 3 pp | none |
| 5 | 512 matches / update | (b); our model: 128 vs 1,024 not different per update (SCALE 7f, a) | per update maybe; 2x wall per update | none |
| 6 | timing head in PPO, th_anchor 1 | arm D (th_anchor 10) no D3 gain: 82.3 / 85.8 / 78.8 / 80.4 vs B 84.6 / 80.4 / 79.8 / 81.5 (a); class mix = +0.04 of the +0.28 lock gap (SIEGE, a) | small | RISK: timing stats are 0.67 of the RMS^2 sum (below) |
| 7 | eval-only opp_T .5 | cell T .25 (ct25): CLXIII -5.6 pp but RMS .31 -> .39 (a) | same trade as ct25 expected | worse |
| 8 | bigger model | (c)-leaning: ftR is ~11.3M params (45 MB fp32) = curve v0 knee; m10 imitation not stronger (89.1-89.4%) nor more human (RMS .32-.34) (a); training win still rising at u320 (a) | none now | - |
| 9 | per-archetype weighting | (c) as a bottleneck: G's gain over ftR is spread (other 35%, hog 20%, weak_other 15%, golem 11% of the net; WHERE_G, a) | none | - |
| 10 | reweighting the same human data | (c) for strength: ftx3 / ftx10 / ftd3 flat on strength + siege (SIEGE, a); ftd3 RMS .31 -> .28 | style only | small gain |

### The style bar is not addressed by any strength arm (a), so it needs its own lever
- ftR RMS .30 (480-game quick card) / .31 (1,920); G u80 .28, G u160 .30; best ever .28 (ftd3). No opponent has reached .20.
- RL re-mixes the error instead of shrinking it (G u160 vs ftR, quick cards): better push_mean -.46 -> -.16, bridge +.36 -> -.03,
  spell_depth +.64 -> +.35; worse our_half +.07 -> +.65, pocket_share +.23 -> +.63, troop_depth +.01 -> -.40, opp_el -.07 -> -.27.
  A stronger pull does not hold it: our_half at u80 = .19 (beta .1) / .32 (.03) / .26 (.003).
- RMS .20 = sum of d^2 <= 1.00 over 25 stats; G u160 = 2.31: timing stats (react_lift +.44, gap_p10 -.48, react_s -.28, ppm_1x
  -.29, ...) 0.67, nearly unmoved in every arm (timing head frozen; ftR -> G u160: react_lift +.51 -> +.44, gap_p10 -.61 -> -.48);
  placement stats 1.33. Both groups must drop; no running arm trains timing.
- Style levers (all (b)): S1 init / pull anchor = ftd3 (RMS .28 at equal strength, a) -- small; S2 the timing head re-imitated on
  CLXIII-era human rows (the only lever on the 0.67; the v6 newest block must stay held out); S3 check whether our_half /
  pocket_share growth is a SIM exploit of CLXIII (lock / damage per pocket play, SIM vs live).
- Success-mark note: G u160 (26.7%) is G's best block; comparing a new arm's single block to it biases against the arm. Compare to
  G's u80-u240 mean (23.3%) as well.

### Style track S0 (2026-10-30 ~21:40 UTC, laptop, `style_s0.py`; sealed block never read): the error is NOT human drift
Data constraint first (a): CLXIII-era human rows exist only in the calibration block (10-25 08:49 .. 10-28 09:06 = the v6 newest
block, the scoring reference) and the sealed block (>= 10-28 09:06, level D only; live_split.json, frozen 10-28). So "re-imitate
on CLXIII-era rows with the newest block held out" has no data unless the owner re-splits. S0 asks whether it is needed at all.
Unweighted Cohen d per stat, humans pre-CLXIII (10-19 .. 10-24, older Marks, n 877 matches; = live_train's span) vs CLXIII-era
(calibration, n 867), and ftR / G u160 (480 games each, 16.635.3, 5e8089a4) against each era (a):

| stat | drift (CLXIII - pre humans) | ftR - pre | ftR - CLXIII | G u160 - pre | G u160 - CLXIII |
|---|---|---|---|---|---|
| react_lift | +0.01 | +0.50 | +0.49 | +0.43 | +0.43 |
| gap_p10 | -0.04 | -0.68 | -0.58 | -0.53 | -0.45 |
| react_s | -0.11 | -0.37 | -0.25 | -0.38 | -0.27 |
| ppm_1x | +0.05 | -0.30 | -0.34 | -0.27 | -0.32 |
| spell_depth | +0.08 | +0.72 | +0.66 | +0.43 | +0.37 |
| push_mean | +0.07 | -0.40 | -0.45 | -0.09 | -0.16 |
| our_half | -0.08 | -0.00 | +0.08 | +0.56 | +0.66 |
| pocket_share | -0.13 | +0.13 | +0.26 | +0.53 | +0.68 |
(all 25 stats: drift |d| <= 0.13; own_half / bridge / troop_depth are masked before 10-25 by the reader rule.)
Reading: (a) human drift between the two eras is <= 0.13 d on every stat, and the model's errors are the same size against the
humans it imitated as against CLXIII-era humans. (c) CONTRADICTED: "the timing error comes from imitating older humans" --
re-imitating the timing head on CLXIII-era rows would target a difference of ~0.05 d. The style error is a closed-loop property
(per decision the timing head is calibrated: SIEGE test 1, slot ECE 0.5-0.75 pp, a). Next style probes (b, ranked):
- S0b instrument / environment: the same stats on HF human-vs-human data vs the model in B-HF closed loop (pairs.py --mvm, both
  seats the model; no live reader, no CLXIII). If react_lift / gap_p10 errors persist there, it is the model's closed-loop
  dynamics; if they vanish, it is the live instrument or CLXIII's SIM behaviour (CLXIII plays 1.79 vs live 2.48 plays in the
  10 s after its X-Bow, SIEGE, a).
- S1 our_half / pocket_share: RL-made (ftR .00 / .13 vs pre humans -> G .56 / .53). Exploit check: CLXIII tower damage per
  opponent pocket / our-half play, SIM (G rows, --record-board) vs live humans (calibration block, analysis only).

## Rounds (ledger)
(none yet)
