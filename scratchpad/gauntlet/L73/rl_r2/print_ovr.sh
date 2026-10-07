#!/bin/bash
# prints run_r2.sh's OVR array, one argv per line (used by dry_validate.py so the check runs the script's exact overrides)
cd /c/Users/benpe/ClashBot
eval "$(sed -n '/^O=/,/^RUN=/p;/^CFG=/,/s1: 0.02}")/p' scratchpad/gauntlet/L73/rl_r2/run_r2.sh)"
printf '%s\n' "${OVR[@]}"
