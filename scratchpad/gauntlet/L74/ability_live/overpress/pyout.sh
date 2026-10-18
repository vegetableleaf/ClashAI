#!/bin/bash
# interpreter wrapper for gap_off.py --python: venvf36 + outcomes_boot.py (ability_stats on every eval row)
exec /workspace/ab/venvf36/bin/python /workspace/ab/cb/scratchpad/gauntlet/L74/ability_live/overpress/outcomes_boot.py "$@"
