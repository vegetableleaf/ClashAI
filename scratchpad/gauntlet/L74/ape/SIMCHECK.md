# SIMCHECK -- why the SIM behaviour check missed CLXII (10-22/23; folded into the exploit worker)

The full tables are in `scratchpad/gauntlet/L74/exploit/EXPLOIT.md` section 1b. Grades: (a) measured,
(b) plausible but untested.

## Why it was missed
- **(a)** The check had no data. CLXII's E4 eval in `/workspace/ckev/out/long_u0100`, and EVERY I u40 eval there,
  had no `--record-board` rows (0 of 164 files).
  - The adcb7f3 "indistinguishable" verdict therefore compared only the proxy metrics (Logs/min, X-Bows, Teslas).
  - The ticket's premise that u100 had board rows was wrong.

## What the re-run shows
- I re-ran u100 with board rows. The outcomes are identical: 1411 wins, delta 0.00.
- Board-recorded SIM, u100 vs CLX:
  - E4 (1,920 vs 1,920):
    - idle-on-threat **+0.023 [+0.008, +0.037]** (live +0.101 [+0.003, +0.218])
    - defence trade -0.55 [-1.15, +0.03] (live -0.55)
    - elixir at play **+0.20 [+0.16, +0.25]** (live +0.08 +- 0.14)
    - seconds at >= 9.9 elixir **+3.0 s**
  - I u40 (960 vs 960): idle -0.002 (no signal), defence trade -0.48 [-1.30, +0.42], elixir at play **+0.30**.
- **(a)** So the SIM shows the live direction on E4, at about 1/4 of the live size on idle. The live sample is small:
  n 30, about 19 idle threats; 11 / 30 at p 0.52 is z -1.68.

## The check (deliverable)
`exploit/tools/drift_check.py CAND_EVAL_DIR ... --base BASE_EVAL_DIR`. Run it from `/workspace/exploit/repo` on the pod.
- Inputs: any `--record-board` eval (ev.sh = ckpt_eval's flags + `--record-board` on BOTH E4 and I u40).
- FLAG = the CI lies wholly on the bad side AND the difference passes the bar.
- Gate bars:
  - win -0.02
  - idle +0.02
  - ignored +0.02
  - defence trade -0.25
  - elixir at play +0.10
  - hazard-fired share +0.01
  - full-elixir seconds +2.0
- Scores vs CLX on E4:

| model | verdict | flags |
|---|---|---|
| CLXII (u100) | **FAIL** | idle, elixir at play, full-elixir seconds |
| u150 | FAIL | |
| u175 | FAIL | includes win -0.079 |
| u220 | FAIL | win -0.034, idle +0.037, ignored +0.031, elixir +0.11 |

- On I u40, CLXII FAILs on hoarding only.
- **(b)** The false-positive rate is unknown: no model that did well live has a board-recorded eval yet. Owed: one
  for CLXI or CXXXVIII, scored against CLX.
- **(b)** Recommended use: as a pre-live gate, run on E4. On I u40 it adds hoarding but not idle.
