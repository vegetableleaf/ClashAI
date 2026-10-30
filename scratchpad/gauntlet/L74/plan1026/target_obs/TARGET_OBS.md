# TARGET-OBS: which unit targets which unit, as a model input (owner priority item 1, 10-30)

Grades: (a) measured (number + source), (b) plausible, untested, (c) contradicted.
Rule: this file and every tracked file it names are READER-AGNOSTIC. Reader internals (field names, layouts) stay in the
git-ignored `icebow/data/reader_targets/`. Tracked code consumes only the per-unit interface below.

## STATUS + restart point (keep current)
- 10-30 13:45 EDT: started. Doc skeleton committed. Next: M1 live internal-consistency measurement (laptop).

## Interface (reader-agnostic)
Per body, in `sim_unit_state.extract`'s schema (SIM: `extract(battle)`; live: `live_unit_state.LiveCues.units(frame, prev)`):
`uid` (SIM) / `generation` (live) = a match-local id; `team`; `x`, `y` (tiles, engine frame); `attack.target` = the id
of the body it targets (None = none); `attack.frac` = attack progress 0..1 (None = idle); tower flag.
