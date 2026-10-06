# Owner-selected tower checkpoint and disabled hand-input switch

Implement the direct October6 owner request without starting a match. The existing
start_live.sh selects through CKPT_OVERRIDE; update that pointer to the exact tested
tower checkpoint. Preserve its old experimental verdict and original STOP.

Add a genuine opt-in HAND_READER flag, defaulting to persistent HAND_READER_ENABLED=0.
The OFF path uses the unchanged canonical live_play.py. The ON path uses a separate
hand companion and strict hand-model loading; it cannot silently reinterpret a tower
checkpoint. Preserve pointer selection and between-match change detection in both.
No flag activation or model-input change occurs in the default path.

Qualify shell syntax and actual start_live.sh --check selection with explicit Git
Bash, default tower and OFF, then explicit hand checkpoint and ON, plus malformed
flag rejection. Offline checks must finish before any emulator/ADB/startup side
effect. No physical/native games, training, secret reads or external model report.

Record the owner feedback, renewed autonomous scope, checks and accurate HANDOFF.
