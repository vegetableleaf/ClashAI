# Pro X-Bow lane placement (IL_Replay, 252,238 replays)

Script: `scratchpad/gauntlet/L74/loss_review/pro_xbow_lanes.py` (tables below are its verbatim output).
Owner question (2026-10-15): do strong humans concentrate offensive X-Bows on one enemy princess, and does concentrating go with winning?

## Method and frames
- Source: `L67/hf/replays/part-*.parquet`, `payload_json` (`royaleapi-battle-replay.v1`). `events[kind=play_card]` give `side` (team|opponent), `replay_tick_20hz`, `coordinates.native_world_units` (1/1000 tile, arena 18 x 32). In that field the team side sits at LOW y and the opponent at HIGH y (one absolute frame; `inversion_applied` is true on every event, verified on the first replay: team Executioner native y=500, opponent Guards native y=30499).
- Own frame: team side unchanged; opponent side rotated 180 deg (x -> 18-x, y -> 32-y). Own king is then at low y for every side.
- Offensive = own-frame y in [12,16). Lane = left if x<8, right if x>10, centre if |x-9|<1 (centre dropped from lane sets, still counted in n_off). Left/right is only a within-side label, so pooled results do not depend on which physical flank it is.
- X-Bow = any form (`x-bow`, `-ev1`, `-hero` suffix stripped). Only 1v1 replays (script skips any replay with more than 1 player per side; the first 10,000 rows were all 1v1). Win: team side from `battle.result`, opponent side inverted, draw = 0.5.
- 10,710 X-Bow deck-sides; 10,147 with >=1 offensive X-Bow; 10,010 with >=1 laned offensive X-Bow (the comparison population).

## Headline
1. Pros are NOT concentrating: 48.3% of side-matches with an offensive X-Bow use BOTH lanes (ours: r1 65%, F1 82%). But that is mostly count: 75% of 5+ X-Bow matches are both-lane; at exactly 2 X-Bows only 30% are.
2. Both-lane goes with a slightly LOWER win rate, in every stratum: pooled 51.5% vs 53.4% one-lane; n_off=2: 47.9 vs 57.3; 3: 54.2 vs 56.6; 4: 57.4 vs 60.5; 5+: 49.0 vs 51.9. Direction is the same in all 4 pooled strata and in Ranked-only; opponent-side-only is lower in all 4, team-side-only in 3 of 4 (n=3 is reversed, 69.3 vs 67.2). The 2-X-Bow gap (9.4 pp, 95% CIs do not overlap) is clear; the 3 / 4 / 5+ gaps (2-3 pp) are within overlapping CIs on their own. Pooled 2+ (both 51.5% vs one 56.5%) is confounded by count.
3. In the close decks the gap is bigger: Tesla+Ice Wizard 43.0% both vs 52.4% one (n=609/1216); exact icebow-8: 43.7% vs 49.0% overall, 2+ only 43.7% vs 57.4% (n=245/317); stratified, one-lane is higher in all 5 strata (n=2: 36.7 vs 53.7; 3: 46.7 vs 59.8; 4: 53.3 vs 62.5; 5+: 40.7 vs 58.3). Strata are small (48-134 per cell), so per-cell CIs are wide; the consistent sign is the evidence, not any one cell.
4. Lane switching: P(next offensive X-Bow is in the other lane) = 35.9% pooled (36.6% team side), 27.6% in Tesla+Ice Wizard, 28.6% exact icebow-8. This equals what independent draws from the side's own L/R mix would give (36.7%, 29.5%, 29.9% with small-sample correction), i.e. a pro picks a preferred lane per match and mostly sticks to it, with no extra tendency to alternate or to repeat beyond that. Pros switch rarely (about 1 in 3 pairs, 1 in 4 in close decks).
5. Comparison to ours: ours 65% / 82% both-lane vs 48% (pooled) and 33-34% (close decks) for pros; ours had 3.9 offensive X-Bows in both-lane matches, pros 4.9 pooled and 3.95-4.06 in close decks, so the count in both-lane matches is comparable, but our both-lane SHARE is roughly double the close-deck pros'. Our switch rate (r1 unknown) was not computable from here.

## Caveats
- Selection: replays are of top players (requested player = team side; team-side win rate 64-66% vs opponent side 36-38%, so absolute win rates are inflated for team; only within-side contrasts are valid). The opponent side is a typical top-ladder opponent, not a requested pro. Matches are mostly Ranked pathOfLegend (about 85% of the 10,010); no trophy/rank column is available to subset on.
- Causality: pros choose lane pattern with the situation (X-Bow vs the matchup, being behind, enemy building placement). Both-lane may reflect forced re-placement after losing an X-Bow in one lane, which is correlated with losing; one-lane does not mean "good". This analysis does not isolate the decision.
- Tower HP over time is NOT in the payload (only `final_tower_hitpoints`), so the "previous target princess damaged" split of the switch rate could not be done. Using final HP would be post-outcome and is not a valid proxy.
- X-Bow count per match: all placements 0:323 1:792 2:1448 3:1817 4:1761 5:1456 6:1182 7:819 8+:1112 (offensive counts in the output below). Offensive X-Bow counts are high (median 3): many placements are re-placements after the 30s lifetime / destruction, so n_off partly measures match length (5+ matches last about 285 s vs 225 s).
- Centre: 137 side-matches with offensive X-Bows had only centre placements and are excluded from pattern tables; centre placements inside laned matches count in n_off but not in lane sets, so a "one-lane, n_off=2" match can include a centre one.
- Switch null uses each side's own L/R mix, which absorbs per-match lane preference; it does not test whether the preference itself is chosen well.
- The "lane" for a pro is the lane on their own half where the X-Bow is placed (x side); I did not map it to the target enemy princess via tower HP, only by x side (an X-Bow in lane L threatens the enemy princess in lane L).

## Tables (script output)
Offensive = own-frame y in [12,16); lane by x vs 9 (|x-9|<1 = centre, dropped from lane sets).

X-Bow deck-sides: 10710; with >=1 offensive X-Bow: 10147; with >=1 laned offensive X-Bow: 10010.

All-X-Bow placements per side-match (8 = 8+): 0:323, 1:792, 2:1448, 3:1817, 4:1761, 5:1456, 6:1182, 7:819, 8:1112
Offensive count per side-match (8 = 8+): 0:563, 1:1412, 2:2042, 3:1930, 4:1544, 5:1157, 6:836, 7:518, 8:708


### ALL x-bow decks, both sides pooled

| n_off | pattern | matches | share of stratum | win % [95% CI] | mean crowns | mean dur s |
|---|---|---|---|---|---|---|
| 1+ | both | 4833 | 48.3% | 51.5% [50.0%,52.9%] | 0.62 | 264 |
| 1+ | one | 5177 | 51.7% | 53.4% [52.0%,54.8%] | 0.68 | 235 |
| 2 | both | 602 | 30.0% | 47.9% [44.0%,51.9%] | 0.77 | 224 |
| 2 | one | 1406 | 70.0% | 57.3% [54.7%,59.8%] | 0.79 | 223 |
| 3 | both | 912 | 47.4% | 54.2% [50.9%,57.4%] | 0.74 | 240 |
| 3 | one | 1011 | 52.6% | 56.6% [53.5%,59.6%] | 0.65 | 236 |
| 4 | both | 913 | 59.2% | 57.4% [54.2%,60.6%] | 0.68 | 254 |
| 4 | one | 628 | 40.8% | 60.5% [56.6%,64.3%] | 0.64 | 256 |
| 5+ | both | 2406 | 74.8% | 49.0% [47.0%,51.0%] | 0.52 | 287 |
| 5+ | one | 811 | 25.2% | 51.9% [48.5%,55.3%] | 0.54 | 284 |
| 2+ | both | 4833 | 55.6% | 51.5% [50.0%,52.9%] | 0.62 | 264 |
| 2+ | one | 3856 | 44.4% | 56.5% [54.9%,58.0%] | 0.68 | 245 |

mean offensive X-Bows: both-lane 4.86, one-lane 2.80

### team side only (the tracked top player)

| n_off | pattern | matches | share of stratum | win % [95% CI] | mean crowns | mean dur s |
|---|---|---|---|---|---|---|
| 1+ | both | 2639 | 48.6% | 64.3% [62.5%,66.1%] | 0.77 | 264 |
| 1+ | one | 2795 | 51.4% | 66.3% [64.6%,68.1%] | 0.83 | 236 |
| 2 | both | 319 | 28.8% | 64.3% [58.9%,69.3%] | 1.00 | 227 |
| 2 | one | 789 | 71.2% | 69.6% [66.3%,72.7%] | 0.93 | 222 |
| 3 | both | 499 | 46.2% | 69.3% [65.2%,73.2%] | 0.90 | 241 |
| 3 | one | 580 | 53.8% | 67.2% [63.3%,70.9%] | 0.75 | 238 |
| 4 | both | 522 | 60.4% | 69.4% [65.4%,73.2%] | 0.83 | 252 |
| 4 | one | 342 | 39.6% | 74.6% [69.7%,78.9%] | 0.78 | 251 |
| 5+ | both | 1299 | 75.5% | 60.4% [57.7%,63.0%] | 0.63 | 286 |
| 5+ | one | 422 | 24.5% | 66.1% [61.5%,70.5%] | 0.69 | 281 |
| 2+ | both | 2639 | 55.3% | 64.3% [62.5%,66.1%] | 0.77 | 264 |
| 2+ | one | 2133 | 44.7% | 69.1% [67.1%,71.0%] | 0.81 | 243 |

mean offensive X-Bows: both-lane 4.84, one-lane 2.79

### opponent side only

| n_off | pattern | matches | share of stratum | win % [95% CI] | mean crowns | mean dur s |
|---|---|---|---|---|---|---|
| 1+ | both | 2194 | 47.9% | 36.0% [34.0%,38.0%] | 0.45 | 265 |
| 1+ | one | 2382 | 52.1% | 38.2% [36.3%,40.2%] | 0.51 | 234 |
| 2 | both | 283 | 31.4% | 29.5% [24.5%,35.1%] | 0.52 | 222 |
| 2 | one | 617 | 68.6% | 41.5% [37.7%,45.4%] | 0.62 | 223 |
| 3 | both | 413 | 48.9% | 35.8% [31.4%,40.6%] | 0.54 | 238 |
| 3 | one | 431 | 51.1% | 42.2% [37.7%,46.9%] | 0.51 | 234 |
| 4 | both | 391 | 57.8% | 41.4% [36.7%,46.4%] | 0.48 | 257 |
| 4 | one | 286 | 42.2% | 43.7% [38.1%,49.5%] | 0.46 | 262 |
| 5+ | both | 1107 | 74.0% | 35.8% [33.0%,38.6%] | 0.39 | 289 |
| 5+ | one | 389 | 26.0% | 36.5% [31.9%,41.4%] | 0.37 | 288 |
| 2+ | both | 2194 | 56.0% | 36.0% [34.0%,38.0%] | 0.45 | 265 |
| 2+ | one | 1723 | 44.0% | 40.9% [38.6%,43.3%] | 0.51 | 247 |

mean offensive X-Bows: both-lane 4.88, one-lane 2.82

### Ranked (pathOfLegend) only

| n_off | pattern | matches | share of stratum | win % [95% CI] | mean crowns | mean dur s |
|---|---|---|---|---|---|---|
| 1+ | both | 4122 | 48.4% | 51.9% [50.4%,53.5%] | 0.62 | 266 |
| 1+ | one | 4390 | 51.6% | 53.5% [52.0%,54.9%] | 0.68 | 237 |
| 2 | both | 505 | 29.9% | 49.1% [44.8%,53.5%] | 0.76 | 228 |
| 2 | one | 1184 | 70.1% | 57.6% [54.8%,60.4%] | 0.79 | 225 |
| 3 | both | 745 | 46.4% | 54.8% [51.2%,58.3%] | 0.73 | 242 |
| 3 | one | 861 | 53.6% | 57.1% [53.8%,60.4%] | 0.66 | 239 |
| 4 | both | 782 | 59.9% | 57.7% [54.2%,61.1%] | 0.68 | 256 |
| 4 | one | 524 | 40.1% | 60.3% [56.1%,64.4%] | 0.64 | 258 |
| 5+ | both | 2090 | 75.5% | 49.5% [47.3%,51.6%] | 0.52 | 288 |
| 5+ | one | 678 | 24.5% | 52.5% [48.7%,56.2%] | 0.55 | 284 |
| 2+ | both | 4122 | 55.9% | 51.9% [50.4%,53.5%] | 0.62 | 266 |
| 2+ | one | 3247 | 44.1% | 56.9% [55.1%,58.5%] | 0.68 | 246 |

mean offensive X-Bows: both-lane 4.90, one-lane 2.79

### Tesla + Ice Wizard decks

| n_off | pattern | matches | share of stratum | win % [95% CI] | mean crowns | mean dur s |
|---|---|---|---|---|---|---|
| 1+ | both | 609 | 33.4% | 43.0% [39.1%,47.0%] | 0.51 | 266 |
| 1+ | one | 1216 | 66.6% | 52.4% [49.6%,55.2%] | 0.61 | 249 |
| 2 | both | 128 | 27.4% | 43.0% [34.7%,51.6%] | 0.57 | 240 |
| 2 | one | 340 | 72.6% | 56.8% [51.5%,61.9%] | 0.69 | 243 |
| 3 | both | 157 | 38.7% | 46.5% [38.9%,54.3%] | 0.57 | 253 |
| 3 | one | 249 | 61.3% | 54.6% [48.4%,60.7%] | 0.59 | 255 |
| 4 | both | 128 | 52.0% | 43.8% [35.5%,52.4%] | 0.50 | 271 |
| 4 | one | 118 | 48.0% | 65.3% [56.3%,73.2%] | 0.65 | 275 |
| 5+ | both | 196 | 62.8% | 39.8% [33.2%,46.8%] | 0.42 | 290 |
| 5+ | one | 116 | 37.2% | 44.8% [36.1%,53.9%] | 0.46 | 290 |
| 2+ | both | 609 | 42.5% | 43.0% [39.1%,47.0%] | 0.51 | 266 |
| 2+ | one | 823 | 57.5% | 55.7% [52.2%,59.0%] | 0.62 | 258 |

mean offensive X-Bows: both-lane 3.95, one-lane 2.43

### exact icebow-8 deck

| n_off | pattern | matches | share of stratum | win % [95% CI] | mean crowns | mean dur s |
|---|---|---|---|---|---|---|
| 1+ | both | 245 | 34.1% | 43.7% [37.6%,49.9%] | 0.49 | 274 |
| 1+ | one | 473 | 65.9% | 49.0% [44.6%,53.5%] | 0.57 | 252 |
| 2 | both | 49 | 26.8% | 36.7% [24.7%,50.7%] | 0.43 | 253 |
| 2 | one | 134 | 73.2% | 53.7% [45.3%,62.0%] | 0.63 | 253 |
| 3 | both | 60 | 40.8% | 46.7% [34.6%,59.1%] | 0.58 | 268 |
| 3 | one | 87 | 59.2% | 59.8% [49.3%,69.4%] | 0.63 | 268 |
| 4 | both | 45 | 48.4% | 53.3% [39.1%,67.1%] | 0.58 | 277 |
| 4 | one | 48 | 51.6% | 62.5% [48.4%,74.8%] | 0.62 | 277 |
| 5+ | both | 91 | 65.5% | 40.7% [31.1%,50.9%] | 0.42 | 289 |
| 5+ | one | 48 | 34.5% | 58.3% [44.3%,71.2%] | 0.58 | 282 |
| 2+ | both | 245 | 43.6% | 43.7% [37.6%,49.9%] | 0.49 | 274 |
| 2+ | one | 317 | 56.4% | 57.4% [51.9%,62.7%] | 0.62 | 265 |

mean offensive X-Bows: both-lane 4.06, one-lane 2.42

### Lane switch rate per consecutive pair of laned offensive X-Bows

| group | pairs | P(next in other lane) [95% CI] | by pair index 1st->2nd / 2nd->3rd / later | expected if each X-Bow picks lane independently at that side's own L/R mix |
|---|---|---|---|---|
| ALL x-bow decks, both sides pooled | 25144 | 35.9% [35.3%,36.5%] | 38% (n=8365) / 34% (n=6213) / 36% (n=10566) | 36.7% |
| team side only (the tracked top player) | 13606 | 36.6% [35.7%,37.4%] | 37% (n=4590) / 35% (n=3390) / 38% (n=5626) | 37.0% |
| opponent side only | 11538 | 35.2% [34.3%,36.1%] | 39% (n=3775) / 33% (n=2823) / 34% (n=4940) | 36.3% |
| Ranked (pathOfLegend) only | 21417 | 36.5% [35.8%,37.1%] | 38% (n=7072) / 34% (n=5265) / 37% (n=9080) | 37.0% |
| Tesla + Ice Wizard decks | 3270 | 27.6% [26.0%,29.1%] | 32% (n=1379) / 26% (n=904) / 23% (n=987) | 29.5% |
| exact icebow-8 deck | 1316 | 28.6% [26.3%,31.1%] | 33% (n=539) / 28% (n=356) / 24% (n=421) | 29.9% |

### Both-lane matches, lopsidedness (>=3 laned offensive X-Bows), all pooled

| minority-lane share | matches | win % |
|---|---|---|
| <=1/3 (mostly one lane) | 2883 | 52.4% |
| >1/3 (balanced) | 1226 | 50.8% |
