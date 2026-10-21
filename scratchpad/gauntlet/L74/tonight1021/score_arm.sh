#!/bin/bash
# score_arm.sh RUN HOST PORT -- tonight 10-21 (lead): pull /workspace/stepd/out/RUN.tgz (sha-checked), extract under
# pod_backup_weekend/tonight1021/RUN, and score u130 vs CLX (E4 promotion eval, paired, std = 741200+742000, fresh =
# 743000+744000) and vs its same-seed tn_base (attribution). Appends to RESULTS.md; prints PASS/FAIL (owner gate: CI low > 0
# on BOTH std and fresh vs CLX; the G-LOG result is reported, not required -- owner 10-21 "promote anyway").
set -u
RUN=$1; H=$2; P=$3
HERE=$(cd "$(dirname "$0")" && pwd); B=/c/Users/benpe/pod_backup_weekend; D=$B/tonight1021/$RUN; WB=C:/Users/benpe/pod_backup_weekend
K="-o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot"
mkdir -p $D && cd $D || exit 1
scp -q $K -P $P root@$H:/workspace/stepd/out/$RUN.tgz root@$H:/workspace/stepd/out/$RUN.tgz.sha . || { echo "PULL FAIL $RUN"; exit 2; }
[ "$(sha256sum $RUN.tgz | awk '{print $1}')" = "$(awk '{print $1}' $RUN.tgz.sha)" ] || { echo "SHA FAIL $RUN"; exit 2; }
tar xzf $RUN.tgz
SEED=${RUN##*_s}
CLX="$WB/tonight1020/clx_fin15/eval/clx_fin15_{s}_fin15/D3/*/matches.jsonl"
BASE="$WB/tonight1020/tn_base_s$SEED/eval/tn_base_s${SEED}_{s}_fin15/D3/*/matches.jsonl"
ARM="$WB/tonight1021/$RUN/rl_$RUN/eval/${RUN}_{s}_fin15/D3/*/matches.jsonl"
VC=$(python "$HERE/paircmp.py" "$ARM" "$CLX"); VB=$(python "$HERE/paircmp.py" "$ARM" "$BASE")
lo() { echo "$1" | grep "^$2:" | sed -E 's/.*\[([-+0-9.]+),.*/\1/'; }
V=FAIL; awk -v a="$(lo "$VC" std)" -v b="$(lo "$VC" fresh)" 'BEGIN{exit !(a>0 && b>0)}' && V=PASS
{ echo "### $RUN ($(date '+%m-%d %H:%M'))"; echo; echo '```'; echo "vs CLX (E4):"; echo "$VC"; echo "vs tn_base_s$SEED (same seed):"; echo "$VB"; echo '```'; echo "gate: $V"; echo; } >> "$HERE/RESULTS.md"
echo "$V $RUN"; echo "$VC"
