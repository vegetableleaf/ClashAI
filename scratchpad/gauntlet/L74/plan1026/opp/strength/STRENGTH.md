# V1-STRENGTH: no-RL strength calibration of the human-like opponent (band token x card/cell T), scored at scale

Plan: REPORT_opponents 3 step 4 (1 band token, 2 card/cell T in {1, .7, .5}, timing head T = 1). Pass bar (lead proposal): B-live RMS d <= 0.20
(pilot-usable) with siege facts inside v6 margins and CLXIII SIM win 30-50%; v6 bar RMS 0.10; STRETCH 0.05 reported for every setting (owner 10-28).

## STATUS (2026-10-28 ~22:00 UTC)
- Pod 33553 (CPUs 0-27, <= 15 GB): code /workspace/strength/cb (git archive 38667610 + research/ext from /workspace/loop/cb), ckpts
  /workspace/strength/ckpt/opp_m10_b{1,2,3}.pt (v0 m10 sim ckpt 88f8bc16 restamped by restamp.py), venv /workspace/venv, crforge fe364ceb, tables 16.635.3,
  CRFORGE_BARREL_DECOY_SIM=1, G2 off (pairs with E4 / iu40 / v0 rows; CLXIII win probably a few pp high: untested).
- Smoke: 4/4 games on 1 worker, 169 s. 12 workers = 11.6 GB RSS.
- RUNNING: `sweep.sh list1.txt 741200` (9 settings x 480 games), log /workspace/strength/logs/sweep1.out, rows /workspace/strength/rows/NAME/.
  Restart (resumable per 480-game block):
  `ssh -p 33553 root@157.157.221.29 'cd /workspace/strength; S=cb/scratchpad/gauntlet/L74/plan1026/opp/strength; setsid nohup bash $S/sweep.sh $S/list1.txt 741200 >> logs/sweep1.out 2>&1 </dev/null &'`
- Score (laptop, 33 s): `icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/humanlike/card.py score --name N --sim strength/rows/N --no-c --no-d --out strength/out/N`
  then `tab.py strength/rows strength/out` (markdown + tab.json). Rows are not committed.
- Baseline (v0 m10 run 2 rows, a677e080, 960 games, v6 sha 26568167): out/v0m10_a677: B RMS 0.34 (6.7x the 0.05 stretch), 17 z-fails, lock .76, zero-lock .005,
  P(lock/failed) .68, CLXIII 89.1%.
- Notes: v0 bands 4-6 (live) are untrained; the SIM decode fixes in the shared tree (Mirror cost, game_over, learned ability head) are uncommitted, so these rows use HEAD decode.
