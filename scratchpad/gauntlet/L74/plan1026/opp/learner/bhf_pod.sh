#!/bin/bash
# bhf_pod.sh NAME OPP_CKPT [OPP_T] -- OPP-PUSH style S0b on a booted opponent pod (boot_opp_pod.sh layout): B-HF closed loop =
# the opponent model in BOTH seats on 3,761 HF test-split tier-A deck pairs (pairs.py --mvm; jobs = mk_mvm_jobs.py, sha 6b799f6b),
# crforge 5e8089a4, tables 16.635.3 (= the D3 block's engine; the original B-HF used fe364ceb / 16.402.22), no CLXIII, no live reader.
# Resumable per chunk (rerun). Out /workspace/style/bhf_NAME; log /workspace/style/bhf_NAME.out. env WORKERS (28) CPUS (0-30).
set -u
NAME=$1; OPP=$2; T=${3:-1.0}
CB=/workspace/oplm/cbe; LIB=/workspace/crforge_main/5e8089a4/plain; FAC=/workspace/style/facade
H=$CB/scratchpad/gauntlet/L74/opp_model/humanlike
if [ ! -f "$FAC/CfCore.class" ]; then
  mkdir -p $FAC && cp $CB/scratchpad/gauntlet/L74/crforge/facade/CfCore.java $FAC/ && javac -nowarn -cp "$LIB/lib/*" -d $FAC $FAC/CfCore.java
fi
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB:/workspace/cfspeed/pylib ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=$LIB/lib \
  CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=1g \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
cd $CB && taskset -c ${CPUS:-0-30} nice -n 10 /workspace/venvf16/bin/python -I $H/pairs.py run --jobs /workspace/style/mvm_jobs3761.jsonl \
  --mvm --out /workspace/style/bhf_$NAME --opp-ckpt $OPP --opp-t $T --workers ${WORKERS:-28} --chunk 25 --python /workspace/venvf16/bin/python
echo "BHF DONE $NAME"
