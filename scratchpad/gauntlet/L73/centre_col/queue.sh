#!/bin/bash
# GPU queue: wait for the R3 dry-run CellRefine, then each candidate as it lands on the VM, one at a time.
HERE="$(cd "$(dirname "$0")" && pwd)"
until grep -qE '"done"|Traceback' "$HERE/train_r3_barrel_v2.out" "$HERE/train_r3_barrel_v2.err"; do sleep 20; done
for spec in "r3c_u0030 icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030.pt" \
            "r3n_u0080 icebow/data/bench/rl_royale/rseries_r3n/rseries_r3n_u0080.pt"; do
  set -- $spec
  until ssh -i ~/.ssh/clashbot_gcp clashbot-gauntlet@34.148.91.90 "test -f ~/ClashBot/$2"; do sleep 120; done
  sleep 60                                  # let the trainer finish writing the file
  bash "$HERE/cand.sh" "$1" "$2"
done
echo QUEUE_DONE
