#!/bin/bash
# loop_pod.sh -- LOOP-OPS, LAPTOP side of the fast-loop pod (pod side = pod_boot.sh). Run from the repo root.
#   RUN=name bash loop_pod.sh up PORT [HOST]     THE one command: stage check -> this pod's key authorised on the store pod
#                                                -> inputs pushed -> pod_boot.sh started detached on the fresh pod
#   RUN=name bash loop_pod.sh watch PORT [HOST]  laptop mirror (sha-verified) of the store copies -> ack -> DONE -> key revoked
#   RUN=name bash loop_pod.sh stop PORT [HOST]   STOP: the loop stops after the current update, saves, writes FINAL
#   RUN=name bash loop_pod.sh status PORT [HOST] boot / ops / throughput tails
#   bash loop_pod.sh add SRC DEST                append artifacts.tsv rows; SRC = laptop:REL | PORT:/ABS (file or directory),
#                                                DEST = path under $W on the loop pod (a directory -> one row per file)
#   bash loop_pod.sh add-tgz PORT DIR DEST/      DIR on pod PORT as one .tgz in the store; extracted at DEST/ on the loop pod
#   bash loop_pod.sh stage                       every artifacts.tsv sha into the store (from its source), sha-verified there
# env: CFG (pilot.yaml), CODE_SHA (default HEAD; must be on origin), W (/workspace/loop), HOST root@157.157.221.29,
#      STORE_PORT 33308, POD_STORE (host:port the LOOP POD uses to reach the store; default = the store's public address),
#      ENTRY, ENTRY_ARGS, TABLES (16.402.22), REQUIRE_ACK (1), MIRROR (C:/Users/benpe/pod_backup_weekend/loop), STREAM_EVERY.
set -uo pipefail
D=scratchpad/gauntlet/L74/plan1026/pilot/ops
A=$D/artifacts.tsv; CFG=${CFG:-$D/pilot.yaml}; W=${W:-/workspace/loop}
IP=${HOST:-root@157.157.221.29}; STORE_PORT=${STORE_PORT:-33308}; STORE_DIR=/workspace/loop_stage/store
POD_STORE=${POD_STORE:-$IP:$STORE_PORT}
ENTRY=${ENTRY:-scratchpad/gauntlet/L74/plan1026/pilot/loop/fastloop.py}; ENTRY_ARGS=${ENTRY_ARGS:-}
TABLES=${TABLES:-16.402.22}; REQUIRE_ACK=${REQUIRE_ACK:-1}; MIRROR=${MIRROR:-C:/Users/benpe/pod_backup_weekend/loop}
K="-i $HOME/.ssh/runpod_clashbot -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=30"
sp() { local port=$1; shift; ssh $K -p $port $IP "$@"; }          # sp PORT CMD (store-side pods share $IP)
SS="ssh $K -p $STORE_PORT $IP"; SSN="ssh -n $K -p $STORE_PORT $IP"   # SSN: no stdin (inside read loops)
die() { echo "loop_pod: $*" >&2; exit 1; }
HASH='if [ -d "$P" ]; then cd "$P" && find . -type f | sort | while read -r f; do printf "%s\t%s\n" "$(sha256sum < "$f" | cut -c1-64)" "${f#./}"; done; else printf "%s\t\n" "$(sha256sum < "$P" | cut -c1-64)"; fi'

add() {   # SRC DEST
  local src=$1 dest=$2 p port out
  case $src in
    laptop:*) p=${src#laptop:}; out=$(P=$p bash -c "$HASH") ;;
    *:*) port=${src%%:*}; p=${src#*:}; out=$(sp $port "P='$p'; $HASH") ;;
    *) die "SRC must be laptop:REL or PORT:/ABS" ;;
  esac
  [ -n "$out" ] || die "nothing hashed at $src"
  while IFS=$'\t' read -r s rel; do
    [ ${#s} = 64 ] || die "bad hash line for $src/$rel"
    if [ -n "$rel" ]; then printf '%s\t%s\t%s\n' "$s" "$dest/$rel" "$src/$rel"; else printf '%s\t%s\t%s\n' "$s" "$dest" "$src"; fi
  done <<< "$out" | tee -a $A
}

add_tgz() {   # PORT DIR DEST/
  local port=$1 dir=$2 dest=$3 s
  [ "${dest: -1}" = / ] || die "DEST must end in /"
  s=$(sp $port "cd $dir && tar czf /tmp/loopops.tgz --sort=name --owner=0 --group=0 --numeric-owner . && sha256sum < /tmp/loopops.tgz | cut -c1-64")
  [ ${#s} = 64 ] || die "tar failed on $port:$dir"
  if [ "$port" = "$STORE_PORT" ]; then sp $port "mkdir -p $STORE_DIR && mv /tmp/loopops.tgz $STORE_DIR/$s"
  else sp $port "cat /tmp/loopops.tgz" | $SS "mkdir -p $STORE_DIR && cat > $STORE_DIR/$s"; fi
  [ "$($SS "sha256sum < $STORE_DIR/$s | cut -c1-64")" = "$s" ] || die "store copy of the tgz has the wrong sha"
  printf '%s\t%s\t%s\n' "$s" "$dest" "store (tar of $port:$dir)" | tee -a $A
}

stage() {   # -> the store holds every artifacts.tsv sha; exit 1 on any failure
  local have s dest src n=0
  have=$($SS "mkdir -p $STORE_DIR && ls $STORE_DIR") || die "store pod unreachable"
  while IFS=$'\t' read -r -u 3 s dest src; do
    [ -z "$s" ] || [ "${s:0:1}" = "#" ] && continue
    grep -qxF "$s" <<< "$have" && continue
    case $src in
      laptop:*) cat "${src#laptop:}" | $SS "cat > $STORE_DIR/$s.part" ;;
      "$STORE_PORT":*) $SSN "cp '${src#*:}' $STORE_DIR/$s.part" ;;
      [0-9]*:*) ssh -n $K -p ${src%%:*} $IP "cat '${src#*:}'" | $SS "cat > $STORE_DIR/$s.part" ;;
      *) die "$dest ($s) is not in the store and has no source" ;;
    esac
    $SSN "[ \$(sha256sum < $STORE_DIR/$s.part | cut -c1-64) = $s ] && mv $STORE_DIR/$s.part $STORE_DIR/$s" \
      || die "sha mismatch staging $dest from $src"
    have+=$'\n'$s; n=$((n + 1)); echo "staged $dest (${s:0:16}) from $src"
  done 3< $A
  echo "stage OK: $(grep -vc '^#' $A) rows, $n newly staged, store $IP:$STORE_PORT:$STORE_DIR"
}

need_run() { [ -n "${RUN:-}" ] || die "set RUN"; }

up() {   # PORT [HOST]
  need_run; local port=$1 host=${2:-$IP} P pub sha=${CODE_SHA:-$(git rev-parse HEAD)}
  P="ssh $K -p $port $host"
  [ ${#sha} = 40 ] || die "CODE_SHA must be a full sha"
  git fetch -q origin && git merge-base --is-ancestor $sha origin/main || die "$sha is not on origin/main (push first)"
  [ -f "$CFG" ] || die "no $CFG"
  stage || exit 1
  $P "mkdir -p $W/in && { [ -f $W/in/id_store ] || ssh-keygen -q -t ed25519 -N '' -f $W/in/id_store -C loop-ops:$RUN; }" \
    || die "pod $host:$port unreachable"
  pub=$($P "cat $W/in/id_store.pub")
  $SS "mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && { grep -qF '$pub' ~/.ssh/authorized_keys || echo '$pub' >> ~/.ssh/authorized_keys; }"
  printf '%s\n' "RUN=$RUN" "CODE_SHA=$sha" "REPO_URL=$(git remote get-url origin)" "STORE_HOST=${POD_STORE%:*}" \
    "STORE_PORT=${POD_STORE##*:}" "STORE_DIR=$STORE_DIR" "CK_REMOTE=/workspace/loop_ckpt/$RUN" "ENTRY=$ENTRY" \
    "ENTRY_ARGS='$ENTRY_ARGS'" "TABLES=$TABLES" "REQUIRE_ACK=$REQUIRE_ACK" "STREAM_EVERY=${STREAM_EVERY:-60}" > /tmp/loopops_run.env
  for f in /tmp/loopops_run.env:run.env $A:artifacts.tsv $D/requirements.txt:requirements.txt $CFG:pilot.yaml \
           $D/pod_boot.sh:pod_boot.sh; do
    tr -d "" < "${f%%:*}" | $P "cat > $W/in/${f##*:}" || die "push ${f##*:} failed"   # CRLF checkouts
  done
  $P "cd $W && W=$W setsid nohup bash $W/in/pod_boot.sh > $W/boot.log 2>&1 < /dev/null & sleep 2; tail -3 $W/ops.log"
  echo "started $RUN on $host:$port (code ${sha:0:12}); follow: RUN=$RUN bash $D/loop_pod.sh status $port $host;"
  echo "mirror + DONE: RUN=$RUN bash $D/loop_pod.sh watch $port $host   (run it in the background now)"
}

watch() {   # PORT [HOST]: mirror every sha-verified store copy to the laptop; ack + DONE when the final one is here
  need_run; local port=$1 host=${2:-$IP} P M=$MIRROR/$RUN R=/workspace/loop_ckpt/$RUN fin s n
  P="ssh $K -p $port $host"; mkdir -p $M
  while :; do
    $SS "cd $R 2> /dev/null && for f in *.pt.sha256; do [ -f \"\$f\" ] && echo \"\$(cut -c1-64 \$f) \${f%.sha256}\"; done" 2> /dev/null |
    while read -r s n; do
      [ -f $M/$n ] && [ "$(sha256sum < $M/$n | cut -c1-64)" = "$s" ] && continue
      $SSN "cat $R/$n" > $M/$n.part && [ "$(sha256sum < $M/$n.part | cut -c1-64)" = "$s" ] && mv $M/$n.part $M/$n \
        && echo "$(date '+%F %T') mirrored $n (${s:0:16})" || echo "$(date '+%F %T') WARN mirror of $n failed"
    done
    fin=$($SSN "cat $R/FINAL 2> /dev/null")
    if [ -n "$fin" ]; then
      set -- $fin
      if [ -f $M/$1 ] && [ "$(sha256sum < $M/$1 | cut -c1-64)" = "$2" ]; then
        $P "echo $2 > $W/ACK" && until $P "[ -f $W/DONE ]"; do sleep 30; done
        $SSN "sed -i '/ loop-ops:$RUN\$/d' ~/.ssh/authorized_keys"
        echo "DONE, safe to shut down: final $1 sha $2 verified on the store pod ($IP:$STORE_PORT:$R) and the laptop ($M/$1); loop pod key revoked"
        return 0
      fi
    fi
    sleep 120
  done
}

stop() { need_run; ssh $K -p $1 ${2:-$IP} "touch $W/run/STOP; mkdir -p $W/cb/scratchpad/gauntlet/L68/rl/$RUN && touch $W/cb/scratchpad/gauntlet/L68/rl/$RUN/STOP" && echo "STOP written"; }
status() { need_run; ssh $K -p $1 ${2:-$IP} "tail -5 $W/ops.log; echo; tail -3 $W/ops_throughput.log 2> /dev/null; tail -3 $W/run/loop.log 2> /dev/null"; }

cmd=${1:-}; shift || true
case $cmd in
  add) add "$@" ;; add-tgz) add_tgz "$@" ;; stage) stage ;; up) up "$@" ;; watch) watch "$@" ;; stop) stop "$@" ;;
  status) status "$@" ;; *) sed -n 2,16p $0; exit 2 ;;
esac
