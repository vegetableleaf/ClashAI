# run_par.sh VER OUTNAME WORKERS : fights.py run (K=8 ceiling) on royalesim VER via PARITY_SIM_PATH, every frame log
V=$1; O=/workspace/results/$2; W=$3; mkdir -p $O; exec >> $O/run.log 2>&1
cd /workspace/cb_par
export PYTHONPATH=/workspace/cb_par PARITY_SIM_PATH=/workspace/rs$V PARITY_BUFFS=/workspace/buffs.json PARITY_ATTACKS=/workspace/attacks.json OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
echo "$(date -u +%T) start V=$V W=$W files=$(ls scratchpad/gauntlet/L68/live_reader/live_play_2026101[5-9]_*.jsonl | wc -l)"
python3 scratchpad/gauntlet/L74/parity/fights.py run --out $O --live scratchpad/gauntlet/L68/live_reader --files 'live_play_2026101[5-9]_*.jsonl' --workers $W --window 240 --ceiling 8 && touch $O/DONE || touch $O/FAILED
echo "$(date -u +%T) end"
