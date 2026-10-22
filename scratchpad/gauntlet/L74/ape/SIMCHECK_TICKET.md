# Why did the SIM behaviour check miss CLXII's live failure? (headless API-key worker, 10-22 evening)

Repo C:\Users\benpe\ClashBot (Windows laptop; Git Bash). Read first: `git show HEAD:HANDOFF.md | head -120` and
scratchpad/gauntlet/L74/ape/APE.md (ape_score.py).

## Facts
- Mark CLXII (the long run tn_long_e1i_s74 at u100, grafted 8af4b560) vs Mark CLX (5d212358):
  - SIM E4 pooled +1.15 [-1.39, +3.68]
  - vs the Ranked-calibrated W14 opponent I u40: +6.82 (CLXII trained vs I u40 at 30% share)
  - LIVE Ranked: 11 W / 19 L (37%) vs CLX 52% (433 matches since 10-19)
- Live ape_score (CLXII n 30 vs CLX n 433):
  - threat-ignored share 0.296 vs 0.213; of which idle >= 4 s with elixir 0.268 vs 0.167 (+0.101 [+0.003, +0.218])
  - defence elixir trade / push -0.47 vs +0.08
  - G-LOG hold 0.455 vs 0.551
- The SIM ape check (adcb7f3: "long-run u100 E4 proxies vs CLX: no hab rows; indistinguishable") found no difference, before
  --record-board existed. Board-recorded SIM evals NOW EXIST on pod 157.157.221.29:32525 (ssh -i ~/.ssh/runpod_clashbot -p 32525):
  - /workspace/ckev/out/clx_rb (CLX)
  - long_u0100 (= CLXII), long_u0150, long_u0175
  - each with e4/ (4 seeds) and the I u40 opponent sets
  - the long run degraded: u150 -1.72, u175 -7.86 vs CLX; it stopped itself at u219 on the pro-agreement tripwire

## Task
1. Run ape_score.py on the SIM dirs (ape_score.py SIM_DIR ... --base SIM_CLX_DIR) for long_u0100 vs clx_rb, on E4 AND on I u40.
   Do the SIM metrics show CLXII's live pattern (idle on threats, worse defence trade, Log hold)? Also run u150 / u175: does the
   SIM behaviour drift track the SIM win drop?
2. If the SIM does NOT show the live pattern, find out why. Candidates:
   - SIM opponents push differently (fewer / smaller threats: the habit diagnosis 10-18 found 1.20 vs 1.95 heavy pushes / match)
   - the threat definition doesn't map to SIM state
   - the board sampling cadence
   - the CLXII live sample is just 30 matches (state the noise honestly)
   Recompute the metric definitions on both sides where needed.
3. Deliver a SIM behaviour check that would have flagged CLXII before live (if one exists), with its thresholds, as a script the
   lead can run on any candidate's --record-board eval, plus how it scores CLX, CLXII, u150 and u175.
Run the heavy parsing on pod 32525 (54 cores, idle now: the long run stopped). Copy needed code there; never overwrite
/workspace/cb_stepd or ckev outputs; work in /workspace/simcheck.

## Rules
- no commits (the lead commits)
- never touch the live process, MuMu, LIVE_OPTIONS or CKPT_OVERRIDE
- never stop a pod, and never arm timers
- never run "python -" (hook-blocked)
- kill only by exact PID
- the laptop is CPU-starved by live play: heavy work on the pod
- write results to scratchpad/gauntlet/L74/ape/SIMCHECK.md and return a plain-English report with every number
