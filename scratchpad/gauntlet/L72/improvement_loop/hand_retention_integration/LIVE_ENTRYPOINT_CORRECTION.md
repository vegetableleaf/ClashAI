# Separate hand live entry-point correction

The final offline CLI check failed before loading the final candidate:
`l72-hand-final-live-check`, exit1, 7.849265s, ModuleNotFoundError hero_button.
The original live_play_hand_v2.py and exact receipt/output are preserved unchanged.
All original model qualification and paired learning sources/results remain frozen.

The v2 companion used runpy.run_path on the canonical live script. That execution
does not put the script's containing directory on sys.path, unlike direct Python
script execution, so canonical sibling imports failed. This was a CLI integration
failure; it did not run inference, ADB or plays. It does not alter the model's
failed development verdict.

The separate live_play_hand_v3.py adds the canonical script's containing directory
before run_path. Its pilot and model remain qualified live_hand_v2/model_hand_belief_v2,
and canonical live files and all checkpoints remain unchanged. Explicit --ckpt
is still mandatory. No assistant-started live trial is authorized by this repair.

Required check: normal icebow Python, final hand checkpoint, --device cpu --check,
under a fresh receipt l72-hand-final-live-check-v3, expecting LIVE_CHECK_PASS and
exit0. This check passed5.675248s, exit0/LIVE_CHECK_PASS. Exact final candidate SHA
c5aedd869b9a8d132be51767dbb1c3aec41d6585e0ce98b1c3f10e251ff7a34a,
explicit selection, CPU, tau.35, public audit ON, anti-leak/sampling/area-aim OFF.
No ADB, taps or real match was started. The original failure remains FAILED.
