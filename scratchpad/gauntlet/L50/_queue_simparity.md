### ⚑ OWNER RULING 2026-09-04 14:4x -- SIM-PARITY ORACLE, queued immediately after the m30k read + verdict
Owner asked whether the sandbox engine (cr-native-sandbox, §5at-§5ay) can raise the sim's fidelity. Answer given:
yes as a MEASURING instrument, not as a training env (no opponent, ~30x slower per worker with observe() per decision,
reset/branch cost unmeasured; it touches only the mechanics half of the gap -- nothing for perception/latency or the
gate). Owner: "sure, queue it after the m30k read + verdict." The order of work, one loop each:
1. **Sim-side timeline driver** (no emulator needed; runs beside c2r): drive the crawl's 20 Hz command timelines
   (`data/royaleapi/crawl2/plays_ext.csv`, the same 211 tags the engine converted, `scratchpad/gauntlet/ext/batch/`)
   through OUR sim with both sides scripted-off, and grade crowns / winner against RoyaleAPI exactly as §5ay graded
   the engine (engine: crowns 77.7%, winner 80.1%, clean 64%). Same conversion caveats apply (levels, abilities
   skipped) so the two numbers are comparable. THE number: our sim's crowns-match on the same 211 replays. If it is
   close to the engine's 77.7%, mechanics are a small part of the gap and the sandbox is a calibration tool; if it is
   far below, mechanics are a large unmeasured part and the per-tick oracle becomes the main line.
2. Only if (1) says mechanics matter: engine per-tick dump (`--record-full --record-every 4`, ~1.1 h over the 135
   clean matches, §5ay.6 item 4 -- emulator, NOT beside c2r) + tick-level diff (positions, death ticks, tower HP,
   elixir) -> a ranked list of mechanic divergences, each its own fix experiment.
3. Levels pass-through in the engine (§5ay.6 item 1) sharpens the oracle's own floor before trusting the diff.
Not queued: training inside the engine; the "ghost pro" eval (our side in the engine vs the recorded pro's commands)
stays a candidate for a periodic fidelity eval only.
