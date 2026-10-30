# PILOT checkpoint: SIM gate vs CLXIII -> 30-match live trial -> 150-match block -> ICEBOW Mark CLXV (PILOT-GATE, 10-30)

Labels: (a) measured (number + source), (b) plausible but untested, (c) contradicted. Owner bars (binding, 10-29; memory
`owner-1029-pilot-closeout-plan.md`): SIM gate = pooled paired 95% CI low > 0 vs CLXIII; live = 30-match safety trial,
REVERT if <= 5/30 wins or idle-on-threat worse; then a 150-match block, KEEP only if the Wilson 95% lower bound > 32.7%.

## STATUS / RESTART POINT (keep current)
- 10-30 ~10:05 EDT: everything below is ready. Nothing of mine is running (33903 dry-run + repeat jobs finished; 33903 CPUs
  202-209 free again). Live untouched (CLXIII NOLEAK via the supervisor; CKPT_OVERRIDE / LIVE_OPTIONS / trial30.sh unchanged).
- Pilot `pilot_box3` (33308) is the lead's: lead 10-30 13:50Z synced auto_stop.py to 33308 and restarted it (PID 179581, log
  /workspace/loop/pilot/pilot_box3/auto_stop.log). **Owner 10:00 EDT: no hour cap any more**: it stops ONLY at 50 updates
  without improvement (hours arg 9999); pilot.yaml `max_updates: 1000` is the outer cap. FINAL marker + checkpoint land in
  /workspace/loop/pilot/pilot_box3/ (FINAL = the last numbered checkpoint
  /workspace/loop/cb/icebow/data/bench/rl_royale/pilot_box3/pilot_box3_uNNNN.pt).
- GATE-SAMPLE 10-30 ~12:00 EDT (8835bed + aaa1ad2, opt-in, absent = byte-identical): the SIM gate can now decode
  the pilot's TRAINED gate (gap.py --gate-sample T / gate.sh GATE_SAMPLE=T) and live can apply it per unit of time
  (--gate-sample-step-ticks 10) and deploy it from LIVE_OPTIONS; commands + open items: "Sampled-gate variant" below.
  Evidence (a): test_gate_sample_identity 6/6 (trainer decode == SIM / live decode with the same draws on 1,511 recorded
  live gate rows; GenPilot replay 1,511 draws 0 differ, per decision and per time); test_decide_identity 5/5 before and
  after; laptop SIM smoke absent = HEAD code 4/4 rows, sampled run deterministic 4/4. Nothing of GATE-SAMPLE is running.
- NEXT (in this order): (0) start the CLXIII BASE rows now (step 1a; they do not depend on the pilot); (1) when FINAL exists,
  candidate rows + score (1b-1c); (2) the lead / owner decides the two open questions in "Decisions owed" (gate decode and
  trial30 bar); (3) live trial (step 2); (4) block (step 3); (5) bookkeeping (step 4).

## Decisions owed (lead / owner) before live
1. **Gate decode (b, untested effect).** The pilot TRAINS a sampled gate at T_gate 0.1 (pilot_box3 config.yaml `T_gate: 0.1`).
   The SIM gate (gap.py D3 = the live stack) and live today both use the THRESHOLD gate (tau .35 + rules). Live has
   `--gate-sample T` (live_play, off by default, LOOP-OPS 10-28 tested); the SIM gate does NOT (search_s0 has no such flag;
   decision_options.decide already takes `gate_sample` + `gate_rngs`). Options: (A) gate and deploy with the threshold gate
   = what the commands below do, consistent SIM <-> live, no new code; (B) deploy with `--gate-sample 0.1` = an opt-in
   search_s0 flag first (eval edit: pyflakes + absent-key identity) AND a LIVE_OPTIONS change for the pilot only, and the
   revert must restore LIVE_OPTIONS too (deploy_ckpt.sh swaps only the checkpoint). Recommendation: (A) (one change at a time).
   **GATE-SAMPLE 10-30: (B) now has its code** (opt-in, absent = byte-identical): see "Sampled-gate variant" below for the
   gate + deploy commands and what is still open. (c) correction: the LOOP-OPS README line "deploy = add `--gate-sample 0.1`
   to LIVE_OPTIONS" did NOT work before this ticket: live_options refused the file (argparse exit 2, lo_check.py).
2. **trial30.sh bar.** trial30.sh keeps a model iff wins >= 16/30 (the 10-22 rule vs CLX's 52%) AND idle <= base + 0.05. The
   owner's 10-29 pilot rule is REVERT iff <= 5/30 (keep >= 6/30). Run as is, trial30.sh would auto-revert a pilot at 6-15 wins.
   Ready, NOT applied (live tooling; lead's call): `git apply scratchpad/gauntlet/L74/plan1026/pilot/gate/trial30_minwins.patch`
   adds opt-in `MIN_WINS` / `IDLE_TOL` (unset = 16 / 0.05 = byte-identical behaviour; `git apply --check` passes on c51efd9;
   the patched awk with MIN_WINS=6, w 7, idle .20 vs .16 prints 1 = keep (a)). "Idle worse" = trial30's established
   `cand <= base + 0.05` (live-trial-30 memory); a strict "cand <= base" is IDLE_TOL=0.

## Sampled-gate variant (decision 1 = B; GATE-SAMPLE 10-30: 8835bed + aaa1ad2, all opt-in, absent = byte-identical)
What exists (evidence in STATUS above):
- (a) The three paths already shared ONE `decision_options.decide`: training (`e1_eval.sample_decide_batch`, decode
  'sample'), SIM (`decide_batch` <- search_s0 D3 via `match_kwargs`), live (`live_gen_v2.GenPilot.decide`). The sampled
  gate in the greedy decode = `decide(gate_sample=T, gate_rngs=...)` (63b0693): the trainer's formula, tau = the phase tau
  (+ tau_delta); tau_threatened and the hazard draw do NOT apply under it (the trainer has neither), finishers / barrel_lane
  / rocket rules still do.
- SIM: `search_s0 --gate-sample T` = `gap.py --gate-sample T` = gate.sh `GATE_SAMPLE=T` -> cfg `gate_sample` -> match_kwargs
  gives decide the gate T + ONE stream per match, seed SeedSequence([obs_seed('gate_sample:'+tag, k), decision_seed])
  (rng_decision_options untouched). Refused with --pipeline-decisions / without decision options. No per-time exponent in
  the SIM: a SIM wait advances exactly decide_every 10 ticks = the pilot's step (pilot.yaml decide_every 10) and a play's
  next decision is one draw, so k = 1 on every SIM row (a, structural: e1_eval Match.apply). The D3 job dirs' run.json
  carry `"gate_sample": T` only when set.
- Live: `live_play --gate-sample T` (per-match seed SeedSequence([decision_seed, match, 0x6A7E]), every draw a 'gate_draw'
  event with the seed) + `--gate-sample-step-ticks N` (default 0 = one trainer draw per decision): k = ticks since the
  previous decision / N when that one was a sampled WAIT, else 1 (first decision, after a play / no draw), cap 4 (2 s);
  fire iff u < 1 - (1 - p_b)^k; k is in the gate_draw event. Both flags are now LIVE_OPTIONS-deployable (aaa1ad2; before
  it the file refused them). (a) Live cadence on the 4 recorded CLXIII logs: 1,511 gate rows, k = 1 on 1,264, k < 1 on 119
  (2-8-tick gaps), k > 1 on 128 (mostly 11-12 ticks), mean k .968: per-decision live over-samples a little at the short gaps;
  the effect on a model's fire rate is (b) small, unmeasured.

Gate commands, sampled variant (same env + seeds as step 1; BASE stays CLXIII with the threshold gate = what is live, so
the comparison is "each model under its own deploy decoder"):
- Sync the code to the gate tree first (it is c51efd9 = the pilot's code; these files changed since only by opt-in hunks):
  `git -c core.autocrlf=false archive --format=tar aaa1ad2 pipeline/decision_options.py pipeline/search_s0.py pipeline/live_options.py scratchpad/gauntlet/L74/gap/gap.py scratchpad/gauntlet/L74/plan1026/d2g/gate.sh | ssh -o BatchMode=yes -i ~/.ssh/runpod_clashbot -p 33903 root@157.157.221.29 "cd /workspace/pgate/cb && tar xf - --unlink-first"`
  Check (owed, not run): `GATE_GAP=scratchpad/gauntlet/L74/plan1026/pilot/gate/gap_chunks.py GAP_CHUNKS=1` BASE iu40 on one
  seed = the 10-30 dry-run rows (repeat.sh's comparison) -> absent flag unchanged on the pod tree.
- 1b'. CANDIDATE: step 1b with `GATE_SAMPLE=0.1` added and tags `cands_e4` / `cands_iu40` (out /workspace/pgate/cands.out);
  1c with `cands_*` in place of `cand_*`. Optional: BASE with GATE_SAMPLE=0.1 (`bases_*`) = both models at the same decoder
  (separates "the RL helped" from "the sampled gate helped"); costs another 3,840 games.
- (a) laptop smoke (royale venv, search_s0 plain, gen_s0 vs gen, 4 seeds, D3 subset): --gate-sample 0.1 ran, rows differ
  from the threshold run 4/4, a re-run gives 4/4 identical rows (seeded per match).

Live commands (lead / owner only; never a worker):
- Back up, then append to LIVE_OPTIONS for the pilot only:
  `cp scratchpad/gauntlet/L70/live/LIVE_OPTIONS scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_clxv && printf ' --gate-sample 0.1 --gate-sample-step-ticks 10\n' >> scratchpad/gauntlet/L70/live/LIVE_OPTIONS`
- Offline check: step 2.3 (`CKPT=<CLXV> start_live.sh icebow --no-fast-plays --ranked --check`) -> LIVE_CHECK_PASS whose
  live_options.from_file shows gate_sample 0.1 + gate_sample_step_ticks 10. (a) the same --check through live_play.py
  directly (CLXIII, CPU, merged-reader env) passes with such a file. After the first live match:
  `grep -c '"event": "gate_draw"' <newest live_play_*.jsonl>` > 0 and the events carry seed and k.
- REVERT must restore LIVE_OPTIONS too: `cp scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_clxv scratchpad/gauntlet/L70/live/LIVE_OPTIONS`
  BEFORE the deploy_ckpt.sh CLXIII line (step 2.5); deploy_ckpt.sh / trial30.sh swap only the checkpoint, so trial30's
  automatic REVERT would leave CLXIII running with the sampled gate (see open item 2).

Still open (restart point):
1. (b) start_live.sh --check with the edited LIVE_OPTIONS was not run (start_live.sh is live tooling; a worker
   must not run it); live_play.py --check directly passed (above).
2. trial30.sh / deploy_ckpt.sh do not restore LIVE_OPTIONS on REVERT: a LIVE_OPTIONS backup/restore hook is needed if the
   sampled gate is deployed through trial30 (live tooling: lead's call), else revert by hand as above.
3. livecal.LIVE (the SIM config generated from LIVE_OPTIONS, PLAN P1) skips EXTRA_LIVE_FLAGS, so a deployed --gate-sample is
   NOT picked up by gap.py automatically and livecal's live_options_diff does not refuse a gate mismatch: pass GATE_SAMPLE by
   hand. Closing this = livecal reading gate_sample from LIVE_OPTIONS (not done; one change at a time).
4. The pod sync + absent re-check above; a flag-on rate check with the PILOT checkpoint
   (`pilot/ops/gate_sample_check.py <pilot ckpt> 0.1 0,1,2 OUT.json`; 10-28 ran it with CLXIII only).

## Findings from the dry run (10-30)
- (a) The gate runs a memory model on crforge 5e8089a4 + tables 16.635.3 end to end: pilot_box3_u0000 (sha 3218c3a9) played
  36 E4 + 12 iu40 games; pair_both.py scored them (e4 +0.00 [-13.53, +13.53] n 36; cal -25.00 [-50.59, +0.59] n 12; pooled
  -6.25 [-18.50, +6.00] n 48 -> FAIL, a 48-game block means nothing; it proves the pipeline). Nothing broke; no code fix needed.
- (a) The SIM gate is deterministic: the iu40 chunk re-run (repeat.sh) gave identical (outcome, plays, end tick, tower HP
  diff) on 12/12 CLXIII games and 12/12 candidate games.
- (a) pilot u0000 is NOT CLXIII in the SIM: identical games only 5/36 (e4) and 2/12 (iu40). Cause: the trunk + heads are
  identical (191 / 191 model tensors == B0, max diff 0; ckpt_diff.py) but the IW ability head `rl.ability_head` is re-fit by
  the run's ability warm start (14,512 BC rows vs B0's 13,026; max |w diff| 0.77; B0's head == CLXIII's exactly;
  meta_diff.py). In the dry run the pilot pressed 66 times vs CLXIII's 50 (p_mean .0169 vs .0131, 36 e4 games). That the
  press head explains ALL the divergence is (b) (it is the only weight difference; not ablated). Consequence: a pilot gate
  result mixes the RL change with a re-fit press head; this is how rl_royale starts every run (CLXIII's head came from its own
  warm start), so it is by design, not a bug -- the lead may want it stated in the CLXV note.
- (a) Live path: the pilot u0000 loads on the laptop: `CKPT=<u0000> start_live.sh icebow --no-fast-plays --ranked --check`
  -> LIVE_CHECK_PASS sha 3218c3a9 (feature_version 6, cuda). On the 4 recorded CLXIII live matches (b0_identity.py run/compare,
  CPU) the pilot u0000 gives 1,718 / 1,718 identical decision dicts, taps and RNG states, max |log-prob diff| 0 for card / cell
  / gate / value / wait / g -> IDENTICAL (presses are fed from the log there, so the re-fit press head is NOT covered).
- (a) Memory in the live path exists and has run live: live_gen.GenPilot.memory_rows builds the MatchMemory on the laptop
  from reader frames (live_gen.py ~280); ICEBOW Mark CLXIV: MEMORY ran live 10-26 09:38-12:43 (CKPT_OVERRIDE.pre_20261026_*);
  memory/live_replay.out: 2,013 / 2,013 decisions identical live path vs the offline build, memory_rows median ~0.8-1.0 ms.
  The LF s1c meta (model_gen.check_memory_meta) loads on the laptop (the --check above).
- (a) Code: 33308's /workspace/loop/cb (the pilot's tree) == c51efd9 for search_s0 / decision_options / model_gen /
  match_memory / crforge_core / CfCore.java after CR stripping. The gate tree /workspace/pgate/cb on 33903 = c51efd9. Main has
  moved on (76d762e MEM-FULL: match_memory opt-in e_max); keep gating on c51efd9 (the pilot's code).
- (a) Speed on 33903 (load ~77-90 on a 54-CPU cgroup): ~35-47 s per game per worker (12-game chunk ~8 min).

## Step 0: get FINAL onto the gate pod (laptop, repo root)
```
K="-o BatchMode=yes -o ConnectTimeout=30 -i $HOME/.ssh/runpod_clashbot"; S="ssh $K root@157.157.221.29 -p"
F=$($S 33308 "cat /workspace/loop/pilot/pilot_box3/FINAL")   # fastloop.py writes the last numbered checkpoint's path ("none" = no checkpoint)
case $F in /*) ;; *) F=/workspace/loop/cb/$F ;; esac; echo "$F"   # (b) the path may be repo-relative
$S 33308 "sha256sum $F"; $S 33308 "cat $F" | $S 33903 "cat > /workspace/pgate/ck/$(basename $F) && chmod 444 /workspace/pgate/ck/$(basename $F) && sha256sum /workspace/pgate/ck/$(basename $F)"
mkdir -p C:/Users/benpe/pod_backup_weekend/loop/pilot_box3 && $S 33308 "cat $F" > C:/Users/benpe/pod_backup_weekend/loop/pilot_box3/$(basename $F) && sha256sum C:/Users/benpe/pod_backup_weekend/loop/pilot_box3/$(basename $F)
```
All three shas must match. (Never copy `_latest.pt` as the candidate; FINAL is a numbered file.)

## Step 1: SIM gate vs CLXIII (pod 33903, tree /workspace/pgate/cb; ~3,840 games per model)
Env (identical for base and candidate; the pilot's SIM: crforge 5e8089a4, tables 16.635.3, barrel decoy on; gap.py itself
sets ROYALE_HEROIW_PRESS=live for its workers):
```
cd /workspace/pgate/cb && export GATE_CB=/workspace/pgate/cb GATE_PY=/workspace/venvf16/bin/python \
  GATE_LIB=/workspace/crforge_main/5e8089a4/plain/lib GATE_TABLES=/workspace/oplm/tables/16.635.3 GATE_FACADE=/workspace/pgate/facade \
  GATE_EV=/workspace/pgate/ev CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=1g JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
G=scratchpad/gauntlet/L74/plan1026/d2g/gate.sh; SEEDS="741200 742000 743000 744000"
```
1a. BASE (CLXIII NOLEAK, GATE_CKPT unset; start now): `setsid nohup bash -c "bash $G crforge base_e4 e4 <CPUS> <W> $SEEDS; bash $G crforge base_iu40 iu40 <CPUS> <W> $SEEDS" > /workspace/pgate/base.out 2>&1 < /dev/null &`
1b. CANDIDATE (after step 0): the same with `GATE_CKPT=/workspace/pgate/ck/pilot_box3_uNNNN.pt` and tags `cand_e4` / `cand_iu40`
   (out `/workspace/pgate/cand.out`). Each block resumes: a seed dir with 480 rows is skipped, a partial one is re-run.
   CPUS / W: check `uptime` + `cat /sys/fs/cgroup/cpu.max` (33903 = 54.4 CPUs cgroup cap) and the other jobs' `taskset -cp`
   first; W = free CPUs. Duration (b, from the dry-run rate ~40 s/game/worker): 3,840 games x 40 s / W -> W 40 ~1.1 h per model,
   W 20 ~2.1 h; two models ~2.2 h at W 40. On 33308 after the pilot ends (more CPUs) the same commands work with
   GATE_CB=/workspace/loop/cb, GATE_TABLES=/workspace/crforge_cache/tables/16.635.3 and a facade compiled as below.
1c. SCORE (owner bar): `/workspace/venvf16/bin/python /workspace/pgate/pair_both.py '/workspace/pgate/ev/cand_e4/cand_e4_{s}/D3/matches.jsonl' '/workspace/pgate/ev/cand_iu40/cand_iu40_{s}/D3/matches.jsonl' '/workspace/pgate/ev/base_e4/base_e4_{s}/D3/matches.jsonl' '/workspace/pgate/ev/base_iu40/base_iu40_{s}/D3/matches.jsonl'`
   -> per suite + pooled paired delta, 95% CI; last line PASS iff pooled CI low > 0 (n must be 3,840; fewer = a block missing).
   Power (memory gate-pooled note: ~+-1.85 pp at 3,840 pairs, (b) for these suites): a true +2 pp passes about half the time.
   PLAN.md L3 also lists behaviour / habit / Rocket >= 1.0 per match / Mortar >= 45% / memory-ablation bars; the owner's 10-29
   end-game plan names only the pooled CI. Report the Rocket count at least (memory spell-use-measurement-requirement).
- Opponent sets = the established pair (pilot/ops/README "Eval after training"): e4 = E4 rdef_e4 u20 at T .1 (PARTLY IN
  DISTRIBUTION: E4 is in the pilot's training pool) and iu40 = w14opp_I T .1 decide 40 + `--opp-decide-every 20 --opp-tau 0.2`
  (cleaner). Seeds 741200 742000 743000 744000, 480 games each. Arm G u0160 (the pilot's best opponent) is NOT a gate set (b:
  could be added as a reported third suite; it is in the training pool).
- Rebuild the gate tree (only if /workspace/pgate is gone): laptop `git -c core.autocrlf=false archive --format=tar c51efd9 pipeline scratchpad/gauntlet/L74/{gap,livecal,heroiw,mix,crforge/facade,memory,plan1026/d2g,plan1026/pilot/gate} | ssh ... -p 33903 "cd /workspace/pgate/cb && tar xf - --unlink-first"`
  after `cp -al /workspace/opp/cb /workspace/pgate/cb` (data via its icebow/data -> /workspace/icebow_data link; 'Cannot unlink:
  Directory' messages are harmless); facade: `F=/workspace/pgate/facade; mkdir -p $F; cp scratchpad/gauntlet/L74/crforge/facade/CfCore.java $F/; javac -nowarn -cp "/workspace/crforge_main/5e8089a4/plain/lib/*" -d $F $F/CfCore.java`;
  copy pair_both.py to /workspace/pgate/. Dry run: `bash scratchpad/gauntlet/L74/plan1026/pilot/gate/dry_run.sh <CKPT>`
  (CPUs 202-209, 36 + 12 games per model, ~9 min; GATE_GAP=gap_chunks.py + GAP_CHUNKS = fewer chunks of gap.py's schedule).
- SIM FAIL -> do not go live; diagnose (no-discard rule): per-suite delta, per-archetype (d2g/score.py), presses, Rockets.

## Step 2: 30-match live safety trial (laptop; the lead / owner starts it -- never a worker without the lead's word)
Preconditions: step 1 PASS; decisions owed 1 + 2 taken; live currently CLXIII via `start_live.sh icebow --no-fast-plays --ranked`.
1. Register first (step 4, so the file has its Mark name and a path under icebow/data on C:).
2. Account: the supervisor is on the MAIN account (memory verify-mumu-account-before-live): own princess max HP 4858,
   X-Bow / Tesla in hand, ~12k trophies; deploy_ckpt.sh's first_match_guard.py checks main account + icebow deck after the
   first match and writes STOP + Discord if wrong.
3. Offline check (no live side effect): `CKPT=<CLXV path> bash scratchpad/gauntlet/L70/live/start_live.sh icebow --no-fast-plays --ranked --check`
   -> last line LIVE_CHECK_PASS with the CLXV sha.
4. Auto path (deploys between matches + auto-revert), with the MIN_WINS patch applied (decision 2):
   `MIN_WINS=6 BASE_CK=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt BASE_SHA=8d328a43bf09fb7e BASE_LABEL=8d328a43 nohup bash scratchpad/gauntlet/L74/deploy/trial30.sh icebow/data/models/ICEBOW/ICEBOW_Mark_CLXV_<WORD>.pt <sha16> CLXV > /dev/null 2>&1 &`
   trial30 -> deploy_ckpt.sh (sha check, CKPT_OVERRIDE backup, `start_live.sh icebow --no-fast-plays --check`, restart_live.py
   between matches keeping the persisted LIVE_FAST off / LIVE_RANKED on / deck, first-match guard, Discord) -> waits for 30
   `[ladder] result:` lines in L70/live/overnight.out -> idle-on-threat via ape_score (live:8d328a43 vs live:<CLXV sha8>,
   since 20261019) -> KEEP, or REVERT = deploy_ckpt.sh with CLXIII. Log: scratchpad/gauntlet/L74/deploy/trial30_CLXV.log.
   Expected duration (a, liveops: median 13 matches / hour): ~2.3 h for 30 matches.
   Manual alternative (README LOOP-OPS): stop_live.sh, back up + write CKPT_OVERRIDE, --check, start_live.sh icebow
   --no-fast-plays --ranked, then the same trial30 line with `NO_DEPLOY=1` (counts only, never touches live; revert by hand).
5. Revert by hand (any time): `bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt 8d328a43bf09fb7e "revert: CLXV <why>"`
   (= CLXIII NOLEAK, sha 8d328a43). Always confirm afterwards: supervisor log tail + `head -1` of the newest live_play_*.jsonl
   (options: pipeline_decisions false = fast plays off; memory live-start-no-fast-plays).
6. Verdict helper: `python scratchpad/gauntlet/L74/plan1026/pilot/gate/block_verdict.py trial <W>` (exit 1 = revert).

## Step 3: 150-match block (live stays on CLXV after a trial KEEP)
- Count (b, my reading of "then a 150-match block": the 150 results AFTER the trial's 30): with S = the overnight.out line
  logged in trial30_CLXV.log ("at overnight.out line S"):
  `tail -n +S scratchpad/gauntlet/L70/live/overnight.out | grep '\[ladder\] result:' | sed -n 31,180p | grep -c WIN`
  (results with no WIN/LOSS/DRAW word are unknown and left out, as liveops' 32.7% = 204 / 624 decided). Then
  `python scratchpad/gauntlet/L74/plan1026/pilot/gate/block_verdict.py block <W> 150` -> KEEP iff Wilson 95% low > 32.7%.
- (a, block_verdict.py power): KEEP needs >= 61 / 150 (40.7%). P(KEEP) at a true win rate of 32.7 / 35 / 38 / 40 / 42 / 45%
  = .025 / .086 / .277 / .465 / .659 / .875. The strict bar keeps a pilot that is truly +5 pp better than CLXIII only ~28% of
  the time; 300 matches would need >= 115 (38.3%), P(KEEP) .474 at 38%.
- Expected duration (a, 13 matches / hour): ~11.5 h. Cross-check with `scratchpad/gauntlet/L74/loss_review/scorecard.py <since>`
  (deck column must say icebow; per-checkpoint segment).
- REVERT (block fails): the deploy_ckpt.sh line in step 2.5.

## Step 4: bookkeeping (laptop)
- Copy the FINAL checkpoint under icebow/data on C: (hard links need the same volume):
  `mkdir -p icebow/data/bench/rl_royale/pilot_box3 && cp -p C:/Users/benpe/pod_backup_weekend/loop/pilot_box3/pilot_box3_uNNNN.pt icebow/data/bench/rl_royale/pilot_box3/`
- `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/models/register_ckpt.py icebow/data/bench/rl_royale/pilot_box3/pilot_box3_uNNNN.pt --deck ICEBOW --change <WORD> --parent "ICEBOW Mark CLXIII" --run pilot_box3 --note "pilot: B0 (CLXIII + S3-aux memory v2, encoder unfrozen) + fast-loop RL u<NNNN>, crforge 5e8089a4 / 16.635.3, opponents incl. arm G u0160; IW press head re-fit at start" --eval "<pair_both pooled line>"`
  -> it assigns the next Mark: CLXV (a: the working-copy registry.json holds CLXIV as n 164 and nothing later; that CLXIV entry
  is UNCOMMITTED in the shared tree -- commit registry.json + REGISTRY.md together with the CLXV entry). Link:
  icebow/data/models/ICEBOW/ICEBOW_Mark_CLXV_<WORD>.pt. WORD = one uppercase word (pilot.yaml: the trained pilot = CLXV; the
  word is the lead's; e.g. PILOT). Check: `register_ckpt.py --name <link>`.
- After the block: record the live result in the Mark's eval / live fields (registry), HANDOFF (lead), Discord.

## Files (this ticket)
- `d2g/gate.sh`: + opt-in GATE_EV (rows root) and GATE_GAP (the gap.py to run); unset = unchanged.
- `pilot/gate/gap_chunks.py` (gap.py with the first GAP_CHUNKS chunks only), `dry_run.sh`, `repeat.sh` (determinism check),
  `pair_rows.py` (per-game pairing diagnostics), `ckpt_diff.py` / `meta_diff.py` (weights / metadata diff),
  `block_verdict.py` (trial / block / power; `--selftest` reproduces liveops' CLXIII CI [29.1, 36.5]),
  `trial30_minwins.patch` (NOT applied).
- Pod state 33903: /workspace/pgate/{cb,facade,ck,ev,*.py,*.out}; ck/pilot_box3_u0000.pt (444). Laptop:
  C:/Users/benpe/pod_backup_weekend/loop/pilot_box3/pilot_box3_u0000.pt (read-only).
