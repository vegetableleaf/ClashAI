#!/usr/bin/env bash
# regen_lo.sh LIST OUT.jsonl -- live-only extraction (api=False) of the matches in LIST (first column), with the v29/v30 flag set + SME_CHAMP_OWN
cd /c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/fresh && env SME_UNIT_HP=1 SME_IW_DEPLOY=1 SME_IW_AREA=1 SME_HERO7=1 SME_OWNPLAY7=1 SME_RASCAL7=1 SME_GOLEM7=1 \
  SME_OWN_CAST=1 SME_BP_VALK=1 SME_BP_GK=1 SME_BP_GIANT=1 SME_BP_RASCALS=1 SME_BP_PRESS=1 SME_MECH_GB=1 SME_MECH_DRILL=1 \
  SME_MECH_HB=1 SME_MECH_ZAP=1 SME_HIDDEN=1 SME_GK8=1 SME_CHARGE8=1 SME_HIDDEN_GEN=1 SME_CHAMP_OWN=1 \
  SME_ZAP_ADD=1 SME_ZAP_POINT=1 SME_LATE9=1 SME_MADE9=1 SME_SAMETICK_ORDER=1 SME_IWPEND9=1 SME_IWGHOST10=1 \
  /c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -I /c/Users/benpe/ClashBot/.foreman/scratch/f1fix3/regen_lo.py "$1" "$2"
