#!/usr/bin/env bash
# Offline Linux pod. No pip, downloads, SSH, emulator lifecycle or live scripts.
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
PYTHON=${DIFFSIM_PYTHON:-/workspace/venv33/bin/python}
ORACLE_PYTHON=${ORACLE_PYTHON:-/workspace/venv33/bin/python}
[[ $(uname -s) == Linux ]] || { echo 'Linux pod launcher only' >&2; exit 2; }
[[ -x "$PYTHON" && -x "$ORACLE_PYTHON" ]] || { echo 'Preinstall both Python runtimes offline' >&2; exit 2; }
exec 9>/workspace/cpu.lock
flock 9
export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
export ROYALE_RUNTIME=fork
cd "$REPO"
# Fork uses pipeline.royale_runtime.activate(); oracle uses the second interpreter's
# installed 0.1.33 wheel. Same explicit card table in both worker processes.
exec "$PYTHON" -m scratchpad.gauntlet.L74.diffsim.cli \
  --candidate fork --candidate-python "$PYTHON" --oracle wheel \
  --oracle-python "$ORACLE_PYTHON" "$@"
