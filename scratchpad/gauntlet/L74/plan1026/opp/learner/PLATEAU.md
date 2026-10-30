# OPP-PLATEAU: why opponent RL from ftR stops at CLXIII D3 73-80% (bar 30-50%), and the one next experiment

Grades: (a) measured (number + source), (b) plausible but untested, (c) contradicted by the data.

## STATUS: FAST-LIVEOPP -- the fast loop plays the 'live' CLXIII partner (2026-10-30 ~15:20 UTC; keep current) -- RESTART POINT
- BOTTOM LINE (a, 15:15 UTC): NOT yet usable for the arm. The board context is exact, but the live stack's rocket_tornado
  combo returns decisions with `follow_ups` (the 2nd card of Rocket + Tornado), which production plays through
  Match._apply_follow_ups (e1_eval.py:1534: 2-tick reader frames, follow_up_verdict / follow_up_have on the engine's exact
  elixir, a landing queue, the next decision after the last landing). CfTrain has no such schedule: the corrected 48-job
  compare (CLXIII on icebow, `/workspace/fliv/out/cmp_live2_u5_48.json`) = **47 / 48 matches identical**; the 3 diverging
  sides (sp0005_05 opp#0 + its learner #0, sp0005_07 opp#1) all diverge on the decision right AFTER a `why: rocket_tornado`
  play (prod next tick 2730 vs fast 2720; 3272 vs 3280). The first msg (census decks) had no combo, hence 16 / 16.
  Guard committed: producer raises NotImplementedError on a live decision with follow_ups (never silently wrong), so the
  live config now stops at the first combo. Remaining = port _apply_follow_ups into CfTrain (spec: LOOP_INT.md
  FAST-LIVEOPP "Follow-ups"), then re-run the 48-job compare (bar 48 / 48).
- DONE (code, a): commits 33d1c0c + 9dd1cc8 (9dd1cc8 = 33d1c0c minus another worker's uncommitted TARGET-OBS hunks it swept
  in; CFTGT's bfc560e then restored both sets). producer.py:702's refusal is gone for a 'live' seat. Design + spec:
  pilot/loop/LOOP_INT.md "FAST-LIVEOPP".
- Correction to the section below (c): "Porting = a Java BoardState export" -- the export ALREADY existed: LOOP-CTX's
  `speed/crforge/obsid/CfCtx.java` + `cf_ctx.py` (2542689, 10-28) = match_kwargs at this exact live option set, identical on
  45,211 (+44,982 hero) facade seat-rows (`obsid/results/ctx_live*.json`). This ticket only wired it into CfTrain / producer.
- Exactness (a, 33903 /workspace/fliv/out/cmp_live_b8.json): compare.py, production actor_main vs the fast loop, cuda,
  8 in flight: **16 / 16 matches identical**, every side's decisions identical (learner timing seat + the CLXIII live seat),
  ability presses 18 / 29 per side both paths, memory tables 16 / 16; lp max card 8.1e-7, cell 1.2e-6 (bar 1e-5);
  4,397 partner rows went through the live decide (producer stats live_rows). Message = an opponent-arm dump
  (oplc_flv0_l01_lr3 u0000: the m10 timing learner) rewritten by `msg_live.py` to the live run's partner keys
  (league_frozen_opponent CLXIII, league_opp_policy live, league_opp_live from oplc_ftR_l0003_live/config.yaml), every job
  vs that frozen CLXIII. CAVEAT (a, found after): that first msg_live MERGED the old opp spec, so CLXIII kept each job's
  original opp deck (census decks for the 'init' partner jobs) -- exact on both paths, but fewer Rocket / Log / X-Bow rule
  rows than the real run. Fixed: msg_live.py now writes production's spec (adaptive_opponents.opponent_pool's frozen entry,
  opp_deck = rl_royale.ICEBOW_DECK, as sample_matchups); the run below uses it.
- 48-job compare DONE (47 / 48, above). No-live regression DONE (a): original u0000 msg, RAW=1, 16 jobs: 16 / 16 identical,
  tables 16 / 16, lp max 8.1e-7 (no 'live' seat = unchanged). Nothing of mine left running on 33903 (used CPUs 178-179 only;
  250-255 were 100% busy with the production arm, whose STATUS range is 240-255). Files:
  `/workspace/fliv/out/cmp_live2_u5_48.{json,log}`, `cmp_raw_u0.{json,log}`. Read: `ssh ... -p 33903 root@157.157.221.29 'head -c 600 /workspace/fliv/out/cmp_live2_u5_48.log; head -c 600 /workspace/fliv/out/cmp_raw_u0.log'`.
  Then the smoke (step 2): `ssh ... -p 33903 root@157.157.221.29 'cd /workspace/fliv/cb && setsid nohup bash scratchpad/gauntlet/L74/plan1026/pilot/loop/fliv_smoke.sh fliv_live_smoke 178-179 >/dev/null 2>&1 < /dev/null &'` (log /workspace/fliv/out/fliv_live_smoke.out).
  Rerun: `cd /workspace/fliv/cb && R=/workspace/oplm/cb2/scratchpad/gauntlet/L68/rl; JOBS=48 bash scratchpad/gauntlet/L74/plan1026/pilot/loop/cmp_live.sh $R/oplc_flv0_l01_lr3/fast_msg_u0005.pkl $R/oplc_ftR_l0003_live/config.yaml OUT.json --device cuda --in-flight 8 --matches 8 --threads 2`
  (tree /workspace/fliv/cb = `pilot/loop/fliv_tree.sh`: symlinks to /workspace/oplm/cb2 + its loop dir copied with the
  FAST-LIVEOPP producer / CfTrain applied to cb2's (older) producer; cb2 itself untouched).
- NOT DONE (remaining steps, in order): (1) read the two runs above (bar: N / N identical, raw 16 / 16). (2) a fast-loop
  smoke of opp_learner_calib_live.yaml (launch_arm.sh ... --smoke, on a tree holding these loop files: SMOKE PASS and the
  league line = frozen CLXIII). (3) measure s / update vs production's ~880 s (the "~6.5x" is (b): 880 s vs 160-240 s
  measured for the SAMPLED partner; the live partner adds CfCtx 22 us JVM + ~80 us Python per partner row (LOOP-CTX, a) and
  its forward runs in the producer, not serve.py). (4) the lead decides whether the running production arm
  oplc_ftR_l0003_live moves to the fast loop (resume from its checkpoint) -- not touched here.

## STATUS: the live-partner run (keep current; OPP-LIVEPARTNER, 2026-10-30 14:30 UTC) -- RESTART POINT
- RUNNING: `oplc_ftR_l0003_live` on 33903, PRODUCTION rl_royale (not the fast loop): timeout PID 81253 -> rl_royale PID
  81255 (+ 20 actor children), CPUs 240-255,180-185, CUDA learner, tree /workspace/oplm/cb2, started 14:24 UTC.
  Log `/workspace/oplm/logs/oplc_ftR_l0003_live.out`; train log `/workspace/oplm/cb2/scratchpad/gauntlet/L68/rl/oplc_ftR_l0003_live/train_log.jsonl`;
  checkpoints every 10 updates in `/workspace/oplm/cb2/icebow/data/bench/rl_royale/oplc_ftR_l0003_live/`. Cap 400 updates.
  Config = opp_learner_calib_live.yaml (pod sha 816728b8) + G's recipe (beta .003, lr 3e-5, th_anchor 10, ftR init); config sha 5cb9a41e6763.
  Launch / resume (resume = the same command + `--resume`):
  `bash scratchpad/gauntlet/L74/plan1026/opp/learner/launch_arm_prod.sh 33903 oplc_ftR_l0003_live 240-255,180-185 20 scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml beta0=0.003 beta_min=0.003 beta_max=0.003`
  Stop: `ssh ... -p 33903 root@157.157.221.29 'kill 81255'` (exact PID; check `pgrep -P 81255` is empty after).
- D3 loop (laptop): bash PID 16372 running a COPY `C:/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/arm_d3_live.sh`
  (= learner/arm_d3.sh, sha 519be4b0) `oplc_ftR_l0003_live 33903 33903 0-179 30 0040 0080 ... 0400`, appends to `out/lead_d3.log`.
  Stop: touch STOP_ARM_D3 in that scratchpad dir, or `Stop-Process -Id 16372`. If it is gone (account switch), restart from a NEW
  copy with the not-yet-scored updates only: `cp learner/arm_d3.sh <scratch>/arm_d3_live2.sh && bash <scratch>/arm_d3_live2.sh oplc_ftR_l0003_live 33903 33903 0-179 30 UNNNN ... >> learner/out/lead_d3.log 2>&1`.
- Monitor: `ssh ... -p 33903 root@157.157.221.29 "grep '^\[rl\] u0' /workspace/oplm/logs/oplc_ftR_l0003_live.out | tail -3 | cut -c1-260"`
  (the `frozen W/N` field = the training win vs the CLXIII live-stack partner); D3 lines in `out/lead_d3.log`.
- Why production: the fast loop REFUSED the config (a): smoke oplc_ftR_l0003_live_smoke -> `NotImplementedError: policy 'live':
  the fast loop samples` (producer.py:702). Not a small exact fix (a, code read): the fast loop's decide builds stand-in boards
  (`_prod_group`: s._cur = (tick, t_sec, my_elixir) only), while the LIVE_OPTIONS rules read the engine BoardState
  (decision_options.match_kwargs: m._cur[1] towers / units, m.state crown_towers for lethal / rocket_dead_target / xbow_dead_lane /
  tau_threatened). Porting = a Java BoardState export + a compare.py exactness pass = a separate ticket. Production smoke
  oplc_ftR_l0003_live_psmoke2 (8 actors, max_updates=2): SMOKE PASS (a); both updates' matchups = `frozen:...CLXIII_NOLEAK.pt`
  only; the merged config carries league_opp_live; live_opp_cfg merges it for opponent type frozen (rl_royale.py:1793, pod tree).
  (Smoke note: `--smoke` does NOT cap updates when max_updates is passed as an override: the first psmoke ran to u11 and was
  stopped by PID; pass max_updates=2 after the others.)
- u0000 (a, log 14:39 UTC): 256 matches, rollout 855 s + update 27 s = ~880 s per update (fast loop 160-240 s); training win
  vs the live-stack partner 28/256 = .109, = ftR's D3 opponent win .110 (the sampled partner gave .14-.16 at u0: the sanity
  check passes, read as a check only, SE ~2 pp). At ~880 s: u40 (first D3) ~00:10 UTC 10-31, u80 ~10:00, u160 ~2026-11-01 05:30
  (b: extrapolated from one update; the pod's load changes with other jobs).
- Success (from "Next experiment"): D3 opponent win at or above G at u80 (G 23.8%) and u160 (G 26.7%), AND training win vs the
  partner within ~3 pp of D3 at the same checkpoint (transfer near 1). Plus the v6 quick card at each D3 (G u160 RMS .30).
  Init sanity check (b): u0's training win vs the live partner should sit near ftR's D3 opponent win (.11), not .14.
  For curves.py: the partner's matchups are `frozen:...`, not `exploiter...`: add that prefix first.
- Seed check oplc_ftR_l0003_s1 (G's recipe, seed 1) STOPPED at u48 (owner priority) by exact PID (33903 60962 / 60963; laptop D3
  loop 2916); checkpoints u0000-u0040 kept on 33903. Results kept (a): D3 u40 390/480 CLXIII = opponent 18.7% (G u40 16.3%; the two
  differ by 2.4 pp, ~1 SE of the difference). Training win vs the sampled partner per 10 updates (curves.py 10, n ~1,400 each):
  .157 (u0-9) .163 .217 .247 .233 (u40-48) = G-family arms' curve (C u20-39 .232).
- Codex dispatches: none (launch + diagnosis + 2 smokes needed decisions at each step).

## STATUS (2026-10-30 ~14:30 UTC, OPP-PLATEAU, account 3) -- superseded by the section above
- DONE: diagnosis from data on disk only (no games, no training, no pod writes). Proposed config written and checked with
  rl_royale's own validators on the laptop. NOT launched (33903's GPU is full: 23.0 / 24.6 GB with the seed check
  oplc_ftR_l0003_s1 + other jobs; 33308 runs the pilot; 30408 is down).
- Seed check oplc_ftR_l0003_s1 (33903, PIDs 60962 / 60963, G's recipe at seed 1): untouched. At u43 its training curve
  matches C's / G-family arms (training win vs the CLXIII partner .161 at u0-19, .232 at u20-39, .240 at u40-43).
- Restart point: the "Next experiment" section below (smoke first, then the launch, then the D3 loop).
- Data (local, not tracked: bulk): `.foreman/scratch/plateau/logs/*.jsonl` (train_log.jsonl of 7 runs) and
  `.foreman/scratch/plateau/m/RUN/w16_matches_uNNNN.json` (per-match outcomes). Scripts (tracked copies in `plateau/`):
  `curves.py [BIN]` (per-bin training curves), `transfer.py` (training win vs D3), `trend.py` (slopes),
  `live_subset.py` (D3 stack -> league_opp_live dict), `check_live_yaml.py` (validators). Outputs: `plateau/curves20.txt`,
  `plateau/transfer.txt`, `plateau/trend.txt`.
- Re-fetch (read-only): 33903 `/workspace/oplm/cb2/scratchpad/gauntlet/L68/rl/RUN/{train_log.jsonl,w16_matches_u*.json}`
  (runs l0001_a10, l0003_s1, l003_lr1e4); 33308 `/workspace/oplc/cb2/.../rl/RUN/` (l001_a10, l003_a10, l01_a10) and
  `/workspace/oplc/cbd/.../rl/oplc_ftR_l003_a10_tpg32m/`. Arm G (oplc_ftR_l0003_a10b) and E (bot100) train logs are on
  stopped pods (30408, 33553): only their D3 rows exist.
- Codex dispatches: none (the work was diagnosis; the fetches were 3 tar commands).

## Bottom line
1. (a) The opponent is NOT stuck in training. Its win rate against the training partner (CLXIII, sampled T .5 decode)
   keeps rising in every weak-pull arm: arm C (beta .01) .161 (u0-19) -> .332 (u160-179) -> .357 (u320-339), slope
   +3.3 +- 0.3 pp per 100 updates over u40-u334 (`trend.txt`).
2. (a) Only about half of that gain reaches D3. Over 24 scored checkpoints of 6 arms:
   **D3 opponent win = 0.053 + 0.51 x training win vs the partner** (r 0.78; `transfer.txt`). The gap grows with training:
   +3 pp at the init (ftR: training .141 vs D3 .110), +4 to +8 pp at u40, +6 to +14 pp after u120 (arm C u320: training
   .355, D3 .219).
3. (a) The clearest case: arm F (lr 1e-4) gains in training (+5.6 +- 1.8 pp / 100 updates) while its D3 gets WORSE
   (-2.6 +- 0.3 pp / 100 updates; 16.9 -> 15.6 -> 14.8% opponent win). Larger steps fit the training partner faster and
   fit D3's partner less.
4. (a) The D3 "plateau" is partly the stop rule's resolution: arm C still climbs +2.4 +- 0.7 pp of D3 opponent win per 100
   updates (8 checkpoints, u40-u320); the rule (2 pp in 50 updates) cannot see 1.2 pp per 50 updates through a 480-game
   block (SE ~1.9 pp). At that rate the bar (opponent win 50-70%) is ~1,100 more updates away (b: linear extrapolation of
   a curve that is slowing).
5. So the opponent stalls for two reasons that multiply: (i) it trains against a different CLXIII than D3 scores (transfer
   0.5), and (ii) its training gains are slow and slowing (arm C: +10.7 pp per 100 updates over u0-u170, +1.6 over u170-u330). The one next
   experiment fixes (i), which has a measured size and a precedent fix in this repo. Nothing on disk says any single
   config reaches the bar soon; (ii) needs a second step (ranked list below).

## Candidate causes, each with its measurement

All numbers from `curves20.txt` (20-update bins, n ~3,000 CLXIII-partner matches per bin, SE ~0.8 pp) unless marked.

| cause | measurement | grade | reading |
|---|---|---|---|
| Partner mismatch (sampled T .5 CLXIII in training vs the LIVE_OPTIONS stack in D3) | D3 = 0.053 + 0.51 x train (24 ckpts, r .78); gap +3 pp at init -> +9-14 pp after u120; F: train up, D3 down | **(a) main cause** | Half of what the opponent learns works only against the sampled partner. Precedent (a, OPP_MODEL.md section 7, W7 R3d/R4, 10-20): the same pattern on CLX (training up, D3 flat at 68%); CLX without its live stack won 63.8% vs 67.7% with it; training against the stack (`league_opp_live`) moved D3 to 63.7% (1,920 games) |
| KL stop / step size binding | kl_cell_stop 5.0 never fired (max KL cell 1.20, arm C u320); beta is fixed (beta_min = beta_max), so no adaptive leash; clip fraction .08-.13 at lr 3e-5, .27-.28 at lr 1e-4; F (3.3x lr) = 2x the KL of B for +1.5 pp training and worse D3 | **(c)** | Bigger steps buy KL, not D3 |
| Pull beta binding | training win vs the partner: beta .1 (A) .20 (u80-99), .03 (B) .25, .01 (C) .30, .001 (H) .31 (u100-139); C = H | (a) binds at >= .03 only | Below .01 the pull is no longer the limit; the sweep is exhausted |
| Entropy collapse | card entropy .70 -> .45, cell 2.82 -> 1.91 by u320 (C; -35% / -32%); guard floor (0.5 x init) never hit; G u160 quick RMS .30 = ftR's | (c) as the cause | Entropy falls while training win still rises; no collapse signature (training would flatten first) |
| Advantage noise (win-only reward, LOO over G 4) | CLXIII groups with mixed outcomes (the only ones with a gradient) .44 at u0-19 -> .62-.66 after u100; CLXIII share of the batch's \|A\| mass .45-.60; 6.7-7.2k learner rows per update (27 plays / match x 256 matches); F: 3.3x lr does not speed training | (a) signal is available but slow; (b) noise-dominated update | For our model (pilot, WITH a critic of explained variance .92) the policy critical batch is >= 230 matches, point ~1,200 (pilot/lrn/SCALE.md 6e, a). The opponent's match_loo has no critic, so its update is very likely noise-dominated too (b: noise_scale.py was never run on opponent records) |
| Card / cell only (timing head frozen + th_anchor 10) | plays/min flat 8.0-8.4 in every arm (ftR 7.94); WHERE_G: P(any play within 10 s after our X-Bow) 94.5% -> 93.4%; arm D (timing_pg 32, th_anchor kept) +1.5-3 pp training win over B from u80 (u100-119 .281 vs .250), D3 CLXIII win not different (82.3 / 85.8 / 78.8 / 80.4 vs B 84.6 / 80.4 / 79.8 / 81.5) | (a) timing does not move; (b) it caps the response to X-Bow | Third-ranked lever; its gradient is 2.7x noisier at K 32 (OPP_LEARNER.md, a) |
| Model capacity | training win still rising at u320 (C); KL keeps growing (the net still finds new policies) | (b) not binding now | Would show as flat training win with large updates; not seen |
| Data per update | 256 matches, ~7k rows; SCALE 7f (our model): 128 vs 1,024 matches per update not resolvably different per update (+0.6 +- 1.0 pp) | (b) | A bigger batch costs wall time linearly; no evidence it pays per hour |
| Table / engine version | ftR 89.4% (16.402.22) vs 89.0% (16.635.3); B u160 81.7 vs 81.5 | (c) | lead_d3.log 10-29 15:28 |
| Init partner dilutes the signal | D3 CLXIII win, arm E (100% CLXIII partner) 77.5 / 82.5 / 77.7 / 77.9 vs B 84.6 / 80.4 / 79.8 / 81.5 (u40-u160) | (c) as a cause; (a) dropping it is harmless | Used below: the proposed config is 100% CLXIII |

Other train / eval differences that remain after the fix (b, untested; each a possible part of the residual gap): D3's
G2 tap handicap (--tap-loss / --tap-slow), own_effects, afford_ticks 23, follow-up taps (the fast loop refuses all five:
producer.UNSUPPORTED_CFG); D3's live census decks vs the training census (icebow/data/rltest/decks_rl.json); levels
(D3 all16; the fast loop defaults to 16 for both sides, producer.py:454, b).

## Next experiment (ONE change vs arm G's recipe): the CLXIII partner plays D3's decision stack

**What:** `learner/opp_learner_calib_live.yaml` = opp_learner_calib.yaml with the partner switched from
`league_exploiters` (CLXIII, sampled T .5 / T_gate .1 / tau_phase, 60%) to `league_frozen_opponent: CLXIII NOLEAK`
(icebow deck, 100% of matches = arm E's share, measured harmless) + `league_opp_policy: live` + `league_opp_live` = the 22
DecisionOptions fields of LIVE_OPTIONS that the fast loop supports (derived by `plateau/live_subset.py` from
livecal.LIVE) + tau .35. Recipe otherwise = G: ftR init, beta .003, lr 3e-5, th_anchor 10, timing / ability frozen.
Checked (a, laptop, `plateau/check_live_yaml.py`): rl_royale.validate_league + adaptive_opponents.validate pass,
league_opp_live parses (23 fields), the opponent pool = the frozen CLXIII only. Changed keys vs the calib yaml: exactly
league_exploiters, league_frozen_opponent, league_opp_live, league_opp_policy.

**Why this one:** it is the only cause with a measured size on this data (transfer 0.51) and a fix that already worked
once in this repo on the same symptom (W7 R4: training win vs the partner fell .49 -> .28-.33 at once, then D3 moved
past its plateau, 68.1% -> 63.7% on 1,920 games). Expected gain (b): D3 tracks the training curve at a slope near 1
instead of 0.5, i.e. about 2x the current D3 gain per update; by u160 roughly D3 opponent win 30-35% (CLXIII 65-70%)
instead of G's 26.7%. It does not by itself reach the 50-70% bar.

**Untested (b), so the smoke decides:** whether the fast loop plays a `frozen` opponent with `policy live` + DecisionOptions
rules (producer: fast_ok is False for this seat -> `_prod_group`, production's decide; never exercised with this config).
If the smoke refuses, the fallback is the production rl_royale path (run_calib.sh style; 1,173 s per update with 20 CPU
actors vs 180-240 s in the fast loop, OPP_LEARNER.md) or a fast-loop port ticket. Do not drop the experiment on a refusal.

**Commands** (next account; pod with a free GPU: 33903 after the seed check stops, CPUs 240-255,180-185; never 33308):
1. Copy the yaml into the pod tree:
   `scp -P 33903 -i ~/.ssh/runpod_clashbot scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml root@157.157.221.29:/workspace/oplm/cb2/scratchpad/gauntlet/L74/plan1026/opp/learner/`
2. Smoke (2 updates; must print SMOKE PASS, and the log's league line must show the frozen CLXIII opponent):
   `bash scratchpad/gauntlet/L74/plan1026/opp/learner/launch_arm.sh 33903 oplc_ftR_l0003_live_smoke 240-255,180-185 /workspace/venvf16/bin/python scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml beta0=0.003 beta_min=0.003 beta_max=0.003 --smoke`
   Also check that the partner really runs the stack: u0's training win vs CLXIII should sit near ftR's D3 opponent win
   (.11) rather than the sampled partner's (.14); with ~256 matches that difference is ~1.5 SE, so read it as a sanity
   check, not a test.
3. Launch (after a PASS; rl_royale refuses an existing run dir, so the smoke uses its own name):
   `bash scratchpad/gauntlet/L74/plan1026/opp/learner/launch_arm.sh 33903 oplc_ftR_l0003_live 240-255,180-185 /workspace/venvf16/bin/python scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml beta0=0.003 beta_min=0.003 beta_max=0.003`
4. D3 every 40 updates (copy of the script, never the running one):
   `cp learner/arm_d3.sh /tmp/arm_d3_live.sh && bash /tmp/arm_d3_live.sh oplc_ftR_l0003_live 33903 33903 CPUS WORKERS 0040 0080 0120 0160 0200`
   (CPUS / WORKERS: whatever the eval pod has free; earlier blocks used 15 workers.)

**Read-out:** compare D3 at u40 / u80 / u120 / u160 with G (16.3 / 23.8 / 23.1 / 26.7% opponent win) and C. Success =
D3 at or above G at u80 and u160, AND training win vs the partner within ~3 pp of D3 at the same checkpoint (transfer near
1). Human-likeness: the v6 quick card (RMS, lock, P(lock|fail)) at each D3, as for G (RMS .30). Note for `curves.py`: the
partner's matchups are logged as `frozen:...`, not `exploiter...`; add that prefix before reading the new run.

## If it works, what next (ranked; each one change)
1. (b) Lower-variance advantage: `advantage: gae` with the critic on the existing value head + potential-based
   `tower_phat` shaping (the pilot's reward variant iii; the fast loop records tower_phat). Never run on a timing-head
   learner: needs a smoke, and the lead's OK because it changes the opponent's training reward (potential-based, so the
   optimal policy is unchanged). Measure first: `pilot/lrn/noise_scale.py` on one opponent rollout dump (FASTLOOP_DUMP=1)
   to get the opponent's own critical batch.
2. (b) Timing in PPO with a weaker timing pull: arm D's timing_pg kept th_anchor 10. A th_anchor 1 arm (timing_pg 32,
   micro_batch 256) is the test of whether the frozen response timing caps the X-Bow answer (plays/min flat 8.0-8.4 in
   every arm, a). Human-likeness risk: timing is what levels A / B score.
3. (b) Cheap eval-only check, no training: G u160 in D3 at opp_T .5 instead of 1.0 (one 480-game block). W7 R1 found
   T worth <= 3 pp on a gate model; untested on the timing-head model.
