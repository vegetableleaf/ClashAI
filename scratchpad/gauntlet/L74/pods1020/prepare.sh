#!/bin/bash
# Mechanical setup only. Run base pod1015/up.sh HOST PORT none first.
# Laptop: prepare.sh package [COMMIT], then prepare.sh upload HOST PORT.
# Pod: bash /workspace/in/pods1020/prepare.sh install
# Nothing here launches a training arm, evaluation, waiter, or GO file.
set -Eeuo pipefail
MODE=${1:?package|upload|install}
L=scratchpad/gauntlet/L74
if [ "$MODE" = install ]; then
  I=/workspace/in/pods1020
  cd "$I"
  sha256sum -c --quiet transport.sha
  test -e /workspace/STAGE_OK
  touch /workspace/KEEP
  # Fresh destinations only. Hard links share base data without extra disk.
  [ -d /workspace/cb_tt ] || cp -al /workspace/clashbot /workspace/cb_tt
  [ -d /workspace/cb_stepd ] || cp -al /workspace/cb_tt /workspace/cb_stepd
  cd /workspace/cb_stepd
  for n in l16_refdeps l16_public_config l16_derived l16_abilities l16_moredeps; do
    tar xf "$I/$n.tar" --no-same-owner
    sha256sum -c --quiet "$I/$n.sha"
  done
  tar xf "$I/stepd_data.tar" --no-same-owner
  sha256sum -c --quiet "$I/data.sha"
  tar xf "$I/extra.tar" --no-same-owner -C /workspace
  (cd /workspace && sha256sum -c --quiet "$I/extra.sha")
  # Install the committed code last; no working-tree pipeline overlay.
  DIRS="pipeline icebow/src $L scratchpad/gauntlet/L73 scratchpad/gauntlet/L69/gen_v2 scratchpad/gauntlet/L70/gen_v31"
  # Fixed paths inside a new pod only, same unlink-before-extract as ship_stepd.sh.
  for d in $DIRS; do
    case "$PWD/$d" in /workspace/cb_stepd/*) rm -rf -- "$d";; *) exit 2;; esac
  done
  tar xf "$I/stepd_code.tar" --no-same-owner
  sha256sum -c --quiet "$I/code.sha"
  cp "$I/code.sha" /workspace/in/code.sha
  cp "$I/stepd_code.tar" /workspace/in/stepd_code.tar
  cp "$I/code.commit" /workspace/in/code.commit
  echo CODE_OK
  # setup_troops expects its code under cb_tt; replace only these new-pod code dirs.
  for d in pipeline icebow/src "$L/troops" "$L/rt35"; do
    case "/workspace/cb_tt/$d" in /workspace/cb_tt/*) rm -rf -- "/workspace/cb_tt/$d";; *) exit 2;; esac
    mkdir -p "/workspace/cb_tt/$(dirname "$d")"
    cp -al "$d" "/workspace/cb_tt/$d"
  done
  cp "$I/fork36/"*.whl /workspace/in/
  mkdir -p /workspace/in/fin13
  cp "$I/fin13/"*.whl /workspace/in/fin13/
  bash "$L/troops/setup_troops.sh"
  # Match the existing source environment beyond the runtime's mandatory pins.
  uv pip install -q -p /workspace/venvf36/bin/python --no-deps -r "$I/all_source_pins.txt" \
    --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
  bash "$L/stepd/setup_fin13.sh"
  mkdir -p /workspace/stepd/bin
  cp "$L/stepd/stepd_chain.sh" /workspace/stepd/bin/stepd_chain.sh
  cp "$I/preflight.py" /workspace/stepd/preflight_pods1020.py
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD ROYALE_RUNTIME=fin13-linux ROYALE_HEROIW_FORM=hero \
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /workspace/venvf13/bin/python /workspace/stepd/preflight_pods1020.py
  echo INSTALL_OK
  exit
fi

cd /c/Users/benpe/ClashBot
S=${PODS1020_STAGE:-/c/Users/benpe/AppData/Local/Temp/claude/pods1020}
K=(-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i "$HOME/.ssh/runpod_clashbot")
if [ "$MODE" = package ]; then
  PIN=${2:-$(git rev-parse HEAD)}
  # Never delete or overwrite the shared stepd_ship/stage directory.
  test ! -e "$S/code.commit"
  mkdir -p "$S/stage" "$S/extra/cb_stepd" "$S/extra/stepd/d1" "$S/fork36" "$S/fin13"
  git -c core.autocrlf=false archive --format=tar "$PIN" pipeline icebow/src "$L" scratchpad/gauntlet/L73 \
    scratchpad/gauntlet/L69/gen_v2 scratchpad/gauntlet/L70/gen_v31 | tar xf - -C "$S/stage"
  (cd "$S/stage" && tar cf "$S/stepd_code.tar" * &&
    find . -type f | sed 's|^\./||' | sort | xargs sha256sum | sed 's/ \*/  /') > "$S/code.sha"
  printf '%s\n' "$PIN" > "$S/code.commit"
  cp /c/Users/benpe/AppData/Local/Temp/claude/stepd_ship/{stepd_data.tar,data.sha} "$S/"
  for n in l16_refdeps l16_public_config l16_derived l16_abilities l16_moredeps; do
    cp ".unlazy/l16/refs/$n.tar" ".unlazy/l16/refs/$n.sha" "$S/"
  done
  cp .unlazy/l16/refs/all_source_pins.txt .unlazy/l16/refs/l16_torch_lib.sha "$S/"
  cp /c/Users/benpe/pod_backup_weekend/stepd/fin13/*.whl "$S/fin13/"
  cp /c/Users/benpe/AppData/Local/Temp/claude/c--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/troops/*.whl "$S/fork36/"
  put() { mkdir -p "$S/extra/cb_stepd/$(dirname "$2")"; cp "$1" "$S/extra/cb_stepd/$2"; }
  RL=icebow/data/bench/rl_royale
  for f in rlarm_succ_levels_u0065.pt rlarm_succ_levels_u0065_grafted.pt; do
    put "/c/Users/benpe/pod_backup_weekend/pod1017_successor/succ_levels/$f" "$RL/rlarm_succ_levels/$f"
  done
  put "$RL/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt" \
    "$RL/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt"
  put /c/Users/benpe/pod_backup_weekend/stepd/d2_relay/gen_cuew_s0.pt icebow/data/pipeline/stepd_il/gen_cuew_s0.pt
  put /c/Users/benpe/pod_backup_weekend/stepd/s2/s2_all_il_sA_u0130.pt "$RL/s2_all_il_sA/s2_all_il_sA_u0130.pt"
  put .unlazy/l16/refs/pool_env_v1_split.json icebow/data/ghost_pool/pool_env_v1_split.json
  cp /c/Users/benpe/pod_backup_weekend/stepd/d1/v32_cue.npz "$S/extra/stepd/d1/"
  cp /c/Users/benpe/pod_backup_weekend/stepd/d1/v32_w3.npy "$S/extra/stepd/"
  (cd "$S/extra" && tar cf "$S/extra.tar" * &&
    find . -type f | sed 's|^\./||' | sort | xargs sha256sum | sed 's/ \*/  /') > "$S/extra.sha"
  cp "$L/pods1020/prepare.sh" "$L/pods1020/preflight.py" "$S/"
  # The original shipper is retained byte-for-byte except its staging-directory setting.
  sed "s|^S=/c/Users/benpe/AppData/Local/Temp/claude/stepd_ship$|S=$S|" "$L/stepd/ship_stepd.sh" > "$S/ship_stepd.sh"
  (cd "$S" && sha256sum *.tar code.sha data.sha extra.sha l16_*.sha *.txt *.commit *.sh *.py fork36/*.whl fin13/*.whl |
    sed 's/ \*/  /') > "$S/transport.sha"
  (cd "$S" && tar czf payload.tgz *.tar *.sha *.txt *.commit *.sh *.py fork36 fin13)
  echo PACKAGE_OK
elif [ "$MODE" = upload ]; then
  H=${2:?HOST}; P=${3:?PORT}
  ssh -n "${K[@]}" -p "$P" "root@$H" 'mkdir -p /workspace/in/pods1020/fin13 /workspace/in/pods1020/fork36'
  scp -q "${K[@]}" -P "$P" "$S/payload.tgz" "root@$H:/workspace/in/pods1020/"
  ssh -n "${K[@]}" -p "$P" "root@$H" 'cd /workspace/in/pods1020 && tar xzf payload.tgz --no-same-owner && sha256sum -c --quiet transport.sha && echo UPLOAD_OK'
else
  echo "unknown mode: $MODE" >&2
  exit 2
fi
