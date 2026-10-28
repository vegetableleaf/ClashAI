Inputs: C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader / live_play_*.jsonl (>=20261026_141400, CLXIII_NOLEAK).
Inputs: C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader / ladder_nav_*.jsonl (>=20261026_140000); C:\Users\benpe\ClashBot\scratchpad\gauntlet\L70\live\supervisor.log.
Scan time: 2026-10-28T13:41:09.797261-04:00 (EDT; snapshot; missing end metrics are null; means exclude null; hourly zero bins included, boundary hours partial).

| Day / deployment window | Matches | W | L | ? | Win rate [Wilson 95%] | Mean seconds | Played | Confirmed | Unconfirmed | Fails | Unconfirmed / 100 plays | p3 failures | barrel_decoy true |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-26 from 14:14 | 137 | 44 | 92 | 1 | 32.35% [25.07, 40.61] | 241.27 | 6083 | 5887 | 196 | 141 | 3.22 | 0 | 0 |
| 2026-10-27 | 299 | 93 | 203 | 3 | 31.42% [26.40, 36.92] | 236.99 | 12901 | 12457 | 444 | 328 | 3.44 | 3 | 0 |
| 2026-10-28 before 11:45 | 165 | 59 | 106 | 0 | 35.76% [28.84, 43.32] | 238.54 | 7257 | 7049 | 208 | 144 | 2.87 | 0 | 0 |
| 2026-10-28 from 11:45 | 28 | 8 | 19 | 1 | 29.63% [15.85, 48.48] | 232.41 | 1170 | 1109 | 61 | 45 | 5.21 | 1 | 28 |

| 6-hour block (EDT, all days) | Matches | W | L | ? | Win rate |
| --- | --- | --- | --- | --- | --- |
| 00-06 | 148 | 51 | 96 | 1 | 34.69% |
| 06-12 | 155 | 52 | 103 | 0 | 33.55% |
| 12-18 | 159 | 44 | 113 | 2 | 28.03% |
| 18-24 | 167 | 57 | 108 | 2 | 34.55% |

| Supervisor start (EDT) | Exit / event time (EDT) | rc | Reason (paired exits: first 140 chars) / unparsed raw line |
| --- | --- | --- | --- |
| 2026-10-26 14:14:37 | - | - | No paired exit |
| 2026-10-26 15:25:23 | 2026-10-27 04:24:42 | 1 | [nav] run stopped before match 185: transition over 300 s |
| - | - | - | ClashAI live run stopped 04:24 (rc 1): [nav] run stopped before match 185: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 1/10 in 60 s. |
| - | - | - | posted 259 chars, HTTP 204 |
| 2026-10-27 04:25:43 | 2026-10-27 04:34:10 | 1 | [nav] run stopped before match 2: transition over 300 s |
| - | - | - | ClashAI live run stopped 04:34 (rc 1): [nav] run stopped before match 2: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 2/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 04:35:12 | 2026-10-27 04:40:25 | 1 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 04:40 (rc 1): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 3/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 04:41:27 | 2026-10-27 04:46:39 | 1 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 04:46 (rc 1): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 4/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 04:47:40 | 2026-10-27 04:47:47 | 2 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 04:47 (rc 2): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 5/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 04:48:48 | 2026-10-27 04:48:55 | 2 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 04:48 (rc 2): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 6/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 04:49:56 | 2026-10-27 04:55:07 | 1 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 04:55 (rc 1): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 7/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 04:56:12 | 2026-10-27 05:01:24 | 1 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 05:01 (rc 1): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 8/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 05:02:25 | 2026-10-27 05:07:37 | 1 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 05:07 (rc 1): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 9/10 in 60 s. |
| - | - | - | posted 257 chars, HTTP 204 |
| 2026-10-27 05:08:38 | 2026-10-27 05:13:52 | 1 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 05:13 (rc 1): [nav] run stopped before match 1: transition over 300 s. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 10/10 in 60 s. |
| - | - | - | posted 258 chars, HTTP 204 |
| 2026-10-27 05:14:53 | 2026-10-27 05:20:05 | 1 | [nav] run stopped before match 1: transition over 300 s |
| - | - | - | ClashAI live run stopped 05:20 (rc 1): [nav] run stopped before match 1: transition over 300 s. Restart limit 10 reached -- NOT restarting. State {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714}. |
| - | - | - | posted 279 chars, HTTP 204 |
| - | - | - | ClashAI live ladder run ended 05:20. Tally {"wins_today": 185, "last_main_t": 1793086643.7214274, "W": 2533, "L": 2480, "D": 1, "trophies_since": null, "trophies_total": 5714} |
| - | - | - | posted 175 chars, HTTP 204 |
| - | 2026-10-27 05:20:07 | - | [sup] done Tue Oct 27 05:20:07 EDT 2026 |
| 2026-10-27 06:57:43 | 2026-10-27 07:23:52 | 0 | [live] stop file scratchpad\gauntlet\L70\live\STOP found -- ending the run before match 7 |
| - | - | - | ClashAI live ladder run ended 07:23. Tally {"wins_today": 186, "last_main_t": 1793098697.6854646, "W": 2534, "L": 2484, "D": 1, "trophies_since": null, "trophies_total": 5714, "pending_match": {"log": "live_play_20261027_071839.jsonl", "towers": {"crowns_me": 0, "crowns_opp": 1, "won": false, "tick": 6234}}} |
| - | - | - | posted 309 chars, HTTP 204 |
| - | 2026-10-27 07:23:53 | - | [sup] done Tue Oct 27 07:23:53 EDT 2026 |
| 2026-10-27 07:37:12 | 2026-10-27 18:23:12 | 0 | [live] stop file scratchpad\gauntlet\L70\live\STOP found -- ending the run before match 155 |
| - | - | - | ClashAI live ladder run ended 18:23. Tally {"wins_today": 229, "last_main_t": 1793137228.9951072, "W": 2580, "L": 2592, "D": 1, "trophies_since": null, "trophies_total": 5714, "pending_match": {"log": "live_play_20261027_181758.jsonl", "towers": {"crowns_me": 0, "crowns_opp": 1, "won": false, "tick": 6205}}} |
| - | - | - | posted 309 chars, HTTP 204 |
| - | 2026-10-27 18:23:14 | - | [sup] done Tue Oct 27 18:23:14 EDT 2026 |
| - | 2026-10-27 18:44:40 | - | [sup] adopting the running live_play Tue Oct 27 18:44:40 EDT 2026 (restart counter reset, limit 10) |
| - | 2026-10-27 18:51:17 | - | [sup] adopted run exited Tue Oct 27 18:51:17 EDT 2026: [live] stop file scratchpad\gauntlet\L70\live\STOP found -- ending the run before match 155 |
| - | - | - | ClashAI live run stopped 18:51: [live] stop file scratchpad\gauntlet\L70\live\STOP found -- ending the run before match 155. State {"wins_today": 229, "last_main_t": 1793137228.9951072, "W": 2580, "L": 2592, "D": 1, "trophies_since": null, "trophies_total": 5714, "pending_match": {"log": "live_play_20261027_181758.jsonl", "towers": {"crowns_me": 0, "crowns_opp": 1, "won": false, "tick": 6205}}}. Restart 1/10 in 60 s. |
| - | - | - | posted 420 chars, HTTP 204 |
| 2026-10-27 18:52:21 | 2026-10-28 07:52:01 | 0 | [live] stop file scratchpad\gauntlet\L70\live\STOP found -- ending the run before match 183 |
| - | - | - | ClashAI live ladder run ended 07:52. Tally {"wins_today": 288, "last_main_t": 1793186775.557504, "W": 2642, "L": 2712, "D": 1, "trophies_since": null, "trophies_total": 5714, "pending_match": {"log": "live_play_20261028_074751.jsonl", "towers": {"crowns_me": 0, "crowns_opp": 1, "won": false, "tick": 4881}}} |
| - | - | - | posted 308 chars, HTTP 204 |
| - | 2026-10-28 07:52:04 | - | [sup] done Wed Oct 28 07:52:04 EDT 2026 |
| 2026-10-28 07:53:25 | 2026-10-28 11:43:11 | 0 | [live] stop file scratchpad\gauntlet\L70\live\STOP found -- ending the run before match 56 |
| - | - | - | ClashAI live ladder run ended 11:43. Tally {"wins_today": 305, "last_main_t": 1793198879.4452102, "W": 2660, "L": 2749, "D": 1, "trophies_since": null, "trophies_total": 5714, "pending_match": {"log": "live_play_20261028_113748.jsonl", "towers": {"crowns_me": 1, "crowns_opp": 0, "won": true, "tick": 6249}}} |
| - | - | - | posted 308 chars, HTTP 204 |
| - | 2026-10-28 11:43:13 | - | [sup] done Wed Oct 28 11:43:13 EDT 2026 |
| 2026-10-28 11:45:05 | 2026-10-28 12:15:17 | 1 | [nav] run stopped before match 7: screenshots failing for 60 s |
| - | - | - | ClashAI live run stopped 12:15 (rc 1): [nav] run stopped before match 7: screenshots failing for 60 s. State {"wins_today": 306, "last_main_t": 1793202937.4082808, "W": 2662, "L": 2754, "D": 1, "trophies_since": null, "trophies_total": 5714}. Restart 1/10 in 60 s. |
| - | - | - | posted 264 chars, HTTP 204 |
| 2026-10-28 12:16:20 | - | - | No paired exit at scan time |

| Paired exit reason class | Count |
| --- | --- |
| [nav] run stopped: screenshots failing for 60 s | 1 |
| [nav] run stopped: transition over 300 s | 11 |
| stop-file | 4 |

| Hour (EDT) | Observed day-hours | Min matches/day-hour | Median matches/day-hour | Max matches/day-hour |
| --- | --- | --- | --- | --- |
| 00 | 2 | 13 | 13.5 | 14 |
| 01 | 2 | 14 | 14.5 | 15 |
| 02 | 2 | 12 | 14.0 | 16 |
| 03 | 2 | 14 | 15.0 | 16 |
| 04 | 2 | 5 | 9.0 | 13 |
| 05 | 2 | 0 | 8.0 | 16 |
| 06 | 2 | 1 | 7.5 | 14 |
| 07 | 2 | 11 | 13.0 | 15 |
| 08 | 2 | 14 | 14.0 | 14 |
| 09 | 2 | 14 | 14.5 | 15 |
| 10 | 2 | 14 | 15.0 | 16 |
| 11 | 2 | 13 | 13.5 | 14 |
| 12 | 2 | 14 | 14.0 | 14 |
| 13 | 2 | 11 | 12.0 | 13 |
| 14 | 2 | 13 | 14.0 | 15 |
| 15 | 2 | 11 | 12.5 | 14 |
| 16 | 2 | 14 | 14.0 | 14 |
| 17 | 2 | 13 | 13.0 | 13 |
| 18 | 2 | 11 | 13.5 | 16 |
| 19 | 2 | 13 | 13.0 | 13 |
| 20 | 2 | 15 | 15.0 | 15 |
| 21 | 2 | 14 | 14.0 | 14 |
| 22 | 2 | 14 | 14.5 | 15 |
| 23 | 2 | 13 | 13.5 | 14 |

| Outcome event src (used results) | Count |
| --- | --- |
| results | 582 |
| towers | 41 |

| Total / audit | Value |
| --- | --- |
| Total matches | 629 |
| Total W / L / ? | 204 / 420 / 5 |
| Overall win rate [Wilson 95%] | 32.69% [29.13, 36.47] |
| Distinct candidate log files | 629 |
| Logs skipped | 0 |
| outcomes without a mappable log: 2 |  |
| skipped records: 0 (reasons: none) |  |
| Skip reasons | none |
| Daily totals equal row totals | PASS |
| Scan elapsed seconds | 7.236 |
