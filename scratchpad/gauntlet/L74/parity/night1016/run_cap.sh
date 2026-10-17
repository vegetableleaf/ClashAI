# run_cap.sh SIMDIR OUTNAME WORKERS [CODEDIR] : fights.py run, K=8, on the captured logs only (/workspace/caplogs)
# SIMDIR = a pip --target dir holding royalesim (e.g. /workspace/rs0.1.35, /workspace/rsfork_ctrl); CODEDIR default /workspace/cb_par
S=$1; O=/workspace/results/$2; W=$3; C=${4:-/workspace/cb_par}; mkdir -p $O; exec >> $O/run.log 2>&1
cd $C
export PYTHONPATH=$C PARITY_SIM_PATH=$S PARITY_BUFFS=/workspace/buffs.json PARITY_ATTACKS=/workspace/attacks.json OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
echo "$(date -u +%T) start SIM=$S CODE=$C W=$W files=$(ls /workspace/caplogs | wc -l)"
nice -n 5 python3 scratchpad/gauntlet/L74/parity/fights.py run --out $O --live /workspace/caplogs --files 'live_play_*.jsonl' --workers $W --window 240 --ceiling 8 && touch $O/DONE || touch $O/FAILED
echo "$(date -u +%T) end"
