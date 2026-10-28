# LOOP-OPS: B0, pilot config, pod launcher (2026-10-28)

Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS (keep current; 10-28 ~10:50 EDT)
- DONE (a): B0 LF rebuild 76d78619, identity PASS on the laptop (RTX 5050) and pod 33308 (4090), CPU + CUDA; pilot.yaml with the
  lead's decisions (tables 16.635.3, 8 opponents x 12.5%, T_gate 0.1); launcher dry run 1 (fake loop) end to end incl. DONE;
  dry run 2 with the REAL fastloop.py + loop/ref_v0.yaml: boot -> 83 artifacts -> loop start OK, then the loop crashed (missing
  ghost_pool/pool_env_v1_split.json -- now an artifact -- and a fastloop.py FINAL bug, `R.CKPT_ROOT / run` with run a function,
  reported to LOOP-INT); the launcher's crash path worked ("LOOP EXITED WITHOUT ... FINAL", "NOT DONE").
- DONE (a) 10-28 ~11:40: live `--gate-sample T` (63b0693 + 92a0d37; off by default; LIVE_OPTIONS untouched, live = CLXIII):
  flag OFF replay == the pre-change tree on 1,718 decisions (dicts / taps / RNG, head log-probs 0.0); flag ON T .1 on 3 seeds
  (4,533 draws): live fires 637 (0.1405) vs the trainer's decide(decode='sample') 639 (0.1410) vs expected 630.1 (0.1390):
  z +0.62 / +0.80 / live - trainer -0.13; p_b == formula exactly (gate_sample_check.py). Deploy for trial30 = add
  `--gate-sample 0.1` to LIVE_OPTIONS (lead / owner step).
- DONE (a): LOOP-IW boot gate in pod_boot.sh: every JVM gets JAVA_TOOL_OPTIONS=--add-modules=jdk.incubator.foreign
  --enable-native-access=ALL-UNNAMED; before the loop starts, exact_gate.py (numpy exp == glibc on 200,000, numpy dot ==
  sequential on 20,000, CfAbil.EXACT, CfAbil self-tests draw / libm / sum) must print EXACT_GATE PASS, else BOOT FAILED.
  33308 (AMD EPYC 7702, no AVX512): PASS with the flags; without them FAIL (EXACT false, libm 83 mismatches) = the gate works.
- DONE (a) 10-28 15:53Z: REAL fastloop.py dry run on 33308 (code 3c0719a, loop/ref_v0.yaml, 2 producers x 64 matches x 4
  threads, cuda:0): boot -> 84 artifacts sha-verified -> EXACT_GATE PASS -> 3 updates (256 matches each; 6.6k -> 11.6k
  matches/h at this tiny size) -> rc 0, FINAL u0003 -> copied to 33308 + laptop mirror (sha dc1d7d39) -> ack -> pod and laptop
  'DONE, safe to shut down'. Found + fixed on the way: gate javac line (literal backslash-n), numbered checkpoints have no
  .sha256 (streamer now copies any present u*.pt: tmp + os.replace = complete; mid-run streaming re-check owed on the next run),
  a re-used RUN name is refused by rl_royale (rm scratchpad/gauntlet/L68/rl/<run> or pass `-- --resume` semantics via INT).
- ACCOUNT SWITCH 10-28 ~11:55 EDT: nothing of mine is running. Next: pilot.yaml itself in fastloop once LOOP-MEM / LOOP-IW /
  LOOP-OPP wiring lands (tables 16.635.3 then), re-check mid-run streaming, then `up` on the rented pod (command below).
- PENDING: LOOP-INT's FINAL fix -> re-run dry run 2 (restart command below); LOOP-MEM (memory in CfTrain), LOOP-IW (hero presses)
  and LOOP-OPP (opp_style / exploiter decode) before pilot.yaml itself runs in fastloop (NotImplementedError until then, per INT);
  LOOP-LRN tower_phat; CF-MAIN jars (interim lib_cfclone staged); a live sampled-gate option (deploy side) before trial30.
- Store: 33308:/workspace/loop_stage/store/<sha256> (84 rows). Dry-run dirs on 33308 (safe to delete): /workspace/loop_dry,
  /workspace/loop_dry2, /workspace/loop_ckpt/loopops_dry*. Laptop mirror: C:/Users/benpe/pod_backup_weekend/loop/<run>/.
- Restart dry run 2 (resumable: re-uses the pod's venv / code / store):
  `RUN=loopops_dry2 W=/workspace/loop_dry2 POD_STORE=root@localhost:22 CFG=scratchpad/gauntlet/L74/plan1026/pilot/loop/ref_v0.yaml TABLES=16.402.22 ENTRY_ARGS="--producers 2 --matches 64 --threads 4 --devices cuda:1" bash scratchpad/gauntlet/L74/plan1026/pilot/ops/loop_pod.sh up 33308`
  (then `watch 33308` in the background).
- The rented pod: `RUN=<run> ENTRY_ARGS="--producers 48 --matches <M> --threads 4 --devices cuda:0,...,cuda:7" bash .../loop_pod.sh up <PORT> root@<HOST>`
  + `watch <PORT> root@<HOST>`; ENTRY_ARGS = LOOP-INT's numbers.

## 1. B0 (lead 10-28: train the GRAFTED B0; not a Mark; the trained pilot checkpoint becomes ICEBOW Mark CLXV)
- File: icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt sha256 76d786192f7e9c27ec1d71aa47d421b8ee09a4dee6f400471288d6cb396639a2
  (LF rebuild, lead 10-28 A+). The first build 984bf572 (kept as .crlf.bak) recorded memory_v2 meta = the laptop's CRLF s1c
  JSONs (4312a8ad / 15065623, inherited from mem_best_ze) and was refused by model_gen.check_memory_meta on every LF pod tree
  (LOOP-OPP's find). Now .gitattributes keeps scratchpad/gauntlet/L74/memory/s1c/*.json LF everywhere and B0 records
  178955c2 / ca144009. Consequence (accepted by the lead: live runs CLXIII, no memory): CLXIV MEMORY, the 10-25 memory arms
  and mem_best_ze.pt (CRLF meta) no longer load on the laptop.
  = CLXIII NOLEAK's 141 tensors unchanged + the 50 mem.* / mem_aux.* tensors of mem_best_ze.pt (3d75a25d), mem.out exactly 0,
  zero_empty; top level = CLXIII's (rl incl. the ability head, grafted_heads_from) + memory v2 / memory_aux v1 / memory_v2 / s3.
  Build: `python -B build_b0.py` (refuses on any sha / trunk / coupling mismatch; same output name -> same sha, (a)).
- (a) The encoder was trained on the RAW succ48_o_s91 u75 (3eda9d23), not on CLXIII: CLXIII = that raw net + heads grafted from
  rlarm_gae_u0250 (cell_refine / tower_refine / projectile_target_*). The 99 trunk tensors are bit-identical; the 5
  projectile_target tensors differ; 37 head tensors exist only in CLXIII. So the encoder's features were learned next to the raw
  trunk; with the coupling at 0 this changes nothing at u0.
- Identity (a) of the LF B0 on the laptop (RTX 5050 = Blackwell sm_120; `icebow/.venv/Scripts/python.exe -B b0_identity.py all
  B0 OUTDIR cpu cuda`) AND on pod 33308 (RTX 4090; /workspace/loop_dry venv + opencv-python-headless 5.0.0.93 --no-deps for the
  live imports, research/ + cue table artifacts, the 4 logs copied in and deleted after): test_decide_identity's 4 recorded CLXIII live matches (1,718 decisions, 229 plays, 1,505 cell-head calls) through
  this tree's live path. CLXIII vs B0, on CPU and on CUDA: decision dicts / taps / decision-RNG states 1718/1718; max |log-prob
  diff| 0.0 for gate, card, cell, value, wait, g. Only difference: B0's dicts carry the log-only `xb_lock_p` (live_gen_v2 adds
  it for a memory v2 model; live_play only logs it). Informational: CLXIII cpu vs CLXIII cuda differ (3/1718 taps; cell log-prob
  up to 6.0e-3, card 1.7e-5) -- device numerics, relevant to the spec's 1e-5 log-prob bar if rollouts and the reference run on
  different devices. The pod gives the same picture (CLXIII cpu vs cuda: 2/1718 taps, cell 6.0e-3). Rule (lead): correctness
  comparisons are SAME-DEVICE only.

## 2. Pilot config: pilot.yaml (header lists every change vs stepd/cfg/succ48_x_s101.yaml)
init B0; memory v2 + aux v1 + encoder frozen + zero_empty; R_win + `shaping: tower_phat`, shaping_critic_scale 1.5 (habit /
tower_crown terms removed); E 128 x G 4 = 512 matches; gae, gamma_tick 0.99994, lambda 0.95, lr 1e-5, clip 0.2, critic warm-up
5, ppo_epochs 2, minibatch 256, grad_clip .5, vf .5 / .2; learner_deterministic; kl_stop_prev 0.02 + kl_ref_refresh_every 1,
beta 0 (no leash; the beta-clamp KL guard is then always armed, it fires only above kl_cell_stop .5 / kl_gate_stop .1 per
update); league_mix latest / older 0 + league_snapshot_every 100000 (snapshot share 0); screen_every 100000; proagree_every 250;
T_gate 0.1 (lead 10-28: the pilot trains the SAMPLED gate at T .1; live has no sampled-gate option yet -- a deploy-side change
is owed before trial30, per LOOP-INT); w14opp_I in its own exploiter slot at share 0.125 with its calibrated decode, init + 5
externals + E4 uniform over the other 7/8 (league_pfsp_gamma 1e-9) = 8 opponents x 12.5%; pre-run check (a)
`python pool_shares.py pilot.yaml 51200`: all 8 within 0.125 +- 0.003; 512 draws: within the joint 95% band (+- 0.040). After
the first update: `python pool_shares.py --log <the update's match records>`; seed 1028; max_updates 1000; save_every 25 (= the streaming interval); fastloop: {decode: live, live_options L70/live/LIVE_OPTIONS,
producers 48, ...} (LOOP-INT strips it; its values are INT's call). Opponent blocks are x_s101's until POOL.json is regenerated:
`python scratchpad/gauntlet/L74/plan1026/pilot/opp/pool_manifest.py --config pilot.yaml --out POOL.json` (pod tree).
Lead 10-28: tables 16.635.3 (the live client; launcher default TABLES=16.635.3, staged from 32657); E4 (rdef_e4 u20 grafted,
430faaee) is a 7th pool checkpoint with an EQUAL share: league_pfsp_gamma 1e-9 = uniform over init + 6 externals (gamma <= 0
is refused); w14opp_I keeps its 0.3 exploiter share, so E4 is ~10% of matches. Because E4 is in the training pool, the gate's
E4 set is partly IN-DISTRIBUTION; iu40 is the cleaner comparison.
Correctness comparisons must be SAME-DEVICE: CLXIII on CPU vs CUDA differs by up to 6.0e-3 cell log-prob and on 3/1,718 taps (a).
Learner keys (LOOP-LRN, owner / lead 10-28; pilot/lrn/LRN.md): `stored_values: true` (the producers' lp_old + v_old; rows
without the LOOP-SRV v_old are refused), `lazy_refine: true` (cell / tower refine features only on the played rows: exact in
math, not in bits -- weights <= 6.4e-6 apart after one update; reversal criterion R1 / R2 in LRN.md), `ent_pair_every`
(the entropy floor's init baseline on every k-th epoch-0 minibatch, paired with the policy's on the same rows).
**Rule (owner 10-28): every identity / recompute / stored gate runs with lazy_refine OFF** (the bit-identity proof stays on
the eager model). rec_identity.py / stored_gate.py / share_gate.py force it off (rec_identity.lazy_off); any other A/B that
builds a learner from pilot.yaml (fastloop / loop/run.sh learner arms, loop_learner) passes `lazy_refine=false`.
LOOP-INT's compare.py compares ACTOR paths only (actors load weights from bytes and never carry lazy_refine): unaffected.

### Eval after training (the order is fixed; nothing goes live without both)
1. SIM gate vs CLXIII on crforge, paired, on the SAME jars + tables as training (baseline rows from another build do not pair):
   on a d2 pod (33308 layout), for TAG in cand, base; MODE in e4, iu40:
   `GATE_CKPT=<ckpt> GATE_LIB=<training lib> GATE_TABLES=<training tables> bash scratchpad/gauntlet/L74/plan1026/d2g/gate.sh crforge <TAG>_<MODE> <MODE> <CPUS> <WORKERS> 741200 742000 743000 744000`
   (both on tables 16.635.3 + the training jars; base = CLXIII NOLEAK, GATE_CKPT unset; 4 x 480 = 1,920 per set, 3,840 total), then
   `python scratchpad/gauntlet/L74/memory/pair_both.py '/workspace/d2/ev/cand_e4/cand_e4_{s}/D3/matches.jsonl' '/workspace/d2/ev/cand_iu40/cand_iu40_{s}/D3/matches.jsonl' '/workspace/d2/ev/base_e4/base_e4_{s}/D3/matches.jsonl' '/workspace/d2/ev/base_iu40/base_iu40_{s}/D3/matches.jsonl'`
   -> per-suite + pooled paired delta with 95% CI; PASS = pooled CI low > 0 (plus the plan's L3 behaviour bars).
2. Live trial (only after 1 passes; the lead / owner starts it): register the checkpoint as ICEBOW Mark CLXV first. Verify the
   MuMu main account (towers lvl 16 = 4858). Stop live (scratchpad/gauntlet/L70/live/stop_live.sh), back up and write
   scratchpad/gauntlet/L70/live/CKPT_OVERRIDE = the CLXV path, then
   `bash scratchpad/gauntlet/L70/live/start_live.sh icebow --no-fast-plays --ranked --check` (must end LIVE_CHECK_PASS with its
   sha) and only then `bash scratchpad/gauntlet/L70/live/start_live.sh icebow --no-fast-plays --ranked`. Count with
   `NO_DEPLOY=1 BASE_CK=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt BASE_SHA=8d328a43bf09fb7e BASE_LABEL=8d328a43 bash scratchpad/gauntlet/L74/deploy/trial30.sh <CLXV path> <sha16> CLXV`
   -> KEEP iff >= 16/30 wins AND idle-on-threat <= CLXIII's + 0.05; FAIL = revert CKPT_OVERRIDE to CLXIII by the same
   --check / start procedure (NO_DEPLOY never touches live). (b) ape_score accepts live:<sha8> for a model not in its NAMES.

## 3. Launcher
Laptop (repo root): `RUN=<run> bash scratchpad/gauntlet/L74/plan1026/pilot/ops/loop_pod.sh up <PORT> [root@HOST]`, then
`RUN=<run> bash .../loop_pod.sh watch <PORT> [root@HOST]` in the background (laptop mirror; prints the DONE line).
`stop` (STOP file), `status` (tails). Env: CODE_SHA (default HEAD; refused unless on origin/main), CFG, ENTRY, ENTRY_ARGS,
TABLES, POD_STORE (how the loop pod reaches the store; default 157.157.221.29:33308), REQUIRE_ACK (1), STREAM_EVERY.
- up: `stage` check -> a key generated ON the loop pod (`loop-ops:<run>`; no laptop key leaves the laptop), authorised on 33308
  (tunnel.sh's W16 pattern; `watch` removes it at DONE) -> run.env / artifacts.tsv / requirements.txt / pilot.yaml / pod_boot.sh
  pushed (CR stripped) -> pod_boot.sh detached.
- pod_boot.sh: versions -> $W/env.txt; apt rsync/git/JDK 17 if missing; venv via uv (python 3.12) + requirements.txt (= 33308's
  venvf16: torch 2.11.0+cu128, arch list incl. sm_120) + a matmul on every GPU; code at CODE_SHA (GitHub, depth 1); one rsync
  of the missing shas from the store, each file verified; loop started with the crforge env (CRFORGE_LIB=$W/crforge/lib,
  CRFORGE_TABLES=$W/crforge/tables/$TABLES, PYTHONPATH=$W/cb:$W/pylib); every STREAM_EVERY s: new `<run>_uNNNN.pt` with a
  `.sha256` -> 33308:/workspace/loop_ckpt/<run>/ (sha re-checked there), one line in $W/ops_throughput.log (load, GPU util,
  memory, copied count, the loop's last throughput.jsonl line); loop exit with FINAL -> final copied + verified -> FINAL marker
  on the store -> after the laptop's sha ack: "DONE, safe to shut down". Loop exit without FINAL -> `_latest.pt` copied, "NOT DONE".
- Restart (resumable): re-running `up` re-uses the pod's venv / store / code (each step skips what is already verified).
- artifacts.tsv: `loop_pod.sh add laptop:REL|PORT:/ABS DEST` (file or dir) / `add-tgz PORT DIR DEST/`; `stage` copies into the
  content-addressed store. Today: B0, CLXIII, the config's data + opponent checkpoints, lib_cfclone (interim), tables
  16.402.22, jpype pylib, royalesim/royalegym (venvf16) = 51 rows.

## Dry run (33308, fresh dir /workspace/loop_dry, POD_STORE=root@localhost:22, ENTRY=fake_loop.py --every 30)
(a) 13:57:13Z boot -> 13:59:58Z venv OK (python 3.12.3, torch 2.11.0+cu128, 2 x 4090, arch list sm_75..sm_120) -> 14:00:54Z
code dfdf8a85 (15,461 files) -> 14:01:00Z 51 artifacts sha-verified -> loop started; u0001-u0003 copied off within 20-40 s of
each; STOP at u0004 -> FINAL. See "DONE" below for the end of the run.
DONE (a): laptop mirror 10:02:56-10:05:23 EDT (u0001-u0004, sha-verified) -> ack -> pod 14:05:31Z "DONE, safe to shut down: final
loopops_dry_u0004.pt sha e4dcfef7... is on root@localhost:22:/workspace/loop_ckpt/loopops_dry and the laptop mirror (sha-verified)";
laptop "DONE, safe to shut down ... loop pod key revoked" (33308 authorized_keys: 0 loop-ops lines after). Boot-to-loop 3 m 47 s
(venv from scratch incl. torch). Not exercised (b): the real fastloop.py, a crash exit (NOT DONE path), a fresh RunPod image
(apt / uv paths: 33308 already had rsync, JDK, python 3.12), Blackwell on the pod (laptop RTX 5050 sm_120 runs the same torch).
Bug found and fixed in the run: `up`'s detached start held the ssh open (`cd && cmd &` backgrounds a subshell); now `cd ||; cmd &`.
