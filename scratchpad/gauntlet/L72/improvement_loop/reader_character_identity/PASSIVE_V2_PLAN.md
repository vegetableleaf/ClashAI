# Separate current-client identity guard correction

Original passive.py and its0.661686s nonzero receipt are preserved. It exited at
the module-base assertion before re_peek, upload, or sampler launch. The expected
single value for map-start minus file-offset was wrong: the current module has
segment alignment gaps. A fresh read-only maps inspection confirms one offset0
mapping and several later segments with different differences. The existing
validated sampler find_libg_base chooses the minimum difference.

Separate passive_v2.py requires exactly one offset0 mapping and that its address
equals that original minimum. Save the current libg map rows. Keep all three
original binary identity windows and rebased-vtable equalities unchanged. This
resolves the guard calculation; no build, field, scene, or latency waiver.
Original failed raw maps were not saved; the diagnosis uses the inspected source
and a fresh read-only maps observation.

Run the original prospectively bounded120frames/500ms once with fresh v2 outputs.
All PASSIVE_PLAN.md scope/limits/thresholds still apply. No new owner policy or
match launch, no original binary/source changes, no STOP writes. No retries of
successful character decoding or adapter tests. If the scene lacks the required
objects, keep runtime qualification incomplete.

CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L71/integration/run_check.py --name l72-reader-character-passive-v2 --expect READER_CHARACTER_PASSIVE_V2_COMPLETE -- research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/passive_v2.py
EXPECT: READER_CHARACTER_PASSIVE_V2_COMPLETE
