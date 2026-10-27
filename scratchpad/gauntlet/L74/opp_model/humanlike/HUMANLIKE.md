# Opponent human-likeness scorecard (plan1026 Pillar 2)

## Pre-registration log
| when | file | sha256 | note |
|---|---|---|---|
| 2026-10-27 | THRESHOLDS.json v1 | `5b9cd2faa46149a69bdf7d091ba2d21ef111fc9cf4ce474ad3d791b1a8f8803c` | written and committed BEFORE any scoring; numbers copied from PLAN.md / REPORT_opponents.md section 4 |
| 2026-10-27 | THRESHOLDS.json v2 | `0ba3aa32763dc3812d55fcaedd827f8fea482605945b2ca2a0cd364d6c5e2802` | before any model score. Two changes found by the human-vs-human control (see section Controls): B3 drops first_tick; A.ece_min_decisions = 200000 added. v1 is superseded |

`scorecard.py` refuses to run if THRESHOLDS.json does not hash to the LAST sha in this table.
