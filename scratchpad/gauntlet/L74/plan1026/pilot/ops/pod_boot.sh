#!/bin/bash
# pod_boot.sh -- LOOP-OPS, POD side (loop_pod.sh up puts it and its inputs in $W/in/ and starts it detached; log $W/boot.log).
# Fresh RunPod PyTorch image -> versions recorded -> apt (rsync, JDK 17) -> venv (requirements.txt: torch 2.11.0+cu128 =
# pod 33308's venvf16; Blackwell needs cu128+) + a matmul on every GPU -> code at CODE_SHA (GitHub, depth 1) -> every
# artifacts.tsv file pulled from the store pod by sha256 and verified -> the loop started -> checkpoints streamed off the
# pod as they appear (store pod, sha-verified there; the laptop mirror acks its own copy) -> throughput log every minute ->
# after the loop exits with FINAL: the final checkpoint copied + verified -> "DONE, safe to shut down".
# Inputs ($W/in): run.env (below), artifacts.tsv (sha256 TAB dest-under-$W [TAB source]; dest ending in / = a .tgz extracted
# there), requirements.txt, pilot.yaml, id_store (this pod's own key, authorised on the store pod by loop_pod.sh).
# run.env: RUN CODE_SHA REPO_URL STORE_HOST STORE_PORT STORE_DIR CK_REMOTE ENTRY ENTRY_ARGS TABLES REQUIRE_ACK; optional
# STREAM_EVERY (s, default 60).
set -Eeuo pipefail
W=${W:-/workspace/loop}
. $W/in/run.env
STREAM_EVERY=${STREAM_EVERY:-60}
V=$W/venv; CB=$W/cb; R=$W/run; CK=$CB/icebow/data/bench/rl_royale/$RUN
K="-i $W/in/id_store -o StrictHostKeyChecking=no -o UserKnownHostsFile=$W/known_hosts -o ServerAliveInterval=30 -o BatchMode=yes"
SS="ssh $K -p $STORE_PORT $STORE_HOST"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $W/ops.log; }
die() { log "BOOT FAILED: $*"; exit 1; }
sha() { sha256sum < "$1" | cut -c1-64; }
trap 'die "line $LINENO: $BASH_COMMAND"' ERR
mkdir -p $R
log "boot $RUN code $CODE_SHA store $STORE_HOST:$STORE_PORT"

# 1. versions (the image's own torch / CUDA, the driver, the GPUs)
{ date -u; cat /etc/os-release | head -2; nproc; free -g | head -2; nvidia-smi --query-gpu=index,name,driver_version,memory.total,compute_cap --format=csv
  nvidia-smi | sed -n 3p; python3 -c "import torch; print('image torch', torch.__version__, 'cuda', torch.version.cuda)" 2>&1 || true
} > $W/env.txt
log "env: $(grep -c NVIDIA $W/env.txt || true) GPU rows, $(sed -n 4p $W/env.txt) cores; $(tail -1 $W/env.txt)"

# 2. system packages
command -v rsync > /dev/null && command -v javac > /dev/null && command -v git > /dev/null || {
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq rsync git openjdk-17-jdk-headless > /dev/null; }
log "java: $(java -version 2>&1 | head -1)"

# 3. venv (uv provides python 3.12 when the image has another python) + GPU check
if [ ! -x $V/bin/python ]; then
  python3 -m pip install -q uv 2> /dev/null || python3 -m pip install -q --break-system-packages uv
  python3 -m uv venv -q --seed --python 3.12 $V
fi
$V/bin/python -m pip install -q -r $W/in/requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
$V/bin/python -c "
import torch, sys
assert torch.__version__ == '2.11.0+cu128', torch.__version__
n = torch.cuda.device_count(); assert n > 0, 'no GPU'
for i in range(n):
    x = torch.ones(256, 256, device=f'cuda:{i}'); assert (x @ x).sum().item() == 256 ** 3
print('venv python', sys.version.split()[0], 'torch', torch.__version__, 'cuda', torch.version.cuda, 'GPUs', n,
      torch.cuda.get_device_name(0), 'cap', torch.cuda.get_device_capability(0), 'arch list', torch.cuda.get_arch_list())
" | tee -a $W/env.txt | while read -r l; do log "$l"; done

# 4. code at the pinned commit
[ -d $CB/.git ] || { git init -q $CB; git -C $CB remote add origin $REPO_URL; }
git -C $CB fetch -q --depth 1 origin $CODE_SHA
git -C $CB checkout -q --force FETCH_HEAD
[ "$(git -C $CB rev-parse HEAD)" = "$CODE_SHA" ] || die "checkout is not $CODE_SHA"
log "code $CODE_SHA checked out ($(git -C $CB ls-files | wc -l) files)"

# 5. artifacts: one rsync of the missing shas from the store, then each verified and put in place
mkdir -p $W/store
grep -v '^#' $W/in/artifacts.tsv | grep . | cut -f1 | sort -u | while read -r s; do [ -f $W/store/$s ] || echo $s; done > $W/need.txt
[ -s $W/need.txt ] && rsync -a --files-from=$W/need.txt -e "ssh $K -p $STORE_PORT" $STORE_HOST:$STORE_DIR/ $W/store/
n=0
while IFS=$'\t' read -r s dest _; do
  [ -z "$s" ] || [ "${s:0:1}" = "#" ] && continue
  [ "$(sha $W/store/$s)" = "$s" ] || die "store copy of $dest has the wrong sha"
  if [ "${dest: -1}" = / ]; then mkdir -p $W/$dest && tar xzf $W/store/$s -C $W/$dest
  else mkdir -p "$(dirname $W/$dest)" && cp $W/store/$s $W/$dest && [ "$(sha $W/$dest)" = "$s" ] || die "$dest sha"; fi
  n=$((n + 1))
done < $W/in/artifacts.tsv
log "artifacts: $n entries verified by sha256 ($(wc -l < $W/need.txt) pulled from the store)"

# 6. start the loop
export ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge ROYALE_HEROIW_FORM=hero CRFORGE_LIB=$W/crforge/lib \
  CRFORGE_TABLES=$W/crforge/tables/$TABLES OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONPATH=$CB:$W/pylib RL_BATCH_SHA=1 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$W/jbuild
# LOOP-IW (LOOP_IW.md 55fe195): every JVM gets the incubator FFI (CfAbil.EXACT = glibc exp / pow, byte-exact abilities)
export JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED"
unset ROYALE_HEROIW_PRESS
cp $W/in/pilot.yaml $R/pilot.yaml
cd $CB
# exactness gate on THIS machine before any rollout (an unseen CPU, e.g. AVX512, must not quietly break byte-exactness):
# CfAbil + the obsid builders compiled as LOOP-IW's abilcheck.sh, then exact_gate.py (numpy exp / dot, CfAbil.EXACT, self-tests)
S=$CB/scratchpad/gauntlet/L74/speed/crforge; GB=$W/jbuild_gate; mkdir -p $GB
javac -nowarn -d $GB -cp "$CRFORGE_LIB/*" $CB/scratchpad/gauntlet/L74/crforge/facade/CfCore.java $S/CfSpeed.java $S/obsid/CfObsBind.java \n  $S/obsid/CfOppElixir.java $S/obsid/CfIdent.java $S/obsid/CfCue.java $S/obsid/CfPubObj.java $S/obsid/CfAbil.java > $W/gate_javac.log 2>&1 \n  || die "javac of the exactness-gate classes (see $W/gate_javac.log)"
$V/bin/python -B scratchpad/gauntlet/L74/plan1026/pilot/ops/exact_gate.py $CRFORGE_LIB $GB > $W/exact_gate.log 2>&1 || true   # verdict = the grep below
while read -r l; do log "exact gate: $l"; done < $W/exact_gate.log
grep -q '^EXACT_GATE PASS' $W/exact_gate.log || die "EXACT GATE FAILED on this machine -- no rollout started (see $W/exact_gate.log)"
if [ -f scratchpad/gauntlet/L74/plan1026/pilot/loop/producer.py ]; then   # = loop/run.sh: facade + obsid builders + CfTrain
  $V/bin/python -c "import sys, os, pathlib; sys.path.insert(0, 'scratchpad/gauntlet/L74/plan1026/pilot/loop'); import producer; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || die "javac (producer.compile_java)"
fi
# fastloop.py argv (LOOP-INT 10-28): [its options] --out RUN_DIR -- [rl_royale args]
setsid nohup sh -c '"$0" "$@"; echo $? > '$R/loop.rc $V/bin/python -u $ENTRY $ENTRY_ARGS --out $R -- --run $RUN --config $R/pilot.yaml \
  > $R/loop.log 2>&1 < /dev/null &                                         # loop.rc = the loop's exit code
echo $! > $R/loop.pid
log "loop started pid $(cat $R/loop.pid): $ENTRY $ENTRY_ARGS --out $R -- --run $RUN --config $R/pilot.yaml"
trap - ERR
set +e

# 7. stream checkpoints off the pod + throughput log, until DONE
$SS "mkdir -p $CK_REMOTE" || log "WARN store mkdir failed"
touch $W/copied.txt
copy_off() {   # $1 = local checkpoint; its sha = $1.sha256 (written by the loop after the rename) or computed now
  local f=$1 b want got
  b=$(basename $f); want=$(cut -c1-64 $f.sha256 2> /dev/null || sha $f)
  [ "$(sha $f)" = "$want" ] || { log "WARN $b local sha != its .sha256; not copied"; return 1; }
  rsync -a -e "ssh $K -p $STORE_PORT" $f $STORE_HOST:$CK_REMOTE/$b.part || return 1
  got=$($SS "cd $CK_REMOTE && s=\$(sha256sum < $b.part | cut -c1-64) && [ \$s = $want ] && mv $b.part $b && echo \$s > $b.sha256 && echo \$s")
  [ "$got" = "$want" ] || { log "WARN $b remote sha mismatch ('$got')"; return 1; }
  echo $b >> $W/copied.txt; log "copied off $b sha ${want:0:16} -> $STORE_HOST:$STORE_PORT:$CK_REMOTE"
}
while :; do
  for f in $CK/${RUN}_u[0-9]*.pt; do
    [ -f "$f.sha256" ] && ! grep -qxF "$(basename $f)" $W/copied.txt && copy_off $f
  done
  gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | tr '\n' ' ')
  printf '%s load %s gpu_util %s mem_used_gb %s copied %s last %s\n' "$(date -u +%FT%TZ)" "$(cut -d' ' -f1 /proc/loadavg)" \
    "[$gpu]" "$(free -g | awk '/Mem:/{print $3}')" "$(wc -l < $W/copied.txt)" "$(tail -1 $R/throughput.jsonl 2> /dev/null)" \
    >> $W/ops_throughput.log
  if ! kill -0 $(cat $R/loop.pid) 2> /dev/null; then
    if [ ! -s $R/FINAL ] || [ "$(head -1 $R/FINAL)" = none ] || [ "$(cat $R/loop.rc 2> /dev/null)" != 0 ]; then
      log "loop exit code $(cat $R/loop.rc 2> /dev/null || echo unknown), FINAL: $(head -1 $R/FINAL 2> /dev/null || echo none)"
      log "LOOP EXITED WITHOUT A CLEAN FINAL (crash?): see $R/loop.log; $(wc -l < $W/copied.txt) checkpoints are off the pod"
      [ -f $CK/${RUN}_latest.pt ] && copy_off $CK/${RUN}_latest.pt
      log "NOT DONE: the run did not finish cleanly; keep the pod until the lead has looked"; exit 2
    fi
    fin=$(head -1 $R/FINAL); [ -f "$fin" ] || fin=$CK/$(basename "$fin")
    grep -qxF "$(basename $fin)" $W/copied.txt || copy_off $fin
    if grep -qxF "$(basename $fin)" $W/copied.txt; then
      fs=$(cut -c1-64 $fin.sha256 2> /dev/null || sha $fin)
      $SS "echo $(basename $fin) $fs > $CK_REMOTE/FINAL"
      if [ "$REQUIRE_ACK" != 1 ] || [ "$(cat $W/ACK 2> /dev/null)" = "$fs" ]; then
        log "DONE, safe to shut down: final $(basename $fin) sha $fs is on $STORE_HOST:$STORE_PORT:$CK_REMOTE$([ "$REQUIRE_ACK" = 1 ] && echo ' and the laptop mirror') (sha-verified)"
        touch $W/DONE; exit 0
      fi
      log "final $(basename $fin) is on the store pod; waiting for the laptop mirror's ack ($W/ACK)"
    fi
  fi
  sleep $STREAM_EVERY
done
