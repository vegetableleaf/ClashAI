#!/bin/bash
# fin13_pod.sh (P3): FIN13 = HEAD harness (cb13) + rsfork_fin14c (clashbot36 427597d3) + exports 13 + caplogs13 (caplogs11 + new13)
set -e
cd /workspace/in && gunzip -f attacks13s.json.gz buffs13.json.gz && sha256sum -c SHA13
[ ! -e /workspace/caplogs13 ] || { echo "caplogs13 exists"; exit 1; }
mkdir -p /workspace/caplogs13
cp -al /workspace/caplogs11/. /workspace/caplogs13/ && tar xzf logs13new.tgz --no-same-owner -C /workspace/caplogs13
(cd /workspace/caplogs13 && sha256sum -c --quiet /workspace/in/SHA13LOGS)
echo "caplogs13: $(ls /workspace/caplogs13 | wc -l) logs"
[ -e /workspace/cb13 ] || cp -r /workspace/w_r7close/cbL /workspace/cb13
S=/workspace/rsfork_fin14c; O=/workspace/results/FIN13; C=/workspace/cb13; mkdir -p $O; exec >> $O/run.log 2>&1
cd $C
export PYTHONPATH=$C PARITY_SIM_PATH=$S PARITY_BUFFS=/workspace/in/buffs13.json PARITY_ATTACKS=/workspace/in/attacks13s.json OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
echo "$(date -u +%T) start SIM=$S CODE=$C files=$(ls /workspace/caplogs13 | wc -l)"
nice -n 5 python3 scratchpad/gauntlet/L74/parity/fights.py run --out $O --live /workspace/caplogs13 --files 'live_play_*.jsonl' --workers 48 --window 240 --ceiling 8 && touch $O/DONE || touch $O/FAILED
echo "$(date -u +%T) run end"
[ -e $O/DONE ] || exit 1
cp -al $O ${O}_stamped 2>/dev/null || cp -a $O ${O}_stamped
rm -f ${O}_stamped/CEILING_* ${O}_stamped/SCOREBOARD_* ${O}_stamped/ceiling_*.json ${O}_stamped/scoreboard_*.json ${O}_stamped/DONE
python3 scratchpad/gauntlet/L74/parity/fights.py score --out ${O}_stamped --stamped > ${O}_stamped/score.log 2>&1 && touch ${O}_stamped/DONE || touch ${O}_stamped/FAILED
echo "$(date -u +%T) stamped end"
