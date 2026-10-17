# fork_build.sh NAME : clone/update /workspace/fork35 from /workspace/in/fork35.bundle (branch clashbot35), build a wheel,
# install it into /workspace/rsfork_NAME (pip --target). First call also installs rustup + a build venv.
set -Eeuo pipefail
N=$1; L=/workspace/results/fork_$N.log; exec > >(tee -a $L) 2>&1
echo "$(date -u +%T) fork_build $N"
if [ ! -x $HOME/.cargo/bin/cargo ]; then curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal > /dev/null; fi
source $HOME/.cargo/env; rustc --version
[ -x /workspace/vfork/bin/python ] || { python3 -m venv /workspace/vfork && /workspace/vfork/bin/pip -q install "maturin>=1.15,<2" numpy msgspec; }
P=/workspace/vfork/bin/python
if [ -d /workspace/fork35/.git ]; then git -C /workspace/fork35 fetch -q /workspace/in/fork35.bundle clashbot35:refs/remotes/b/clashbot35 && git -C /workspace/fork35 checkout -q -B clashbot35 b/clashbot35
else git clone -q -b clashbot35 /workspace/in/fork35.bundle /workspace/fork35; fi
cd /workspace/fork35; echo "src $(git rev-parse --short HEAD) $(git log -1 --format=%s | cut -c1-80)"
$P tools/extract_arena.py && $P tools/extract_cards.py --vintage 2018 && cp data/derived/cards-15.535.json data/derived/cards.json && $P tools/extract_globals.py && $P tools/stage_wheel_data.py
rm -rf target/wheels crates/royalesim/target/wheels; nice -n 5 $P -m maturin build --release -q -j 16 2>&1 | tail -2
W=$(ls crates/royalesim/target/wheels/*.whl | head -1); echo "wheel $W $(sha256sum $W | cut -c1-16)"
rm -rf /workspace/rsfork_$N; $P -m pip -q install --no-deps --target /workspace/rsfork_$N $W
PYTHONPATH=/workspace/rsfork_$N python3 -c "import royalesim, hashlib, pathlib; p=pathlib.Path(royalesim.__file__).parent; print('installed', hashlib.sha256((p/'data/derived/cards.json').read_bytes()).hexdigest()[:16])"
touch /workspace/results/fork_$N.DONE; echo "$(date -u +%T) built $N"
