# APE -- behaviour scorer for picking the next live model (W22, 2026-10-22)

Owner 10-22: "get a new and better model live ASAP ... a model that doesn't play like an ape" -- it "completely ignores
threats and plays X-Bows and Teslas like an ape, and still wastes the Log". `ape_score.py` measures those three complaints
plus defence outcome, per match then per model, on LIVE logs and SIM eval rows, with a difference vs a base model and a
95% match-bootstrap CI.

    python scratchpad/gauntlet/L74/ape/ape_score.py live:CLX live:CLXI --base live:CLX [--since 20261019] [--no-log]
    python scratchpad/gauntlet/L74/ape/ape_score.py SIM_DIR [...] --base SIM_CLX_DIR      (dirs searched for matches.jsonl)

## PROMOTION BEHAVIOUR CHECK

**A candidate must be no worse than CLX (difference CI high end not above 0 for the "bad" shares, not below 0 for
G-LOG hold) on: Tesla APE share, X-Bow low-reserve share, THREAT IGNORED share, own tower HP lost per push, G-LOG hold --
scored on the same eval set with `--record-board` rows (SIM) and, once it is live, on >= 100 live matches.**

Which of the five training can move (my expectation, untested):
- **Tesla APE share -- yes, directly.** No live rule places Teslas (grep: no tesla key in `pipeline/live_options.py` /
  `decision_options.py`); 62% of live CLX Teslas go to ONE cell (own-frame y 0.5625) chosen by the model's cell head.
  Any RL change that rewards keeping the tower alive under a push, or imitation of pro Tesla rows, acts on exactly this.
- **X-Bow low-reserve share -- yes, but partly a rule.** The card/time choice is the model's; the gate (tau_phase,
  gate_hazard_*) and `xbow_class: class_sample` decode also shape when X-Bows fire. Expect it to move with training only
  if the reward prices the push that follows (tower HP lost after the X-Bow).
- **THREAT IGNORED share -- slowly.** 78% of "ignored" threats are idle-with-a-unit-already-there (see below), which the
  SIM's opponent and the reward both affect. `tau_threatened` (live 0.2) is a decode lever that moves it without training.
- **HP lost per push -- yes, but it is an OUTCOME** (opponent strength, deck mix, trophies), so it is the noisiest of
  the five; on ladder it also drifts with trophy range. Use it paired (same SIM seeds) not across live periods.
- **G-LOG hold -- yes** (bait-aware opponents in training, LOG_USE.md section 5), but the live sample is small: only
  matches where the opponent revealed a CORE bait card count (CLXI: 9 of 30 matches).

## 1. LIVE: CLX vs CLXI (main account, level-16 towers, since 10-19)

CLX ckpt sha 5d212358 (n 419 matches), CLXI 686b245a (n 30). Difference = CLXI - CLX [95% CI, unpaired match bootstrap].

| metric | CLX (n 419) | CLXI (n 30), diff [CI] |
|---|---|---|
| win rate | 0.518 | 0.400 (-0.118 [-0.301, +0.056]) |
| 1 threats (>= 5 elixir on our half, > 3 s) / match | 3.19 | 3.17 (-0.03 [-0.69, +0.62]) |
| 1 THREAT IGNORED share (wrong play or idle >= 4 s) | 0.214 | 0.200 (-0.014 [-0.088, +0.071]) |
| 1 -- next play elsewhere (wrong) | 0.047 | 0.042 (-0.005 [-0.040, +0.050]) |
| 1 -- idle >= 4 s with elixir | 0.167 | 0.158 (-0.009 [-0.080, +0.058]) |
| 1 ignored AND no own unit on our half in that lane | 0.020 | 0.021 (+0.001 [-0.024, +0.036]) |
| 1 seconds unanswered per threat | 1.99 | 1.93 (-0.06 [-0.48, +0.38]) |
| 2 X-Bow+Tesla plays / match | 10.46 | 11.77 (+1.31 [-0.37, +3.00]) |
| 2 APE / match (X-Bow+Tesla offensive while >= 5 on our half or lane push) | 1.191 | 1.333 (+0.142 [-0.334, +0.655]) |
| 2 APE share of X-Bow+Tesla plays | 0.114 | 0.113 (-0.001 [-0.040, +0.038]) |
| 2 X-Bows / match | 4.83 | 5.47 (+0.63 [-0.33, +1.67]) |
| 2 X-Bow offensive share (y < 0.58) | 0.004 | 0.006 (+0.002 [-0.006, +0.015]) |
| 2 X-Bow APE share | 0.000 | 0.000 |
| 2 X-Bow in the OTHER lane of a >= 5 threat on our half (any y) | 0.004 | 0.012 (+0.008 [-0.005, +0.026]) |
| 2 X-Bow at < 4 reserve with >= 5 enemy troop elixir on board | 0.265 | 0.299 (+0.034 [-0.061, +0.132]) |
| 2 Teslas / match | 5.63 | 6.30 (+0.67 [-0.25, +1.65]) |
| 2 Tesla offensive share (y < 0.58) | 0.623 | 0.577 (-0.046 [-0.157, +0.048]) |
| 2 Tesla APE share | 0.211 | 0.212 (+0.000 [-0.069, +0.070]) |
| 3 G-LOG hold rate (no Log before the first CORE bait play) | 0.549 | 0.556 (+0.007 [-0.351, +0.374]) |
| 3 Logs / minute (not rule-forced) | 1.54 | 1.60 (+0.06 [-0.08, +0.21]) |
| 3 Logs killing < 1 elixir (share) | 0.639 | 0.605 (-0.034 [-0.138, +0.060]) |
| 4 pushes (>= 3 elixir crossing) / match | 6.90 | 8.23 (+1.34 [+0.30, +2.42]) |
| 4 own tower HP lost per push | 610 | 555 (-54 [-202, +121]) |
| 4 own tower HP lost per push elixir | 79 | 75 (-4 [-22, +17]) |
| 4 defence elixir trade per push (push value - our spend) | +0.13 | -0.11 (-0.24 [-0.94, +0.53]) |

What this says (a = measured):
- **CLXI behaves like CLX on every behaviour metric** -- no difference CI excludes 0 except "pushes faced per match"
  (+1.34, an opponent-side number). The complaint is about the model family, not a CLXI regression. CLXI's n is 30, so
  "no difference" means "no difference larger than the CI", e.g. Tesla APE could still be 7 points worse.
- **The ape building is the Tesla, not the X-Bow.** Live X-Bows: 81% at y 0.6094, 0.4% forward of 0.58, X-Bow APE 0.000.
  Live Teslas: 62% at y 0.5625 (one cell, 2 tiles back from the centre line y 0.5), and 21% of all Teslas go forward while >= 5
  elixir of enemy troops is on our half or pushing that lane.
- **The X-Bow problem is reserve, not position**: 26.5% of CLX X-Bows leave < 4 elixir while >= 5 elixir of enemy troops
  is on the board.
- **"Ignores threats" is real but narrow**: 21% of threats get no lane answer, mostly idle >= 4 s with elixir (16.7%);
  90% of the ignored ones already had one of our units on our half in that lane (only 2.0% ignored with nothing there).
  Whether that unit was enough is not measured here -- "HP lost per push" is the outcome side.
- **"Still wastes the Log" -- confirmed**: 64% of CLX's non-forced Logs kill < 1 elixir outright (log_use kill value),
  and the G-LOG hold is 0.55 (pros 0.73 per LOG_USE.md).

## 2. Definitions (live; SIM `--record-board` rows use the same code, `score()`)

Frame: own frame, own edge y = 1, forward = DECREASING y (`pipeline/obs_contract.py` MY_PRINCESS_Y 0.797). **Verified
on this data**: each X-Bow play's y vs the own-frame y of the NEW X-Bow body that appears <= 3 s later, 2,086 plays,
median and p90 |difference| 0.0000. Lanes: own-frame x < 9 tiles = lane 0.
Enemy value: each visible enemy troop body (reader `raw_bodies`; buildings excluded) = card elixir (opp_elixir_count
card_cost) / bodies per card, x hp/max_hp; role children (max_hp < 45% of the card's biggest body) and Graveyard / Clone
bodies = 1/3. Our side: OUR elixir and hand only; the opponent's hand / deck / elixir estimate are never read.
1. **THREAT IGNORED**: episode per lane when enemy value on our half >= 5, ending when < 2.5; episodes gone within 3 s
   are excluded (`thr_short`). Answer = a play on our half (y > 0.5) in that lane or the centre (|x - 9| <= 1.5).
   Ignored = our first play from 1 s before onset is within 3 s but NOT an answer (wrong), or no play for >= 4 s while
   our elixir >= the cheapest card in hand (idle). Seconds unanswered = onset to the first answer (cap 15 s / episode end).
2. **APE BUILDINGS**: X-Bow / Tesla play with y < 0.58 (the live `xbow_forward_board_y`; the pro row 0.604 counts as
   defensive) while enemy value on our half >= 5 (either lane) or enemy troop value in the play's lane anywhere >= 5.
   Plus: X-Bow / Tesla in the other lane of a >= 5 threat on our half (any y), and X-Bows leaving < 4 elixir
   (elixir at the play - 6) while enemy troop value on the board >= 5.
3. **LOG WASTE**: G-LOG hold = glog_score.py's G-LOG1 (no Log of ours before the opponent's first CORE bait play;
   matches with a CORE reveal only); Logs killing < 1 elixir = log_use.kill_value (path bodies with hp <= 429, the
   measured level-16 Log hit) < 1, rule-forced Logs excluded. Live Log metrics come from log_use.analyse (frames).
4. **DEFENCE OUTCOME**: push = from an enemy troop's first crossing onto our half until our half is clear (>= 6 s, cap
   20 s); its crossings summed (hp-scaled at crossing); pushes < 3 elixir dropped. HP lost = our three towers' HP
   (model_towers hp_frac x 7728 / 4858) before the push minus 2 s after it. Trade = push value - elixir of our plays on
   our half from 2 s before the push to its end.

## 3. SIM

**What the current CLX eval rows can support** (`own_plays`, `habits.xbow_y`, `o3_plays`, `crown`; no board bodies):
metric 1 and 4 cannot be computed (no enemy positions / HP); Tesla positions are not recorded; Log kill value cannot be
computed. Proxies the script prints (rows prefixed S): X-Bow y (offensive share), X-Bows within 8 s after >= 5 enemy elixir
was played, those leaving < 4 elixir, Teslas / match, own tower fractions lost; G-LOG hold and Logs / minute on rows with
`o3_plays` (W12, Iu40; the E4 `eval/` rows have none).

CLX SIM (base = E4 `clx_fin15/eval`, n 1920; W12 = R6 u20 opponent; Iu40 = CLX vs I u40):

| metric | W12 (n 1920) | Iu40 (n 2880) | E4 base (n 1920) |
|---|---|---|---|
| win rate | 0.640 | 0.488 | 0.723 |
| G-LOG hold | 0.516 | 0.508 | n/a |
| Logs / minute (all) | 1.62 | 1.67 | 1.64 |
| X-Bows / match | 4.32 | 4.30 | 5.17 |
| X-Bow offensive share (y < 0.58) | 0.003 | 0.004 | 0.004 |
| X-Bow within 8 s after >= 5 enemy elixir played | 0.487 | 0.462 | n/a |
| X-Bow < 4 reserve within 8 s after >= 5 enemy elixir | 0.416 | 0.391 | n/a |
| Teslas / match | 5.21 | 5.56 | 5.43 |
| own tower fractions lost / match | 1.248 | 1.468 | 1.001 |

First candidate, long-run u100 on the same E4 set (`tonight1021/long/u100_e4`, n 1920, no o3 / hab, `sim_u100.out`): win
0.735 (+0.011 [-0.016, +0.037]), X-Bows 5.14 / match, offensive X-Bow 0.006, Teslas 5.43, Logs / min 1.68 (+0.04
[+0.01, +0.07]), own tower fractions lost 0.966 (-0.035 [-0.075, +0.008]) -- indistinguishable from CLX on everything
these rows can show; the behaviour check needs its `--record-board` re-eval.

SIM agrees with live where both measure the same thing: X-Bows almost never forward of 0.58 (0.3-0.4% vs 0.4% live),
G-LOG hold 0.51-0.52 vs 0.55 live.

**`--record-board` (new, commit below)**: `pipeline/search_s0.py` flag that adds `hab` to each match line (both sides'
plays with engine x,y + a 1-s sample of towers, enemy bodies and our X-Bows; the L74/habits HABITS_REC format). Absent =
lines and run.json unchanged. With it, `ape_score.py` scores metrics 1-4 and both Log metrics with the live code
(`score()`), with these differences, all because `hab` does not record them: board sampled every 1 s (live: every
decision, ~0.5 s); "own unit in that lane" is n/a (only our X-Bows are sampled); the idle test uses 2 elixir (the Log)
for "cheapest card in hand"; a Log's path bodies come from the last sample <= 0.5 s after it lands (live: every frame).
EXTRA for gap.py: append `--record-board` to the eval's existing `--extra` string. (`HABITS_REC=1` alone does nothing on
the gap.py path: livecal imports `pipeline/search_s0.py`, and only the L74/habits/pod copy read that variable.)

Validation of the flag + adapter (laptop, `tiny_gap.py`, CLX, 2 seeds, composite 0.1.35 venv `unpinned-linux`, IW form
normal because the laptop has no Hero IW runtime -- a plumbing test, not a result): both rows carry `hab`; 159 / 157 samples
at 20-tick spacing; engine units are millitiles; every own play's own-frame y from engine Y matches its decided cell's y
within 0.0044 (frame check printed by the script); the X-Bow bodies sit at the played X,Y. Pre-ship: pyflakes clean;
`rl_royale --smoke` PASS; `pipeline/tests/test_search_s0.py` + `test_e1_eval_gen.py` 21 pass / 3 fail, and the same 3
fail on HEAD without this change (plays_attempted 0 x2, a SimpleNamespace runner without last_result).
Compare "HP lost per push" only within one eval setup: SIM tower HP depends on `--live-levels` (this tiny run: level 11).
The first real `--record-board` CLX baseline goes here when it lands.
