# SIMPRICE (account 3, 2026-10-31): does the SIM price Rocket and the Hero IW press as losses, and why

Owner ask 10-31: the model must learn to use Rocket and the Hero Ice Wizard ability at the right moments. Lead's diagnosis to
test: the SIM prices both as losses. Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.

## STATUS (keep current) -- 2026-10-31 ~15:25 UTC: DONE_WITH_CONCERNS, nothing of mine running
- Step 0 DONE (section 1). Step 1 DONE: spa1 (CLXIII's head, sections 3.1 / 4), spa2 (CLXV's head, section 3.2). Step 2: Rocket
  landing artifact found + fixed (section 2); IW: no loss at CLXIII's own press moments, but an added press is NOT priced positive
  even on > 6-elixir pushes for CLXV (section 3.2): candidate wrong sign vs the doctrine, causes listed, not yet isolated.
  Step 3: IW triggers built, smoke-tested in a real policy update (33308 GPU 1, section 5); the opt-in config
  cf/simprice_train.yaml is BLOCKED for the press-restoration goal (on CLXV it would push presses DOWN further) until 3.2's
  valuable-class sign is resolved. Rocket family stays OFF (no positive class except the finishing Rocket).
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

## 7. Next steps (in order)
1. IW valuable-class sign (3.2): run iw_press only (p 0.2) on CLXV with cf_audit_p 1.0 (terminal for every sample) and on p2init
   with K 3: does a press with > 6 elixir / a win condition in the freeze turn positive at the end? Then test causes 1-3.
2. Hold-window variant (b, not built): an iw_hold that also blocks re-presses for N ticks in the fork (opt-in key; one inert line
   in e1_eval.ability_decide) = "freeze vs no freeze at all" at CLXIII's press moments (today's iw_pressed is "now vs a moment later").
3. Rocket: re-run the audit with RECON-7's tap_hold in the continuations once it is a training key, and with an opponent
   calibrated on X-Bow defence (OPP-PUSH); the finishing-Rocket class (+0.14, n 7) needs ~100 samples to be a usable signal.
4. Production: Java forks (JAVA_FORKS.md) or cf rows under micro_batch before any fork credit can train at pilot2 scale.
