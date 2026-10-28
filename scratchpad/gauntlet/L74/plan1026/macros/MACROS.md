# P6-MACRO: the macro library mined from human data (plan1026 PLAN P6)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Every lift here is an ASSOCIATION in
matched states, never a causal effect: humans choose a macro when it looks good to them, so a lift can be selection, and a
negative lift can be "used when already in trouble". The library is a list of fork ALTERNATIVES for P3-FORK, not rules
or rewards (PLAN P6 mechanism 2): the SIM fork decides each macro's value from the state where it starts.

## STATUS (keep current)
- **Library: `LIBRARY.json` (this dir), sha256 in the "Library table" section below.** Built by `stats.py --B 1000` on
  pod 33308 from episode set ep3 (`/workspace/macros/ep3`: HF 2,020 shard files, pro, live). 21 entries (20 owner-named /
  doctrine + the new opening pattern) + 9 refinements + mined per-play extras.
- Code: `mine.py` (19 detectors + per-play pairs, three source adapters -> episodes), `stats.py` (cell-matched lifts,
  cluster bootstrap, horizon, status, LIBRARY.json), `spec.json` (fixed part of each entry), `live_index.py` (CLXIII live
  index, sealed block excluded), `table.py` (LIBRARY -> the tables below), `epcheck.py`, `rss_probe.py`, `test_stats.py`
  (planted-effect check: +0.10 planted -> 0.111 [0.077, 0.141], naive 0.277; null -> 0.026 [-0.005, 0.065]; passes).
- Pod 33308 `/workspace/macros`: code copies `cb/` (ep v2) and `cb3/` (ep3, final); episode sets `ep_v1` (superseded: old
  margin), `ep` (v2), `ep3` (final). Memory: one HF worker 0.64 GB peak RSS (rss_probe); 8 workers on CPUs 64-71 ~5 GB;
  stats run under `ulimit -v 20000000` (lead budget 20 GB). Nothing of mine runs after the final stats run.
- Live: `index_clxiii.json` = 858 graded CLXIII Ranked matches from 10-25 08:44 up to the seal (108 sealed logs never
  read); win 0.378 in this set (a). Pickles in `live_cache/` (not committed). Ranked result lines say "trophies n/a", so
  `card_use.results()` returns none of them; `live_index.results()` pairs them without the trophy digits.
- Codex: P6-MACRO_1 (low): stopped by me before it ran anything (the episodes were being regenerated). P6-MACRO_2 (low):
  verified the v2 passes (E = P = 2,020 files, clean logs), ran `stats.py --B 1000`, copied back to
  `.foreman/scratch/p6macro/pod/`; I checked its LIBRARY sha (6fe92ed4...) against the log line: equal. DONE.
- Restart (all resumable): HF pass `cd /workspace/macros && PYTHONPATH=/workspace/redrive/pylib setsid nohup taskset -c
  64-71 nice -n 5 python -B cb3/scratchpad/gauntlet/L74/plan1026/macros/mine.py hf --rows
  /workspace/redrive/full_bec5811a/rows --hf /workspace/hf_il_replay/data --out /workspace/macros/ep3/hf --workers 8 >
  hf_pass5b.log 2>&1 &` (skips finished files); pro `cd cb3 && python -B scratchpad/gauntlet/L74/plan1026/macros/mine.py
  pro --out /workspace/macros/ep3/pro.jsonl.gz`; live (laptop) `python -B mine.py live --out EP/live.jsonl.gz`; stats
  `bash /workspace/macros/run_stats3.sh` (writes out3/LIBRARY.json + out3/stats.log). Check
  `cat /sys/fs/cgroup/memory/memory.usage_in_bytes` before each launch.

## Data (a)
| source | what | player-sides | X-Bow sides | full icebow8 |
|---|---|---|---|---|
| HF IL_Replay, crforge re-drive pass 1, tier A | plays from HF actions (exact), towers / own elixir / hand from the re-drive rows; both sides | 172,496 | 4,097 | 384 |
| pro corpus (icebow8, Path of Legend) | invlib.pro_matches: decisions + results real, frames = native re-drive | 1,629 | 1,629 | 1,629 |
| CLXIII live, before the seal | reader frames; our model, so a USAGE reference, not human data | 858 | 858 | 858 |
- X-Bow decks are 2.4% of HF sides; Hero Ice Wizard decks: **0** in HF (a: the HF hero cards are Berserker, Valkyrie,
  Knight, Giant, ...; no `ice-wizard-hero` key), and neither pro nor live loaders carry presses. Macro 15 has NO data.
- Card costs / types from the native live card catalogue: hablib's CardDB (icebow/config/cards.yaml) lacks 91 of the 118
  HF cards, and on pod 33308 it returned x_bow -> cost 3.0 / kind None. mine.py patches H.cost / H.kind in-process only
  (this also corrects the opponent elixir counter for non-icebow cards in this miner). Other tools using hablib are
  untouched; whether their numbers moved is untested (b).

## Method
- Episode = one occurrence of a macro's START condition for one player-side; treated = the scripted PREFIX was played in
  the macro's window; well = the prefix's immediate success (lock, chip, Log on the Barrel, ...).
- Lift = exact-stratification effect on the treated: cells (phase 1x/2x/OT, crown diff, princess-HP margin band, own
  elixir band, opponent deck archetype, own deck archetype, [source], [macro key: attacking unit + Tesla in hand for the
  king redirect, failures so far for Rocket cycling, answer context for the defensive X-Bow, siege card]). Coverage (treated
  share inside cells holding both arms) is 0.79-1.00 for the human sources (lowest: one_one_other pro 0.79,
  siege_answer.xbow pro 0.80, king_redirect pro 0.88); live rows go down to 0.66.
- 95% CI: Poisson bootstrap over MATCHES (both sides and all episodes of a match move together), B = 1000 (B = 250 above
  200k episodes).
- Outcomes: match win; princess-HP margin change (enemy princess HP lost - own, princess units; king HP excluded: it
  decides nothing short of 3 crowns and the king redirect trades king HP for princess HP) over 10/20/30/60 s and to the end.
- "human" = pro + HF pooled with the source in the cell; it is each entry's `primary` (sets status + horizon), except
  iw_press. Status: win_lift (win CI low > 0) / win_negative (CI high < 0) / margin_lift / success_lift / no_lift / thin.
- Horizon for forks: the shortest of 10/20/30/60 s/end whose margin lift reaches 80% of the largest one with CI low > 0;
  else the doctrinal default in spec.json (reason recorded in `horizon_basis`).
- Diagnosis rows per macro: `well_lift_win` (treated AND well-executed vs control) and `failed_lift_win`. They condition
  on an outcome measured after the start, so they are biased toward "executed well = good" by construction: a diagnosis
  of execution, not the macro's value.

## Findings (human pooled unless named)
1. **Rocket cycling after failed X-Bows in 2x / OT: the clearest owner-named lift. (a)** Win +0.082 [+0.030, +0.143]
   (n 3,155 episodes, 1,703 matches, 832 treated; horizon measured 600 ticks); margin over 30 s +0.079 [+0.057, +0.103] in BOTH sources separately
   (pro +0.079 [+0.050, +0.117], HF +0.079 [+0.046, +0.109]). After >= 2 failures: win +0.091 [+0.033, +0.153]. Usage in
   the same start state: pros 25.1%, HF 27.9%, **CLXIII live 2.1%** (n 1,585). The SIM fork of this macro is the one with
   the strongest prior to pay.
2. **Defensive X-Bow in a hard matchup: win +0.117 [+0.070, +0.166] (a)** (pro +0.162 [+0.080, +0.238], HF +0.081 [+0.014,
   +0.146]); with the answer ready +0.124 [+0.069, +0.178]. Its 30 s margin is NEGATIVE (-0.058 [-0.081, -0.034]): it
   gives up chip now for the match. The "then counter-lock" half is rare: an own bridge X-Bow locks within 30 s after it in
   4-8% of cases (pro 4.3%, HF 7.0%), no more often than after other X-Bows (success lift -0.022 [-0.045, +0.004]).
   Usage: pros 30.9%, live 12.5%.
3. **Owner-named macros WITHOUT a win lift, diagnosed (a), all kept (NO-DISCARD):**
   - Sneaky lock: win +0.017 [-0.024, +0.058], but the LOCK rate rises: success +0.056 [+0.015, +0.096] (pro +0.051
     [+0.003, +0.097]). The Tornado does what it is for; the win effect of one extra lock is too small to see at n 727
     treated. Refined start (an enemy body within 7 tiles of the X-Bow site; pro frames only): +0.030 [-0.056, +0.118],
     n 188 treated: thin. Usage: pros 13.6%, live 4.0%.
   - Rocket + Tornado: clump -0.030 [-0.120, +0.053] (142 treated), into a princess -0.019 [-0.061, +0.022] (607):
     no lift; the combo's chip success is not higher either (pro -0.045 [-0.082, -0.010]). Thin and play-based: the clump
     is inferred from opponent plays (no body positions on HF). Usage: pros 12.8% of tower Rockets, live 0.7%.
   - King redirect: pooled +0.016 [+0.001, +0.033] (n 123,853), HF +0.024 [+0.006, +0.042], but **pro -0.085 [-0.147,
     -0.016]** (n 10,883, 551 treated). On win conditions (Hog, Balloon, giants, ...) HF +0.048 [+0.026, +0.072] and on the
     Hog HF +0.065 [+0.041, +0.090] with princess HP saved (+0.036 margin) — the macro's intended case works in human
     data; the icebow8 pro sample disagrees (Hog: -0.083 [-0.162, +0.000], 224 matches). Matching on Tesla-in-hand did
     not remove it. Diagnosis open (b): pro frames are a native re-drive (counterfactual positions), and pros may Tornado
     the king when nothing else is in hand. Usage: pros 5.1%, live 0.5%.
   - X-Bow when the answer is out of cycle: -0.016 [-0.044, +0.013]; lock +0.021 [-0.010, +0.050]. The "cycled" label
     comes from the opponent's revealed cycle; matching cannot see what the opponent actually holds. Executed well (lock):
     +0.112 HF — the lock matters, the timing label does not separate it. (b) refine with the memory encoder's state.
   - Counter-push: -0.010 [-0.016, -0.004] (n 109,569). Start too broad: survival of our defenders is not observed (no own
     bodies in HF / pro frames), so "behind surviving defenders" is not tested yet (b).
   - Lead protection (1-0 up, defend out): **HF -0.045 [-0.052, -0.039] (n 49,136), 30 s margin -0.146** — human players
     who stop investing while ahead win LESS in matched cells (c, as association, against the "defend out" doctrine);
     pros +0.009 [-0.094, +0.125] (n 305: thin). Kept; refine the start to "their banked push is coming" (b).
   - 1-1 take the other princess: -0.009 [-0.018, -0.001] win but +0.056 [+0.051, +0.061] margin: it chips more, does not
     win more.
   - Bank vs their bank (hold): -0.006 [-0.010, -0.003]; margin -0.062. Pre-2x bank: +0.015 [+0.010, +0.021] (a, small).
   - Opening restraint vs beatdown (generic, <= 3 offensive elixir in 30 s): -0.005 [-0.013, +0.003] (n 71,964): no lift.
     X-Bow decks, no X-Bow before their first tank: pro +0.058 [-0.028, +0.141], **HF -0.077 [-0.128, -0.025]** (n 1,608):
     the sources disagree; pooled -0.033 [-0.077, +0.013]. Live: CLXIII places an X-Bow before the first tank in 59% of
     beatdown matches vs pros 22% (a).
   - **The live 10-28 pattern, the 10-elixir X-Bow + Tesla opening vs beatdown (new entry opening_no_xb_tesla):** pros
     open with it in 6.5% of beatdown matches, HF X-Bow players 7.0%, **CLXIII live 19.6%** (a: 3x the human rate).
     Avoiding it: pro +0.108 [-0.037, +0.243] (n 690), HF -0.115 [-0.211, -0.017] (n 1,608), pooled -0.048 [-0.127,
     +0.030]: the human data do NOT show that this opening loses (b at best; HF leans the other way). The live loss pattern
     is real in our model's matches (avoiding it there: -0.098 [-0.232, +0.042], n 326, association) but the cause is
     not shown to be the opening itself; candidates: what CLXIII does after it (elixir race), measured by the SIM fork.
4. **Doctrine macros WITH a small win lift (a):** opposite-lane punish +0.016 [+0.012, +0.020] (n 424k; 30 s margin +0.089);
   focus the weakest princess +0.051 [+0.048, +0.053]; Log held for the Barrel +0.035 [+0.020, +0.050] (pro +0.080
   [-0.002, +0.163]; Logged within 3 s: pro 75% when held vs 5% when not); siege answer (troop within 2 s) +0.036 [+0.018, +0.055], on
   an X-Bow +0.056 [+0.020, +0.091]; pulls +0.022 [+0.017, +0.028].
5. **Hero IW press (15): no data (a: 0 episodes).** Needs the Hero Ice Wizard pro crawl or our own press logs.
6. **Mined extras.** A match-level "pair used at least once" comparison (`extras_match_level`) gives large lifts for any
   pair ending in Rocket (+0.17..0.19): that is the finisher Rocket of winning matches, i.e. confounded; it is kept only as
   a record. The library's extras are the PER-PLAY comparison (`extras`): A followed by B within 5 s vs A with B in hand
   but not played next, in matched cells. 135 pairs tested: **none survives Bonferroni** (z 3.56); 9 have a raw CI low
   > 0 (skeletons>rocket:Oo +0.097 [+0.043, +0.152], the_log>rocket:Oo +0.094, knight>skeletons:Oo +0.077, ...), about
   what 135 tests give by chance at 2.5% one-sided (3.4 expected). So no mined extra enters the library as a macro; the
   list is kept as candidates (b) for a re-test on re-drive passes 2 / 3.

## Library table
Generated by `python -B table.py LIBRARY.json` (the live rows are OUR model's usage and association, not human
data; 'margin 30 s' = lift_n600, 'end' = lift_nend, success = the prefix's immediate success).

LIBRARY.json sha256 `828cedf71ae30bce2f0903a366c4daf2857a44c1bfa9061cb2053bf63c4d959b`, B = 1000, data: {"hf": {"sides": 172496, "xbow_sides": 4097, "icebow8_sides": 384}, "live": {"sides": 858, "xbow_sides": 858, "icebow8_sides": 858}, "pro": {"sides": 1629, "xbow_sides": 1629, "icebow8_sides": 1629}}

| macro | src | n (matches) | treated | win lift [95% CI] | margin lift 30 s | margin lift end | success lift | status | horizon |
|---|---|---|---|---|---|---|---|---|---|
| sneaky_lock | pro | 4096 (1498) | 559 (13.7%) | +0.007 [-0.042, +0.055] | +0.005 [-0.023, +0.036] | +0.013 [-0.041, +0.073] | +0.051 [+0.003, +0.097] | margin_lift | 400 |
|  | hf | 1446 (607) | 168 (11.6%) | +0.047 [-0.027, +0.126] | +0.026 [-0.029, +0.079] | +0.033 [-0.042, +0.102] | +0.073 [-0.014, +0.163] |  |  |
|  | human | 5542 (2105) | 727 (13.1%) | +0.017 [-0.024, +0.058] | +0.010 [-0.015, +0.036] | +0.018 [-0.024, +0.065] | +0.056 [+0.015, +0.096] |  |  |
|  | live | 3376 (837) | 135 (4.0%) | +0.001 [-0.075, +0.081] | -0.013 [-0.066, +0.041] | -0.095 [-0.181, -0.009] | +0.057 [-0.028, +0.151] |  |  |
| sneaky_lock.defender | pro | 967 (677) | 188 (19.4%) | +0.030 [-0.056, +0.118] | +0.012 [-0.049, +0.064] | -0.016 [-0.145, +0.086] | +0.063 [-0.029, +0.141] | no_lift | 400 |
|  | hf | 0 (-) | 0 (-) | - | - | - | - |  |  |
|  | human | 967 (677) | 188 (19.4%) | +0.030 [-0.056, +0.118] | +0.012 [-0.049, +0.064] | -0.016 [-0.145, +0.086] | +0.063 [-0.029, +0.141] |  |  |
|  | live | 407 (301) | 18 (4.4%) | -0.074 [-0.341, +0.211] | -0.116 [-0.248, -0.004] | -0.186 [-0.385, -0.005] | - |  |  |
| rocket_cycle | pro | 1702 (924) | 427 (25.1%) | +0.062 [-0.015, +0.148] | +0.079 [+0.050, +0.117] | +0.030 [-0.033, +0.102] | - | win_lift | 600 |
|  | hf | 1453 (779) | 405 (27.9%) | +0.102 [+0.031, +0.165] | +0.079 [+0.046, +0.109] | +0.070 [+0.020, +0.107] | - |  |  |
|  | human | 3155 (1703) | 832 (26.4%) | +0.082 [+0.030, +0.143] | +0.079 [+0.057, +0.103] | +0.050 [+0.010, +0.091] | - |  |  |
|  | live | 1585 (580) | 33 (2.1%) | +0.123 [-0.013, +0.304] | +0.129 [+0.029, +0.221] | +0.081 [-0.090, +0.277] | - |  |  |
| rocket_cycle.after2 | pro | 1204 (638) | 330 (27.4%) | +0.066 [-0.019, +0.158] | +0.079 [+0.046, +0.123] | +0.045 [-0.021, +0.125] | - | win_lift | 600 |
|  | hf | 1058 (559) | 325 (30.7%) | +0.116 [+0.039, +0.196] | +0.086 [+0.045, +0.121] | +0.081 [+0.022, +0.124] | - |  |  |
|  | human | 2262 (1197) | 655 (29.0%) | +0.091 [+0.033, +0.153] | +0.082 [+0.058, +0.108] | +0.064 [+0.016, +0.108] | - |  |  |
|  | live | 1299 (462) | 22 (1.7%) | +0.227 [+0.056, +0.432] | +0.176 [+0.086, +0.263] | +0.265 [+0.119, +0.426] | - |  |  |
| rocket_tornado_clump | pro | 828 (612) | 79 (9.5%) | -0.020 [-0.133, +0.094] | +0.000 [-0.087, +0.080] | -0.008 [-0.131, +0.120] | +0.064 [-0.064, +0.196] | no_lift | 600 |
|  | hf | 1345 (950) | 63 (4.7%) | -0.043 [-0.188, +0.087] | -0.032 [-0.098, +0.025] | -0.025 [-0.112, +0.053] | -0.051 [-0.180, +0.110] |  |  |
|  | human | 2173 (1562) | 142 (6.5%) | -0.030 [-0.120, +0.053] | -0.014 [-0.070, +0.039] | -0.015 [-0.096, +0.069] | +0.015 [-0.076, +0.110] |  |  |
|  | live | 224 (177) | 13 (5.8%) | -0.064 [-0.222, +0.000] | -0.102 [-0.331, +0.058] | -0.129 [-0.370, +0.112] | - |  |  |
| rocket_tornado_tower | pro | 2371 (1045) | 304 (12.8%) | -0.025 [-0.093, +0.042] | -0.015 [-0.045, +0.015] | -0.015 [-0.064, +0.029] | -0.045 [-0.082, -0.010] | no_lift | 600 |
|  | hf | 3077 (1420) | 303 (9.8%) | -0.014 [-0.068, +0.036] | +0.008 [-0.011, +0.026] | -0.007 [-0.036, +0.021] | +0.009 [-0.010, +0.029] |  |  |
|  | human | 5448 (2465) | 607 (11.1%) | -0.019 [-0.061, +0.022] | -0.004 [-0.022, +0.014] | -0.011 [-0.039, +0.016] | -0.018 [-0.041, +0.003] |  |  |
|  | live | 150 (134) | 1 (0.7%) | -0.667 [-1.000, +0.000] | -0.381 [-0.652, -0.234] | -0.591 [-1.195, -0.234] | - |  |  |
| king_redirect | pro | 10883 (1560) | 551 (5.1%) | -0.085 [-0.147, -0.016] | -0.036 [-0.064, -0.004] | -0.025 [-0.090, +0.053] | -0.065 [-0.132, +0.005] | win_lift | 1200 |
|  | hf | 112970 (23357) | 6864 (6.1%) | +0.024 [+0.006, +0.042] | -0.032 [-0.041, -0.022] | +0.011 [-0.008, +0.030] | +0.037 [+0.023, +0.060] |  |  |
|  | human | 123853 (24917) | 7415 (6.0%) | +0.016 [+0.001, +0.033] | -0.032 [-0.040, -0.022] | +0.008 [-0.010, +0.027] | +0.030 [+0.016, +0.053] |  |  |
|  | live | 6179 (796) | 28 (0.4%) | -0.214 [-0.470, +0.048] | -0.169 [-0.318, -0.012] | +0.038 [-0.352, +0.365] | - |  |  |
| king_redirect.wincon | pro | 3473 (1069) | 282 (8.1%) | -0.105 [-0.189, -0.026] | -0.025 [-0.056, +0.017] | +0.005 [-0.075, +0.087] | +0.033 [-0.052, +0.124] | win_lift | 400 |
|  | hf | 37450 (15759) | 4056 (10.8%) | +0.048 [+0.026, +0.072] | +0.017 [+0.005, +0.030] | +0.058 [+0.036, +0.085] | +0.200 [+0.179, +0.224] |  |  |
|  | human | 40923 (16828) | 4338 (10.6%) | +0.039 [+0.018, +0.063] | +0.014 [+0.003, +0.028] | +0.055 [+0.033, +0.080] | +0.190 [+0.169, +0.213] |  |  |
|  | live | 2066 (574) | 10 (0.5%) | -0.066 [-0.384, +0.245] | -0.225 [-0.380, -0.058] | +0.073 [-0.375, +0.781] | - |  |  |
| king_redirect.hog | pro | 838 (224) | 246 (29.4%) | -0.083 [-0.162, +0.000] | +0.001 [-0.033, +0.036] | +0.029 [-0.059, +0.115] | +0.071 [-0.013, +0.151] | win_lift | 400 |
|  | hf | 8037 (3124) | 3511 (43.7%) | +0.065 [+0.041, +0.090] | +0.036 [+0.024, +0.049] | +0.082 [+0.057, +0.110] | +0.262 [+0.237, +0.288] |  |  |
|  | human | 8875 (3348) | 3757 (42.3%) | +0.056 [+0.033, +0.082] | +0.034 [+0.022, +0.047] | +0.079 [+0.055, +0.107] | +0.249 [+0.227, +0.276] |  |  |
|  | live | 534 (156) | 7 (1.3%) | -0.076 [-0.428, +0.281] | -0.198 [-0.402, -0.032] | +0.096 [-0.439, +0.764] | - |  |  |
| def_xbow_hard | pro | 973 (469) | 301 (30.9%) | +0.162 [+0.080, +0.238] | -0.067 [-0.112, -0.016] | -0.010 [-0.106, +0.097] | -0.030 [-0.068, +0.010] | win_lift | 1200 |
|  | hf | 2172 (950) | 384 (17.7%) | +0.081 [+0.014, +0.146] | -0.052 [-0.076, -0.026] | -0.024 [-0.078, +0.025] | -0.016 [-0.050, +0.017] |  |  |
|  | human | 3145 (1419) | 685 (21.8%) | +0.117 [+0.070, +0.166] | -0.058 [-0.081, -0.034] | -0.018 [-0.066, +0.039] | -0.022 [-0.045, +0.004] |  |  |
|  | live | 786 (290) | 98 (12.5%) | -0.048 [-0.164, +0.075] | -0.108 [-0.167, -0.046] | -0.152 [-0.268, -0.016] | +0.025 [-0.053, +0.108] |  |  |
| def_xbow_hard.ready | pro | 801 (425) | 241 (30.1%) | +0.172 [+0.081, +0.257] | -0.053 [-0.099, -0.002] | +0.015 [-0.085, +0.127] | -0.023 [-0.063, +0.020] | win_lift | 1200 |
|  | hf | 1770 (845) | 324 (18.3%) | +0.090 [+0.026, +0.161] | -0.040 [-0.067, -0.015] | -0.006 [-0.059, +0.049] | -0.013 [-0.047, +0.025] |  |  |
|  | human | 2571 (1270) | 565 (22.0%) | +0.124 [+0.069, +0.178] | -0.045 [-0.072, -0.020] | +0.003 [-0.053, +0.062] | -0.017 [-0.044, +0.011] |  |  |
|  | live | 618 (256) | 65 (10.5%) | -0.115 [-0.235, -0.001] | -0.132 [-0.195, -0.065] | -0.232 [-0.350, -0.076] | -0.033 [-0.122, +0.057] |  |  |
| opp_lane_punish | pro | 5138 (1462) | 794 (15.4%) | -0.014 [-0.053, +0.020] | -0.012 [-0.034, +0.009] | -0.040 [-0.084, +0.002] | +0.130 [+0.099, +0.163] | win_lift | 400 |
|  | hf | 419074 (84419) | 62092 (14.8%) | +0.016 [+0.013, +0.019] | +0.090 [+0.088, +0.094] | +0.039 [+0.036, +0.044] | +0.302 [+0.297, +0.305] |  |  |
|  | human | 424212 (85881) | 62886 (14.8%) | +0.016 [+0.012, +0.020] | +0.089 [+0.086, +0.092] | +0.038 [+0.034, +0.042] | +0.299 [+0.296, +0.303] |  |  |
|  | live | 2600 (773) | 356 (13.7%) | -0.019 [-0.067, +0.029] | +0.066 [+0.026, +0.104] | -0.090 [-0.158, -0.023] | +0.244 [+0.190, +0.300] |  |  |
| counterpush | pro | 2044 (1024) | 1282 (62.7%) | -0.044 [-0.095, +0.010] | -0.017 [-0.048, +0.019] | -0.086 [-0.155, -0.021] | +0.044 [-0.009, +0.093] | win_negative | 600 |
|  | hf | 107525 (56014) | 64045 (59.6%) | -0.009 [-0.015, -0.003] | -0.016 [-0.020, -0.013] | -0.028 [-0.033, -0.024] | +0.120 [+0.114, +0.125] |  |  |
|  | human | 109569 (57038) | 65327 (59.6%) | -0.010 [-0.016, -0.004] | -0.016 [-0.020, -0.013] | -0.029 [-0.035, -0.024] | +0.118 [+0.113, +0.124] |  |  |
|  | live | 998 (498) | 561 (56.2%) | -0.055 [-0.119, +0.008] | -0.041 [-0.082, +0.004] | -0.081 [-0.152, -0.002] | -0.026 [-0.104, +0.042] |  |  |
| xbow_out_of_cycle | pro | 1570 (627) | 861 (54.8%) | -0.030 [-0.087, +0.030] | +0.002 [-0.038, +0.040] | -0.029 [-0.099, +0.047] | +0.023 [-0.034, +0.083] | no_lift | 400 |
|  | hf | 3761 (1312) | 1935 (51.4%) | -0.010 [-0.043, +0.024] | -0.003 [-0.023, +0.013] | +0.003 [-0.032, +0.037] | +0.021 [-0.015, +0.054] |  |  |
|  | human | 5331 (1939) | 2796 (52.4%) | -0.016 [-0.044, +0.013] | -0.002 [-0.019, +0.016] | -0.007 [-0.039, +0.028] | +0.021 [-0.010, +0.050] |  |  |
|  | live | 1321 (355) | 645 (48.8%) | -0.050 [-0.108, +0.015] | -0.014 [-0.048, +0.028] | -0.064 [-0.134, +0.013] | +0.029 [-0.026, +0.087] |  |  |
| weakest_princess | pro | 11669 (1342) | 7987 (68.5%) | +0.008 [-0.023, +0.042] | +0.023 [+0.008, +0.038] | +0.018 [-0.010, +0.046] | +0.212 [+0.186, +0.235] | win_lift | 200 |
|  | hf | 976590 (80598) | 699541 (71.6%) | +0.051 [+0.048, +0.054] | -0.013 [-0.014, -0.011] | -0.013 [-0.015, -0.011] | +0.247 [+0.245, +0.249] |  |  |
|  | human | 988259 (81940) | 707528 (71.6%) | +0.051 [+0.048, +0.053] | -0.012 [-0.014, -0.010] | -0.013 [-0.015, -0.010] | +0.247 [+0.244, +0.249] |  |  |
|  | live | 5377 (690) | 3029 (56.3%) | +0.021 [-0.012, +0.052] | -0.022 [-0.044, -0.002] | -0.011 [-0.047, +0.029] | +0.154 [+0.120, +0.184] |  |  |
| lead_defend | pro | 305 (175) | 141 (46.2%) | +0.009 [-0.094, +0.125] | -0.137 [-0.233, -0.047] | -0.195 [-0.345, -0.057] | +0.016 [-0.041, +0.072] | win_negative | end |
|  | hf | 49136 (29543) | 18229 (37.1%) | -0.045 [-0.052, -0.039] | -0.146 [-0.153, -0.139] | -0.146 [-0.156, -0.137] | -0.026 [-0.033, -0.020] |  |  |
|  | human | 49441 (29718) | 18370 (37.2%) | -0.045 [-0.050, -0.039] | -0.146 [-0.153, -0.139] | -0.146 [-0.155, -0.137] | -0.026 [-0.033, -0.020] |  |  |
|  | live | 177 (95) | 114 (64.4%) | +0.003 [-0.050, +0.052] | -0.066 [-0.202, +0.090] | -0.207 [-0.351, +0.033] | -0.019 [-0.069, +0.021] |  |  |
| one_one_other | pro | 147 (24) | 76 (51.7%) | +0.054 [-0.187, +0.385] | -0.004 [-0.206, +0.152] | +0.055 [-0.144, +0.316] | +0.197 [-0.022, +0.402] | win_negative | 400 |
|  | hf | 82143 (9589) | 37447 (45.6%) | -0.009 [-0.018, -0.000] | +0.056 [+0.051, +0.061] | +0.061 [+0.055, +0.067] | +0.170 [+0.162, +0.177] |  |  |
|  | human | 82290 (9613) | 37523 (45.6%) | -0.009 [-0.018, -0.001] | +0.056 [+0.051, +0.061] | +0.061 [+0.055, +0.066] | +0.170 [+0.161, +0.177] |  |  |
|  | live | 218 (38) | 148 (67.9%) | +0.046 [+0.000, +0.126] | +0.081 [-0.048, +0.170] | +0.079 [-0.097, +0.206] | +0.113 [-0.096, +0.224] |  |  |
| bank_pre2x | pro | 1533 (1533) | 418 (27.3%) | +0.001 [-0.057, +0.063] | -0.015 [-0.043, +0.011] | -0.018 [-0.102, +0.065] | - | win_lift | 200 |
|  | hf | 150334 (76797) | 31644 (21.1%) | +0.015 [+0.011, +0.020] | -0.029 [-0.032, -0.025] | +0.003 [-0.003, +0.009] | - |  |  |
|  | human | 151867 (78330) | 32062 (21.1%) | +0.015 [+0.010, +0.021] | -0.029 [-0.032, -0.026] | +0.003 [-0.003, +0.009] | - |  |  |
|  | live | 842 (842) | 187 (22.2%) | +0.055 [-0.015, +0.127] | +0.018 [-0.040, +0.071] | +0.056 [-0.054, +0.185] | - |  |  |
| hold_vs_bank | pro | 5540 (1600) | 4479 (80.8%) | -0.021 [-0.061, +0.019] | -0.028 [-0.045, -0.011] | -0.079 [-0.137, -0.020] | +0.039 [+0.007, +0.071] | win_negative | 600 |
|  | hf | 396972 (83488) | 288147 (72.6%) | -0.006 [-0.009, -0.002] | -0.062 [-0.065, -0.060] | -0.041 [-0.045, -0.037] | -0.004 [-0.007, -0.001] |  |  |
|  | human | 402512 (85088) | 292626 (72.7%) | -0.006 [-0.010, -0.003] | -0.062 [-0.064, -0.060] | -0.042 [-0.046, -0.037] | -0.004 [-0.007, -0.000] |  |  |
|  | live | 1794 (683) | 1370 (76.4%) | +0.042 [-0.015, +0.102] | -0.003 [-0.045, +0.037] | +0.039 [-0.048, +0.127] | -0.005 [-0.058, +0.047] |  |  |
| pull_split | pro | 2366 (1063) | 844 (35.7%) | -0.001 [-0.044, +0.043] | -0.026 [-0.052, -0.004] | -0.033 [-0.091, +0.019] | -0.002 [-0.049, +0.036] | win_lift | 200 |
|  | hf | 114412 (58751) | 29580 (25.9%) | +0.023 [+0.017, +0.029] | -0.010 [-0.014, -0.005] | -0.012 [-0.018, -0.005] | +0.000 [-0.007, +0.007] |  |  |
|  | human | 116778 (59814) | 30424 (26.1%) | +0.022 [+0.017, +0.028] | -0.010 [-0.014, -0.006] | -0.012 [-0.018, -0.006] | +0.000 [-0.007, +0.006] |  |  |
|  | live | 1128 (512) | 379 (33.6%) | -0.022 [-0.080, +0.035] | -0.023 [-0.063, +0.028] | -0.040 [-0.113, +0.046] | -0.001 [-0.073, +0.066] |  |  |
| log_for_barrel | pro | 656 (111) | 309 (47.1%) | +0.080 [-0.002, +0.163] | +0.037 [-0.007, +0.082] | +0.107 [+0.014, +0.201] | +0.723 [+0.669, +0.783] | win_lift | 200 |
|  | hf | 14975 (2376) | 7709 (51.5%) | +0.034 [+0.018, +0.048] | +0.022 [+0.015, +0.029] | +0.021 [+0.007, +0.035] | +0.542 [+0.528, +0.556] |  |  |
|  | human | 15631 (2487) | 8018 (51.3%) | +0.035 [+0.020, +0.050] | +0.023 [+0.016, +0.030] | +0.024 [+0.009, +0.038] | +0.548 [+0.535, +0.563] |  |  |
|  | live | 555 (122) | 188 (33.9%) | -0.026 [-0.120, +0.071] | +0.066 [+0.011, +0.115] | -0.001 [-0.153, +0.115] | +0.680 [+0.597, +0.764] |  |  |
| siege_answer | pro | 811 (150) | 18 (2.2%) | +0.090 [-0.137, +0.313] | +0.042 [-0.155, +0.249] | +0.168 [-0.146, +0.426] | - | win_lift | 400 |
|  | hf | 67027 (14729) | 2264 (3.4%) | +0.036 [+0.015, +0.055] | +0.003 [-0.008, +0.013] | +0.015 [-0.005, +0.034] | -0.074 [-0.094, -0.054] |  |  |
|  | human | 67838 (14879) | 2282 (3.4%) | +0.036 [+0.018, +0.055] | +0.003 [-0.008, +0.014] | +0.017 [-0.004, +0.035] | -0.075 [-0.095, -0.054] |  |  |
|  | live | 217 (42) | 25 (11.5%) | -0.076 [-0.281, +0.150] | +0.045 [-0.068, +0.199] | +0.021 [-0.247, +0.408] | - |  |  |
| siege_answer.xbow | pro | 213 (39) | 5 (2.4%) | +0.405 [+0.133, +0.750] | +0.262 [-0.067, +0.553] | +0.375 [-0.131, +0.879] | - | win_lift | 600 |
|  | hf | 15484 (3819) | 730 (4.7%) | +0.054 [+0.016, +0.090] | +0.019 [-0.001, +0.038] | +0.023 [-0.018, +0.060] | -0.053 [-0.090, -0.016] |  |  |
|  | human | 15697 (3858) | 735 (4.7%) | +0.056 [+0.020, +0.091] | +0.020 [+0.001, +0.040] | +0.025 [-0.015, +0.063] | -0.053 [-0.088, -0.015] |  |  |
|  | live | 84 (16) | 14 (16.7%) | -0.096 [-0.409, +0.210] | +0.071 [-0.137, +0.322] | -0.004 [-0.420, +0.493] | - |  |  |
| iw_press | pro | 0 (-) | 0 (-) | - | - | - | - | thin | 200 |
|  | hf | 0 (-) | 0 (-) | - | - | - | - |  |  |
|  | live | 0 (-) | 0 (-) | - | - | - | - |  |  |
| opening_restraint | pro | 690 (690) | 545 (79.0%) | -0.086 [-0.174, +0.006] | -0.022 [-0.044, -0.001] | -0.101 [-0.259, +0.058] | - | no_lift | 1200 |
|  | hf | 71274 (55660) | 43157 (60.6%) | -0.004 [-0.012, +0.004] | -0.071 [-0.074, -0.068] | -0.046 [-0.056, -0.035] | - |  |  |
|  | human | 71964 (56350) | 43702 (60.7%) | -0.005 [-0.013, +0.003] | -0.070 [-0.073, -0.067] | -0.047 [-0.057, -0.036] | - |  |  |
|  | live | 326 (326) | 182 (55.8%) | +0.024 [-0.078, +0.129] | -0.075 [-0.130, -0.027] | +0.151 [-0.034, +0.329] | - |  |  |
| opening_restraint_xb | pro | 690 (690) | 537 (77.8%) | +0.058 [-0.028, +0.141] | +0.012 [-0.009, +0.033] | +0.020 [-0.129, +0.178] | - | margin_lift | 400 |
|  | hf | 1608 (1608) | 1104 (68.7%) | -0.077 [-0.128, -0.025] | -0.000 [-0.012, +0.012] | -0.155 [-0.226, -0.083] | - |  |  |
|  | human | 2298 (2298) | 1641 (71.4%) | -0.033 [-0.077, +0.013] | +0.004 [-0.007, +0.014] | -0.098 [-0.172, -0.030] | - |  |  |
|  | live | 326 (326) | 133 (40.8%) | -0.019 [-0.117, +0.085] | +0.004 [-0.049, +0.055] | -0.114 [-0.299, +0.075] | - |  |  |
| opening_no_xb_tesla | pro | 690 (690) | 645 (93.5%) | +0.108 [-0.037, +0.243] | +0.022 [-0.012, +0.054] | -0.069 [-0.360, +0.241] | - | no_lift | 1200 |
|  | hf | 1608 (1608) | 1496 (93.0%) | -0.115 [-0.211, -0.017] | +0.003 [-0.012, +0.018] | -0.239 [-0.380, -0.103] | - |  |  |
|  | human | 2298 (2298) | 2141 (93.2%) | -0.048 [-0.127, +0.030] | +0.009 [-0.007, +0.023] | -0.187 [-0.323, -0.051] | - |  |  |
|  | live | 326 (326) | 262 (80.4%) | -0.098 [-0.232, +0.042] | -0.023 [-0.092, +0.039] | -0.220 [-0.435, +0.003] | - |  |  |

Mined per-play extras: 135 icebow8 pairs tested (Bonferroni z 3.56); listed = raw CI low > 0 (candidates; a library entry needs Bonferroni = yes):

| pair (A>B:lane rel + B zone) | n A-plays (B in hand) | treated (B next) | win lift [95% CI] | Bonferroni |
|---|---|---|---|---|
| skeletons>rocket:Oo | 36419 | 280 | +0.097 [+0.043, +0.152] | no |
| the_log>rocket:Oo | 36253 | 221 | +0.094 [+0.026, +0.149] | no |
| knight>skeletons:Oo | 10117 | 305 | +0.077 [+0.024, +0.131] | no |
| knight>rocket:So | 28845 | 370 | +0.062 [+0.017, +0.104] | no |
| tesla>x_bow:Od | 19276 | 366 | +0.060 [+0.010, +0.113] | no |
| knight>x_bow:Od | 15865 | 419 | +0.050 [+0.009, +0.100] | no |
| skeletons>x_bow:Sd | 21046 | 551 | +0.044 [+0.007, +0.085] | no |
| tesla>tornado:So | 12951 | 201 | +0.065 [+0.002, +0.130] | no |
| the_log>x_bow:Od | 18057 | 331 | +0.051 [+0.002, +0.097] | no |

## What P3-FORK needs to run a macro as a fork prefix
1. Trigger evaluators in the SIM state for each `start_condition` (all need only what the SIM already has: tower HP,
   crowns, phase, own hand + elixir, the opponent's plays + public elixir counter + revealed cycle; sneaky_lock.defender
   and rocket_tornado_clump also need enemy body positions near the X-Bow site / the clump centroid).
2. A prefix executor: each `prefix` step is (card, placement rule in OUR frame tiles, after_ticks). Map tiles to engine
   cells with the side's mirror (own frame: own king (9, 29)); a step whose card is not in hand or not affordable at its
   tick aborts the fork (no stand-in card). Steps with card "none" are restraint macros: the fork plays the learned policy
   with the named card class masked for the window (e.g. no offensive play >= 4 elixir for 600 ticks).
3. Horizon = `horizon_ticks` ('end' -> run to the match end with K = 2 paired continuations, PLAN P6.3); the 10%
   terminal-run bias audit per macro.
4. Credit: the composite-return difference vs the base branch on EVERY prefix action (alternative rows, PLAN P6.2).
5. Pin the library by sha (LIBRARY.json sha256 in the table header); a new library = a new sha.
6. Usage parity check per candidate (PLAN "Measured on every candidate"): run `mine.py` on the candidate's SIM / live
   matches and compare `tr_rate` with the pro / HF rate in the same start states (e.g. Rocket cycling pros 25.1% vs
   CLXIII live 2.1%).

## Next steps
- Diagnose the king redirect source split (pro -0.085 vs HF +0.024): re-run the pro side with the pro raw frames' own
  bodies, and split by what else was in hand (b).
- Sneaky lock: the lock gain is measured (+0.056); test the win effect where it matters (OT / even crowns) and with body
  positions from the HF re-drive tokens (`tok` column) instead of plays only.
- Counter-push: add own-body survival from the re-drive tokens; lead protection: condition on the opponent's banked elixir.
- Hero IW press: needs data (Hero IW pro crawl; or live press logs from CLXIII).
- Re-run on re-drive passes 2 / 3 (more tier A) and add tier-B prefixes (results real, states only up to the cut).
