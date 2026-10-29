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

## Same-environment control and the per-card refinement (a)
E4 on 5e8089a4, G2 on, the same 4 seeds as ftR (1,920 games, 30408, `humanlike/rows/e45e`): lock .553 (gap +0.09 vs live),
class mix -0.02, within class +0.11; same card on time (live / E4-5e / ftR): tesla .49/.52/.80, knight .36/.46/.72, cannon
.53/.60/.79, valkyrie .38/.46/.61, mega knight .24/.28/.32. So the environment (engine, instrument, CLXIII's SIM stack, the deck
census, G2) CAN give near-live answer effectiveness: the ftR within-class gap is the OPPONENT's play, not the engine (a; one
alternative left (b): E4's strength elsewhere in the match changes the states its answers face).
Placement (place_b.py, on-time answers, dx = toward the centre, dy = toward the opponent's side, tiles from the X-Bow): cannon
dx median live 0.0 / E4 0.0 / ftR 5.0; knight dy median live 9 / E4 10 / ftR 5; tesla dx q25-q75 live -0.5..0.5, E4 -0.5..2.5,
ftR -0.5..3.5. ftR's buildings / knight land off the human spots ("right card, wrong cell") (a).
Commitment (sup_b.py / com_b.py): opponent elixir in the 10 s after the X-Bow live 7.82 / E4 7.73 / ftR 6.35; re-weighting ftR
to the live commitment mix only moves its lock .750 -> .726 (a). CLXIII plays more in live (2.48 plays in 10 s vs 1.79 SIM).
Per-card calibration per decision (cardcal.py on the live_cal dump; slot rows with the card in hand: model expected plays =
sum h * p(card) vs the humans' actual plays; inside X-Bow windows vs outside):

| card | in window: human / model-expected (ratio) | outside (ratio) | choice rows in window: human P / model p |
|---|---|---|---|
| earthquake | 152 / 83 (0.55) | 88 / 113 (1.29) | .454 / .295 (n 313) |
| electro-giant | 69 / 48 (0.70) | 77 / 134 (1.74) | .463 / .344 |
| ice-golem | 116 / 82 (0.70) | 163 / 148 (0.91) | .639 / .551 |
| rocket | 110 / 94 (0.85) | 35 / 83 (2.36) | .371 / .353 |
| pekka | 78 / 66 (0.85) | 62 / 103 (1.67) | .470 / .412 |
| knight / valkyrie / mega knight | 0.85 / 0.95 / 1.13 | 1.05 / 1.19 / 1.38 | matched |
| arrows / tesla / cannon | 1.76 / 1.23 / 1.10 | 1.61 / 1.44 / 1.47 | matched |

So the aggregate test 1 hides a card-specific miss (a): the X-Bow-specific counters (earthquake above all) are under-played in
X-Bow windows and over-played outside -- the model's use of them is not conditioned on the X-Bow enough. Closed loop it grows:
P(card played in a window | in deck) live vs ftR: earthquake .73 vs .32, rocket .55 vs .29, pekka .51 vs .23, electro-giant .45 vs
.18, mega knight .51 vs .28 (win_cards.py live rows / sim_cards.py SIM with bodiless spells; caveat (b): live decks are mostly
"all 8 seen", which biases every live in-deck rate up a little; the-log .29 vs .30 shows the bias is small).
Not shown: that more earthquakes would lower the lock rate (SIM X-Bows with an earthquake in 10 s lock .78 vs .75 without,
n 86 -- selection; the 5% lock happens in the first seconds).
Revised reading of the hypothesis: per decision the model knows WHEN to answer and mostly WHICH unit (c for "missing answers"),
but (a) its X-Bow-specific card choice is under-conditioned (earthquake 0.55x) and (a) closed loop its answers land off the human
spots and commit less elixir; the effective-answer gap, not the answer rate, carries +0.24 of the +0.28.

## Fix 1 (ONE learned change): X-Bow-window rows oversampled in a short fine-tune from ftR
`train_gen --opp-oversample MASK.npy:K` (opt-in; absent = unchanged; test_opp_model 9 passed on 30408, the legacy fingerprint
fails on every pod for HEAD too, README). Mask = make_mask.py on mix_train (rows in (t_x, t_x + 200] after an enemy reach X-Bow:
79,142 of 556,410 rows; 70,627 of 509,475 train rows). Run ftx3 = init ftR's opp_ft_s0.pt, K 3 (train rows 650,729), 4,000
steps, bs 128, lr 2e-5 one-cycle, else ftR's recipe; held-out = live split 1 (unweighted). Chain `run_ftx.sh ftx3 3 4000` ->
attach_sim (band 6, mode 1, era 2) -> siege_a + cardcal on live_cal -> level B (after_ftx3.sh).

### Fix 1 result (a): NO EFFECT -- iterate (NO-DISCARD), do not drop
ftx3 (30408; held-out live split-1 total 5.161 vs ftR 5.206; ckpt `/workspace/siege/ft/ftx3/opp_ft_s0.pt`, _sim.pt sha d7d2794c):
| (a) | ftR (5e8089a4) | ftx3 (5e8089a4) | E4 (5e8089a4, reference) | live / bar |
|---|---|---|---|---|
| CLXIII SIM win (1,920 games, same seeds, G2 on, T 1) | 88.4% | 87.7% (1,683) | 66.5% (1,276) | 30-50% |
| lock / zero-lock / P(lock / fail) | .75 / .00 / .68 | .75 / .00 / .66 | .55 / .04 / .49 | .47 / .12 / .36 |
| B-live RMS d / C-live AUC (v6) | 0.31 / 0.974 | 0.31 / 0.982 | 0.54 / - | <= 0.20 / <= 0.60 |
| within-class share of the lock gap | +0.241 of +0.284 | +0.235 of +0.283 | +0.107 of +0.087 | |
| P(earthquake in window / deck) | .32 | .33 | - | .73 |
| per decision (live_cal): earthquake model-expected / human in windows | 0.55 | 0.60 | - | 1.00 |
| window card / cell NLL | 1.024 / 3.227 | 1.023 / 3.180 | - | |
Reading (a): 3x oversampling in a 4k-step, lr 2e-5 fine-tune moves the per-decision X-Bow conditioning only slightly (earthquake
0.55 -> 0.60; outside over-use grows: electro-giant 1.74 -> 2.19, pekka 1.67 -> 1.98) and nothing closed loop. Cards and
placements of ftx3's on-time answers are as off as ftR's (cannon dx median 2.5, knight dy 5, tesla dx q75 4.5).
Contradicted (c): "CLXIII has an elixir lead when it places the X-Bow vs ftR" -- CLXIII elixir at its reach X-Bow 8.52 (ftR) vs
8.48 (E4); the opponent's TRUE elixir 6.58 (ftR) vs 6.20 (E4) (el_b.py): ftR is not starved and still loses the X-Bow fight.
Open (b): what makes ftR's same-card, on-time answers fail where E4's work -- placement (measured off-spot for cannon / knight /
part of tesla), unit follow-up, or the rest of the board; the next measurement = per-answer position of the X-Bow's first target
and the answer unit's survival (needs the board's body list, `hab` samples s[6]).

### Iteration 2 (dose only): ftx10 = window rows x10 -- also NO EFFECT (a)
ftx10 (1,145,118 train rows; 4,000 steps; else ftx3's recipe), 1,920 games, same env: CLXIII win 86.7% (1,665), lock .75,
zero-lock .01, P(lock|fail) .65, B-live RMS 0.31, C-live 0.983. Per decision earthquake in windows 0.63 of the human rate (ftR
0.55, ftx3 0.60); closed loop P(earthquake in window | deck) .29 (ftR .32). Dose response flat: oversampling the X-Bow-window
rows of the current data does not move the siege facts. The lever is exhausted at this data size; the next change must be a
different one (STATUS).

## OPP-SIEGE2 (account 2, from 2026-10-29 10:10 UTC): placement vs follow-up
### 2a. Lock by offset from the HUMAN spot (place_off.py; on-time unit/building answers; human spot = live median dx, dy per card,
cards with >= 20 live answers; offset = tiles from that spot) (a):

| source (lib) | 0-1.5 tiles | 1.5-3 | > 3 |
|---|---|---|---|
| live (CLXIII calibration block) | .40 (n 738) | .35 (222) | .36 (522) |
| E4 (5e8089a4, e45e) | .41 (1,919) | .51 (390) | .48 (1,336) |
| ftR (5e8089a4, ftR5e) | .55 (683) | .65 (190) | .63 (654) |
| ftx3 (5e8089a4) | .56 (618) | .64 (185) | .61 (581) |

Per card ON the human spot (live / E4 / ftR): tesla .53/.53/.90 (n 59/146/29), cannon .58/.52/.95 (50/106/22), valkyrie
.35/.44/.59, mega knight .28/.28/.25. Re-weighting ftR to the live offset mix gives ~.59 vs its own ~.60 (from the 2-decimal bin rates; offset mix explains
~0.00). Reading: (c) CONTRADICTED -- "ftR's answers fail because they land off the human spot": an ftR answer ON the human spot
locks .55 vs .40 live / .41 E4, the gap is the same at every offset. Placement relative to the X-Bow is not the cause; what
happens after the answer lands is (next: 2b, board targets).

### 2b. What the X-Bow shoots (siege_t.py, xbhp_t.py, strat_t.py, fol_b.py; probe recorder SIEGE_TGT, read only: tgtR = ftR
480 games seed 741200 outcome-identical to ftR5e 480/480; tgtE4 = E4, identical to e45e 480/480; crforge 5e8089a4) (a):

| on-time unit/building answers (all reach X-Bows in brackets) | ftR (tgtR) | E4 (tgtE4) |
|---|---|---|
| reach X-Bows / lock | 1,746 / .78 | 2,261 / .57 |
| X-Bow's FIRST target: the answer / tower / another body | .61 / .10 / .28 (all: .21 / .39 / .40) | .61 / .04 / .34 (all: .43 / .15 / .41) |
| lock when the first target is the answer | .62 | .46 |
| X-Bow ever targets a tower in its life | .59 (all .76) | .44 (all .51) |
| lock if it never does (other damage sources) | .19 | .14 |
| tower ticks per X-Bow, median | 68 (all 142) | 0 (all 25) |
| distinct enemy bodies the X-Bow shoots, mean | 2.02 | 2.58 |
| X-Bow shoots the answer / answer shoots the X-Bow / answer alive when the X-Bow dies | .80 / .54 / .32 | .82 / .53 / .30 |
| CLXIII units shoot the answer / CLXIII tower shoots it | .84 / .34 | .81 / .34 |
| X-Bow HP share at +5 / +10 / +15 s | .50 / .39 / .31 | .46 / .33 / .22 |
| X-Bow life median (ticks) / died in 30 s | 354 / .85 | 334 / .92 |
| opponent / CLXIII bodies on board at the X-Bow | 1.52 / 2.63 | 1.94 / 2.65 |

Stratified, the gap stays at every level (lock ftR / E4): by bodies the X-Bow shoots 1: .54/.38, 2: .70/.53, 3+: .71/.53; by
opponent bodies on board 0: .63/.53 ... 3+: .70/.45; by CLXIII bodies; by X-Bow life 200-400 ticks .52/.38, > 400 .94/.78.
Follow-up plays landing in X-Bow range (11.5 tiles) after the answer, in 10 s (fol_b.py): live .89 / ftR .74 / E4 1.10, and the
lock gap holds in each count bin (0 / 1 / 2+: live .43/.38/.41, ftR .64/.65/.64, E4 .56/.47/.47).
Reading: (a) the answer's first engagement is the SAME for ftR and E4 (same first-target split, same answer-vs-X-Bow exchange,
same answer survival, same CLXIII defence); (a) the difference is how much of the X-Bow's life goes on a tower: E4 keeps it on
more bodies (2.58 vs 2.02) and damages it faster (HP .22 vs .31 at +15 s), so its X-Bows reach the tower less (.44 vs .59).
(c) contradicted as the single cause: placement (2a), follow-up play count in range, CLXIII's defence of the X-Bow. (b) untested:
the bodies that keep the X-Bow busy come from the opponent's general board presence (units walking in, not plays landing in
range; E4 has more bodies on board at the X-Bow, 1.94 vs 1.52) -- a whole-match strength property rather than an answer skill.
No live counterpart for targets (the reader has no target field).

### 2c. Probe (NOT a fix): cell sampling temperature, whole match (SIEGE_CELL_T, pod copy only; card stays T 1)
Quick block, seed 741200, 480 games (a): ftR (same seed) CLXIII win 89.4%, lock .776; cell T .25 (ct25): 85.2%, lock .732
(-0.044; on-time troop answers .29 -> .34 share, "elsewhere" .13 -> .08, answers ON the human spot 158 -> 257 but still lock
.54 there). Full 1,920 of ct25 and the T .5 block: see STATUS.

## STATUS (OPP-SIEGE2, 2026-10-29 12:10 UTC) -- restart point
- RUNNING on 30408 (`ssh -o BatchMode=yes -i ~/.ssh/runpod_clashbot -p 30408 root@157.157.221.29`), one job at a time, 44 workers:
  1. `lanes.sh quick` (PID 3777297, /workspace/siege/queue.out): tgtR, ct25, tgtE4 DONE (480 each); ct50 (cell T .5) running.
  2. then `lanes.sh full ct25 0.25` (waiter PID 3781621, /workspace/siege/queue_full.out): ct25 seeds 742000 742800 743600.
  3. then fix 2 `run_ftd.sh ftd3 3 4000` (waiter PID 3784059, /workspace/siege/ftd3.out; script in
     /workspace/siege/opp/cb/scratchpad/gauntlet/L74/plan1026/opp/siege/): train (GPU, ~11 min) -> _sim.pt -> level A + cardcal ->
     level B 4 x 480 (rows /workspace/siege/score/rows/ftd3). Mask built: /workspace/siege/ft/mask_fail600.npy (63,105 train rows).
  Restart any step by re-running its command (each stage / 480-block skips if done): `cd /workspace/siege && setsid nohup bash
  lanes.sh quick > queue.out 2>&1 < /dev/null &`, `... bash lanes.sh full ct25 0.25 > queue_full.out ...`, `... bash
  /workspace/siege/opp/cb/scratchpad/gauntlet/L74/plan1026/opp/siege/run_ftd.sh ftd3 3 4000 > ftd3.out ...`. NEVER two at once.
- Code: probes use the POD-ONLY copy `/workspace/siege/opp/cb2` (= cb + `probe/patch_pod.py`: SIEGE_CELL_T = cell temperature
  of timing-head seats, SIEGE_TGT=1 = hab sample s[8] [[uid, team, kind, target_uid]]; unset = unchanged; NOT in pipeline/).
  Fix 2 and its level B use the unpatched cb (as ftx3 / ftx10). crforge 5e8089a4, G2 on, CLXIII 8d328a43, seeds as P2-OPP2.
- 30408 limits (a): cgroup 54.4 CPUs (cpu.max) and 62 GB RAM (memory.limit_in_bytes; `free` shows the host's 251 GB): two lanes
  of 80 + 60 workers hit the memory limit at ~11:15 UTC and stalled the pod (sshd timed out); stopped by PID, relaunched as one
  44-worker queue. Never more than ~45 workers on 30408.
- Recorder control (a): the first 170 tgtR games are outcome-identical to ftR5e (170/170 end tick + outcome). 30408's cgroup
  CPU quota is 54.4 CPUs (cpu.max 5440000/100000; nproc 256 is misleading): 80+60 workers share it, so wall per match is ~3x
  ftx10's (40 workers); the recorder's own cost is ~1.3x (tgtR 101 games / 80 workers vs ct25 104 / 60 in the same 12 min).
  The target arms stay at one seed block (480).
- Score: fetch rows to opp_model/humanlike/rows/NAME, `win_b.py DIR`, `siege_b.py sim NAME=DIR` (+ `SIEGE_ALL` unset),
  `siege_t.py NAME=DIR` (target arms), `card.py score --name NAME --sim DIR --no-d` (icebow/.venv python).

## STATUS history (OPP-SIEGE, 2026-10-29 ~10:10 UTC)
- Nothing of mine is running (30408 idle GPU; 33903 untouched beyond the finished ftR5e / siege_a runs; PID 5431 untouched).
- Next single changes, in order (one per experiment): (1) the open (b) measurement: per on-time answer, the X-Bow's first
  target and the answer unit's survival from the board bodies (`hab` samples s[6] / s[7]), ftR vs E4 vs (live: reader bodies)
  -- it decides between "answer placed off the pull spot" and "answer fine, follow-up wrong"; (2) if placement: a learned cell
  fix (e.g. cell-head fine-tune on window play rows only, or a feature the model lacks: the X-Bow's current target per body
  token -- check the obs first); (3) DAgger-style rows stay blocked (no expert labels for SIM states).
  ftx3 / ftx10 checkpoints: `/workspace/siege/ft/{ftx3,ftx10}/opp_ft_s0.pt` + `_R_sim.pt` (30408); rows `rows/{ftx3,ftx10}`.
- Done rows: ftR5e (33903 `/workspace/opp/siege/rows/ftR5e`), e45e, ftx3 (30408 `/workspace/siege/score/rows/`); laptop copies
  `humanlike/rows/{ftR5e,e45e,ftx3}` (not committed, bulk). Test-1 dumps: 33903 `/workspace/opp/siege/D_ftR_live_cal.npz`,
  30408 `/workspace/siege/ft/ftx3/D_live_cal.npz`.
- 30408 setup (lead 10-29: use 30408): `/workspace/siege/opp/cb` = 33903's /workspace/opp/cb (code ed890aa + P2-OPP2 files)
  + this dir + train_gen --opp-oversample; icebow/data -> `/workspace/siege/icebow_data` (CLXIII 8d328a43); data
  `/workspace/siege/opp/{live,v1}`; tables `/workspace/siege/crforge_cache/tables/16.402.22` (content sha = 33903's);
  `/workspace/siege/venv` = private venv: .pth onto venvf16 + cfspeed/pylib (jpype) and COPIES of royalesim / royalegym (the
  runtime pin checks the venv's own purelib; 30408's venvf16 lacks jpype and gap.py resets PYTHONPATH for its workers).
  Nothing in /workspace/p4 touched. 33903: nothing of mine running (PID 5431 untouched).
- If ftx10 also leaves lock at ~.75: the lever is exhausted at this data size (b, not counted: live train holds few human earthquake-in-window
  plays); next single changes, in order: (1) the open (b) measurement above, (2) a feature the model lacks for answer placement
  (e.g. the X-Bow's current target / lock state per body token -- check the obs first), (3) DAgger-style rows are blocked: no
  expert labels for SIM states (the humans are not queryable).
- Codex: none used (all steps were diagnosis or needed checking line by line).
