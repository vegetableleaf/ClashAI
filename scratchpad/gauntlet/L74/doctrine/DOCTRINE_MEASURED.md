# The "keep both princess towers" doctrine, measured (owner claim 10-18)

Owner claim (a hypothesis, tested here): for X-Bow / icebow, a 1-1 crown state is far harder to win than keeping both
princess towers, and a defence-first style wins: positive trades, the most effective play rather than the cheapest, early
restraint, chip via X-Bow locks + Rocket cycling.

Everything below comes from `measure.py` -> `measure.out` (one run, local files only). Proportions carry Wilson 95% CIs,
differences carry Newcombe 95% CIs, and means / episode shares carry a match-bootstrap 95% CI. n is printed in every cell.

## Bottom line

1. **The core claim holds on the data, and it is X-Bow-specific.** Pro X-Bow players who start overtime at 1-1 win
   29.9% vs 52.7% from 0-0 (-22.9 pp [-28.4, -16.8]). Adjusted for opponent archetype it is -24.6 pp [-30.3, -18.9]. Among
   deck types X-Bow has the biggest penalty: mortar -5.0, bridge/bait -10.7, beatdown **+11.9** (beatdown gains from 1-1).
   Our live models show the same, -28 to -39 pp.
2. **Losing the first princess is close to fatal for X-Bow.** Pros: P(win | lost the first princess) <= 2.5% for all X-Bow
   decks and <= 0.6% for the exact icebow deck. For non-X-Bow decks it is <= 21% (17.3% win after losing any princess).
   Ours: 1.4-3.6%.
3. **Our bot's real gap is giving leads back, not getting broken.** It loses a princess about as often as pros do (47-55% of
   matches vs 48% for icebow pros). But after going 1-0 up it loses a tower back in 15-20% of matches. Pros do that in
   at most 5.1% (icebow) / 10.2% (all X-Bow). Both sides take a princess in 14-20% of our matches, vs 2.0% (icebow pros) /
   3.7% (X-Bow pros). Our matches look like non-X-Bow games (18.3%), not like pro X-Bow games.
4. **The SIM does not teach any of this.** In the CLIII SIM eval the 1-1 penalty is only -8.1 pp [-18.8, +2.3], and the
   SIM opponent takes a princess in 31.6% of games vs 47-55% live. Training sees a world where towers are safer and 1-1 is
   nearly harmless. It is the same root the habits diagnosis found ("SIM opponents don't convert").
5. **Style.** Our bot gives cheap-only answers to heavy pushes more often (CLIII 42% vs pros 28%). It almost never Rockets a
   heavy push (0.4-2.2% vs 8.3%), Rockets a tower 3-4x less (0.39-0.58 vs 1.60 per match) and commits its first bridge
   X-Bow 23 s earlier (51 s vs 74.5 s). Two parts of the doctrine are **not** supported as stated: (a) by the spend measure
   our bot's trades are already as "positive" as pros'; (b) pros who bridge X-Bow before 60 s win *more*, not less
   (+5.4 pp), so "early X-Bow loses" is wrong in its simple form.

## Data

| source | what | n | crown timing |
|---|---|---|---|
| pro_icebow8 | exact icebow deck (Tornado, Tesla, IW, X-Bow, Rocket, Knight, Log, Skeletons), Path of Legend: crawl2 (1,335) + HF (715) | 2,050 | final crowns + length (HF) or last play tick (crawl2) |
| pro_xbow_other | other X-Bow decks, Path of Legend, HF replays | 8,350 | final crowns + length |
| pro_nonxbow | every side of HF Path of Legend games with no X-Bow on either side (the deck-neutral reference) | 397,710 | final crowns + length |
| sim_CLIII | CLIII promotion eval on fin13 vs generated opponents (4 seed sets; **not self-play**) | 1,920 | final crowns + end tick |
| live CLIII / CXXXVIII / CXXIV | graded live ladder matches from the reader logs | 168 / 262 / 300 | **exact** (tower HP every frame) |
| live cue_ab2 | live since 10-18 18:07 | **9** (no conclusions possible) | exact |

- No pro or SIM source has a tower-fall timeline. Exact for them: final crowns, the **overtime-start state** and "ever lost
  / ever took a princess". In the HF replays regulation ends at 184.5 s of replay time and replay ticks are game-clock ticks
  (no play after tick 3602 in a regulation game). So a replay longer than about 186 s reached overtime tied at min(crowns).
  crawl2 has no length: a play after tick 3600 proves overtime. Checked on HF, that rule misses 77 / 6,746 overtime games
  (1.1%).
- "Who fell first" is known for pros / SIM only when one side ended with 0 crowns. For the rest (icebow 41, all X-Bow 382)
  I report **bounds**: each ambiguous match is assigned both ways, and the extremes are the interval. I tried a
  pocket-deploy estimate too (a troop placed in the enemy half proves that princess is down). It has 0 false positives on
  pros, but it got only 56 / 118 (47.5%) of the live first crowns right, because our bot almost never uses the pocket.
  So it is **not used**.
- Live clock: live `game_tick` = clock + 78 (regulation-end frames sit at 3676-3681). The crown timeline matches the logged
  result in 737 / 739 matches.
- Tiebreak: a full overtime with unequal crowns means the winner got one tower from the tiebreak. The tables below drop
  that tower ("in play"). With it counted the conclusions are the same (measure.out has both).

## 1. Crown state

### 1a. Overtime-start state (exact everywhere)

| group | P(win) all | OT starts 0-0 | OT starts 1-1 | 1-1 minus 0-0 |
|---|---|---|---|---|
| pro_icebow8 | 47.2% [45.0, 49.3] n=2050 | 50.7% [48.3, 53.2] n=1555 | 20.0% [8.9, 39.1] n=25 | **-30.7 pp [-42.2, -11.4]** |
| pro_xbow_other | 51.7% [50.6, 52.8] n=8350 | 53.3% [52.0, 54.5] n=5949 | 31.0% [25.3, 37.4] n=221 | -22.3 [-28.1, -15.8] |
| pro_all_xbow | 50.8% [49.9, 51.8] n=10400 | 52.7% [51.6, 53.9] n=7504 | 29.9% [24.5, 35.9] n=246 | **-22.9 [-28.4, -16.8]** |
| sim_CLIII | 65.2% [63.0, 67.3] n=1920 | 62.5% [59.5, 65.5] n=990 | 54.4% [44.2, 64.3] n=90 | -8.1 [-18.8, +2.3] |
| live CLIII | 47.6% [40.2, 55.1] n=168 | 56.4% [43.3, 68.6] n=55 | 26.3% [11.8, 48.8] n=19 | -30.0 [-49.0, -4.0] |
| live CXXXVIII | 48.1% [42.1, 54.1] n=262 | 62.8% [52.2, 72.3] n=86 | 24.0% [11.5, 43.4] n=25 | -38.8 [-54.5, -16.7] |
| live CXXIV | 51.3% [45.7, 56.9] n=300 | 67.0% [57.7, 75.1] n=109 | 39.1% [22.2, 59.2] n=23 | -27.8 [-46.7, -5.7] |

(pro_nonxbow is 50.0 / 50.0 by symmetry, so it is not a reference here. The deck-type split below is the reference.)

**Is it X-Bow-specific?** The same gap for each pro's OWN deck type, same-type mirrors dropped:

| own deck | OT 1-1 | OT 0-0 | gap |
|---|---|---|---|
| beatdown | 56.1% n=8568 | 44.2% n=53575 | +11.9 pp [+10.8, +13.1] |
| bridge / bait | 44.3% n=7429 | 54.9% n=52174 | -10.7 [-11.9, -9.5] |
| mortar | 46.9% n=1229 | 51.8% n=14059 | -5.0 [-7.9, -2.1] |
| **x-bow** | 30.2% n=230 | 53.2% n=6372 | **-23.0 [-28.7, -16.7]** |

**Is it just the matchup?** (Unfavourable matchups might simply reach 1-1 more often.) Pro X-Bow, Mantel-Haenszel within
opponent archetype: beatdown 29.5% (n=222) vs 54.9%; bridge/bait 36.4% (n=22) vs 51.6%. Adjusted gap **-24.6 pp
[-30.3, -18.9]**. Not tested: player skill. Weaker X-Bow players may reach 1-1 more often (crawl2 ratings would allow a
check, but only 25 icebow 1-1 games exist).

### 1b. Losing / taking a princess in play (tiebreak tower removed)

| group | P(win \| ever lost one) | P(win \| ever took one) | P(lose one at all) | P(win \| lost FIRST) | P(win \| took FIRST) |
|---|---|---|---|---|---|
| pro_icebow8 | 0.6% [0.3, 1.3] n=993 | 95.6% [94.0, 96.8] n=797 | 48.4% [46.3, 50.6] | **bound [0.0, 0.6]%** | bound [95.6, 100]% |
| pro_all_xbow | 2.3% [1.9, 2.8] n=3997 | 92.2% [91.3, 93.0] n=3740 | 38.4% [37.5, 39.4] | bound [0.0, 2.5]% | bound [92.0, 100]% |
| pro_nonxbow | 17.3% [17.2, 17.5] n=210080 | 82.7% [82.5, 82.8] | 52.8% [52.7, 53.0] | bound [0.0, 21.0]% | bound [79.0, 100]% |
| sim_CLIII | 11.7% [9.4, 14.5] n=607 | 93.5% [92.0, 94.8] n=1187 | **31.6%** [29.6, 33.7] | bound [0.0, 13.4]% | bound [93.1, 100]% |
| live CLIII | 9.8% [5.2, 17.6] n=92 | 75.0% [65.7, 82.5] n=100 | 54.8% [47.2, 62.1] | 1.4% [0.2, 7.3] n=74 | 88.1% [79.5, 93.4] n=84 |
| live CXXXVIII | 6.7% [3.6, 12.3] n=134 | 77.4% [70.2, 83.3] n=155 | 51.1% [45.1, 57.1] | 3.6% [1.4, 9.0] n=110 | 85.9% [79.1, 90.8] n=135 |
| live CXXIV | 7.0% [3.9, 12.5] n=142 | 80.9% [74.5, 86.0] n=178 | 47.3% [41.8, 53.0] | 3.4% [1.3, 8.4] n=118 | 87.5% [81.5, 91.8] n=160 |

### 1c. Crown trades and given-back leads

| group | both sides took a princess | gave a 1-0 lead back (reached 1-1 after 1-0) | P(win \| reached 1-1, any time) |
|---|---|---|---|
| pro_icebow8 | **2.0%** [1.5, 2.7] | **<= 5.1%** (bound) | bound [12.5, 23.1]% |
| pro_all_xbow | 3.7% [3.3, 4.1] | <= 10.2% | bound [20.2, 34.7]% |
| pro_nonxbow | 18.3% [18.2, 18.4] | <= 34.6% | bound [34.6, 65.4]% |
| sim_CLIII | 7.7% [6.6, 9.0] | <= 12.5% | bound [38.9, 63.4]% |
| live CLIII | **20.2%** [14.9, 26.9] | **20.2%** [13.0, 30.0] n=84 | 26.7% [14.2, 44.4] n=30 |
| live CXXXVIII | 16.8% [12.8, 21.8] | 17.0% [11.6, 24.3] n=135 | 19.5% [10.2, 34.0] n=41 |
| live CXXIV | 14.0% [10.5, 18.4] | 15.0% [10.3, 21.3] n=160 | 25.6% [14.6, 41.1] n=39 |

Live trade order (matches that reached 1-1): took first then traded, pooled over the 3 Marks, 17/64 wins (27%). Lost first
then traded back: CLIII 7.7% n=13, CXXXVIII 22.2% n=18, CXXIV 26.7% n=15.

### 1d. Live crown state at 60 s / 120 s / overtime start (exact; pros not measurable)

CLIII at 120 s (start of double elixir): 0-0 56% [46, 65] n=106; 1-0 100% [82, 100] n=17; 0-1 4% [1, 20] n=24; 1-1 22%
[6, 55] n=9. At overtime start: 0-0 56% n=55; 1-0 100% n=21; 0-1 0% n=16; 1-1 26% n=19. CXXXVIII and CXXIV look the same
(measure.out "LIVE exact"). At 60 s almost every match is still 0-0 (144 / 168 for CLIII).

## 2. Style: pros vs our live models (same play-only code for both)

A defence episode = opponent troop plays with gaps <= 5 s (= one push, value = their elixir). Our answer = our plays on our
half (not a bridge X-Bow) from 2 s before to 8 s after the push. "Heavy" = a push of >= 10 elixir.

| metric | pro_icebow8 | pro X-Bow other | CLIII | CXXXVIII | CXXIV |
|---|---|---|---|---|---|
| spend trade per push, theirs minus ours (all) | +0.64 [+0.59, +0.68] | +0.64 | +0.60 [+0.46, +0.73] | +0.71 | +0.68 |
| spend trade, heavy pushes | +2.44 [+2.29, +2.58] | +2.62 | +2.60 [+2.18, +3.02] | +2.83 | +2.94 |
| cheap-only answers (all cards <= 3), all pushes | 53.2% [52.6, 53.7] | 53.0% | **60.0%** [58.2, 61.7] | 59.4% | 59.8% |
| cheap-only answers, heavy pushes | **27.5%** [26.4, 28.7] | 29.5% | **42.4%** [36.3, 48.8] | 32.4% [28.1, 36.9] | 39.0% [34.3, 43.7] |
| Rocket in the answer to a heavy push | **8.3%** [7.4, 9.2] | 2.7% | 0.4% [0.0, 1.4] | 0.8% | 2.2% |
| heavy pushes left unanswered | 3.8% | 3.4% | 0.4% | 0.5% | 0.9% |
| offensive spend, first 60 s (elixir) | 4.00 [3.85, 4.14] | 4.23 | 4.66 [4.18, 5.14] | 4.61 [4.19, 5.03] | 4.35 [3.98, 4.73] |
| matches with any offensive spend in the first 60 s | 61.7% [59.5, 63.7] | 65.9% | 73.2% [66.1, 79.3] | 69.1% [63.2, 74.4] | 67.0% |
| first bridge X-Bow (clock s) | **74.5** [72.1, 76.9] | 64.8 | **51.2** [44.1, 58.7] | 51.9 [46.5, 57.5] | 56.5 |
| bridge X-Bows per minute | 0.690 [0.672, 0.709] | 0.890 | 0.877 [0.824, 0.928] | 0.886 | 0.816 |
| Rockets at a tower per match | **1.60** [1.53, 1.67] | 0.43 | **0.39** [0.30, 0.49] | 0.42 [0.33, 0.52] | 0.58 [0.49, 0.67] |
| Rockets per minute (any aim) | 0.593 | 0.159 | 0.139 | 0.153 | 0.200 |
| own princess HP lost per minute (1.0 = one tower) | 0.340 [0.322, 0.357] (HF n=715) | 0.323 | 0.381 [0.344, 0.424] | **0.396** [0.358, 0.436] | 0.365 [0.333, 0.397] |
| own princess HP lost per match | 1.297 [1.258, 1.337] | 1.201 | 1.174 [1.083, 1.267] | 1.175 | 1.132 |
| per bridge X-Bow: life (s) / enemy tower HP lost while it lives | not measurable (no frames) | - | 16.7 / 1664 | 16.4 / 1567 | 17.0 / 1550 |

Early X-Bow vs winning (association; the opponent deck drives both): pros who bridge X-Bow before 60 s win **more**.
pro_icebow8 50.1% (n=942) vs 44.7% (n=1108), +5.4 pp [+1.1, +9.7]; other X-Bow +6.4 [+4.3, +8.6]. Live n.s. (CLIII +5.9
[-10.0, +21.2], CXXXVIII +0.3, CXXIV -2.5).

Caveats. Live opponent plays come from the reader's first sightings, so some are missed or late. Our matches show 1.4 heavy
pushes per match vs 2.5 for pros, which is part reader, part opponent pool. Live opponents are ~13k-trophy ladder players;
pro opponents are top Path of Legend players. The spend "trade" counts elixir committed, not elixir value destroyed.

## 3. Verdicts

| # | claim | verdict | evidence |
|---|---|---|---|
| 1 | 1-1 is far harder for X-Bow than 0-0 | **(a) measured, supported** (association) | pros -22.9 pp [-28.4, -16.8], matchup-adjusted -24.6 [-30.3, -18.9]; X-Bow worst of all deck types (beatdown +11.9); live -28..-39 pp. Not tested: player-skill selection |
| 2 | X-Bow must keep both towers to have a chance | **(a) measured, supported**, with a sharper form | losing the FIRST princess: pros <= 0.6% (icebow) / <= 2.5% (X-Bow) vs <= 21% non-X-Bow; live 1.4-3.6% |
| 2b | our bot loses towers too often | **(c) contradicted as stated** | P(lose a princess in play) 47-55% vs pros 48.4% (icebow). The measured gap is **giving a lead back**: 15-20% vs <= 5.1%; both-crown games 14-20% vs 2.0% |
| 3 | positive elixir trades | **(c) contradicted as a gap** | by spend our bot already matches or beats pros (heavy pushes +2.6..+2.9 vs +2.44). The measure cannot see value destroyed, so "trades matter" itself is (b) untested |
| 4 | most effective, not cheapest | **(a) measured gap** | cheap-only on heavy pushes 42.4% (CLIII) / 39.0% (CXXIV) / 32.4% (CXXXVIII) vs 27.5%; Rocket answers 0.4-2.2% vs 8.3%. That it causes wins is (b) untested |
| 5 | early restraint wins | gap **(a) measured**; win link **(c) contradicted in its simple form** | first bridge X-Bow 51 s vs 74.5 s, but early-X-Bow pros win +5.4 pp more. The conditional version (don't X-Bow into a heavy punish; habits: 40.5% vs 60.0% for CXXXVIII) is (b) plausible, untested causally |
| 6a | chip via Rocket cycling | **(a) measured gap** | tower Rockets 0.39-0.58 vs 1.60 per match (3-4x) |
| 6b | chip via X-Bow locks | volume: **(c) not a gap** (we place more: 0.82-0.89 vs 0.69 per min); lock time on pros **not measurable** | needs re-driven pro frames (step-d D1 re-drive could record tower HP) |
| 7 | minimise own-tower damage | **(a) small measured gap per minute**, none per match | CXXXVIII 0.396 [0.358, 0.436] vs 0.340 [0.322, 0.357] per minute; CLIII / CXXIV overlap; per match ours is lower (shorter games) |
| 8 | a defence-first style wins (overall) | **(b) plausible, untested** | pros differ from our bot in the doctrine's direction on 1c, 4, 6a and the first-X-Bow time, but this is observational, and claim 5 runs the other way |

## 4. Proposals for REB's successors (proposals only; no config or live change made)

In priority order, one change per experiment.

**Eval slices (cheap, first).** Add to stepd/readout.py and the live monitor, per Mark. Targets are pro icebow values:
- crown-path slices: P(lose a princess in play) (48%), both-crown rate (<= 2-4%), give-back after 1-0 (<= 5%), P(win |
  OT 1-1), and P(win | lost first);
- style slices: cheap-only on heavy pushes (28%), Rocket in heavy answers (8%), tower Rockets per match (1.6), first bridge
  X-Bow time (75 s).

The SIM readout should print the same crown slices next to live. Right now SIM 31.6% vs live 47-55% for losing a princess,
and SIM 54% vs live 20-27% for P(win | reached 1-1), so a SIM pass says little about tower discipline.

**Curriculum (the measured root).**
- C1. Gate the Stage-2 / exploiter opponent mix on crown statistics, not only win %. Keep a mix only if CLIII's P(lose a
  princess) against it is ~0.5 and its P(win | 1-1) is ~0.2-0.3, as on live. This is the habits lever 1 ("opponents gated
  on tower conversion"), now with a target number.
- C2. Crown-state starts: begin a share of episodes at 1-0 (a dead enemy princess at a clock time sampled from live falls)
  and at 1-1. That gives a direct "hold the lead" signal: live give-back is 15-20% vs pros <= 5%. It needs engine support
  for initial tower HP (untested).

**Reward terms (after C1, one at a time).**
- R1. Lead-protection penalty: our princess falls while we lead 1-0. Size it by the value mismatch. Live, going 1-0 ->
  1-1 drops P(win) from ~0.87 to ~0.27 (pooled took-first-then-traded 17/64). In the SIM the drop is ~0.93 -> ~0.54
  (bounds). So the SIM under-prices a given-back lead by ~0.2 of a win, and the penalty starts at ~0.2 x the win reward.
  This deliberately moves the SIM optimum toward live values. Risk: passivity. Guard it with the tower-Rocket and
  bridge-X-Bow slices.
- R2. Potential-based crown-state shaping, Phi = P_hat(win | crown state, clock) from the live tables. It is
  policy-invariant (it cannot change the best policy), so it only speeds up credit assignment. It does **not** fix the
  SIM's wrong values: lower priority than R1. Context: factorial factor E (tower_score shaping) is +1.4 pp naive on 15/16
  runs (analyze.py refuses with one run missing, factorial_analyze.out). Inconclusive, SIM only.
- R3. Re-grade the Rocket reward arms (spell_value, combo_rew) on tower Rockets per match and Rocket-in-heavy-answer share,
  not only on SIM win %. The SIM cannot reward what it doesn't punish. The pro gap is 3-4x.

**For REB itself (pro-imitation init):** IL-cue-w already plays more Rockets (1.09 vs 0.62 per game). Score REB's arms on
the slices above when the relays land. A REB that closes the give-back / both-crown gap is evidence for this doctrine
even if SIM win % is flat.

## Reproduce

```
icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/doctrine/pro_scan.py          # 252k HF replays -> pro_scan.parquet (~80 s)
icebow/.venv/Scripts/python.exe -X utf8 scratchpad/gauntlet/L74/habits/index.py          # refresh the live index
icebow/.venv/Scripts/python.exe -X utf8 scratchpad/gauntlet/L74/doctrine/build_live.py   # cache CLIII / CXXXVIII / CXXIV / cue_ab2 logs
icebow/.venv/Scripts/python.exe -X utf8 scratchpad/gauntlet/L74/doctrine/measure.py > measure.out
```

Inputs: habits/pro_sides.jsonl (pro plays, own frame), L67/hf/replays, icebow/data/royaleapi/crawl2, habits/cache (live),
pod_backup_weekend/stepd/clIII_fin13/eval (SIM). pro_scan.parquet (17 MB) is derived and not committed.
