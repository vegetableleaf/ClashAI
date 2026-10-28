# GB-DECOY status (ticket GB-DECOY; worker doc for re-dispatch)

## Done
- Measurement (a): `scan.py` over live_play_2026102[5-8]_* (893 logs) -> `results/casts_clxiii.jsonl` (559 casts);
  `measure.py` -> `results/measure_clxiii.txt`; CLXIII: evo first answer in the real lane 30/50, plain 446/467.
- Cause (a): `tokens.py` (80/80 evo in-flight decisions: two card-42 tokens, identical but mirrored x);
  `inflight.py` (real barrel = lower generation key 50/50; same first/last frame 50/50).
- Fix prepared, NOT wired: `pipeline/barrel_decoy.py` + `pipeline/tests/test_barrel_decoy.py` (4 tests);
  `wiring.diff` (two lines; needs lead + owner go + blind verifier).

## Next
- Model-level replay of the 50 evo windows (baseline vs barrel_decoy.objects) through the real GenPilot, as
  `scratchpad/gauntlet/L74/speed/live_profile.py` does; run on a pod (not the live laptop). Not started.
- Successor: add `goblin-barrel-decoy` to the card vocab; crforge Java obs (CfPubObj) must rename the decoy.
- Post-landing: GoblinDummy bodies map to `goblins` (vocab._SPELL_BODY; the "81-hp body" = GoblinDummy 32 x 2.56 at
  L11); barrel_lane abstains while they live. Not changed.
