#!/usr/bin/env bash
# usage: regen9z.sh OUT.jsonl [VAR=1 ...] -- inputs_v24's flag set (round 8) plus extras; old match list = v24
OUT=$1; shift
cd "$(dirname "$0")/.." && env SME_UNIT_HP=1 SME_IW_DEPLOY=1 SME_IW_AREA=1 SME_HERO7=1 SME_OWNPLAY7=1 SME_RASCAL7=1 SME_GOLEM7=1 \
  SME_OWN_CAST=1 SME_BP_VALK=1 SME_BP_GK=1 SME_BP_GIANT=1 SME_BP_RASCALS=1 SME_BP_PRESS=1 SME_MECH_GB=1 SME_MECH_DRILL=1 \
  SME_MECH_HB=1 SME_MECH_ZAP=1 SME_HIDDEN=1 SME_GK8=1 SME_CHARGE8=1 "$@" \
  /c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -I regen_inputs.py "${V24:-/c/Users/benpe/ClashBot/.foreman/scratch/a2c9z/v24.jsonl}" "$OUT" 4
