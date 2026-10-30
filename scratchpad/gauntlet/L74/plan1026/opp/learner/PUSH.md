# OPP-PUSH: opponent model to the pilot bar (owner goal 2026-10-30; PLAN.md Pillar 2; no-discard)

Bar: CLXIII SIM win vs the opponent 30-50% on the D3 block (480 games, seed 741200, tables 16.635.3, crforge 5e8089a4, CLXIII on
its live stack); v6 B-live RMS <= 0.20; siege facts inside the v6 margins (lock .47 +- .05, zero-lock .12 +- .06,
P(lock|fail) .36 +- .07). Grades: (a) measured (number + source), (b) plausible untested, (c) contradicted.

## STATUS (2026-10-30 ~20:45 UTC, account 3) -- RESTART POINT
- Prepared, nothing launched by me. Running elsewhere (not mine, do not duplicate): `oplc_ftR_l0003_live` on 33903 (PID 81255,
  production, u23 at 20:15 UTC, ~850 s/update -> u40 ~00:30 UTC), its D3 loop = the lead's laptop job (arm_d3_live2.sh).
- Built (this commit): `boot_opp_pod.sh NEWPORT` (pod bootstrap, below), `arm_d3_card.sh` (= arm_d3.sh + the v6 quick card per
  block; card step tested on G u160's rows: RMS .30, lock .70, zero .01, plf .60 = the lead's numbers), `launch_arm_prod.sh`
  opt-in `GPU=` / `ALLOC=` (unset = byte-identical remote command, checked).
- Waiting on: the new pod's SSH port (lead); the u40 D3 of the live run (~00:30-01:00 UTC); FASTLOOP-FIX (48/48).
- Codex dispatches: none (design + script writing; nothing menial yet).
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

## Rounds (ledger)
(none yet)
