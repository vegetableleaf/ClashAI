# RX-X23 STATUS (X2 farm audit + X3 SIM calibration, 3 R_exchange variants), updated 2026-10-28 ~15:45 UTC

## Done (a)
- Code: rx/x23/{sim_worker.py, run_x23.py, run_x23.sh, analyze.py}; rx/hf_traces.py + rx/build.py now save E_i (elixir). Commit a46092f.
- HF re-extraction with exact elixir: 33308:/workspace/rx23/hfE.npz (50k replays, 14,845 decisive; log hfE.log).
- Live traces with elixir: 30408:/workspace/rx23/liveE.npz (copy on 33308:/workspace/rx23s/liveE.npz; battlelog x23_bl.jsonl).
- Section-1 identity on HF: C_opp - C_own vs (leak+stock)_own - (leak+stock)_opp: r .982 per match (end), .978 all rows,
  residual sd 1.6 vs lhs sd 8.5 elixir; vs HF's own committed totals r .85.
- X1 (HF held-out '4', live): 33308:/workspace/rx23s/an_hf.out / an_p1.out. Variant iii: HF AUC .663/.810/.913, ECE
  .012/.020/.014; live ECE .18/.10/.09 (HF observer wins 66% -> prior); the symmetric fit (both views) gives live ECE .04/.02/.03.

## SIM runs: ALL DONE (32 x 480 = 15,360 games; 1 engine-gap skip in hold10_e4_741200)
- SIM runs: 33308:/workspace/rx23s/ev/<policy>_<mode>_<seed>/ (4 lanes, queue /workspace/rx23s/q33.txt, logs lane33_*.out).
  Plus 30408:/workspace/rx23/ev/clxiii_{e4,iu40}_741200 (done; copied to 33308:/workspace/rx23s/ev30/). 30408 lanes stopped
  (CF-CLONE neighbour load 270 on a 54-core quota).
- Blocks: seed 741200 (480 games/mode/policy) then 742000. 8 policies x {e4, iu40}.

## Restart (resumable: a job with 480 rows is skipped, a partial one is redone)
    ssh -p 33308 root@157.157.221.29; cd /workspace/rx23s
    export X23_ROOT=/workspace/rx23s X23_PYLIB=/workspace/d2/stage/pylib X23_TABLES=/workspace/crforge_cache/tables/16.402.22
    # requeue any missing "TAG POLICY MODE SEED [CKPT]" lines into q33.txt, then per lane:
    nohup bash cb/scratchpad/gauntlet/L74/plan1026/rx/x23/run_x23.sh lane /workspace/rx23s/q33.txt 0-255 18 > laneN.out 2>&1 &
  imitation = "imit_<mode>_<seed> clxiii <mode> <seed> icebow/data/pipeline/gen_v32_s0/gen_s0.pt" (Mark LXXVII, 61011b6c).

## Failures seen (handled by rerun)
- crforge "not modelled": Deflect_3000018 deflecting a projectile off the king tower (hold10_e4_741200 chunk 26). sim_worker now
  turns it into a skipped row (one match lost, counted in analyze.py sim_skipped_engine_gap) instead of a lost 12-seed chunk.
- Intermittent SIGSEGV in libtorch oneDNN get_max_cpu_isa_mask inside the JPype JVM process (3 chunks in ~25 runs); the
  chunk is now retried up to 3x inside run_x23.py (commit 2d46cec, swept into a P2-OPP1 commit via the shared index).

## Next
- DONE: analysis -> rx/out/x23_final.{json,out}, trade-term shares rx/out/x23_final_terms.json (term_share.py). Re-run: cd /workspace/rx23s; /workspace/venvf16/bin/python cb/scratchpad/gauntlet/L74/plan1026/rx/x23/analyze.py
  /workspace/rx23/hfE.npz liveE.npz x23_bl.jsonl an_final.json ev ev30 > an_final.out
- Nothing running. Pods 33308 / 30408 hold no RX-X23 processes.
