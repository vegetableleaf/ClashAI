#!/bin/bash
# W7 gate relay (laptop, Git Bash). P1 trains, 19899 evaluates (opp_eval.sh: CLX learner vs the snapshot, all16, 480 games).
#   bash gate.sh push RUN UPD [T DE SEEDS]  copy P1's rlarm_RUN_uUPD.pt here (pod_backup_weekend/w7/, sha-checked) and to 19899,
#                                           then start opp_eval.sh NAME=w7_RUN_uUPD_T<T>d<DE> there (default T .1, DE 40, 741200)
#   bash gate.sh eval NAME OPP_REL T DE SEEDS  start opp_eval.sh on 19899 for an opponent already there (knob scans)
#   bash gate.sh pull                       pull every finished 19899 /workspace/o3/out/w7*.tgz (sha-checked) into
#                                           pod_backup_weekend/w7/o3/ (Git-Bash sha256sum prints "hash *file": compare field 1)
set -uo pipefail
KEY=$HOME/.ssh/runpod_clashbot
TRN=root@64.247.206.80; TRN_PORT=48148
EVH=root@64.247.206.76; EVH_PORT=19899
D=/c/Users/benpe/pod_backup_weekend/w7; mkdir -p $D/o3
CLX=icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt
on_trn() { ssh -i $KEY -p $TRN_PORT $TRN "$@"; }
on_ev() { ssh -i $KEY -p $EVH_PORT $EVH "$@"; }
start() {  # NAME OPP_REL T DE SEEDS...
  local N=$1 O=$2 T=$3 DE=$4; shift 4
  on_ev "setsid nohup bash /workspace/o3/opp_eval.sh $N $CLX $O $T $DE 0 $* > /dev/null 2>&1 < /dev/null & echo started $N"
}
case $1 in
push)
  RUN=$2; U=$(printf %04d $3); T=${4:-0.1}; DE=${5:-40}; shift; shift; shift; shift 2 2>/dev/null; SEEDS=${*:-741200}
  F=rlarm_${RUN}_u$U.pt; SRC=/workspace/cb_stepd/icebow/data/bench/rl_royale/rlarm_$RUN/$F
  want=$(on_trn "sha256sum $SRC" | awk '{print $1}'); [ -n "$want" ] || { echo "no $F on P1"; exit 2; }
  scp -q -i $KEY -P $TRN_PORT $TRN:$SRC $D/$F; got=$(sha256sum $D/$F | awk '{print $1}')
  [ "$want" = "$got" ] || { echo "SHA MISMATCH $F"; exit 3; }
  on_ev "mkdir -p /workspace/o3/cb/icebow/data/pipeline/o2/w7"
  scp -q -i $KEY -P $EVH_PORT $D/$F $EVH:/workspace/o3/cb/icebow/data/pipeline/o2/w7/$F
  got2=$(on_ev "sha256sum /workspace/o3/cb/icebow/data/pipeline/o2/w7/$F" | awk '{print $1}')
  [ "$want" = "$got2" ] || { echo "SHA MISMATCH on 19899 $F"; exit 3; }
  echo "$F ${want:0:12}" >> $D/shas.txt
  start w7_${RUN}_u${U}_T${T}d$DE icebow/data/pipeline/o2/w7/$F $T $DE $SEEDS ;;
eval) start "$2" "$3" "$4" "$5" "${@:6}" ;;
pull)
  cd $D/o3 || exit 1
  for f in $(on_ev 'cd /workspace/o3/out && ls w7*.tgz 2>/dev/null'); do
    n=${f%.tgz}; [ -f $n.OK ] && continue
    scp -q -i $KEY -P $EVH_PORT $EVH:/workspace/o3/out/$f $EVH:/workspace/o3/out/$f.sha . || continue
    want=$(awk '{print $1}' $f.sha); got=$(sha256sum $f | awk '{print $1}')
    if [ "$want" = "$got" ]; then rm -rf $n; tar xzf $f && touch $n.OK && echo "pulled $n"; else echo "SHA MISMATCH $n"; fi
  done ;;
o4link)
  D3=$D/o3; mkdir -p $D3/$2/$2_741200 && cp -rl $D3/$3/$3_741200/D3 $D3/$2/$2_741200/ && echo "linked 741200 into $2" ;;
*) echo "usage: gate.sh push|eval|pull|o4link"; exit 2 ;;
esac
# O4 pooling (after pull): link the gate run's 741200 block into the O4 dir, so o4_table.py pools 4 blocks under one name:
#   bash gate.sh o4link w7O4_C1u40 w7_oppC1_icemix_s74_u0040_T0.1d40
