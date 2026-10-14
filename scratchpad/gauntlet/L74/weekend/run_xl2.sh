#!/bin/bash
# Run in a separate XL2 checkout. No simulator work before S10XL/DONE.
set -u
R=/workspace/results/wk
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$R"
# CAL re-run (L74): XL2_SUFFIX renames the stage dirs (S9XL2b, S10XL2b); XL2_WAIT_PICK=<CAL/PICK.env> waits for the calibration
# pick and exports its OPP_GEN / OPP_T (run_wk.sh switches).  Both unset = the original behaviour.
SUF=${XL2_SUFFIX:-}
exec 9>"$R/xl2.chain.lock"
flock -n 9 || { echo 'XL2 chain already running'; exit 1; }
for s in S9XL2 S10XL2; do
  [ ! -e "$R/$s$SUF/DONE" ] || { echo "$s$SUF already completed; refusing to overwrite evidence"; exit 1; }
done
while [ ! -e "$R/S10XL/DONE" ]; do sleep 30; done
if [ -n "${XL2_WAIT_PICK:-}" ]; then
  while [ ! -s "$XL2_WAIT_PICK" ]; do sleep 30; done
  set -a; . "$XL2_WAIT_PICK"; set +a
fi

# The completion marker also releases the waiting Log Bait job on failure.
finish() {
  rc=$?
  for s in S9XL2 S10XL2; do
    mkdir -p "$R/$s$SUF"
    if [ ! -e "$R/$s$SUF/DONE" ]; then
      echo "FAILED: XL2 chain ended before $s$SUF completed (rc=$rc). VERDICT: no gain" >> "$R/$s$SUF/SUMMARY.txt"
      touch "$R/$s$SUF/DONE"
    fi
  done
  touch "$R/ICEBOW_DONE"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
failed=0
for s in S9XL2 S10XL2; do
  mkdir -p "$R/$s$SUF"
  # Pod split: S10XL2 needs the second pod's S9XL2 drills (the laptop relay touches POD2_DONE after copying them in).
  [ "$s" != S10XL2 ] || [ -z "${XL2_WAIT_POD2:-}" ] || while [ ! -e "$R/S9XL2$SUF/POD2_DONE" ]; do sleep 60; done
  if [ "$s" = S10XL2 ]; then
    # Global order: GPU FIRST, then CPU, held through training and paired eval.
    flock /workspace/gpu.lock flock /workspace/cpu.lock bash "$HERE/wk_driver.sh" __run "$s" > "$R/$s$SUF/stage.log" 2>&1
  else
    flock /workspace/cpu.lock bash "$HERE/wk_driver.sh" __run "$s" > "$R/$s$SUF/stage.log" 2>&1
  fi
  rc=$?
  [ "$rc" -eq 0 ] || failed=1
  if [ ! -s "$R/$s$SUF/SUMMARY.txt" ]; then
    echo "FAILED: $s$SUF rc=$rc; see stage.log. VERDICT: no gain" > "$R/$s$SUF/SUMMARY.txt"
  fi
  echo "stage rc=$rc" >> "$R/$s$SUF/SUMMARY.txt"
  touch "$R/$s$SUF/DONE"
done
exit "$failed"
