# SIMPRICE (account 3, 2026-10-31): does the SIM price Rocket and the Hero IW press as losses, and why

Owner ask 10-31: the model must learn to use Rocket and the Hero Ice Wizard ability at the right moments. Lead's diagnosis to
test: the SIM prices both as losses. Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.

## STATUS (keep current) -- 2026-10-31 ~21:20 UTC: FREEZE-LIVE (section 9) DONE, nothing of mine running
- FREEZE-LIVE (10-31, section 9; verdict: the ENGINE does NOT under-power the freeze, (c) contradicted): 220 fully exact RECON records
  contain 419 Hero IW presses (376 ours, 233 with >= 6 elixir of enemy troops in the cube radius), every tower / unit (side, x, y, hp)
  equal on every frame, ~82,600 frames inside 450 ticks after a press; re-running the same records with a freeze 10% leaky breaks 87%,
  radius -20% / +20% 29% / 22%, cube 4 s 51%, slow -15% / 0 51% (no-op control 0%). Exact rate with a press 220 / 257 = without 240 / 290
  (Fisher p .41). Engine press - no press at live presses (own, >= 6): our princess +312 HP at 7.5 s, +607 [+487, +732] at 15 s, but median
  +86 (45% change nothing); at held moments ~+60-90 HP at 7.5 s; the SIM's forks show the same split (held ~-45 HP, pressed hundreds).
  Same estimator live vs SIM: princess HP lost in the next 15 s after a press 0.121 (live CLXIII, n 849) vs 0.120 (SIM p2init, n 43), CLXV
  0.157 vs 0.150; after a held moment 0.075 vs 0.078, 0.077 vs 0.097. So the SIM's ~0 net press value is engine-consistent; the learned
  "stop pressing" is not an engine artefact. Code `freeze_live_*.py`, results `freeze_live_out/`; no engine / trainer change.
- ROUND 2 (coordinator 10-31, section 8): match-end IW audit on CLXV (490271e5) + p2init, valuable class (>= 6 elixir in the
  freeze target); opt-in cf_iw_block_ticks (no freeze for 200 ticks in the no-press copy) + cf_iw_min_elixir (c95368e, sp_smoke7
  SMOKE PASS). Result: at match end the press is ~0 for BOTH heads (CLXV +0.009 [-0.055, +0.082] n 474; p2init -0.017, clean
  no-freeze contrast -0.028 [-0.080, +0.023] n 307); CLXV's 45-s critic price is negative (-0.038 all / -0.050 held) and sits
  +0.054 [-0.011, +0.123] below its own match end. Stop rule NOT reached (half-width 0.068 / 0.059; the disk-full crash lost one
  96-match run).
- Round 1 (sections 1-7): live counts; Rocket landing artifact (cf_alt_afford); IW and Rocket audits; config BLOCKED.
- Real smokes: sp_smoke6 (33903, rl_royale --smoke, pilot2.yaml + every SIMPRICE key, critic warm-up) SMOKE PASS 14:47 UTC;
  sp_train2 (33308 GPU 1, simprice_train.yaml, critic_warmup_updates 1 -> u1 = a policy step with the iw alternative rows in the
  ability loss) SMOKE PASS 15:10 UTC. Pod tests pipeline/tests/test_cf_credit.py 43 pass / 3 skip; laptop 38 pass / 8 skip.
- Code (dfe4b33): pipeline/cf_credit.py (opt-in triggers iw_pressed / iw_press, opt-in
  cf_alt_afford, cf_diag refusal record), pipeline/e1_eval.py (one stored attribute, _ab_cmd), pipeline/rl_royale.py (cf_append:
  an iw alternative row carries the opposite press + the decision's press weight; inert without the iw triggers),
  pipeline/tests/test_cf_credit.py (TestIwPress, TestAltAfford). Tools: simprice_live.py, simprice_audit.py, simprice_run.sh,
  p4_audit.py (+ princess_hp split), simprice_train.yaml.
- Pod 33903 tree /workspace/simprice/cb = HEAD d77316e code + the edits (+ artifacts: pgate/cb hard links, p2init cdde779a,
  G u0160 9f8470a7, gen_dataset_v32_fv5_memory_v1 a0ecce38, pilot2_Lc_u0080 ec4c10f5 in rl_royale/b0/). Pod 33308 tree
  /workspace/simprice/cb = /workspace/loop/cb hard links + HEAD pipeline + the edits. Logs /workspace/simprice/logs/ (both pods).
  Data on the laptop (gitignored): cf/data/spa1_u0.jsonl (128 matches), cf/data/spa2_u0.jsonl (127).
- Restart an audit: `ssh -p 33903 ... 'cd /workspace/simprice && MAXU=1 ./simprice_run.sh RUN 166-169,194-201 10 [init=...]'`
  (round 2: CF_DUMP_DIR=/dev/shm/simprice puts the dump in RAM -- 33903 disk filled 10-31; CLXV init = cb/icebow/data/bench/rl_royale/b0/clxv_u34.pt 490271e5)
  (MAXU 1 + kill after logs/RUN.jsonl appears: the CPU learner's critic step takes > 25 min and blocks the actors; E / G / CFP
  env overrides; memwatch guard 118 GB). Tables: `python -B simprice_audit.py data/RUN.jsonl` (IW), `python -B p4_audit.py
  data/RUN.jsonl` (Rocket family). Stop: exact PIDs (the rl_royale --run RUN process whose cwd is /workspace/simprice/cb + its
  children). Cost: ~45 min per 128 matches on 10 throttled actors (33903 load 30-140).
- Codex dispatches: none (the work was diagnosis + design; runs were short and needed live decisions).

## 1. Step 0: live counts (a; simprice_live.py, live_play_*.jsonl events `confirmed` / `ability` / `ability_confirmed`)
The lead's grep returned zeros because the play event is `confirmed` {name, intended [x, y]} and the press events are `ability`
(tap) / `ability_confirmed` (seen); X-Bow placement from intended y (screen-normalised, own side at the bottom): bridge / reach
y <= .64 (card_use.OFFENSIVE_Y), enemy half (pocket) y < .50. Groups by checkpoint + decision_options digest. Per match, 95%
match-bootstrap CI:

| group | matches | Rocket | X-Bow | of which bridge | pocket | IW presses (seen) | plays | mins |
|---|---|---|---|---|---|---|---|---|
| CLXIII, old rules (10-30 00:01-20:07) | 246 | 0.32 [0.25, 0.40] | 5.09 | 4.22 | 0.00 | 0.93 [0.79, 1.09] | 42.4 | 3.98 |
| CLXIII, stripped (10-30 21:38-10-31 02:24, 04:40-06:01) | 93 | 0.13 [0.06, 0.20] | 4.45 | 3.86 | 0.03 | 0.96 [0.71, 1.20] | 40.2 | 3.77 |
| CLXV, stripped (10-31 02:30-04:40, 06:04-07:43) | 54 | 0.22 [0.04, 0.46] | 5.37 | 4.44 | 0.04 | 0.31 [0.17, 0.48] | 45.8 | 4.12 |

- CLXV - CLXIII stripped: IW presses **-0.64 [-0.93, -0.35]** (a third of CLXIII's rate; SIM 0.57 vs 1.86 has the same ratio);
  Rocket +0.09 [-0.10, +0.36] (no difference: BOTH models Rocket rarely without the rules); X-Bows +0.92 [+0.06, +1.73] per match
  but the same share of plays (11.7% vs 11.1%) and the same bridge share (83% vs 87%; old-rule CLXIII 83%) -> (a) "aggressive
  X-Bow" is not new with CLXV.
- Removing the rules cut CLXIII's Rockets by 0.19 [0.09, 0.30] per match (the rocket_value / combo / lethal rules fired them);
  presses unchanged (+0.02). Win (reader towers.won): CLXIII rules .362, stripped .280, CLXV .389 (n 243 / 93 / 54).

## 2. Finding: about a third of the forced Rocket alternatives in every past audit never played a Rocket (a)
P4 audits cfaud3 / f3base2 (P4_AUDIT s1-9) forced Rockets at decisions where the look-ahead afford mask allowed them. crforge's
client gate checks elixir when the play is ISSUED (decision + 6 ticks: e1's delay 26 minus crforge's own 20) and charges it
when it runs (+26); the mask reads the elixir at +26. f3base2, forks whose own plays list a Rocket within 150 ticks:
| phase | root elixir 5-6 | 6-7 | >= 7 |
|---|---|---|---|
| 1x | 58 / 232 (0.25) | 606 / 606 | 994 / 994 |
| 2x | 102 / 738 (0.14) | 418 / 422 | 486 / 488 |
| OT | 59 / 400 (0.15) | 148 / 152 | 146 / 146 |
(The refusal share matches an issue-tick check: expected 77% of the 5-6 band at 1x / 2x.) By alternative: rocket_cycle
rocket_princess landed 26%, rocket_empty 19%; xbow_after_fail 73-75%; rocket 82-88%; the combo 98-100%. A refused "Rocket" fork is
a wait with the Rocket kept, so the old prices mixed two actions. Restricted to root elixir >= 6 (pre-treatment, lands ~100%),
f3base2 u1-4: rocket_princess - chosen 1x -0.327 [-0.372, -0.280], 2x -0.205, OT -0.075 [-0.171, +0.008], terminal -0.105
[-0.275, +0.064] (n 93); chip itself (princess - empty) rocket_cycle +0.122 [+0.058, +0.198], xbow_after_fail +0.071 [+0.032, +0.110];
finishing Rocket (weak princess hp <= 546) in rocket_cycle +0.020 [+0.012, +0.028] (n 21). So the artifact DILUTED the old
negative prices toward 0; it did not create them. Fix (opt-in `cf_alt_afford`): offer a card alternative only when my elixir at
the issue tick covers its cost.
- (b, for RECON / the lead) The same gate applies to every SIM play: live accepts a tap up to ~22 ticks before the elixir is there
  (latency/afford_arrival.txt (a): refusals 2-7% for waits <= 21 ticks), crforge refuses at +6 -> the SIM refuses boundary plays live
  accepts. Size for the policy's own plays not yet measured (the run log's refused/m monitor is the read).

## 3. Step 1: IW press audit
Triggers (opt-in, cf_credit): iw_pressed = the head pressed -> alternative iw_hold (same card decision, no press); iw_press = the
head held a pressable button -> alternative iw_press (same card decision + the press). The fork records ab_n (presses the engine
accepted per fork: checks the forced press lands and how often the head re-presses after a hold) and the head's P(press) and
freeze features (target troops / elixir / win condition, cube on my half).

### 3.1 spa1 (pod 33903, 128 matches, u0): CLXIII's press head (p2init = CLXIII + memory) on the current SIM (a)
Policy FIXED, pilot2.yaml pool (init league opponent = p2init, externals, G u0160, w14opp_I), sampled gate T .1, crforge 5e8089a4
plain + tables 16.635.3; K 2, horizon 900 + sweep 150-600, 30% audited to the end; critic = p2init's (not adapted: the CPU
learner's warm-up step took > 25 min, run stopped after the u0 dump). 466 IW samples / 124 matches; dQ = Q(press) - Q(hold),
+-1 = a win (win probability = dQ / 2), 90% match-cluster CI (`simprice_audit.py data/spa1_u0.jsonl`, data gitignored):
| moment | n | 45 s | terminal (audited) |
|---|---|---|---|
| the head PRESSED (iw_pressed): press now - hold | 188 | -0.014 [-0.057, +0.031] | +0.111 [-0.066, +0.290] (50) |
| ... nothing in the freeze | 46 | -0.071 [-0.134, -0.019] | -0.012 (10) |
| ... freeze target 3-6 elixir | 50 | +0.022 [-0.062, +0.116] | +0.262 [+0.000, +0.534] (14) |
| ... freeze target > 6 elixir | 62 | +0.001 [-0.072, +0.071] | +0.100 [-0.309, +0.493] (20) |
| the head HELD a pressable button (iw_press): forced press - hold | 278 | -0.059 [-0.089, -0.029] | -0.260 [-0.418, -0.113] (83) |
| ... nothing in the freeze | 143 | -0.062 [-0.109, -0.015] | -0.283 [-0.530, -0.043] (45) |
| ... freeze target <= 3 elixir | 63 | -0.114 [-0.167, -0.058] | -0.184 (19) |
| ... freeze target > 6 elixir | 16 | +0.034 [-0.058, +0.119] | n 3 |
- (a) Forced presses land: the press branch has +0.85 (held moments) / +0.41 (pressed moments) more accepted presses per fork
  than the hold branch. After a hold the head re-presses within the horizon in 77% of forks at its own press moments (49% at held
  moments): iw_pressed prices "press now vs press a little later", not "freeze vs no freeze".
- (a) Noise controls: reliability SNR iw_pressed 1.08 (900) / 1.34 (300) / 2.48 (150); iw_press 0.50 (900) / 1.11 (300); critic
  slope (terminal on horizon, within-sample) iw_pressed 1.11 +- 0.33 (n 26, in the PLAN band [0.7, 1.3]), iw_press 0.51 +- 0.24 (69).
- Reading vs the evidence (owner doctrine: the freeze is core defence; triage = cheapest sufficient answer): (c) "the SIM prices
  pressing as a loss" is contradicted for the press moments themselves: at the head's own presses the price is ~0 at 45 s and
  positive-leaning at the end, ~0 / + where something worth >= 3 elixir is frozen. What the SIM prices negative is (a) pressing
  with nothing (or <= 3 elixir) in the freeze: 24% of CLXIII's presses (46 / 188) freeze nothing and cost -0.07, and a press forced
  where the head held costs -0.06 (45 s) / -0.26 (end). That is the doctrine's sign (2 elixir for nothing), not a wrong sign.
- (b) Why pilot2 then lowered presses 1.86 -> 0.48 / match: the GAE gradient pushes down the empty presses (correctly) and nothing
  holds up the useful ones (their GAE / fork value vs pressing a moment later is ~0), so the head's whole P(press) drifts down; the
  live count (CLXV 0.31 / match) says it went below the useful level. spa2 (3.2) answered the test: on CLXV a forced press at
  a held moment is NOT positive even with a valuable freeze target, so fork credit as built would not restore presses.

### 3.2 spa2 (127 matches, u0): CLXV's own head (pilot2_Lc_u0080 ec4c10f5, critic adapted over 80 updates) (a)
Same setup, IW-focused triggers (iw_pressed 1.0, iw_press 0.05). Deviation: the league's "init" opponent is then CLXV-lineage
itself (pilot2's is p2init). CLXV pressed 31 times in 127 matches (0.24 / match; live 0.31); P(press) < 0.02 at 598 / 625 button
decisions. Forced press - hold at CLXV's held moments (the hold branch re-presses in only 10% of forks: a clean press vs no press):
| moment (iw_press, CLXV held) | n | 45 s | terminal (audited) |
|---|---|---|---|
| all | 594 | -0.065 [-0.086, -0.045] | +0.005 [-0.109, +0.118] (166) |
| nothing in the freeze | 291 | -0.053 [-0.083, -0.022] | -0.010 (90) |
| freeze target 3-6 elixir | 103 | -0.103 [-0.152, -0.053] | +0.342 [+0.088, +0.618] (24) |
| freeze target > 6 elixir | 80 | -0.046 [-0.107, +0.022] | -0.147 [-0.301, -0.003] (24) |
| win condition in the freeze | 94 | -0.076 [-0.150, -0.000] | -0.132 [-0.285, +0.002] (26) |
| cube on my half, target > 3 elixir | 77 | -0.034 [-0.105, +0.042] | -0.005 (25) |
Horizon sweep 150 / 300 / 450 / 600: -0.046 / -0.040 / -0.041 / -0.049 (all CIs below 0). Reliability SNR 0.75 (900); critic
slope (within-sample, terminal on horizon) 0.53 +- 0.19 (n 133): BELOW the PLAN band [0.7, 1.3], and the 45-s and terminal reads
disagree in sign on two classes (3-6 elixir: -0.10 vs +0.34; > 6: -0.05 vs -0.15).
Reading: (a) on CLXV the SIM prices one more press at its held moments slightly negative at 45 s and ~0 at the match end, with no
target class robustly positive. Against the doctrine ("press the freeze on a real push") the > 6-elixir / win-condition classes are
a candidate WRONG SIGN (b): ~0 to negative where a defender would expect positive. Fork credit on CLXV with these triggers would
push its presses further DOWN, so it must stay off for the press-restoration goal until the cause is found. Candidate causes, in
the order to test (none measured yet):
1. critic / horizon: slope 0.53 and sign flips between 45 s and the end -> the critic misvalues post-press states (CLXV rarely
   presses: those states are off its training distribution). Test: the same samples at a longer audited horizon (cf_audit_p 1.0
   on iw_press only) or with p2init's critic (spa1: iw_pressed slope 1.11 in band).
2. continuation: CLXV's policy may not exploit a freeze it would not have pressed (no follow-up into the frozen push). Test:
   forced press with the p2init continuation on CLXV-like states (swap continuation weights in the fork).
3. engine: the hero IW cube / freeze in crforge. Tables match live (ManaCost 2 = live's measured 2.0 from the elixir drop;
   IceWizardHero_FreezeBuff -100% speed / hit speed, then IceWizardHero_SlowBuff -30%); SME: 3 of 82 failing records first
   diverge on hero IW cube / ability rows (RECON.md 13.1) -> mostly faithful (b). Test: a scenario fork (push of N elixir into
   our princess, press vs no press) compared with the live reader's freeze durations.
4. alternative spec: "press now" is the head's cube target; a human presses when the push is in reach of the princess + Tesla.
   The freeze features say where the cube lands (cube on my half: -0.03 / ~0), so the spec is not obviously wrong (b).

## 4. Step 1: Rocket audit on the current SIM (spa1 u0, cf_alt_afford on, drift aim, 128 matches; `p4_audit.py`) (a)
| alternative - the policy's action | n | 45 s |
|---|---|---|
| chip Rocket (rocket_princess), all / 1x / 2x / OT | 121 | -0.277 [-0.332, -0.223] / -0.276 / -0.249 / -0.362 (7) |
| Rocket into nothing (rocket_empty) | 104 | -0.348 [-0.406, -0.285] (chip itself +0.07) |
| best lone clump (rocket_clump): value < 4 / 4-6 / 8+ | 61 | -0.217 [-0.310, -0.132]: -0.328 / -0.143 / -0.234 (13) |
| wincon rocket_on: heavy (Golem etc.) / hog-like | 25 | -0.131 [-0.193, -0.082]: -0.138 / -0.144 |
| rocket_cycle (2x / OT after 2 failed X-Bows) | 92 | -0.205 [-0.290, -0.128]; Tesla in hand -0.119, not -0.292 |
| finishing Rocket (weak princess hp <= 546), rocket_cycle | 7 | +0.143 [+0.000, +0.426] |
| Rocket + Tornado combo | 25 | -0.295 [-0.471, -0.140]; lone clump 8+ in that state +0.032 (9) |
| the policy's OWN Rocket vs wait (rocket_played) | 12 | wait - Rocket +0.009 [-0.088, +0.102] |
Reading: same picture as P4_AUDIT s9 on fe364ceb / 5e8089a4 + tables 16.402.22: a Rocket forced at an affordable moment the policy
did not choose is priced negative in every class except the finishing Rocket; the policy's own Rockets are priced like waiting.
The "lone Golem" (expected -) and "hog-like with Tesla out of cycle" (expected +) do not separate (both -0.14). (b) Open causes
from s9 (not re-tested here): the opponent's X-Bow defence (SIM lock .73-.78 vs live .47 inflates the displaced X-Bow line the
Rocket's 6 elixir costs), and the chosen-vs-forced estimand.

## 5. Step 3: fork credit for the IW press in a real training update (a) + what blocks a production run
- sp_train2 (pod 33308 GPU 1, CPUs 108-111, `rl_royale --smoke --config cf/simprice_train.yaml critic_warmup_updates=1
  learner_device=cuda`, iw_pressed 1.0 / iw_press 0.3): u0 warm-up, u1 a real policy step (KL g/c/x .0073 / .0004 / .0006,
  kl_stop at minibatch 6), ability head deciding (856 decisions, l_ab monitor live), cf 50 samples -> 50 alternative rows (one per
  iw sample: the same card action with the opposite press; its card term cancels the decision row's, its press term carries the
  fork advantage), reliability SNR 1.16 (iw_press) / 1.02 (iw_pressed) at the 300-tick horizon, fork cost 1.57 fork ticks per
  match tick (IW triggers only). Resume check incl. ability_head / ability_opt PASS. SMOKE PASS.
- Config: cf/simprice_train.yaml = pilot2.yaml minus stored_values / mem_row_cache / split_attn / trunk_graph / ppo_decoupled +
  cf_credit with iw_pressed 1.0, iw_press 0.05, horizon 300 for both, K 2, shrink by batch reliability, cf_alt_afford, Rocket
  family 0. BLOCKED (section 3.2): do not run it to restore presses before the valuable-class sign is resolved.
- Production blockers (b, from code): the fast loop (pilot2's trainer) has no forks (JAVA_FORKS.md is a design note), and
  rl_royale refuses cf rows with micro_batch (the pilot2_L recipe uses micro_batch 256/512) -> today fork credit trains only on
  the slow Python path.

## 6. Related engine finding (for RECON-7, already being fixed there)
(a) crforge refuses a play whose elixir is short at the ISSUE tick (+6), live holds the tap ~22 ticks (latency/afford_arrival.txt):
SIM init screen of p2init refused/m 1.248 (702 matches) vs live 0.275 (421 matches 10-30 / 10-31, 2.5% of plays); in spa1's forks
"not_enough_elixir" is the dominant refusal (3,291 in 1,756 chosen forks over 45 s). RECON-7 landed the opt-in `tap_hold`
(00ca929: 11.6% -> 1.3% of attempts). Not an rl_royale / cf key here yet; the audits above ran without it (cf_alt_afford keeps
the forced alternatives clean, the continuations still see the strict gate).

## 8. Round 2: the IW press sign at match end, valuable moments, CLXV vs p2init, with / without a no-freeze window (a)
Setup: pod 33903, crforge 5e8089a4 plain + tables 16.635.3, pilot2.yaml pool (deviation: the league "init" opponent = the audited
policy), K 2 CRN continuations, BOTH run to the match end (cf_horizon_by iw_* 7000; q = the discounted match result, no critic),
critic Q also read on the same forks at 300 / 900 ticks (cf_horizon_sweep), iw triggers p 1.0 at every decision whose freeze
target holds >= 6 elixir of troops (cf_iw_min_elixir 6; the class the doctrine names; the "nothing to freeze" / small-target
classes are in sections 3.1 / 3.2: negative at 45 s, ~0 to negative at the end). dQ = Q(press) - Q(no press), +-1 = a win,
90% match-cluster CI (simprice_audit.py; data gitignored: cf/data/spb_clxv2.jsonl, spb_clxv3.jsonl, spb_p2i.jsonl,
spc_p2i_blk.jsonl).
- Window (engine tables 16.635.3): the press's cube IceWizardHero_IceCube lives <= 5,000 ms (cube_lifetime_timer; killed 2 s
  after no target is left), freeze aura radius 2.5 t linked to the cube, then IceWizardHero_SlowBuff (-30%); with the 26-tick
  input delay and the 400 ms cube deploy delay one press acts for ~26 + 8 + 100 + ~50 ticks -> block 200 ticks (10 s). Check:
  hold-branch first accepted press within 200 ticks 0 / 118 and 0 / 496 forks with the block (66 / 118, 102 / 496 without).

| policy, run | samples / matches | match end, all | own presses (iw_pressed) | held moments (iw_press) | > 6 elixir | win condition | critic 900 / 300 (all) |
|---|---|---|---|---|---|---|---|
| CLXV (spb_clxv2 + 3) | 474 / 87 | **+0.009 [-0.055, +0.082]** | +0.041 [-0.075, +0.170] (26) | +0.008 [-0.061, +0.085] (448) | +0.032 [-0.049, +0.111] (337) | -0.025 [-0.105, +0.059] (291) | -0.038 [-0.074, -0.000] / -0.035 [-0.050, -0.020] |
| p2init, no block (spb_p2i) | 307 / 65 | -0.017 [-0.077, +0.040] | +0.097 [-0.006, +0.208] (59) | -0.044 [-0.110, +0.027] (248) | -0.009 [-0.081, +0.065] (215) | -0.016 [-0.076, +0.045] (234) | -0.023 [-0.052, +0.008] / -0.016 [-0.029, -0.003] |
| p2init, block 200 (spc_p2i_blk) | 307 / 65 (same roots) | **-0.028 [-0.080, +0.023]** | +0.071 [-0.041, +0.181] (59) | -0.051 [-0.114, +0.014] (248) | -0.033 [-0.097, +0.034] (215) | -0.019 [-0.072, +0.036] (234) | -0.031 [-0.064, +0.002] / -0.015 [-0.030, +0.001] |

- Paired (identical 307 roots, the two p2init runs): no-block - block +0.011 [-0.013, +0.034]: denying the hold branch its later
  press does not hurt it, so "press now vs a moment later" and "freeze vs no freeze for 10 s" price the same (~0) in the SIM.
- Stop rule (valuable-class CI half-width <= 0.05): NOT reached. CLXV 0.068 at n 474 / 87 matches, p2init 0.059 at n 307 / 65.
  Why: match-end outcomes are +-1 per continuation (reliability SNR of the end value 0.55 CLXV iw_press, ~0.1 p2init), the 3-h
  budget, and the first CLXV run (96 matches, spb_clxv) died writing its dump when 33903's disk filled at ~16:30 UTC. About 1.9x
  (CLXV) / 1.4x (p2init) more samples would reach 0.05 (~2 more 48-match runs on 14 actors, ~1 h).
- What the freeze does on the board (press - no press, cf_diag snapshots, princess units: 1.0 = one princess tower, 4,858 HP):
  own princess HP lost at 15 s: p2init block -0.021 [-0.036, -0.006] (~100 HP saved), CLXV -0.030 [-0.047, -0.016] (clxv2) /
  -0.012 (clxv3); by 45 s the saving is gone (-0.003 / +0.000 / -0.014) and the FOE loses less (-0.029 p2init block, -0.055 CLXV
  clxv2 at 45 s): the 2 elixir comes out of our offence. The freeze works mechanically; its net value at these moments is ~0.

### 8.1 Which cause the data points to (round-2 question 3)
- (a) critic mis-valuation: YES for CLXV's 45-s price, NO for p2init. On the same CLXV samples the critic reads -0.038 (900) /
  -0.035 (300) where the match end reads +0.009; paired end - critic900 +0.045 [-0.015, +0.109] (all), +0.054 [-0.011, +0.123]
  (held moments): the critic under-prices CLXV's presses by ~0.05 (the 90% CI touches 0 at its lower end). p2init: end -
  critic900 +0.011 [-0.049, +0.069] (critic consistent). Plainly: CLXV's negative press price at 45 s (round 1: -0.065) is mostly
  its critic; at the match end the press is NOT positive either, it is ~0. The critic explains "negative", not a hidden "positive".
- (c) CLXV continuation not using the freeze: contradicted as the cause of a negative price. At held valuable moments CLXV's
  match-end price (+0.008) is no worse than p2init's (-0.044, -0.051 with the block).
- (b) engine: not shown wrong, not cleared. The freeze saves ~100-150 HP over 15 s on >= 6-elixir pushes and costs offence
  later; tables match live where checked (cost 2.0, -100% freeze, -30% slow, cube <= 5 s), SME divergences on IW cube rows 3 / 82.
  The size of the saving has no live reference yet; that comparison is the one remaining check before calling the SIM's ~0
  "right" or "a wrong sign".
- For training: fork credit for the press read at 300-900 ticks would carry CLXV's critic bias (pushes presses down); read at the
  match end it is ~0 for both heads (no push either way; end SNR 0.55 / ~0.1 is too low for credit). Neither restores presses.
  The decision stays the lead's / owner's: the SIM does not price the press as a loss at match end, but it does not reward it.

## 9. FREEZE-LIVE (10-31): does the engine model the Hero IW freeze's real effect? (labels a / b / c)
Question (owner 10-31): is the SIM's ~0 press value (sections 3, 8) an engine under-power? Tools `freeze_live_*.py` (laptop: collect / sel /
parse / est / report; pod 33903 CPUs 226-237, /dev/shm, tree /workspace/smeR6: cf / held / mktabs / env, nothing left running), results
`freeze_live_out/` (report.txt, estimator_out.txt, freeze_live_data.tar.gz = the raw per-press / per-moment rows). Engine, trainer and tables
untouched (perturbed table COPIES in /dev/shm only). Reproduce the tables: extract the tarball into a directory D, `python -I freeze_live_report.py D`;
the live estimator needs `freeze_live_parse.py` output (32 MB, not committed): `python -B freeze_live_est.py LIVE.jsonl`. Pod order: `freeze_live_collect.py` ->
`freeze_live_sel.py` (laptop) -> `freeze_live_list.py` -> `freeze_live_cf.py` (full) / `freeze_live_sens.sh` (perturbed tables) / `freeze_live_held.py`.

### 9.1 Step 1: the freeze inside exact RECON records (a)
- What the SME comparator compares (SME.md "The comparator", sme.py canon_rec / canon_sim): the multisets of (side, x, y, **hp**) of every
  tower and every unit (the ice cube is a unit: hp 104 and its decay compared), (side, x, y) of projectiles and area effects, and our elixir /
  hand / queue, on every reader frame (~every 2nd tick), no tolerance; reader-flagged torn frames are excluded. Card names and buff states are
  NOT compared: a freeze shows only through positions, hp and attack timing, which is exactly what it changes (a frozen unit that moved or hit
  one frame too early is a diff).
- Count (all RECON runs pooled, best plan per match; `freeze_live_collect.py`, `freeze_live_sel.py`): 547 matches, 460 fully exact. **220 exact
  records contain >= 1 Hero IW press (either side): 419 presses = 376 ours + 43 the opponent's**; 188 of those records / 359 presses come from the
  hand-rule gate plans (no RECON edits; the press is the extractor's, run ticks moved only inside their window); press sources 368 cast_seen
  (cube sighting), 49 own_press, 2 charge_drop. 206 / 391 re-run plain-exact (the other 14 contain reader-torn frames, counted exact by RECON's
  comparator). Engine exposure at the cube (enemy bodies within 2.5 t, approx. elixir from the card table): **233 presses >= 6 elixir (207
  ours)**, 102 3-6, 16 < 3, 68 nothing. The cube stood median 54 ticks, max 100 (= the table's 5.0 s; 108 presses ran the full 5 s).
- Windows: ~82,600 reader frames lie within 450 ticks (22 s: cube <= 5 s + slow) after a press, all exact (77,600 in the 206 plain-exact
  records); the exact stretch is the whole record (median 2,090 frames, range 941-3,054).
- Not a selection artefact of "exact records only": exact rate in matches WITH a press 220 / 257 (0.856) vs WITHOUT 240 / 290 (0.828), Fisher
  p .41 (gate plans only: 188 / 259 = .726 vs 210 / 288 = .729, p 1.0). Of the 37 failing records with a press, 7 first diverge <= 300 ticks
  after one: 230352 + 134929 = Golden Knight press plans (RECON-8, not the freeze), 094801 (the opponent's hero Balloon ability: its Skeletrooper spawns differently; the cube stood 5 tiles from the Balloon, which tracks the reader
  to the unit until then), 132322 (an opponent MiniPekka the plan lacks, 189 ticks after the press), 093127 (opponent Skeleton / Tesla_EV1 plays), 190605
  (Miner deploy point) are not freeze rows; **153413 is the one IW row** (the SIM has a cube + freeze
  aura at 2452 where the reader lists none, 81 ticks after the press at 2371; an old d49_cyc_old1 plan; cube timing / target, not power).
- **Sensitivity (the comparator's power; c-test of "the engine under-powers it")**, the 206 plain-exact records re-run with a perturbed copy of the
  tables 16.635.3 (`freeze_live_mktabs.py`), records that stop being exact (>= 6-elixir class of 145 in brackets):
  | perturbation | broke | first diff after the press |
  |---|---|---|
  | no-op copy (control) | 0 / 206 (0 / 145) | - |
  | FreezeBuff speed / hit-speed -100% -> -90% | 179 (87%) (137) | 10 ticks |
  | freeze aura radius 2.5 t -> 2.0 t / -> 3.0 t | 59 (29%) (47) / 45 (22%) (39) | 9 ticks |
  | cube lifetime timer 5 s -> 4 s | 106 (51%) (83) | 87 ticks |
  | cube timer + LifeTime 4 s (also changes the cube's hp decay) | 198 (96%) | 28 ticks |
  | slow after the freeze -30% -> -15% / -> 0 | 106 (51%) (90) both | ~80 ticks |
  So a freeze that leaks 10% of its speed, a 20% smaller or larger aura, a 1-s shorter cube or a weaker slow would have shown in most
  records; the engine's numbers (-100% freeze, 2.5 t, 5 s, -30% slow) are the live ones to that resolution. **(c) contradicted: "the engine
  under-powers the freeze".** (b) Not covered: freeze on buildings / evolutions as a separate class, regimes the 220 records do not contain.

### 9.2 Engine press - no press from the reconstructed state (step 3, a; `freeze_live_cf.py`)
Each press in the 220 exact records dropped on its own (the true history re-run without it), same recorded later plays, our princess HP
(both princesses, HP) at +150 / +300 / +450 / +900 ticks after the run tick, 90% match-cluster CI, press - no press (+ = the press saves):
| presses | +150 | +300 | +450 | +900 |
|---|---|---|---|---|
| ours, target >= 6 elixir (n ~198 / 186 / 167 / 133) | +312 [+240, +393] | **+607 [+487, +732]** | +686 [+543, +839] | +742 [+566, +938] |
| ours, 3-6 elixir | +154 [+90, +231] | +339 [+185, +519] | +384 | +359 |
| ours, nothing in the cube (n 57 / 51 / 44 / 36; negative control) | +0 | +8 [-5, +26] | +33 [-5, +92] | -12 [-97, +61] |
| the opponent's, >= 6 (their freeze on our units) | -94 [-220, +7] | -115 [-243, -15] | -144 [-294, -26] | -148 [-353, +2] |
- Heavy-tailed (own >= 6, +300, n 186): mean 607 but **median +86 HP, 45% of presses change nothing, 44% save > 300** (a freeze matters when the frozen
  push is on the tower, not otherwise). 188 / 207 own >= 6 presses change some enemy body (x, y, hp) vs no press. 0 / 207 have the no-press branch
  accept a recorded play the live history refused.
- (b) Bias: both branches replay the recorded plays, which were timed to the press world, so this reading is tilted UP for the press branch and
  grows with the horizon (see 9.3's placebo); read +150 / +300 as mechanics, not +450 / +900. It carries no offence cost (plays are fixed).
### 9.3 The press added at HELD moments, and the SIM's own forks (a; `freeze_live_held.py`)
At the 934 moments (177 exact records) where the live head held a pressable button with a >= 6-elixir target (head feature 46), the engine with
one press ADDED at tick + 26 (752 accepted, 265 dropped as a real own press lies within 600 ticks), vs the live (no-press) history; only moments
where the press branch refuses none of my recorded plays (the press costs 2 elixir): OUR princess HP, press - live: +100 +48 [+24, +75] (n 429),
**+150 +59 [+29, +94] (395)**, +300 -29 [-90, +34] (338), +450 -303 [-418, -194] (297). By what the engine says the cube catches: >= 6 elixir
+76 / +88 [+42, +141] / +21 / -268; **placebo (cube catches nothing): +6 / -5 [-30, +19] / -144 [-271, -25] / -414 [-707, -152]** -> beyond 150
ticks this CF measures replay mismatch, not the freeze. At +150 a press at a held moment saves ~+90 HP (>= 6 class) vs +312 at the live press
moments: the head's own presses are the ~3.5x better moments (selection works).
The SIM's forks, same estimand (cf_diag snapshot, `freeze_live_est.py`, princess units x 4858, adaptive continuations; negative = the press saves):
| | held moments (forced press - hold), h 300 | pressed moments (press - hold), h 300 | clean pairs (the hold branch never presses) at pressed moments |
|---|---|---|---|
| CLXV (spb_clxv2 + 3) | -0.009 [-0.017, -0.001] = -45 HP (n 367; clean -56, n 323) | -0.064 [-0.142, +0.027] = -311 HP (n 22) | -0.024 [-0.106, +0.040] = -116 HP (n 12) |
| p2init (spb_p2i) | -0.009 [-0.019, +0.000] = -43 HP (n 202) | -0.018 [-0.043, +0.002] = -89 HP (n 43; its hold branch re-presses in 77%) | -0.067 [-0.156, -0.004] = -326 HP (n 12) |
So the SIM's own per-press saving has the engine-on-live split: tens of HP at held moments (SIM saves 43-56 HP at 15 s; engine on live held moments +59 [+29, +94]
at 7.5 s and -29 [-90, +34] at 15 s), hundreds at pressed moments (SIM -311 / -326 = saves; engine on live presses +607 at 15 s; the CIs are wide and overlap). The SIM does not under-price the freeze mechanically.
### 9.4 Step 2: the same observational estimator on live and SIM (a; `freeze_live_parse.py`, `freeze_live_est.py`)
Live: 1,759 logs 10-26 .. 10-31 (52,820 press / held decisions; `ability` taps vs `ability_held`, 55 'freeze' head features, our princess HP lost from the reader
frames, a tower row missing for < 40 ticks = reader gap). SIM: the spb forks' CHOSEN branch only (what the policy did), the same cf_diag HP
lost over h ticks from the root snapshot. Outcome: our princess HP lost in the next h ticks (princess units; 1.0 = 4,858 HP); target >= 6 elixir
(feature 46); estimators raw / OLS (target elixir, win condition, cube side + y, tick, own elixir, HP lost so far, phase) / stratified (target
bin x phase x cube side x own elixir >= 6); 90% match-cluster bootstrap.
| group | pressed / held (matches) | lost 15 s: pressed / held | pressed - held at 15 s: raw / OLS / strat | at 45 s: raw / OLS / strat |
|---|---|---|---|---|
| LIVE CLXIII | 923 / 5,929 (1,166) | 0.121 (n 849) / 0.075 (5,530) | +0.046 [+0.034, +0.058] / +0.036 [+0.026, +0.047] / +0.039 [+0.028, +0.050] | +0.086 / +0.073 / +0.079 (all CIs > 0) |
| SIM p2init | 59 / 248 (65) | 0.120 (n 43) / 0.078 (203) | +0.042 [-0.002, +0.098] / +0.013 [-0.025, +0.062] / +0.022 [-0.027, +0.084] | -0.005 / -0.035 / -0.071 (CIs ~ +-0.1) |
| LIVE CLXV | 31 / 796 (134) | 0.157 (n 29) / 0.077 (750) | +0.080 [+0.024, +0.130] / +0.041 [-0.008, +0.083] / +0.043 [-0.013, +0.089] | +0.061 / +0.031 / +0.046 (CIs span 0) |
| SIM CLXV | 26 / 448 (87) | 0.150 (n 23) / 0.097 (368) | +0.053 [-0.017, +0.140] / +0.032 [-0.042, +0.125] / +0.019 [-0.047, +0.101] | +0.028 / +0.007 / -0.009 (CIs ~ +-0.1) |
- (a) The SIM's boards match live around the decision: princess HP lost in the next 15 s after a press 0.121 live vs 0.120 SIM (CLXIII / p2init),
  0.157 vs 0.150 (CLXV), after a held moment 0.075 vs 0.078 and 0.077 vs 0.097 (SIM pressed n 23-43: SE ~0.03). Like for like the two agree.
- (a) The contrast pressed - held is POSITIVE everywhere (live CLXIII adjusted +0.036 [+0.026, +0.047] = ~175 HP at 15 s): the head presses when the
  push is already on the tower. The listed covariates do not remove that. (b) So the observational estimate cannot size the freeze's saving (selection
  is larger than the effect, CIs +-0.02 live / +-0.1 SIM); what it does show is that live and SIM behave alike under the same estimator.
- (b) Confounding stated plainly: the model chooses when to press; the live logs have no randomisation. Unconfirmed taps sit in the pressed group
  (371 of 398 taps were confirmed in the 10-30 / 10-31 logs = 93%; the `conf` join in the parse output is empty because of a 24-byte head slice, fixed in the
  script, data not re-parsed).
### 9.5 Verdict
- **The SIM's ~0 freeze value is not an engine under-power (c: contradicted).** The engine's freeze reproduces every frame of 220 live records with
  419 presses (233 on >= 6-elixir pushes), and the same records break under a 10% leak, a 20% radius change, a 1-s shorter cube or a weaker slow. No
  mechanic (duration, radius, slow, targeting, cube timing) is shown wrong; the one IW cube row that fails is 1 record of 37 with a press (153413).
- What the engine says a press is worth: hundreds of HP of our princess at the moments the head presses (+312 at 7.5 s, +607 at 15 s) but ~+60-90 at
  held moments (7.5 s) and 0 with nothing in the cube; heavy-tailed (45% of presses change nothing). The SIM's forks reproduce that split. The value is rare-moment,
  so a decision-level mean of ~0 (section 8: match end +0.009 [-0.055, +0.082] over all >= 6 moments) is what the engine predicts for forced presses, net of 2 elixir.
- (b) Not shown here: that the match-end price is right as a policy price (adaptive continuation, offence cost, noise; no per-decision live reference can exist),
  and the CLXV critic bias of 8.1 stands. The "stop pressing" the trainer learned is therefore not an engine artefact: it comes from rare, heavy-tailed value,
  a certain 2-elixir cost, and a critic / credit signal that cannot see the rare large saving. Owed if the owner wants the last link: a policy-in-the-loop fork
  from RECON-reconstructed live states (press vs hold, adaptive), which would put live and SIM on exactly one estimand.

## 7. Next steps (in order)
1. DONE in round 2 (section 8). Remaining: ~2 more 48-match runs per policy for the 0.05 half-width; a live reference for the
   freeze's HP saving: DONE in section 9 (FREEZE-LIVE: the engine reproduces 419 live presses frame for frame, so it does not
   under-power the freeze; the saving is concentrated in a minority of moments). Owed (b): one policy-in-the-loop fork from RECON
   reconstructed live states (press vs hold, adaptive) to put live and SIM on one estimand; the CLXV critic bias (8.1) stays.
2. DONE (cf_iw_block_ticks, c95368e). For CLXV the critic bias (8.1) is the training-side item: a critic refit on states after
   presses, or match-end returns for the iw triggers once their SNR allows.
3. Rocket: re-run the audit with RECON-7's tap_hold in the continuations once it is a training key, and with an opponent
   calibrated on X-Bow defence (OPP-PUSH); the finishing-Rocket class (+0.14, n 7) needs ~100 samples to be a usable signal.
4. Production: Java forks (JAVA_FORKS.md) or cf rows under micro_batch before any fork credit can train at pilot2 scale.
