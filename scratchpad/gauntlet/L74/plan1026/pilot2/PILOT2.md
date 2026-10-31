# PILOT2: two arms (S = 256-row steps, L = large-batch steps) on 2x RTX PRO 6000, every change since CLXIII (owner 10-31)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.

## STATUS (keep current)
- **pilot2_Lc = pilot2_L CONTINUED on 33308 (L-RESUME, 10-31 07:05 UTC, RUNNING).** TRUE resume (rl_royale --resume): the
  laptop's pilot2_L_latest.pt (after update 34, sha 490271e5fccc2a21 = Mark CLXV) copied as pilot2_Lc_latest.pt -> log
  "resumed at update 35, beta 0.0" (optimizer, update counter, rng, kl_ref, guards restored; the stored run name is not checked).
  Same recipe as L (pilot2.yaml + minibatch 65536, lr 2e-5, ppo_epochs 2, ppo_decoupled 2.0, overlap 1, 512 matches / update);
  "RESUME with a changed config" = exactly {max_updates 600 -> 200, trunk_graph 512 -> 256, micro_batch 512 -> 256} (micro =
  exact gradient accumulation; trunk_graph = the graphed row count, follows micro). Fit to one 4090: SERVER=eager (no graph
  pools), FASTLOOP_SHARDS 1, LOCAL_FWD=0 (producers make no CUDA context; their timing-head forwards on CPU), GPU 0 only
  (CUDA_VISIBLE_DEVICES=0; GPU 1 untouched, 1 MiB). Tree /workspace/loopL (setup_Lc.sh: copy of the lead's /workspace/loop/cb
  with pipeline/ + scratchpad/gauntlet/L74/ from 7c9af63 (training code == 930adf2's), 85 artifacts from the store by sha,
  init p2init.pt sha cdde779a); the lead's /workspace/loop/cb + /workspace/pgate2 untouched.
  - (a) u0035 (first policy update after the resume): W/L/D 396/116 (77.3%), 6 steps, kl_stop no, KL g/c/x .0012/.0002/.0005
    (L u0030-34: .0005-.0009 / .0001-.0003 / .0002-.0004), rollout 321 s (server-bound, eager: 1,069 rows/s vs L's ~3,000),
    learner 212 s (L 120 s on the PRO 6000) -> ~5.5 min / update (b: ~15 h to u200 without a plateau stop).
  - (a) GPU 0 peak 13,026 / 24,564 MiB through the rollout + the u0035 learner step (2 s samples): learner 9,108, eager server
    3,876, MPS 30 -> 11.5 GB headroom (>= 3 GB rule met). RAM: cgroup rss 48.3 GB at u0035 (24 producers ~2.1 GB each, learner
    4.9 GB, server 3.0 GB) of the 116 GiB cap shared with the lead's gate (cgroup oom_kill counter 2 = before this run).
  - CPUs: producers + server on 0-104, learner 105-107; while any gap.py runs (the lead's SIM gate) the pinner moves the
    producers + server to 96-104 within 30 s (arm.sh PCPUS_BUSY), so with the gate on 0-95 we stay under the 108.8-CPU quota.
  - Stop: auto_stop (patience 50 from the resume, 0.5 pp, 48 h cap) or max_updates 200. Graceful stop by hand:
    `ssh ... -p 33308 root@157.157.221.29 touch /workspace/loopL/p2/pilot2_Lc/STOP`.
  - PIDs (33308): sh 226864, main 226866, auto_stop 226884, pinner 226885, server 226936. Log /workspace/loopL/p2/pilot2_Lc/loop.log;
    checkpoints /workspace/loopL/cb/icebow/data/bench/rl_royale/pilot2_Lc/ (u0040, u0050, ...: save_every 10).
  - Laptop watcher (WMI bash 112384): `POD_W=/workspace/loopL NO_STOP=1 bash scratchpad/gauntlet/L74/plan1026/pilot2/watch.sh Lc
    pilot2_Lc 33308 33308 root@157.157.221.29` -> C:/Users/benpe/pod_backup_weekend/pilot2/Lc/ (every u%20, sha-checked; FINAL /
    crash: copy + Discord, NEVER stops 33308). Stop it: touch STOP_Lc there.
  - Lead's checks: pilot/gate/pilot_check2.sh starts at u0020 (it would wait forever: Lc's first numbered checkpoint is u0040).
  - Restart after a crash (pod): `cd /workspace/loopL/cb && P2ENV=/workspace/loopL/cb/scratchpad/gauntlet/L74/plan1026/pilot2/envL.sh
    SERVER=eager LOCAL_FWD=0 PCPUS=0-104 PCPUS_BUSY=96-104 LCPUS=105-107 PRODUCERS=24 MATCHES=22 bash
    $PWD/scratchpad/gauntlet/L74/plan1026/pilot2/arm.sh pilot2_Lc minibatch=65536 micro_batch=256 critic_warmup_minibatch=256
    lr=2.0e-5 ppo_epochs=2 trunk_graph=256 max_updates=200 --resume`, then re-arm the watcher (it exits on a crash).
  - Rebuild trap (a): `git archive` on the laptop (core.autocrlf true) wrote CRLF files -> the runtime stamp (CfCore.java,
    body_map.json, fin16 manifest hashes) differed and --resume refused. Build CODE_TGZ with
    `git -c core.autocrlf=false archive --format=tar.gz -o code.tgz <sha> pipeline scratchpad/gauntlet/L74`.
- 10-31 01:30 UTC pods booted with loop_pod.sh (ENTRY=-c, no loop): POD1 arm S `ssh -i ~/.ssh/runpod_clashbot -p 29153
  root@81.27.69.177` (RunPod id dlkk6eevgt9yhv), POD2 arm L `-p 28263` (id 8cq6fx8mbv0ynf). 86 artifacts sha-verified, EXACT_GATE
  PASS on both (EPYC 9554, AVX-512 paths). Code on both = origin 930adf2 (then later commits, see below).
- Init BUILT + identity PASS (section 1). Smokes PASS + compare 16/16 (section 2). SIM-gate path PASS (section 3).
- 10-31 02:03 UTC arms launched (try1, 32 producers x 16), then STOPPED at u0001 by me (watchers first, then the process
  groups by exact id, MPS quit, GPU 0 MiB; dirs renamed *_try1, laptop copies in pilot2/ARM/try1/): (a) GPU 90.4-93.3 / 97.9 GB
  in the critic warm-up (3 graph servers 59 GB: learner shard 23.6 GB, opponent shards 18.1 + 17.2; 32 producer contexts
  29 GB; learner 3.5-4.9 GB) vs LSPEED's arm-L learner peak 10.9 GB at micro 1024 without mem-full -> an OOM at the first
  policy update was likely.
- 10-31 02:10 UTC ARMS RELAUNCHED (code 930adf2), same names, PRODUCERS=24 MATCHES=22 (528 slots, 512 matches / update) on
  both: `pilot2_S` on POD1 (sh 10222 main 10224 auto_stop 10287 pinner 10288); `pilot2_L` on POD2 with minibatch 65536
  micro_batch 512 (exact accumulation) critic_warmup_minibatch 256 lr 2e-5 ppo_epochs 2 trunk_graph 512 (sh 9729 main 9731
  auto_stop 9801 pinner 9802). Laptop watchers (WMI): S bash 76640, L 92168. Lead's checks (33308) read the laptop copies.
- (a) First policy update u0005, both clean: S KL stop e0 mb78 KL 0.0212 (78 steps, learner 18 s); u0006 0.0211; steady state
  72-78 s / update (u0007 72.1 s, 25.6k matches/h) = ~48 updates/h; GPU peak 89.4 / 97.9 GB. L 6 steps (3 minibatches x 2
  epochs), kl_stop never fired (checked after each step -> KL vs previous <= 0.02 at every step), update KL g/c/x
  .0062/.0021/.0023, learner 120 s = the bottleneck (u0006 137 s, ~26 updates/h); GPU peak 93.4 / 97.9 GB. Warm-up updates:
  rollout ~112 s + critic ~93 s. (b) 600 updates = S ~12.5 h, L ~23 h if no plateau stop.
- (a) 02:43 UTC watcher S copied pilot2_S_u0020.pt (laptop sha 2d7f7e85 == pod) and posted the u0020 line to Discord;
  auto_stop reading the log (best10 70.39 @ 9). Training win rate vs the pool, arm S: u0000 372/512 (72.7%), u0005 359,
  u0017 330, u0020 336, u0021 323 (63.1%) -- a downward drift of ~9 pp over the first 16 policy updates (b: per-update SE
  ~2 pp, pool composition is fixed, so the trend is probably real; the lead's 480-game checks decide). Arm L u0010 367/512 (71.7%),
  update KL ~0.001 (L moves far less per update than S, by design).

## Restart / operate
- Pod env: `/workspace/p2/env.sh` (= pilot2/env.sh). Launch an arm (pod): `bash /workspace/loop/cb/scratchpad/gauntlet/L74/plan1026/pilot2/arm.sh RUN [k=v ...]`
  - S: `PRODUCERS=24 MATCHES=22 arm.sh pilot2_S`; L: `PRODUCERS=24 MATCHES=22 arm.sh pilot2_L minibatch=65536 micro_batch=512
    critic_warmup_minibatch=256 lr=2.0e-5 ppo_epochs=2 trunk_graph=512`. A re-used RUN is refused: move its 3 dirs aside first
    (scratchpad/gauntlet/L68/rl/RUN, icebow/data/bench/rl_royale/RUN, /workspace/loop/p2/RUN), or resume a crash with the same
    line + `--resume` (old loop.log kept as loop.log.TIME; auto_stop counts from the resume; touch KEEP_ARM first, re-arm the watcher).
  - Outputs /workspace/loop/p2/RUN/ (loop.log, loop.rc, pids, throughput.jsonl, FINAL, auto_stop.log, pin.log, gpu.log);
    checkpoints /workspace/loop/cb/icebow/data/bench/rl_royale/RUN/ (save_every 10).
  - Graceful stop: `touch /workspace/loop/p2/RUN/STOP` (finishes the update, saves, FINAL).
- Laptop watcher per arm (WMI, Git\bin\bash.exe): `bash scratchpad/gauntlet/L74/plan1026/pilot2/watch.sh ARM RUN PORT POD_ID`;
  log + copies C:/Users/benpe/pod_backup_weekend/pilot2/ARM/ (watch.log); KEEP_ARM there = keep the pod after a crash;
  STOP_ARM = stop the watcher.

## 1. Init + u0 identity (a)
`build_init.py` on POD1 (CPU): B0-full v2 (fc1caf14...) + zero tgt_in / tgt_out / tgt_back ->
`icebow/data/bench/rl_royale/b0/b0_full_v2_tgt.pt` sha256 cdde779a6ca58090bde79a238f072ee8d330ccf38c5c0707ef7b5a3dd9b12119
(141 CLXIII tensors + 51 memory + 3 zero target tensors). rl.ability_head == CLXIII NOLEAK's (4 tensors, torch.equal).
G-pilot2-0 vs CLXIII NOLEAK (8d328a43...), G-mem-0's recipe (gen_dataset_v32_fv5 val rows with a snap_full table, memory at
e_max 256 + snapshot): 10,000 rows (351 with > 128 events), each batch run with random target rows (630,234 random edges),
all-none target rows and no target keys: max |diff| of gate / card / cell / value and card / cell log-probs = 0.0 in all 18
cells. Result file `b0_full_v2_tgt.id.json` (this dir). Copies: POD2 + 33308 /workspace/pgate2/ck/p2init.pt (sha checked).

## 2. Fast loop vs production with BOTH keys + real smoke
`check.sh TAG` (pod): fast-loop `rl_royale --smoke` on pilot2.yaml with the training flags (graphs, local-forward, overlap 1,
MPS), E=4, critic_warmup_updates=1 (u0001 = a PPO policy step through the widened encoder + target layers), FASTLOOP_DUMP;
then compare.py on its u0000 message under MPS (CELLS1 + SHARDS 3), FASTLOOP_MEMHASH. compare.py now also reports which traj
keys the row check covered (`traj_keys`; a key one side lacks is skipped).
RESULT (a): arm S smoke (`check_a`, config sha 7a229e7c2ea9) SMOKE PASS: u0 round trip identical, u0001 = a PPO policy step
(KL stop 0.0211 at 10 steps, trunk_graph 256 + split_attn + overlap), resume check all True. compare.py, under MPS with graphs
+ local-forward: u0000 message 8 / 8 identical, u0001 message 8 / 8 = 16 / 16; first_div_keys {}; lp max 2.1e-5 (bar 5e-5);
memory tables 16 / 16 and rows 5,294 / 5,294 equal (MEMHASH); v_old max 8.0e-7, 0 wver mismatches; ability 16 / 16; traj keys
compared byte for byte include tgt, tgt_idx, mem_t, cue (one side only: mem_h = the hash itself, v_old / wver = server-only).
Arm L smoke (`check_L`, config sha 883c1836b8cf, its learner keys) SMOKE PASS; its u0001 policy step = 1 step of all 2,517
rows, KL 0.0307 then the 0.02 stop (a 2.5k-row smoke, not the 170k-row update: watch the real first update). Its compare
re-ran the same u0000 message (L's keys do not change u0's rollouts): identical numbers to S's = deterministic.

## 3. SIM-gate path with the PILOT2 checkpoint (lead 10-31)
33308, the lead's tree /workspace/loop/cb + /workspace/pgate2 (`p2gate.sh`, `p2plant.py` there): 12 iu40 games
(GAP_CHUNKS=1, seed 741200, CPUs 96-107): p2init under GATE_SAMPLE 0.1 (runs?), p2init under the threshold gate (== CLXIII's
base2 rows for the same 12 games?), and two planted controls under the threshold gate (random target layers; random memory
coupling mem.out) that MUST differ from CLXIII if the SIM decide feeds target rows / memory.
RESULT (a), rows_sub.py vs the lead's base2_iu40_741200 (CLXIII, same tree, LIVE_OPTIONS with `--lethal-rocket log`, built
01:34 UTC, before every block): p2init GATE_SAMPLE 0.1 runs, 12 rows (8 wins); p2init threshold 12 / 12 identical to CLXIII;
planted target layers 0 / 12 identical; planted memory coupling 0 / 12 identical. -> the SIM decide (gap.py -> search_s0 ->
e1_eval Match.gen_row) loads the checkpoint and feeds target rows and memory; no gap.py change needed. (b) e_max 256 + snap in
the SIM decide come from the checkpoint's mem.full through match_memory.opts (the same call the trainer's production path uses;
16 / 16 memory-table equality above is on the fast loop vs production, not on gap.py).

## Decisions / known mismatches
- Learner seat runs NO decide rule (pilot2.yaml has no SAMPLE_RULES key; the fast decide refuses one for a server-forwarded
  learner). Live (4e0b15f) runs the lethal Log finisher (`--lethal-rocket log --lethal-log on --lethal-quiet 1.0`): a known
  small train / live mismatch (rare, deploy-time; lead 10-31 agreed). tau_phase removed: the sampled gate is centred on tau
  0.35 at every phase (= live --gate-sample with the stripped LIVE_OPTIONS).
- (b) target_obs is not wired into live yet (LIVE-TGT worker): a PILOT2 checkpoint must not go live before that lands, or it
  plays target-blind.

- (a) Laptop watcher dry run (DRY=1, POLL 10, fake runs on POD2): FINAL path copied u0000 / u0020 / logs / FINAL (sha) then
  "would stop pod"; crash path ("[rl] CRASH") copied + _latest, alert, waited KEEP_WAIT, then "would stop". Fake files removed.

## Codex dispatches
- none (every step needed a decision or verification; Codex is free for babysitting if the lead wants it).
