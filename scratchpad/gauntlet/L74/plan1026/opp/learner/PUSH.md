# OPP-PUSH: opponent model to the pilot bar (owner goal 2026-10-30; PLAN.md Pillar 2; no-discard)

Bar: CLXIII SIM win vs the opponent 30-50% on the D3 block (480 games, seed 741200, tables 16.635.3, crforge 5e8089a4, CLXIII on
its live stack); v6 B-live RMS <= 0.20; siege facts inside the v6 margins (lock .47 +- .05, zero-lock .12 +- .06,
P(lock|fail) .36 +- .07). Grades: (a) measured (number + source), (b) plausible untested, (c) contradicted.

## STATUS (2026-10-31 ~11:00 UTC, account 3) -- RESTART POINT
**KEY FINDING (a, style track S0c): CLXIII plays 17% FEWER cards in SIM than live -- 9.3 vs 11.2 plays / min (median gap
between its plays 4.7 s SIM vs 3.8 s live; ftR D3 480 games vs the CLXIII calibration block 856).** The opponent's reaction
stats (react_lift, react_s) are measured against OUR plays, and the same ftR scores B-live RMS .30 against live humans vs CLXIII
but RMS .20 against HF humans with no CLXIII in the loop (react_lift +.50 -> -.08). So most of the B-live style error is the
CLXIII-in-SIM environment (or the live reader), not the opponent model; the opponent cannot reach RMS .20 on B-live while
CLXIII's SIM pace is off (b: mechanism; size not yet measured -- next: a pace-matched B-live).
- LEAD 10-31 ~11:00 UTC: (1) arm 2 gae ACCEPTED. (2) pod A -> ARM 3 = the large-batch recipe as ONE change (minibatch = the
  whole update batch with micro_batch 256 accumulation + lr from an equal-KL probe: one update ~0.02 KL, no step > 0.03),
  after s1f's u160 + u200 D3s. Yaml `opp_learner_calib_live_lb.yaml` (minibatch 16384, micro_batch 256), probe `lb_probe.sh`.
  (3) Usage high: milestone reports only, Codex for babysitting, no runs beyond the three arms.
Pods: A = `ssh -i ~/.ssh/runpod_clashbot -p 40088 root@213.192.2.118` (3090, quota 31.1 CPUs, EPYC 7H12); B = `-p 40008
root@213.192.2.110` (3090, 31.1 CPUs, EPYC 7763). Both booted by boot_opp_pod.sh (BOOT OK). Fast-loop trees: pods A / B
`/workspace/mfl/cbm`, 33903 `/workspace/mfl/cbopp`; all = origin/main 6ebf9ad (pipeline + pilot/loop + obsid) over links to cb2
(mfl_tree.sh), facade build `jbuild_mfl` inside (pods' copy has CRLF from a laptop archive -- harmless for fresh runs, E3 exact
at u0; 33903's is LF, built with `git -c core.autocrlf=false archive`, needed for --resume of a cb2 run).
- RUNNING (mine, 2026-10-31 ~12:20 UTC), all FAST LOOP, D3 loops ON THE PODS (pod_d3_loop.sh; two laptop WMI loops died silently):
  - ARM 3 pod A `oplc_ftR_l0003_live_lb` = live recipe at seed 1 (paired with s1f) + LARGE-BATCH (opp_learner_calib_live_lb.yaml:
    minibatch 16384 = the whole update, micro_batch 256) + lr 1.4e-4 from the equal-KL probe (lb_probe.sh, fresh Adam, update 0,
    same batch: lr 2e-4 -> step 1 KL .0228 / update .0385; 5e-4 -> step 1 .128 (stopped); 1.4e-4 -> step 1 .0114 / update .0193;
    base mb-256 lr 3e-5 update 0 = .0094). Batch + lr = ONE recipe change. CPUs 0-21, PIDs 9509 -> 9512 -> 9513 (stop: kill
    9513, then its producers: `pgrep -P 9513` captured first -- killed fast loops leave orphaned producers holding the GPU).
    Resume: `HOST=213.192.2.118 TREE=/workspace/mfl/cbm JB=jbuild_mfl bash learner/launch_arm.sh 40088 oplc_ftR_l0003_live_lb 0-21 /workspace/venvf16/bin/python scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live_lb.yaml beta0=0.003 beta_min=0.003 beta_max=0.003 seed=1 lr=1.4e-4 --resume`
    D3: pod A PID 10485 `pod_d3_loop.sh oplc_ftR_l0003_live_lb /workspace/mfl/cbm /workspace/oplm/cbe 22-30 8 0040..0400`, log
    `/workspace/oplm/d3/oplc_ftR_l0003_live_lb.d3.log` (~2 h per block at 8 workers).
  - ARM 2 pod B `oplc_ftR_l0003_live_gae` (gae + pre-fit critic; details below). D3: pod B PID 9869 (same loop, 22-30, 8 workers),
    log `/workspace/oplm/d3/oplc_ftR_l0003_live_gae.d3.log`.
  - ARM 4 33903 `oplc_ftR_l0003_d3env` (PUSH-70 item A: D3 conditions; opp_learner_calib_live_d3env.yaml, seed 0, smoke PASS:
    "895 census decks"). Started by `/workspace/opppush/switch_arm4.sh switch` (PID 1612451, log /workspace/oplm/logs/switch_arm4.out):
    waits for oplc_ftR_l0003_live_u0120.pt, then stops the seed-0 live run (fastloop 1602464 + its children captured first) and
    launches arm 4 on CPUs 240-255,180-185 + GPU (log /workspace/oplm/logs/oplc_ftR_l0003_d3env.out, ckpts
    /workspace/mfl/cbopp/icebow/data/bench/rl_royale/oplc_ftR_l0003_d3env/). D3: 33903 PID 1612691 (`pod_d3_loop.sh ...
    /workspace/mfl/cbopp /workspace/opp/cb 32-145 28`), log `/workspace/oplm/d3/oplc_ftR_l0003_d3env.d3.log`.
    The lead's laptop D3 loop for oplc_ftR_l0003_live will wait forever after u120 (that run stops): the lead stops it.
  - Quick cards: run by hand at milestones (laptop, card.py --no-c --no-d on rows fetched from /workspace/oplm/d3/rows/NAME).
- STOPPED: s1f at u225 (11:25 UTC) for arm 3; the seed-0 live run at u120 (automatic, for arm 4).
- Seed-0 live run history (for the record): moved from production at u85 (10:22 UTC): production stopped by PID 81255 after u84's
  latest.pt, its 20 orphaned actors 81286-81305 stopped by exact PID, fast-loop resume accepted ("changed config n_actors 20 -> 1").
  Run dirs are REAL in /workspace/mfl/cbopp with cb2's old paths as symlinks to them (rl_royale refuses to write through a link
  that leaves its tree: the first resume crashed at the u85 save, nothing written). launch_arm.sh truncated its log (u0-u84 rows
  stay in train_log.jsonl). u85 on the fast loop: 214 + 25 s vs production 1,114 + 26 s.
  - Pod B `oplc_ftR_l0003_live_gae` = ARM 2 (lever 3): opp_learner_calib_live_gae.yaml, seed 0, init `/workspace/oplm/opp_ftR_vfit12.pt`
    (sha 47afe8cc) = ftR with a PRE-FIT value head: run gae_vfit1 (12 critic-only updates at lr 1e-3, vf_trunk_grad false;
    ev .02 -> .38-.47, V 0 -> -0.77, advantage mean -0.45 -> 0.00); same_policy.py: 220 of 222 tensors identical to ftR (max |d|
    0), only value_head.{weight,bias} differ. CPUs 0-21, PIDs 8955 -> 8958 -> 8959 (stop `kill 8959`), log
    `/workspace/oplm/logs/oplc_ftR_l0003_live_gae.out`. Resume: `HOST=213.192.2.110 TREE=/workspace/mfl/cbm JB=jbuild_mfl bash learner/launch_arm.sh 40008 oplc_ftR_l0003_live_gae 0-21 /workspace/venvf16/bin/python scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live_gae.yaml beta0=0.003 beta_min=0.003 beta_max=0.003 init=/workspace/oplm/opp_ftR_vfit12.pt --resume`
    Why the pre-fit (a): the first gae smoke (gae_smoke2, warm-up 1, lr 3e-5) left V at +-0.002, ev .02-.05 and advantages
    UNCENTERED (mean -0.36 to -0.55: the opponent loses ~85%), which would push every taken action down -- not launched as is.
- Done on pod B: style S0b B-HF run (bhf_pod.sh ftR, 3,741 of 3,761 games); E1.
- E1 (a): pod B (EPYC 7763) replayed oplc_ftR_l0003_s1_u0040's D3 block: 390 / 480, game-identical to 33903's (digest 9deb687d).
- LEAD 10-30 ~22:10 UTC: arm 2 goes on POD B's GPU (fast loop), started only AFTER the style B-HF run finishes (~00:30 UTC; never
  overlap them on pod B's 31 CPUs); its lever = the u40 read (gae + critic warm-up if training win is within ~3 pp of D3, else
  lever 4). Re-imitation plan REPLACED by the closed-loop diagnostic (calibration / sealed blocks stay untouched).
- RUN TYPES: oplc_ftR_l0003_live = PRODUCTION on cb2 u0-u84, FAST LOOP (cbopp) u85-u120; every other run = FAST LOOP.
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

## PUSH-70 plan (owner 10-31): opponent win 70% (CLXIII 30%) at B-live RMS <= .20 -- ranked by evidence, then cost
Where we stand (a): every RL recipe so far tops out at D3 opponent win ~22% with single-block spikes to ~27% (G 26.7% u160, s1f
26.9% u160); the strength it finds is deep pushing (pocket_share +.99, our_half +.73 at s1f u80) with NO siege gain (lock .71-.75
vs live .47). 70% is ~3x today's level; no single lever below has evidence of that size, so the plan stacks them.
Context (b): live humans beat live CLXIII far more often than any SIM opponent does (ftR 11%, best arm ~27%), and SIM CLXIII plays
17% fewer cards than live (S0c) -- part of the strength gap may be the SIM environment too; RECON-7 (pace parity) lands -> re-score
ftR / G u160 / s1f u160 strength AND style on the parity build before reading any arm against 70%.

| # | item | evidence | expected effect | how style is protected | cost | status |
|---|---|---|---|---|---|---|
| A | train under D3's conditions: live census decks (decks_live_eval, 895 decks) + CLXIII Log 15 | (a) the train-vs-D3 gap reopens to +10 pp by u200 (s1f train .319, D3 .219) although the partner plays D3's stack | D3 -> the training level (~+5-10 pp, b) | style-neutral (no objective change) | config; smoke PASS | **ARM 4 (33903), starts at the seed-0 run's u120** |
| B | large-batch PPO (minibatch = whole batch, micro 256, lr 1.4e-4 by equal-KL probe) | (a) for OUR model: pilot2_L learned (+6.9 pp) where mb-256 drifted (-15 pp); opponent: s1f training plateaus at ~.30 after u100 | faster / cleaner training per update (b) | same pull (beta .003) | running | ARM 3 (pod A) |
| C | gae + pre-fit critic (win-only reward) | (b) noise-dominated update (no critic; mixed groups .44-.66) | lower-variance advantages (b) | same pull; vf_trunk_grad false | running | ARM 2 (pod B) |
| D | decode-time search over the policy's OWN top-k (fork the engine per decision, k ~4 candidates, short rollouts with the policy, pick by tower-HP / P_hat) | (b) search is the classic way to add strength without training drift; fork machinery exists (cf_credit / SIM forks in the fast loop) | the largest potential toward 70% (b, untested) | every played action is one the imitation model already rates top-k, at the timing head's own times (timing untouched); measure the drift on the quick card | HIGH: a new opponent decode path in gap.py + ~k x the D3 cost; first an eval-only prototype on ftR | design next |
| E | style-constrained RL: a stronger pull on the CELL head only (placement), card head free | (a) the RL style cost is placement (pocket / our_half / troop_depth / own_half carry RMS .30 -> .41); (a) one beta for card+cell did not hold placement (our_half u80 .19 / .32 / .26 at beta .1 / .03 / .003) | keeps placement near ftR while card choice learns; strength may fall if it lives in placement | the cell pull IS the protection | MEDIUM: opt-in trainer key (beta per head) + smoke | after A / B / C read |
| F | league / population partners (CLXIII + CLXV LARGEBATCH + pilot2 checkpoints, each on its live stack) | (b) the opponent overfits its training conditions (A's gap); a varied partner set generalises -- but D3 scores vs CLXIII only, so a population dilutes the target | robustness for the pilot's use; D3 effect unclear | neutral | config if those checkpoints run the live stack | after A |
| G | per-stat moment matching on the 25 v6 stats as a reward term | (b) | holds style directly | it is the protection | reward change = owner; per-match stats are noisy | not proposed now |
| H | timing head in PPO | (a) arm D null on D3 | small | risk to timing stats | - | low |
| I | bigger model / more human data | (c) unchanged by the new goal: capacity not binding (training still rises), 3 data reweightings flat on strength, and ftR's own style is already RMS .20 on B-HF | none | - | - | dropped from the plan (not discarded: revisit if A-E stall with training flat) |

Read-out: arms 2 / 3 / 4 at u40 / u80 / u160 (D3 + quick card + training-vs-D3 gap); keep the best one, stack the next item on it.

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
### Round 1 (2026-10-31 ~11:00 UTC): live-stack partner, 2 seeds, u40 / u80 (a)
D3 = CLXIII wins / 480 (opponent win %); training win vs the live partner over the 20 updates around the checkpoint.

| run | ckpt | D3 CLXIII W | opp win | training win (window) | train - D3 | quick RMS | lock / zero / P(lock|fail) |
|---|---|---|---|---|---|---|---|
| oplc_ftR_l0003_live (seed 0, production) | u40 | 377 | 21.5% | .200 (u30-49) | -1.5 pp | .30 | .75 / .00 / .67 |
| | u80 | 376 | 21.7% | .254 (u70-83) | +3.7 pp | .37 | .75 / .01 / .66 |
| oplc_ftR_l0003_live_s1f (seed 1, fast) | u40 | 393 | 18.1% | .212 (u30-49) | +3.1 pp | .31 | .73 / .01 / .63 |
| | u80 | 372 | 22.5% | .262 (u70-89) | +3.7 pp | .41 | .73 / .01 / .64 |
| G (sampled partner, ref) | u40 / u80 | 402 / 366 | 16.3 / 23.8% | - | (+4 to +8 at u40 in that regime) | - / .28 | - / .71 / .58 |

| oplc_ftR_l0003_live_s1f | u120 | 371 | 22.7% | - | - | .30 | .74 / .01 / .65 |
| | u160 | 351 | 26.9% | - | - | .29 | .71 / .01 / .59 |
| | u200 | 375 | 21.9% | .319 (u180-199) | +10.0 pp | .35 | .71 / .01 / .60 |
- s1f STOPPED at u225 (11:25 UTC, kill 5484 + its 2 orphaned producers 5557 / 5558 by exact PID; its 2 D3 loops stopped) for
  arm 3. Its D3 series 18.1 / 22.5 / 22.7 / 26.9 / 21.9% = G's shape (G 16.3 / 23.8 / 23.1 / 26.7 / 21.9 / 21.2%): a u160 peak
  equal to G's best, then back to ~22%; u160 is the first live-partner block at G's best (26.9 vs 26.7%) and its style is the
  ftR level (RMS .29). At u200 the training-vs-D3 gap is back to +10 pp (training .319): the transfer gap REOPENS with
  training, as in the sampled-partner regime, only later.
- Transfer: fixed at u40 (pooled gap +0.8 pp) and much better than the sampled-partner regime (old fit predicts D3 18.5% at
  training .258; measured 22.1%), but a +3.7 pp gap reopens by u80 in BOTH seeds (D3 SE ~1.9 pp per block): on the edge of the
  ~3 pp rule. D3 u40 -> u80: seed 0 flat (+0.2), seed 1 +4.4.
- Success marks at u80: below G's best block (23.8%) and G's u80-u240 mean (23.3%) in both seeds (21.7 / 22.5%; ~1 SE). At u40
  above G (21.5 / 18.1 vs 16.3%).
- s1f training win per 20 updates: .140 .208 .225 .256 .281 .307 .307 .302 .293 .319 (u0 .. u199): a training plateau at ~.30
  after u100 (the noisy-update / large-batch question below).
- STYLE COST (a): the live partner rewards deep aggression. s1f u80 vs ftR: pocket_share +.23 -> +.99, our_half +.07 -> +.73,
  troop_depth +.01 -> -.68, own_half -.43 -> -.78 (seed 0 u80: pocket +1.09, our_half +.64); RMS .30 -> .41 / .37. Siege facts
  NOT improved (lock .73-.75 vs ftR .78; G .70): the strength comes from pushing into CLXIII's half, not from stopping X-Bows.
- Decision taken: arm 2 = lever 3 (gae + pre-fit critic) on pod B, despite the +3.7 pp edge case, because (i) u40 transfer is
  fixed in both seeds and u80 is within 1 SE of 3 pp, (ii) the binding problem visible in s1f is the training plateau (~.30),
  which lever 3 targets, (iii) lever 4 is mostly not available in the fast loop (own_effects / afford_ticks / G2 taps are refused
  there; the D3 census file is a different format from league_decks).

### Style track S0b / S0c (2026-10-31, a): most of the B-live error is the CLXIII-in-SIM environment, not the opponent
- B-HF (ftR in both seats on 3,741 HF test deck pairs, no CLXIII, no live reader; HF humans 7,522 sides): RMS 0.20 (B-live 0.30).
  The big B-live errors vanish there: react_lift +.50 -> -.08, spell_depth +.65 -> +.15, push_mean -.45 -> -.04, own_half -.42 ->
  +.20, bridge +.36 -> -.16. Kept: gap_p10 -.62 -> -.41 (a real closed-loop timing error); new in B-HF: ppm_ot -.53, react_3s -.35.
- CLXIII's own cadence, live (calibration block, 856) vs SIM (ftR D3, 480): 11.2 vs 9.3 plays / min, median gap 3.8 vs 4.7 s
  (style_s0c.py): CLXIII plays 17% fewer cards in SIM. react_lift / react_s are measured against OUR plays, so a slower SIM CLXIII
  inflates them with no opponent error (b: the mechanism; the size match is untested).
- Reading: the B-live RMS <= .20 bar is mostly limited by CLXIII's SIM stack (and possibly the live reader), which the opponent
  cannot fix; the opponent's own human-likeness on HF pairs is RMS .20. Next (b): (1) a cadence-matched B-live (stats conditioned
  on our play rate, or CLXIII with the live tap rate) to size the environment share; (2) S1 exploit check on pocket / our_half
  (now the largest RL-made errors).
