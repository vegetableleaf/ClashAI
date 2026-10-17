set -e
cd /workspace/in && sha256sum -c SHA256SUMS.pod
mkdir -p /workspace/cb_par/scratchpad/gauntlet/L68/live_reader /workspace/results
tar xzf code.tgz -C /workspace/cb_par && tar xzf logs.tgz -C /workspace/cb_par/scratchpad/gauntlet/L68/live_reader
cp buffs.json attacks.json /workspace/
PY=$(command -v python3); $PY -V
for v in 0.1.35 0.1.36; do $PY -m pip install -q --disable-pip-version-check --target /workspace/rs$v royalesim==$v 2>&1 | grep -v "WARNING: Running pip as" | tail -2; done
for v in 0.1.35 0.1.36; do PYTHONPATH=/workspace/rs$v $PY -c "import royalesim, importlib.metadata as m, hashlib, pathlib; p=pathlib.Path(royalesim.__file__).parent; print('$v', m.version('royalesim'), hashlib.sha256((p/'data/derived/cards.json').read_bytes()).hexdigest()[:16])"; done
nproc; ls /workspace/cb_par/scratchpad/gauntlet/L68/live_reader | wc -l
touch /workspace/PAR_READY
