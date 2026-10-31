# PILOT2: two arms (S = 256-row steps, L = large-batch steps) on 2x RTX PRO 6000, every change since CLXIII (owner 10-31)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.

## STATUS (keep current)
- 10-31 01:30 UTC pods booted with loop_pod.sh (ENTRY=-c, no loop): POD1 arm S `ssh -i ~/.ssh/runpod_clashbot -p 29153
  root@81.27.69.177` (RunPod id dlkk6eevgt9yhv), POD2 arm L `-p 28263` (id 8cq6fx8mbv0ynf). 86 artifacts sha-verified, EXACT_GATE
  PASS on both (EPYC 9554, AVX-512 paths). Code on both = origin 930adf2 (then later commits, see below).
- Init BUILT + identity PASS (section 1). Smokes PASS + compare 16/16 (section 2). SIM-gate path PASS (section 3).
- 10-31 02:03 UTC ARMS LAUNCHED (code 930adf2): `pilot2_S` on POD1 (config sha of the run: see loop.log START line),
  `pilot2_L` on POD2 (+ minibatch 65536 micro_batch 1024 critic_warmup_minibatch 256 lr 2e-5 ppo_epochs 2 trunk_graph 1024).
  Pods: arm.sh pids in /workspace/loop/p2/RUN/pids (S: sh 4292 main 4294 auto_stop 4365 pinner 4366; L: sh 4420 main 4422
  auto_stop 4488 pinner 4489). Laptop watchers (WMI): S bash PID 77760, L 35140 (watch.log in the backup dirs).

## Restart / operate
- Pod env: `/workspace/p2/env.sh` (= pilot2/env.sh). Launch an arm (pod): `bash /workspace/loop/cb/scratchpad/gauntlet/L74/plan1026/pilot2/arm.sh RUN [k=v ...]`
  - S: `arm.sh pilot2_S`; L: `arm.sh pilot2_L minibatch=65536 micro_batch=1024 critic_warmup_minibatch=256 lr=2.0e-5 ppo_epochs=2 trunk_graph=1024`.
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
