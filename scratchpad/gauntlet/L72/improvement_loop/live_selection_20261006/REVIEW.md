# Owner-selected live checkpoint

The direct owner request selects tower_spatial_v7 via the existing CKPT_OVERRIDE
used by start_live.sh. Its exact SHA is
2feffe4f0990d93721ceb0b6661338f52e7f935e85b80e29535ea713ad6569a0.
Previous numerical development failures remain unchanged. The owner reports good
live performance; no controlled live superiority or statistical acceptance is claimed.

HAND_READER_ENABLED=0 is the persistent default. HAND_READER=1 is an explicit
environment opt-in that routes to the separate live_play_hand_v4.py and strict
hand-model loader. This successor retains canonical CKPT_OVERRIDE selection and
between-match checkpoint-change detection. The OFF path uses canonical live_play.py.
Enabling the flag with the tower checkpoint is rejected, rather than ignoring the
flag or reinterpreting incompatible tensors. No hand model is enabled by this change.

Actual explicit-Git-Bash start_live.sh --check passes: default tower/OFF, explicit
hand checkpoint/ON, plus malformed flag and incompatible checkpoint rejection.
Three shell syntax checks pass. All checks stop before emulator/ADB/startup actions.
l72-owner-tower-selection:16.959988s, exit0/OWNER_LIVE_SELECTION_VERIFIED.
verified.json binds settings, exact checkpoint, sources, outputs and controls.
Original scripts and old pointer are retained in original/. STOP timestamp/content
are exact before/after; no worker or match was started or stopped.

The same autonomous worker heartbeat is resumed at its existing20minute interval
under renewed owner authority, without the expired overnight cutoff. Daily newsletter
unchanged. All target/component/gameplay/physical/statistical/public/Q4/Q5/N2-N7
requirements remain. Future hand activation requires measured improvement, not
reader engineering success alone. No new model report is due for this selection.
