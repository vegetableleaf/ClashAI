#!/bin/bash
# Run in a separate XL2 checkout. No simulator work before S10XL/DONE.
set -u
R=/workspace/results/wk
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$R"
exec 9>"$R/xl2.chain.lock"
flock -n 9 || { echo 'XL2 chain already running'; exit 1; }
for s in S9XL2 S10XL2; do
  [ ! -e "$R/$s/DONE" ] || { echo "$s already completed; refusing to overwrite evidence"; exit 1; }
done
while [ ! -e "$R/S10XL/DONE" ]; do sleep 30; done

# The completion marker also releases the waiting Log Bait job on failure.
finish() {
  rc=$?
  for s in S9XL2 S10XL2; do
    mkdir -p "$R/$s"
    if [ ! -e "$R/$s/DONE" ]; then
      echo "FAILED: XL2 chain ended before $s completed (rc=$rc). VERDICT: no gain" >> "$R/$s/SUMMARY.txt"
      touch "$R/$s/DONE"
    fi
  done
  touch "$R/ICEBOW_DONE"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
failed=0
for s in S9XL2 S10XL2; do
  mkdir -p "$R/$s"
  # Pod split: S10XL2 needs the second pod's S9XL2 drills (the laptop relay touches POD2_DONE after copying them in).
  [ "$s" != S10XL2 ] || [ -z "${XL2_WAIT_POD2:-}" ] || while [ ! -e "$R/S9XL2/POD2_DONE" ]; do sleep 60; done
  if [ "$s" = S10XL2 ]; then
    # Global order: GPU FIRST, then CPU, held through training and paired eval.
    flock /workspace/gpu.lock flock /workspace/cpu.lock bash "$HERE/wk_driver.sh" __run "$s" > "$R/$s/stage.log" 2>&1
  else
    flock /workspace/cpu.lock bash "$HERE/wk_driver.sh" __run "$s" > "$R/$s/stage.log" 2>&1
  fi
  rc=$?
  [ "$rc" -eq 0 ] || failed=1
  if [ ! -s "$R/$s/SUMMARY.txt" ]; then
    echo "FAILED: $s rc=$rc; see stage.log. VERDICT: no gain" > "$R/$s/SUMMARY.txt"
  fi
  echo "stage rc=$rc" >> "$R/$s/SUMMARY.txt"
  touch "$R/$s/DONE"
done
exit "$failed"
