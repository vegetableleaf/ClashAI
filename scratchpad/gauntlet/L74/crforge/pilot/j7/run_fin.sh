#!/bin/bash
# fin15 / fin16 arms of J7 (A2b-2) on the same plans; 16 workers each, arms in sequence
cd /workspace/pilot/j7
export PYTHONPATH=/workspace/pilot/j7/cb PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1
P=/workspace/venvf15/bin/python; J=cb/scratchpad/gauntlet/L74/crforge/pilot/j7/fin_run.py; PL=${PL:-plans}; R=${R:-runs}
for t in lo hi; do
  PARITY_SIM_PATH=/workspace/pilot/j7/sim16 PARITY_TABLE_1019=1 $P $J --plans $PL --out $R/fin16_force_$t --tick $t --workers 16 > $R/fin16_$t.log 2>&1
  ROYALE_RUNTIME=fin15-linux $P $J --plans $PL --out $R/fin15_force_$t --tick $t --workers 16 > $R/fin15_$t.log 2>&1
done
touch $R/FIN_DONE
