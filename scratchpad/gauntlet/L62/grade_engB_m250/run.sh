set -u
export PYTHONPATH=src PYTHONHASHSEED=0
P=./.venv/Scripts/python.exe
O=../scratchpad/gauntlet/L62/grade_engB_m250
for a in ctrl kl; do
  echo "=== read_ckpt engB_${a}_m250"; $P ../scratchpad/gauntlet/L62/read_ckpt.py data/bench/engB_${a}_m250.pt > $O/read_${a}.txt 2>&1; tail -20 $O/read_${a}.txt
done
for a in ctrl kl; do
  echo "=== gate_probe engB_${a}_m250"; $P ../scratchpad/gauntlet/L62/gate_probe.py data/bench/engB_${a}_m250.pt 3 > $O/gate_${a}.txt 2>&1; tail -25 $O/gate_${a}.txt
done
for a in ctrl kl; do
  echo "=== policy-stats engB_${a}_m250"; $P -m clashrl.cli policy-stats --ckpt data/bench/engB_${a}_m250.pt --size 432 --matches 16 --envs 4 --seed 4242 --out $O/pstats_${a}.json > $O/pstats_${a}.log 2>&1; tail -15 $O/pstats_${a}.log
done
echo DONE_ALL
