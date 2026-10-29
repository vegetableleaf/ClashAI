# OPP-SIEGE: why imitation opponents let CLXIII's X-Bow lock (plan1026 Pillar 2)

Problem (P2-OPP2, measured): live humans vs CLXIII lock .47 / zero-lock .12 / P(lock|fail) .36; imitation opponents v0fix /
v1s0 / ftR .75/.70/.75, .00/.01/.00, .70/.64/.68; CLXIII SIM win 88.3 / 82.2 / 88.4%. Hypothesis under test: "imitation misses
rare high-stakes X-Bow answers" (untested at the start). Labels: (a) measured, (b) plausible untested, (c) contradicted.

Code (this dir): `siege_a.py` (test 1, per decision, GPU, pod), `siege_b.py` (test 2, closed-loop breakdown, laptop),
`tab_b.py` / `dec_b.py` / `place_b.py` / `dmg_b.py` (tables from `out/siege_b_*.json`). Lock rule everywhere = card.py's
(an enemy princess loses >= 5% max HP within 30 s of our reach X-Bow; live via match_memory on the reader's tower HP).

## Test 1: per decision on held-out human rows (siege_a.py; pod 33903; results `results/A_*.json`)
Window = a seat's rows in (t_x, t_x + 200] after an enemy reach X-Bow at t_x; early = first 80 ticks (4 s). Outside = the same
seats' other rows (deck matchups held equal). live_cal = humans vs CLXIII (708 matches, split 2, never trained on by ftR / v1);
hf_test = HF test split (346 X-Bow windows). Selftest (planted hazards): `siege_a.py selftest` OK (calibrated PIT 0.503,
a 3x-too-slow model 0.235).

| ftR on live_cal (a) | outside | X-Bow window 0-4 s | 4-10 s |
|---|---|---|---|
| card top-1 / NLL | 56.2% / 0.994 | 55.4% / 1.027 | 55.3% / 1.021 |
| cell top-1 / NLL | 23.5% / 3.37 | 23.2% / 3.42 | 27.2% / 3.01 |
| slot hazard vs human event rate | .074 vs .067 | .174 vs .178 | .113 vs .106 |
| slot ECE | 0.71 pp | 0.50 pp | 0.75 pp |

First response after the X-Bow (2,871 windows): humans play within 4 s in 94.1% (no play 5.9%). Hazard on the slots up to the
human's first play: model .256 vs human event rate .255; randomised PIT of the human's first-play time under the model 0.557
(0.5 = calibrated; > 0.5 = the model expects the answer EARLIER than humans give it), KS 0.16. Locked and failed X-Bows alike
(PIT .559 / .555). Control windows (after other enemy plays, 17,693): PIT 0.520. v1s0 on live_cal: PIT 0.635 (more eager),
card 54.0% in window vs 54.9% outside. HF test (325 windows): v1s0 / ftR PIT 0.512 / 0.514, card top-1 57.5 / 56.9% in window
vs 62.5 / 60.5% outside (n 737 vs 2,270; a 3-5 pp drop, small n).
Reading: (c) CONTRADICTED -- on human trajectories the model gives the human's actual X-Bow response (play vs wait, card, cell)
about the same probability as elsewhere, and its answer hazard is if anything early, not late or missing.

## Test 2: closed loop (siege_b.py; live = CLXIII calibration block; SIM = P2-OPP2 level B rows, fe364ceb, G2 on)
Response classes per reach X-Bow (first opponent play; on-time = in lane, <= 12 tiles, <= 80 ticks = match_memory's answer rule):

| class (a) | live n (share, lock) | ftR (share, lock) | v1s0 | v0fix | E4 (a677e080, G2 off) |
|---|---|---|---|---|---|
| reach X-Bows (lock) | 3,108 (.466) | 7,068 (.750) | 7,058 (.705) | 6,627 (.754) | 8,767 (.566) |
| on-time troop | 1,688 (.543, .39) | 2,372 (.336, .64) | (.352, .60) | (.351, .66) | (.619, .50) |
| on-time building | 292 (.094, .45) | 313 (.044, .68) | (.049, .61) | (.046, .69) | (.101, .52) |
| on-time spell | 30 (.010, .67) | 115 (.016, .77) | (.016, .70) | (.017, .82) | (.027, .51) |
| late (in lane, 4-10 s) | 769 (.247, .56) | 2,944 (.417, .82) | (.387, .77) | (.359, .80) | (.181, .75) |
| elsewhere only | 210 (.068, .53) | 865 (.122, .82) | (.139, .80) | (.162, .84) | (.050, .80) |
| no play in 10 s | 119 (.038, .78) | 459 (.065, .79) | (.057, .79) | (.064, .82) | (.022, .64) |
| spent >= 4 elixir in the 5 s before (share, lock) | .327 (.46) | .349 (.78) | .389 (.74) | .383 (.78) | .477 (.58) |
| on-time answer delay median | 56 ticks | 59 | 58 | 58 | 50 |

Decomposition (dec_b.py): SIM lock with the LIVE class mix = .707 (ftR) / .663 (v1s0) -> the class mix (late / no / wrong-lane
answers) explains +0.04 of the +0.28 (ftR) and +0.24 (v1s0) gaps; the rest (+0.24 / +0.20) is WITHIN class: the same kind of
answer, on time, in lane, works far less in SIM. Same card, on time (live / ftR lock, n): knight .36/.72 (121/103), valkyrie
.38/.61 (129/135), tesla .49/.80 (75/61), cannon .53/.79 (81/63), skeletons .47/.70, mega knight .24/.32. Tesla is placed on the
same tile in both (dx -0.5..0.5, dy 5.5 from the X-Bow, place_b.py), yet .49 vs .80. E4 (another engine build and G2 off) gets
tesla .50, cannon .57, mega knight .23 = close to live.
Instrument control (dmg_b.py): the gap holds at every damage threshold (on-time unit answers, share with princess damage >=
2% / 10% / 20% / 50%: live .46/.33/.26/.09, ftR .67/.60/.48/.22), and with NO answer live and SIM agree at every threshold
(lock .78 vs .79; >= 20%: .69 vs .69; n 119 / 459) -> (c) contradicted: the 5% threshold / live HP reads are not the cause.
Not elixir-starved (a): the "spent >= 4 in 5 s" share is the same (.33 vs .35) and starvation does not change the live lock rate.
Engine build (a): ftR re-run on 5e8089a4 (1,920 games, same seeds, G2 on, 33903) is outcome-identical to fe364ceb: CLXIII win
88.44%, sum of end ticks 7,681,947 both, lock .75 / zero-lock .00 / P(lock|fail) .68, B-live RMS 0.31, C-live 0.974 (card.py v6,
`humanlike/out/card_ftR5e/`).

## STATUS (2026-10-29 ~07:30 UTC) -- restart point
- Done: tests 1-2 (above); ftR baseline on 5e8089a4 (33903 `/workspace/opp/siege/rows/ftR5e`, laptop `humanlike/rows/ftR5e`).
- RUNNING: E4 on 5e8089a4, G2 on, same 4 seeds (30408, `/workspace/siege/score/rows/e45e`, log `/workspace/siege/score/e45e.out`)
  = the same-environment control for "is the within-class gap the opponent or the environment". Restart (resumable per block):
  `ssh -p 30408 ... 'cd /workspace/siege/score && (PY=/workspace/siege/venv/bin/python CB=/workspace/siege/opp/cb LIB=/workspace/crforge_main/5e8089a4/plain CRFORGE_TABLES=/workspace/siege/crforge_cache/tables/16.402.22 WORKERS=40 CPUS=0-127 G2_ON=on setsid nohup bash /workspace/siege/opp/cb/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh e45e /workspace/siege/score/rows/e45e 741200 742000 742800 743600 >> /workspace/siege/score/e45e.out 2>&1 < /dev/null &)'`
- 30408 setup (lead 10-29: use 30408): `/workspace/siege/opp/cb` = 33903's /workspace/opp/cb (code ed890aa + P2-OPP2 files),
  icebow/data -> `/workspace/siege/icebow_data` (CLXIII 8d328a43), data `/workspace/siege/opp/{live,v1}`, tables
  `/workspace/siege/crforge_cache/tables/16.402.22` (content sha = 33903's). `/workspace/siege/venv` = private venv: a .pth onto
  venvf16 + cfspeed/pylib (jpype) and COPIES of royalesim / royalegym (the runtime pin checks the venv's own purelib; 30408's
  venvf16 lacks jpype and gap.py resets PYTHONPATH for its workers). Nothing in /workspace/p4 touched.
- Next: read E4-5e within-class rates -> pick ONE learned fix (section below) -> fine-tune from ftR on 30408 -> level B (same seeds).
