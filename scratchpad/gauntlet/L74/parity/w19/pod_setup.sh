#!/bin/bash
# W19 pod setup (the laptop uploads /workspace/w19/in/: cb22.tgz, w19/ scripts, the fin15 wheel, caplogs13.tgz, attacks13s /
# buffs13 .json.gz; later caplogs22.tgz + attacks22_<k> / buffs22_<k> .json.gz): code tree, the fin15 runtime (pip --target, as
# fork_build.sh), logs, exports split into chunk dirs (split_export.py). Re-runnable: each cohort is set up once its inputs exist.
#   bash pod_setup.sh > /workspace/w19/setup.log 2>&1   -> /workspace/w19/SETUP_c13 / SETUP_c22
set -euo pipefail
B=/workspace/w19; I=$B/in; cd $B
WHL=$I/royalesim-0.1.36-cp310-abi3-manylinux_2_34_x86_64.whl
echo "88f3fdcbebabe3e81d64954b48861ccabe03457b2d92fd5e34eb2f56a607f5ab  $WHL" | sha256sum -c
[ -d cb22 ] || { tar --no-same-owner -xzf $I/cb22.tgz && cp $I/w19/* cb22/scratchpad/gauntlet/L74/parity/w19/; }
[ -d rsfork_fin15 ] || /workspace/venvf15/bin/python -m pip -q install --no-deps --target $B/rsfork_fin15 $WHL
PYTHONPATH=$B/rsfork_fin15 python3 -c "import royalesim, json, pathlib; p=pathlib.Path(royalesim.__file__).parent; c=json.loads(next(p.rglob('calibration.json')).read_text()); print('calib MANA_REGEN_STEP', c['match'].get('MANA_REGEN_STEP', {}).get('value'), 'TIEBREAK_REGEN', c['match'].get('TIEBREAK_REGEN', {}).get('value'))"
S=$B/cb22/scratchpad/gauntlet/L74/parity/w19/split_export.py
mkdir -p logs
if [ ! -e SETUP_c13 ] && [ -e $I/caplogs13.tgz ]; then
  tar --no-same-owner -xzf $I/caplogs13.tgz -C logs
  gunzip -kf $I/attacks13s.json.gz $I/buffs13.json.gz
  python3 $S $B/logs $B/ch c13 8 $I/attacks13s.json $I/buffs13.json
  touch SETUP_c13
fi
if [ ! -e SETUP_c22 ] && [ -e $I/caplogs22.tgz ]; then
  tar --no-same-owner -xzf $I/caplogs22.tgz -C logs
  for k in 0 1 2 3; do gunzip -kf $I/attacks22_$k.json.gz $I/buffs22_$k.json.gz; done
  python3 $S $B/logs $B/ch c22 8 $(for k in 0 1 2 3; do echo $I/attacks22_$k.json $I/buffs22_$k.json; done)
  touch SETUP_c22
fi
echo "logs $(ls logs | wc -l)"; ls -d ch/* | wc -l; echo SETUP_END
