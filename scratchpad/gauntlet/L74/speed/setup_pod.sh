#!/bin/bash
# S1 speed pod (30408): venv matching 32657's /workspace/venvf15 (torch 2.11.0+cu128, numpy 2.5.4, ...) built from
# PyPI; royalesim fin15 (0.1.36) + royalegym 0.1.23 site-packages copied from 32657 (read-only there) as engine.tgz.
set -Eeuo pipefail
V=/workspace/venvf15
[ -x $V/bin/python ] || python3.12 -m venv $V
$V/bin/pip install -q --upgrade pip
$V/bin/pip install -q torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
$V/bin/pip install -q numpy==2.5.4 gymnasium==1.4.0 pettingzoo==1.27.0 PyYAML==6.0.3 orjson==3.13.0 msgspec==0.22.0 \
  psutil==7.2.2 pyflakes==4.0.3 pytest==9.1.1 jsonschema==4.26.0 cloudpickle==3.1.2
tar xzf /workspace/in/engine.tgz -C $V/lib/python3.12/site-packages
$V/bin/python -c "import importlib.metadata as m, torch; print({k: m.version(k) for k in ('royalesim','royalegym','torch','numpy')}, torch.cuda.is_available())"
touch /workspace/SETUP_OK
