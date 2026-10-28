#!/bin/bash
# pull_ckpt.sh RUN [PORT] -- LOOP-INT2, LAPTOP side: mirror a 33308 pilot arm's numbered checkpoints (rl_royale writes tmp +
# os.replace, so a listed u*.pt is complete) to C:/Users/benpe/pod_backup_weekend/loop/RUN/, each sha256-verified against the
# pod's own sha256sum; every 300 s until the arm's --out dir holds FINAL (then the FINAL checkpoint too) -> exit.
RUN=$1; P=${2:-33308}
POD="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot -p $P root@157.157.221.29"
CK=/workspace/loop/cb/icebow/data/bench/rl_royale/$RUN; OUT=/workspace/loop/pilot/$RUN
M=C:/Users/benpe/pod_backup_weekend/loop/$RUN; mkdir -p $M
while :; do
  fin=$($POD "cat $OUT/FINAL 2> /dev/null")
  pat="${RUN}_u[0-9]*.pt"; [ -n "$fin" ] && pat="$pat ${RUN}_latest.pt"   # STOP saves _latest (numbered only on save_every)
  for line in $($POD "cd $CK 2> /dev/null && for f in $pat; do [ -f \$f ] && echo \$f:\$(sha256sum < \$f | cut -c1-64); done"); do
    f=${line%%:*}; s=${line#*:}
    [ -f $M/$f ] && [ "$(sha256sum < $M/$f | cut -c1-64)" = "$s" ] && continue
    $POD "cat $CK/$f" > $M/$f.part && [ "$(sha256sum < $M/$f.part | cut -c1-64)" = "$s" ] && mv $M/$f.part $M/$f \
      && echo "$s  $f" >> $M/SHA256SUMS && echo "$(date) copied $f ${s:0:16}" || echo "$(date) FAILED $f (retry next round)"
  done
  if [ -n "$fin" ]; then echo "$(date) FINAL: $fin"; echo "$fin" > $M/FINAL; exit 0; fi
  sleep 300
done
