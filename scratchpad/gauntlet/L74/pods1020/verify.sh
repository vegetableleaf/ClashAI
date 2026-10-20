#!/bin/bash
# Read-only acceptance verification. The real smoke is run separately once.
set -euo pipefail
H=${1:?HOST}; P=${2:?PORT}
ssh -T -o BatchMode=yes -o ConnectTimeout=20 -i "$HOME/.ssh/runpod_clashbot" -p "$P" "root@$H" bash -s <<'REMOTE'
set -euo pipefail
CB=/workspace/cb_stepd
I=/workspace/in/pods1020
S=/workspace/stepd/l16_smoke_stepd_l16_s74
cd "$CB"
sha256sum -c --quiet /workspace/in/code.sha
for n in l16_refdeps l16_public_config l16_derived l16_abilities l16_moredeps data; do
  sha256sum -c --quiet "$I/$n.sha"
done
(cd /workspace && sha256sum -c --quiet "$I/extra.sha")
test -e /workspace/SETUP_OK
test -e /workspace/STAGE_OK
test -e /workspace/troops/SETUP_OK
test -e /workspace/stepd/fin13/FIN13_OK
test -e "$S/SMOKE_OK"
grep -q 'SMOKE PASS' "$S/smoke.log"
sha256sum -c --quiet "$S/yaml.sha"
grep -q '^live_levels: all16$' scratchpad/gauntlet/L68/rl/smoke_stepd_l16_s74/config.yaml
test -e /workspace/stepd/smoke/SMOKE_OK
cmp "$S/smoke.log" /workspace/stepd/smoke/pods1020_all16.log
cmp scratchpad/gauntlet/L74/stepd/stepd_chain.sh /workspace/stepd/bin/stepd_chain.sh
bash -n scratchpad/gauntlet/L74/stepd/w6_arm.sh
bash -n /workspace/stepd/bin/stepd_chain.sh
grep -q 'LEVEL_ARGS=(--levels "$EVAL_LEVELS")' /workspace/stepd/bin/stepd_chain.sh
export PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export ROYALE_RUNTIME=fin13-linux ROYALE_HEROIW_FORM=hero
/workspace/venvf13/bin/python /workspace/stepd/preflight_pods1020.py
/workspace/venvf13/bin/python -c "import torch; print(torch.cuda.is_available()); assert torch.cuda.is_available()"
SITE=$(/workspace/venvf13/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
(cd "$SITE" && sha256sum -c --quiet "$I/l16_torch_lib.sha")
/workspace/venvf13/bin/python -c "import importlib.metadata as m; from pathlib import Path; pins=[line.split('==') for line in Path('/workspace/in/pods1020/all_source_pins.txt').read_text().splitlines() if line]; bad=[(k,v,m.version(k)) for k,v in pins if m.version(k)!=v]; assert not bad,bad; print('PINS_OK',len(pins))"
ROYALE_RUNTIME=fork36-linux /workspace/venvf36/bin/python -c "from pipeline.royale_runtime import activate; print(activate()['runtime_id'])"
if pgrep -f 'pipeline[.]rl_royale|gap/gap[.]py|stepd_chain[.]sh|train_gen[.]py|_train_every_epoch[.]py|arm_waiter[.]sh' >/dev/null; then
  echo 'unexpected training/evaluation process' >&2
  exit 1
fi
test -z "$(find /workspace/stepd -maxdepth 1 -name 'GO_*' -print)"
test -e /workspace/KEEP
date -u +%FT%TZ
df -h /workspace
echo POD_READY
REMOTE
