# LIVEOPS_4: short opponent-three-crown outcomes

Scan started (local laptop time): 2026-10-28T15:53:10.

20 ticks = 1 second; 1800 = 90 s, 1500 = 75 s, 1350 = 67.5 s, 2400 = 120 s. Thresholds are strict.

Days and split use match start timestamps from log stems, without timezone conversion. Losses use outcome `won == false`; opponent-three-crown counts use only `crowns_opp == 3`.

Deduplication keeps the last eligible outcome in ascending navigator filename order and line order. Null-log/null-towers outcomes are excluded before deduplication. This is a one-pass live-file snapshot; later transitions are not included.

## Table 1: daily counts

| Day / period | Matches with towers | Losses | Opp 3 | Opp 3 <1800 | Opp 3 <1500 | Opp 3 <1350 | Any <1800 | Any <1500 | Missing tick |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-20 | 161 | 74 | 8 | 0 | 0 | 0 | 1 | 1 | 0 |
| 2026-10-21 | 166 | 94 | 8 | 1 | 0 | 0 | 2 | 1 | 0 |
| 2026-10-22 | 159 | 84 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-23 | 117 | 57 | 6 | 2 | 2 | 1 | 3 | 3 | 0 |
| 2026-10-24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-25 | 173 | 91 | 6 | 1 | 1 | 0 | 1 | 1 | 0 |
| 2026-10-26 | 278 | 168 | 15 | 3 | 1 | 1 | 3 | 1 | 0 |
| 2026-10-27 | 295 | 203 | 14 | 1 | 0 | 0 | 1 | 0 | 0 |
| 2026-10-28 | 224 | 150 | 16 | 2 | 2 | 2 | 2 | 2 | 0 |
| TOTAL | 1573 | 921 | 81 | 10 | 6 | 4 | 13 | 9 | 0 |

### Before 2026-10-26 14:14

| Day / period | Matches with towers | Losses | Opp 3 | Opp 3 <1800 | Opp 3 <1500 | Opp 3 <1350 | Any <1800 | Any <1500 | Missing tick |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-20 | 161 | 74 | 8 | 0 | 0 | 0 | 1 | 1 | 0 |
| 2026-10-21 | 166 | 94 | 8 | 1 | 0 | 0 | 2 | 1 | 0 |
| 2026-10-22 | 159 | 84 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-23 | 117 | 57 | 6 | 2 | 2 | 1 | 3 | 3 | 0 |
| 2026-10-24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-25 | 173 | 91 | 6 | 1 | 1 | 0 | 1 | 1 | 0 |
| 2026-10-26 | 142 | 76 | 10 | 1 | 0 | 0 | 1 | 0 | 0 |
| 2026-10-27 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-28 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 918 | 476 | 46 | 5 | 3 | 1 | 8 | 6 | 0 |

### At/after 2026-10-26 14:14 (CLXIII back on)

| Day / period | Matches with towers | Losses | Opp 3 | Opp 3 <1800 | Opp 3 <1500 | Opp 3 <1350 | Any <1800 | Any <1500 | Missing tick |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026-10-26 | 136 | 92 | 5 | 2 | 1 | 1 | 2 | 1 | 0 |
| 2026-10-27 | 295 | 203 | 14 | 1 | 0 | 0 | 1 | 0 | 0 |
| 2026-10-28 | 224 | 150 | 16 | 2 | 2 | 2 | 2 | 2 | 0 |
| TOTAL | 655 | 445 | 35 | 5 | 3 | 3 | 5 | 3 | 0 |

## Table 2: every opponent-three-crown match with tick <2400

| Log stem | Start time | Tick | Crowns me | Checkpoint basename | won |
| --- | --- | --- | --- | --- | --- |
| live_play_20261021_040033 | 2026-10-21 04:00:33 | 1968 | 0 | rlarm_stepd_ctrl_nos2_u0130_grafted.pt | false |
| live_play_20261021_061807 | 2026-10-21 06:18:07 | 1538 | 0 | rlarm_stepd_ctrl_nos2_u0130_grafted.pt | false |
| live_play_20261022_124313 | 2026-10-22 12:43:13 | 2229 | 1 | rlarm_tn_long_e1i_s74_u0100_grafted.pt | false |
| live_play_20261023_000221 | 2026-10-23 00:02:21 | 1827 | 0 | ICEBOW_Mark_CLX_PARITY_grafted.pt | false |
| live_play_20261023_000407 | 2026-10-23 00:04:07 | 1313 | 0 | ICEBOW_Mark_CLX_PARITY_grafted.pt | false |
| live_play_20261023_023124 | 2026-10-23 02:31:24 | 1462 | 0 | ICEBOW_Mark_CLX_PARITY_grafted.pt | false |
| live_play_20261023_072108 | 2026-10-23 07:21:08 | 2129 | 1 | ICEBOW_Mark_CLX_PARITY_grafted.pt | false |
| live_play_20261025_150841 | 2026-10-25 15:08:41 | 1397 | 1 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261026_023916 | 2026-10-26 02:39:16 | 2086 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261026_073401 | 2026-10-26 07:34:01 | 2186 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261026_101626 | 2026-10-26 10:16:26 | 1518 | 0 | ICEBOW_Mark_CLXIV_MEMORY.pt | false |
| live_play_20261026_145118 | 2026-10-26 14:51:18 | 1545 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261026_194012 | 2026-10-26 19:40:12 | 2239 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261026_222554 | 2026-10-26 22:25:54 | 1345 | 1 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261027_104639 | 2026-10-27 10:46:39 | 2328 | 1 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261027_105718 | 2026-10-27 10:57:18 | 1608 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261027_141522 | 2026-10-27 14:15:22 | 2114 | 1 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261027_204400 | 2026-10-27 20:44:00 | 2397 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261028_054253 | 2026-10-28 05:42:53 | 2356 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261028_075349 | 2026-10-28 07:53:49 | 2274 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261028_154218 | 2026-10-28 15:42:18 | 1328 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |
| live_play_20261028_154335 | 2026-10-28 15:43:35 | 1311 | 0 | ICEBOW_Mark_CLXIII_NOLEAK.pt | false |

## Anchor presence

- `live_play_20261028_154218`: PRESENT; tick 1328 (expected 1328); crowns_opp=3; table 2: yes.

- `live_play_20261028_154335`: PRESENT; tick 1311 (expected 1311); crowns_opp=3; table 2: yes.

## Table 3: tick distribution

Percentiles use linear interpolation at index (n-1)*p; missing ticks are excluded.

| Population | Known ticks | Missing ticks | Min | p5 | p25 | Median | p75 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Opponent 3 crowns | 81 | 0 | 1311.00 | 1397.00 | 2356.00 | 2883.00 | 3367.00 | 6241.00 |
| All matches | 1573 | 0 | 423.00 | 3306.60 | 3681.00 | 4304.00 | 6070.00 | 6273.00 |

## Table 4: opponent-three-crown rate

| Day | Opp 3 / matches with towers | Rate |
| --- | --- | --- |
| 2026-10-20 | 8/161 | 4.97% |
| 2026-10-21 | 8/166 | 4.82% |
| 2026-10-22 | 8/159 | 5.03% |
| 2026-10-23 | 6/117 | 5.13% |
| 2026-10-24 | 0/0 | n/a |
| 2026-10-25 | 6/173 | 3.47% |
| 2026-10-26 | 15/278 | 5.40% |
| 2026-10-27 | 14/295 | 4.75% |
| 2026-10-28 | 16/224 | 7.14% |
| TOTAL | 81/1573 | 5.15% |

## Acceptance and scan footnotes

- Per-day match sum = 1573; deduplicated outcome events used = 1573; equality verified.

- Navigator files selected: 1610; lines read: 16022; outcome events: 1582; eligible events before deduplication: 1573; duplicate eligible events removed: 0; deduplicated matches before start date excluded: 0.

- Bad JSON lines skipped: 0; null-log outcomes: 2; null-towers outcomes: 9; union excluded: 9 (categories can overlap).

- Missing tick: 0; included in match/rate denominators, excluded from threshold counts and distributions.

- Flagged matches: 22; live-log first lines read: 22; unreadable checkpoints: 0.

- Opponent-three-crown outcomes with won=true: 0.

- Elapsed seconds: 1.485; under 240 seconds: yes.

- STATUS: DONE
