# Navigator nograb history

Nav files: 5888; nograb files: 9; episodes: 11. Single-process, below-normal priority scan; no live_play files read.

## 1. Every nav file with nograb

Consecutive nograb screen events form one episode, ending at the next different screen, stop, or last event. Durations are seconds rounded to one decimal.

| Nav file (stamp) | Nograb events | Episode durations (s) | End | Pending match basename |
| --- | --- | --- | --- | --- |
| ladder_nav_20261018_133928.jsonl | 1 | 4.2 | handoff | live_play_20261018_133611.jsonl |
| ladder_nav_20261018_134321.jsonl | 1 | 4.0 | handoff | live_play_20261018_133951.jsonl |
| ladder_nav_20261018_141155.jsonl | 1 | 6.6 | handoff | live_play_20261018_140841.jsonl |
| ladder_nav_20261019_081740.jsonl | 3 | 1.7, 60.9 | stop: screenshots failing for 60 s | unknown |
| ladder_nav_20261020_190609.jsonl | 1 | 10.8 | handoff | live_play_20261020_190258.jsonl |
| ladder_nav_20261020_192525.jsonl | 1 | 11.3 | handoff | live_play_20261020_192008.jsonl |
| ladder_nav_20261021_073743.jsonl | 2 | 2.2, 5.7 | handoff | live_play_20261021_073433.jsonl |
| ladder_nav_20261021_074103.jsonl | 1 | 2.0 | handoff | live_play_20261021_073811.jsonl |
| ladder_nav_20261028_121413.jsonl | 2 | 60.3 | stop: screenshots failing for 60 s | live_play_20261028_120902.jsonl |

## 2. Episode histogram and stop counts

Histogram bins use unrounded durations; lower bounds are inclusive and upper bounds exclusive.

| Duration (s) | Episodes |
| --- | --- |
| <1 | 0 |
| 1-5 | 5 |
| 5-15 | 4 |
| 15-60 | 0 |
| >=60 | 2 |

| Stop reason | Nav files with stop | Python substring file count |
| --- | --- | --- |
| screenshots failing for 60 s | 2 | 2 |

Substring count is the Python equivalent of grep -l 'screenshots failing' ladder_nav_*.jsonl | wc -l, using the same files (including malformed lines).

## 3. Supervisor screenshots-failing lines

| Line | Text (first 200 characters) |
| --- | --- |
| 1651 | [sup] exit 1 Mon Oct 19 08:20:49 EDT 2026: [nav] run stopped before match 1: screenshots failing for 60 s |
| 2082 | [sup] exit 1 Wed Oct 28 12:15:17 EDT 2026: [nav] run stopped before match 7: screenshots failing for 60 s |
| 2083 | ClashAI live run stopped 12:15 (rc 1): [nav] run stopped before match 7: screenshots failing for 60 s. State {"wins_today": 306, "last_main_t": 1793202937.4082808, "W": 2662, "L": 2754, "D": 1, "troph |

## 4. p3_capture join from health_rows.jsonl since 2026-10-26 14:14

Next nav is mapped only by exact nav_start state.pending_match.log basename.

| Match stem | Start HH:MM | Result | Next nav | Had nograb | Longest episode (s) |
| --- | --- | --- | --- | --- | --- |
| live_play_20261027_042605 | 04:26 | ? | unmapped | N/A | N/A |
| live_play_20261027_182451 | 18:24 | ? | unmapped | N/A | N/A |
| live_play_20261027_182603 | 18:26 | ? | unmapped | N/A | N/A |
| live_play_20261028_120902 | 12:09 | L | ladder_nav_20261028_121413.jsonl | yes | 60.3 |

| p3_ok | Next nav nograb yes | Next nav nograb no |
| --- | --- | --- |
| true | 0 | 622 |
| false | 1 | 0 |

Health rows: 629; false: 4; mapped with boolean p3_ok: 623; unmapped: 5; null p3_ok: 2 (excluded from the 2x2).

## 5. Supervisor exit timing after episodes >=10 s

Times use local EDT (UTC-04:00). Approximate matching: show the next recorded [sup] exit and its time minus the nav file last-event epoch. The requested window is 0 through 120 s; time differences are reported without judging restart causality.

| Nav file | Longest (s) | Last event EDT | Next supervisor exit EDT | Exit minus last event (s) | Supervisor line |
| --- | --- | --- | --- | --- | --- |
| ladder_nav_20261019_081740.jsonl | 60.9 | 2026-10-19T08:20:47.810000-04:00 | 2026-10-19T08:20:49-04:00 | 1.19 | 1651 |
| ladder_nav_20261020_190609.jsonl | 10.8 | 2026-10-20T19:06:42.740000-04:00 | 2026-10-20T19:14:47-04:00 | 484.26 | 1805 |
| ladder_nav_20261020_192525.jsonl | 11.3 | 2026-10-20T19:26:04.070000-04:00 | 2026-10-20T19:31:26-04:00 | 321.93 | 1809 |
| ladder_nav_20261028_121413.jsonl | 60.3 | 2026-10-28T12:15:14.320000-04:00 | 2026-10-28T12:15:17-04:00 | 2.68 | 2082 |

## Footnote: skipped bad JSON lines and unparsable values

| Input | Skipped lines / values |
| --- | --- |
| nav bad JSON | 0 |
| health_rows bad JSON | 0 |

supervisor lines with unparsed dates: 0, first at line N/A. Date parsing applies to [sup] exit lines used in table 5; table 3 preserves raw text.

## Acceptance

Nav files=5888; nograb files=9; episodes=11; stop count=2; substring count=2; health rows=629; p3 false=4; long-episode navs=4; nav anchor=True; supervisor anchor (2026-10-19 08:20:49)=True; elapsed seconds=113.531
