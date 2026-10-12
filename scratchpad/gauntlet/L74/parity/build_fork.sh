#!/usr/bin/env bash
# Linux pod only. All dependencies/toolchains must ALREADY be present, offline.
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
SRC="$REPO/research/ext/Royale/RoyaleSim"
OUT="$REPO/research/ext/Royale-fork"
PYTHON=${BUILD_PYTHON:-/workspace/venv33/bin/python}
JOBS=${BUILD_JOBS:-24}
: "${WHEELHOUSE:?Set WHEELHOUSE to the offline directory containing royalegym 0.1.23 wheel}"
[[ $(uname -s) == Linux ]] || { echo 'Linux wheel build only' >&2; exit 2; }
[[ $JOBS =~ ^[0-9]+$ ]] && (( JOBS >= 1 && JOBS <= 24 )) || exit 2
exec 9>/workspace/cpu.lock
flock 9
[[ $(git -C "$SRC" branch --show-current) == clashbot ]] || { echo 'Select local clashbot branch first' >&2; exit 2; }
[[ -z $(git -C "$SRC" status --porcelain --untracked-files=no) ]] || { echo 'Fork tracked sources must be clean for pinned provenance' >&2; exit 2; }
[[ ! -e "$OUT" ]] || { echo "Refusing to overwrite $OUT; archive it before a new build" >&2; exit 2; }
export CARGO_NET_OFFLINE=true CARGO_BUILD_JOBS="$JOBS" PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1
export RUSTUP_AUTO_INSTALL=0
export PYTHONDONTWRITEBYTECODE=1
# No rustup install, cargo fetch or pip download; missing caches fail visibly.
rustc --version
cargo --version
"$PYTHON" -m maturin --version
mkdir -p "$OUT/wheels" "$OUT/runtime"
cd "$SRC"
# Upstream wheels.yml stages the embedded tables before maturin builds a wheel.
"$PYTHON" tools/extract_arena.py
"$PYTHON" tools/extract_cards.py --vintage 2018
cp data/derived/cards-15.535.json data/derived/cards.json
"$PYTHON" tools/extract_globals.py
"$PYTHON" tools/stage_wheel_data.py
[[ -z $(git status --porcelain --untracked-files=no) ]] || { echo 'Generated tracked data differs; review as an evidence-backed patch' >&2; exit 2; }
"$PYTHON" -m maturin build --release --locked --offline --no-default-features --out "$OUT/wheels"
wheels=("$OUT"/wheels/royalesim-*.whl)
[[ ${#wheels[@]} == 1 && -f ${wheels[0]} ]] || exit 2
"$PYTHON" -m pip install --no-index --no-deps --no-compile --target "$OUT/runtime" "${wheels[0]}"
"$PYTHON" -m pip install --no-index --no-deps --no-compile --only-binary=:all: --find-links "$WHEELHOUSE" --target "$OUT/runtime" 'royalegym==0.1.23'
cd "$REPO"
"$PYTHON" "$HERE/pin_fork.py" --wheel "${wheels[0]}"
ROYALE_RUNTIME=fork "$PYTHON" -c 'from pipeline.royale_runtime import activate; print(activate())'
printf 'FORK_BUILD_VERIFIED\n'
