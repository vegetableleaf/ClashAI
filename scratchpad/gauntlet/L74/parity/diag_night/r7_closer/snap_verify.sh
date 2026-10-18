#!/bin/bash
# r7 closer: independent H-SNAP-BACK verification on P3. clean HEAD tree (= cb12) + patch, tests, all 499 logs vs FIN12.
B=/workspace/w_r7close; mkdir -p $B; cd $B
exec > $B/snap_verify.log 2>&1
set -x
rm -rf cbS && cp -r /workspace/cb12 cbS
cd cbS && sed -i 's/\r$//' scratchpad/gauntlet/L74/parity/fights.py && git apply --check $B/H_snap_back.patch 2>/dev/null; cd $B
(cd cbS && patch -p1 --dry-run < $B/H_snap_back.patch && patch -p1 < $B/H_snap_back.patch) || { touch SNAP.FAILED; exit 1; }
python3 -m pyflakes cbS/scratchpad/gauntlet/L74/parity/fights.py || PYTHONPATH=/workspace/pyt python3 -m pyflakes cbS/scratchpad/gauntlet/L74/parity/fights.py
(cd cbS && PYTHONPATH=$B/cbS:/workspace/pyt PARITY_SIM_PATH=/workspace/rsfork_fin11 PYTHONDONTWRITEBYTECODE=1 nice -n 10 python3 -m pytest -q -p no:cacheprovider scratchpad/gauntlet/L74/parity/tests 2>&1 | tail -8)
O=/workspace/results/v7c_snap; rm -rf $O; mkdir -p $O
cd $B/cbS
export PYTHONPATH=$B/cbS PARITY_SIM_PATH=/workspace/rsfork_fin11 PARITY_BUFFS=/workspace/in/buffs11.json PARITY_ATTACKS=/workspace/in/attacks11s.json OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
nice -n 10 python3 scratchpad/gauntlet/L74/parity/fights.py run --out $O --live /workspace/caplogs11 --files 'live_play_*.jsonl' --workers 40 --window 240 --ceiling 8 > $O/run.log 2>&1 && touch $O/DONE || touch $O/FAILED
cd $B
for s in 1 0; do STAMPED=$s CB=$B/cbS python3 $B/cmp.py /workspace/results/FIN12 $O > snap_st$s.txt 2>&1; done
touch SNAP.DONE
