# L74 forked "same moment, two choices" -- 6 jobs x 240 seeds (2026-10-10)

A = the model's own choice at the root, B = the mechanic, both continued from one engine snapshot.
Deltas are B - A, 95% CIs clustered by match. `table.md` = per-job table; `s_<mech>_<census>.{json,txt}` and
`summary_<mech>.{json,txt}` (evo+lad pooled) = full mech_summary output. Raw per-match records stay in
ClashBot/scratchpad/gauntlet/L74/mechanic_fork/results/full_*/matches.jsonl.

Engine limit: the snapshot cannot be restored while a Bowler-hero ability buff is live (~7 s). Those rounds are
skipped for A and B alike and counted (sneaky 3, rocket_tower 14, patience 0 -- see `skipped` column).
Faithfulness: 56/56 A-replays per mechanic (28 per job) are hash-identical to the original at +10 s, +20 s and the end.
| mech | census | matches | opps | skipped | B root accepted | tower diff +10s | +20s | end | win B-A (95% CI half-width) | win A->B | A-replay hash eq end |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sneaky | evo | 240 | 290 | 0 | 281/290 | +106 +/-50 | -90 +/-100 | -524 +/-321 | -11.7pp +/-7.3 | 0.752->0.634 | 28/28 |
| sneaky | lad | 240 | 292 | 3 | 276/292 | +117 +/-53 | -22 +/-86 | -333 +/-246 | -7.9pp +/-6.0 | 0.781->0.702 | 28/28 |
| rocket_tower | evo | 240 | 2172 | 8 | 2143/2172 | +177 +/-16 | -125 +/-38 | -807 +/-167 | -12.8pp +/-5.4 | 0.656->0.528 | 28/28 |
| rocket_tower | lad | 240 | 2202 | 6 | 2174/2202 | +177 +/-14 | -105 +/-34 | -771 +/-142 | -15.9pp +/-4.4 | 0.743->0.584 | 28/28 |
| patience | evo | 240 | 445 | 0 | 0/445 | -27 +/-32 | -3 +/-58 | -92 +/-301 | -4.7pp +/-6.9 | 0.629->0.582 | 28/28 |
| patience | lad | 240 | 441 | 0 | 0/441 | -22 +/-34 | +7 +/-74 | +167 +/-301 | -3.2pp +/-6.5 | 0.692->0.660 | 28/28 |
